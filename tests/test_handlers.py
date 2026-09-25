"""Lambda handlers with boto3 clients replaced by mocks (no AWS calls)."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import api.actions as actions
import api.read as read
import diagnosis.handler as diagnosis
import inference.handler as inference
import pipeline.evaluate as evaluate
from diagnosis.prompt import NO_CONTEXT_MARKER, PROMPT_TEMPLATE, build_query


def _conditional_failure() -> ClientError:
    return ClientError({"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}}, "UpdateItem")


# ------------------------------------------------------------------ inference
@pytest.fixture
def inference_env(monkeypatch):
    for key, value in {
        "ENDPOINT_NAME": "maintainops-xgb", "DIAGNOSIS_FUNCTION": "diag", "RISK_THRESHOLD": "0.5",
        "ALERT_COOLDOWN_SECONDS": "600", "READING_TTL_DAYS": "7",
    }.items():
        monkeypatch.setenv(key, value)
    runtime, lam, table = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(inference, "runtime", runtime)
    monkeypatch.setattr(inference, "lambda_client", lam)
    monkeypatch.setattr(inference, "table", table)
    return runtime, lam, table


def test_inference_escalates_only_critical(inference_env, healthy_reading):
    runtime, lam, table = inference_env
    runtime.invoke_endpoint.return_value = {
        "Body": io.BytesIO(b"0.97,0.01,0.01,0.005,0.005\n0.1,0.02,0.8,0.05,0.03\n")
    }
    readings = [healthy_reading, healthy_reading | {"machine_id": "m2"}]
    result = inference.handler({"readings": readings}, None)

    assert result == {"scored": 2, "escalated": 1}
    sent = runtime.invoke_endpoint.call_args.kwargs
    assert sent["ContentType"] == "text/csv" and len(sent["Body"].decode().splitlines()) == 2
    payload = json.loads(lam.invoke.call_args.kwargs["Payload"])
    assert payload["reading"]["machine_id"] == "m2"
    assert payload["prediction"]["failure_type"] == "HDF"
    assert lam.invoke.call_args.kwargs["InvocationType"] == "Event"


def test_inference_respects_alert_cooldown(inference_env, healthy_reading):
    runtime, lam, table = inference_env
    runtime.invoke_endpoint.return_value = {"Body": io.BytesIO(b"0.1,0.02,0.8,0.05,0.03")}
    table.update_item.side_effect = [None, _conditional_failure()]  # latest update ok, alert slot taken
    result = inference.handler({"readings": [healthy_reading]}, None)
    assert result["escalated"] == 0
    lam.invoke.assert_not_called()


def test_inference_empty_batch_is_noop(inference_env):
    runtime, *_ = inference_env
    assert inference.handler({"readings": []}, None) == {"scored": 0, "escalated": 0}
    runtime.invoke_endpoint.assert_not_called()


# ------------------------------------------------------------------ diagnosis
def test_prompt_template_has_bedrock_placeholders():
    assert "$search_results$" in PROMPT_TEMPLATE
    assert "$output_format_instructions$" in PROMPT_TEMPLATE
    assert NO_CONTEXT_MARKER in PROMPT_TEMPLATE


def test_query_carries_derived_evidence(healthy_reading):
    query = build_query(healthy_reading, {"failure_type": "HDF", "risk": 0.91})
    assert "heat dissipation failure" in query
    assert "difference 10.2 K" in query
    assert "91%" in query


def test_diagnosis_stores_grounded_alert(monkeypatch, healthy_reading):
    for key, value in {"KNOWLEDGE_BASE_ID": "KB123", "LLM_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
                       "RETRIEVAL_RESULTS": "5", "ALERT_TOPIC_ARN": "arn:aws:sns:ap-south-1:111:t"}.items():
        monkeypatch.setenv(key, value)
    agent, sns, table = MagicMock(), MagicMock(), MagicMock()
    ref = {"content": {"text": "5.2 Coolant filter: apply lockout..."},
           "location": {"s3Location": {"uri": "s3://b/manuals/02-heat-dissipation-failure.md"}}}
    agent.retrieve_and_generate.return_value = {
        "output": {"text": "### Likely cause\nClogged coolant filter (HDF-MAN Section 5.2)."},
        "citations": [{"retrievedReferences": [ref, ref]}],
    }
    monkeypatch.setattr(diagnosis, "agent_runtime", agent)
    monkeypatch.setattr(diagnosis, "sns", sns)
    monkeypatch.setattr(diagnosis, "table", table)

    result = diagnosis.handler(
        {"ts": "t", "reading": healthy_reading, "prediction": {"failure_type": "HDF", "risk": 0.9}}, None
    )
    assert result["grounded"] is True
    item = table.put_item.call_args.kwargs["Item"]
    assert item["citations"] == [{"source": "02-heat-dissipation-failure.md",
                                  "snippet": "5.2 Coolant filter: apply lockout..."}]  # deduplicated
    config = agent.retrieve_and_generate.call_args.kwargs["retrieveAndGenerateConfiguration"]
    assert config["knowledgeBaseConfiguration"]["modelArn"].endswith("anthropic.claude-3-haiku-20240307-v1:0")
    sns.publish.assert_called_once()


def test_diagnosis_not_grounded_without_citations(monkeypatch):
    response = {"output": {"text": f"{NO_CONTEXT_MARKER}: no manual covers this."}, "citations": []}
    assert diagnosis.extract_citations(response) == []


# ------------------------------------------------------------------------ api
def _event(route: str, body: dict | None = None, **params) -> dict:
    return {"routeKey": route, "pathParameters": params or None, "body": json.dumps(body) if body else None}


@pytest.fixture
def api_env(monkeypatch):
    monkeypatch.setenv("MACHINE_COUNT", "6")
    monkeypatch.setenv("SCHEDULE_NAME", "maintainops-simulator")
    monkeypatch.setenv("SIMULATOR_FUNCTION", "sim")
    table, lam, sched = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(actions, "table", table)
    monkeypatch.setattr(actions, "lambda_client", lam)
    monkeypatch.setattr(actions, "scheduler", sched)
    return table, lam, sched


@pytest.mark.parametrize(
    ("event", "status"),
    [
        (_event("POST /api/machines/{machineId}/fault", {"fault": "HDF"}, machineId="m99"), 404),
        (_event("POST /api/machines/{machineId}/fault", {"fault": "rm -rf"}, machineId="m1"), 400),
        (_event("POST /api/simulator", {"enabled": "yes"}), 400),
        (_event("DELETE /api/everything"), 404),
    ],
)
def test_actions_validate_input(api_env, event, status):
    assert actions.handler(event, None)["statusCode"] == status


def test_inject_fault_sets_state_and_ticks_machine(api_env):
    table, lam, _ = api_env
    response = actions.handler(_event("POST /api/machines/{machineId}/fault", {"fault": "osf"}, machineId="m3"), None)
    assert response["statusCode"] == 202
    assert table.update_item.call_args.kwargs["ExpressionAttributeValues"][":f"] == "OSF"
    assert json.loads(lam.invoke.call_args.kwargs["Payload"]) == {"machine_ids": ["m3"]}


def test_toggle_simulator_preserves_schedule_definition(api_env):
    _, _, sched = api_env
    sched.get_schedule.return_value = {
        "Name": "maintainops-simulator", "GroupName": "default", "ScheduleExpression": "rate(1 minute)",
        "FlexibleTimeWindow": {"Mode": "OFF"}, "Target": {"Arn": "a", "RoleArn": "r"}, "State": "DISABLED",
        "Arn": "ignored", "CreationDate": "ignored",
    }
    response = actions.handler(_event("POST /api/simulator", {"enabled": True}), None)
    assert json.loads(response["body"])["data"] == {"simulator_enabled": True}
    kwargs = sched.update_schedule.call_args.kwargs
    assert kwargs["State"] == "ENABLED" and kwargs["Target"] == {"Arn": "a", "RoleArn": "r"}
    assert "Arn" not in kwargs and "CreationDate" not in kwargs


def test_read_rejects_unknown_machine(monkeypatch):
    monkeypatch.setenv("MACHINE_COUNT", "6")
    response = read.handler(_event("GET /api/machines/{machineId}/readings", machineId="../etc"), None)
    assert response["statusCode"] == 404


def test_read_limit_is_clamped():
    assert read._limit({"queryStringParameters": {"limit": "100000"}}, 20, 50) == 50
    assert read._limit({"queryStringParameters": {"limit": "abc"}}, 20, 50) == 20


# ------------------------------------------------------------------ pipeline
def test_evaluate_quality_gate(monkeypatch):
    monkeypatch.setenv("DATA_BUCKET", "bucket")
    monkeypatch.setenv("RISK_THRESHOLD", "0.5")
    monkeypatch.setenv("MIN_PR_AUC", "0.7")
    monkeypatch.setenv("MIN_RECALL", "0.7")
    s3 = MagicMock()
    objects = {
        "runs/r1/test/test_labels.json": json.dumps([0, 2, 0, 3]),
        "runs/r1/transform/test_features.csv.out":
            "0.9,0.02,0.03,0.03,0.02\n0.1,0.1,0.6,0.1,0.1\n0.8,0.05,0.05,0.05,0.05\n0.2,0.1,0.1,0.5,0.1\n",
    }
    s3.get_object.side_effect = lambda Bucket, Key: {"Body": io.BytesIO(objects[Key].encode())}
    monkeypatch.setattr(evaluate, "s3", s3)

    result = evaluate.handler({"run_id": "r1"}, None)
    assert result["passed"] is True and result["recall"] == 1.0
    written = {c.kwargs["Key"] for c in s3.put_object.call_args_list}
    assert written == {"runs/r1/metrics.json", "metrics/latest.json"}


def test_prepare_weights_train_but_not_validation(monkeypatch, dataset_text):
    import pipeline.prepare as prepare

    monkeypatch.setenv("DATA_BUCKET", "bucket")
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": io.BytesIO(dataset_text.encode())}
    monkeypatch.setattr(prepare, "s3", s3)
    result = prepare.handler({"run_id": "r1"}, None)

    written = {c.kwargs["Key"]: c.kwargs["Body"].decode() for c in s3.put_object.call_args_list}
    train_weights = {float(line.split(",")[1]) for line in written["runs/r1/train/train.csv"].splitlines()}
    val_weights = {float(line.split(",")[1]) for line in written["runs/r1/validation/validation.csv"].splitlines()}
    assert len(train_weights) > 1 and max(train_weights) > 1
    assert val_weights == {1.0}
    assert result["rows"]["dropped"] == 9
    test_line = written["runs/r1/test/test_features.csv"].splitlines()[0]
    assert len(test_line.split(",")) == 11  # features only: no label, no weight


def test_quality_gate_blocks_low_precision(monkeypatch):
    for key, value in {"DATA_BUCKET": "b", "RISK_THRESHOLD": "0.5", "MIN_PR_AUC": "0.1", "MIN_RECALL": "0.1",
                       "MIN_PRECISION": "0.9"}.items():
        monkeypatch.setenv(key, value)
    s3 = MagicMock()
    objects = {  # 1 true positive, 1 false alarm -> precision 0.5
        "runs/r2/test/test_labels.json": json.dumps([2, 0]),
        "runs/r2/transform/test_features.csv.out": "0.1,0.1,0.6,0.1,0.1\n0.2,0.1,0.5,0.1,0.1\n",
    }
    s3.get_object.side_effect = lambda Bucket, Key: {"Body": io.BytesIO(objects[Key].encode())}
    monkeypatch.setattr(evaluate, "s3", s3)
    assert evaluate.handler({"run_id": "r2"}, None)["passed"] is False

"""`cdk synth` succeeds and the templates keep the cost and security properties we rely on."""

from __future__ import annotations

import json
import re

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template


@pytest.fixture(scope="module")
def templates() -> dict[str, Template]:
    from app import build

    app = build(cdk.App())
    assembly = app.synth()
    return {s.stack_name: Template.from_stack(app.node.find_child(s.stack_name)) for s in assembly.stacks}


def test_all_stacks_synthesize(templates):
    assert set(templates) == {"MaintainOps-Data", "MaintainOps-ML", "MaintainOps-KnowledgeBase", "MaintainOps-App"}


def test_no_always_on_compute(templates):
    for template in templates.values():
        body = json.dumps(template.to_json())
        # no instance-backed endpoints, OpenSearch collections, NAT gateways or EC2
        for resource in ("AWS::SageMaker::Endpoint", "AWS::OpenSearchServerless::Collection",
                         "AWS::EC2::NatGateway", "AWS::EC2::Instance", "AWS::RDS::DBInstance"):
            assert resource not in body


def test_knowledge_base_uses_s3_vectors(templates):
    kb = templates["MaintainOps-KnowledgeBase"]
    kb.resource_count_is("AWS::S3Vectors::VectorBucket", 1)
    kb.has_resource_properties("AWS::S3Vectors::Index", {"Dimension": 1024, "DistanceMetric": "cosine"})
    kb.has_resource_properties("AWS::Bedrock::KnowledgeBase", {
        "StorageConfiguration": {"Type": "S3_VECTORS", "S3VectorsConfiguration": Match.any_value()},
    })


def test_serverless_inference_configured(templates):
    body = json.dumps(templates["MaintainOps-ML"].to_json())
    assert "ServerlessConfig" in body and "MemorySizeInMB" in body
    assert "EnableManagedSpotTraining" in body


def test_simulator_schedule_starts_disabled(templates):
    templates["MaintainOps-App"].has_resource_properties("AWS::Scheduler::Schedule", {"State": "DISABLED"})


def test_demo_actions_are_throttled(templates):
    templates["MaintainOps-App"].has_resource_properties("AWS::ApiGatewayV2::Stage", {
        "RouteSettings": {
            "POST /api/machines/{machineId}/fault": {"ThrottlingRateLimit": Match.any_value(),
                                                     "ThrottlingBurstLimit": Match.any_value()},
        },
    })


def test_dynamodb_on_demand(templates):
    templates["MaintainOps-Data"].has_resource_properties(
        "AWS::DynamoDB::GlobalTable", {"BillingMode": "PAY_PER_REQUEST"}
    )


def test_no_hardcoded_account_ids(templates):
    allowed = {"720646828776"}  # AWS-owned SageMaker XGBoost image registry
    for template in templates.values():
        found = set(re.findall(r"(?<![\d.])\d{12}(?![\d.])", json.dumps(template.to_json())))
        assert found <= allowed, found


def test_buckets_block_public_access(templates):
    for template in templates.values():
        for bucket in template.find_resources("AWS::S3::Bucket").values():
            config = bucket["Properties"]["PublicAccessBlockConfiguration"]
            assert all(config[k] for k in ("BlockPublicAcls", "BlockPublicPolicy",
                                           "IgnorePublicAcls", "RestrictPublicBuckets"))


def _state_machine_definition(template: Template) -> dict:
    machine = next(iter(template.find_resources("AWS::StepFunctions::StateMachine").values()))
    parts = machine["Properties"]["DefinitionString"]["Fn::Join"][1]
    return json.loads("".join(p if isinstance(p, str) else 'TOKEN' for p in parts))


def test_pipeline_states_preserve_run_id(templates):
    """Every task after Init must write its result under a sub-path, or $.run_id is lost."""
    states = _state_machine_definition(templates["MaintainOps-ML"])["States"]
    for name, state in states.items():
        if state["Type"] == "Task":
            assert "ResultPath" in state, f"{name} would overwrite the execution state"
            assert state["ResultPath"] is None or state["ResultPath"].startswith("$."), name


def test_pipeline_can_create_endpoint_from_config(templates):
    """CreateEndpoint/UpdateEndpoint are authorised against the endpoint *and* the endpoint config."""
    policies = templates["MaintainOps-ML"].find_resources("AWS::IAM::Policy").values()
    for action in ("sagemaker:createEndpoint", "sagemaker:updateEndpoint"):
        statements = [
            s for p in policies for s in p["Properties"]["PolicyDocument"]["Statement"]
            if action in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])
        ]
        assert statements, f"no statement grants {action}"
        resources = json.dumps([s["Resource"] for s in statements])
        assert "endpoint-config/maintainops-" in resources, action

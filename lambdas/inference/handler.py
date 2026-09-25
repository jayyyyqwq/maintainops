"""Inference: score a batch of readings on the SageMaker serverless endpoint, persist, escalate.

One endpoint call per batch (CSV, one row per machine). Readings whose failure risk crosses
the threshold trigger the diagnosis Lambda, at most once per machine per cooldown window.
"""

from __future__ import annotations

import json
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

from common.features import engineer, to_csv_line
from common.predictions import parse_probabilities, summarise
from common.store import STATE_SK, machine_pk, now_iso, reading_sk, to_dynamo

logger = logging.getLogger()
logger.setLevel(logging.INFO)

runtime = boto3.client("sagemaker-runtime")
lambda_client = boto3.client("lambda")
table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "maintainops"))


def score(readings: list[dict]) -> list[dict]:
    body = "\n".join(to_csv_line(engineer(r)) for r in readings)
    response = runtime.invoke_endpoint(
        EndpointName=os.environ["ENDPOINT_NAME"],
        ContentType="text/csv",
        Accept="text/csv",
        Body=body.encode(),
    )
    return [summarise(p) for p in parse_probabilities(response["Body"].read().decode())]


def claim_alert_slot(machine_id: str, now: int, cooldown: int) -> bool:
    """Atomically take the per-machine alert slot; False if an alert fired recently."""
    try:
        table.update_item(
            Key={"pk": machine_pk(machine_id), "sk": STATE_SK},
            UpdateExpression="SET last_alert_epoch = :now",
            ConditionExpression="attribute_not_exists(last_alert_epoch) OR last_alert_epoch < :cutoff",
            ExpressionAttributeValues={":now": now, ":cutoff": now - cooldown},
        )
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def handler(event: dict, _context: object) -> dict:
    readings = event["readings"]
    if not readings:
        return {"scored": 0, "escalated": 0}
    threshold = float(os.environ["RISK_THRESHOLD"])
    cooldown = int(os.environ["ALERT_COOLDOWN_SECONDS"])
    ttl = int(time.time()) + int(os.environ["READING_TTL_DAYS"]) * 86400

    predictions = score(readings)
    escalated = 0
    for reading, prediction in zip(readings, predictions, strict=True):
        machine_id = reading["machine_id"]
        ts = now_iso()
        status = "critical" if prediction["risk"] >= threshold else (
            "warning" if prediction["risk"] >= threshold / 2 else "healthy"
        )
        record = {"ts": ts, "reading": reading, "prediction": prediction, "status": status}
        table.put_item(
            Item=to_dynamo({"pk": machine_pk(machine_id), "sk": reading_sk(ts), "ttl": ttl, **record})
        )
        table.update_item(
            Key={"pk": machine_pk(machine_id), "sk": STATE_SK},
            UpdateExpression="SET latest = :latest, machine_id = :id",
            ExpressionAttributeValues={":latest": to_dynamo(record), ":id": machine_id},
        )
        if status == "critical" and claim_alert_slot(machine_id, int(time.time()), cooldown):
            lambda_client.invoke(
                FunctionName=os.environ["DIAGNOSIS_FUNCTION"],
                InvocationType="Event",
                Payload=json.dumps({"ts": ts, "reading": reading, "prediction": prediction}).encode(),
            )
            escalated += 1

    logger.info("scored=%d escalated=%d", len(predictions), escalated)
    return {"scored": len(predictions), "escalated": escalated}

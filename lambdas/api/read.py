"""Read-only API: machines, reading history, alerts. IAM grants this function DynamoDB reads only."""

from __future__ import annotations

import os
from urllib.parse import unquote

import boto3
from boto3.dynamodb.conditions import Key

from api.responses import error, ok
from common.store import ALERTS_PK, STATE_SK, from_dynamo, is_valid_machine, machine_ids, machine_pk

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME", "maintainops"))
scheduler = boto3.client("scheduler")

MAX_READINGS = 120
MAX_ALERTS = 50


def machine_count() -> int:
    return int(os.environ["MACHINE_COUNT"])


def list_machines() -> dict:
    keys = [{"pk": machine_pk(m), "sk": STATE_SK} for m in machine_ids(machine_count())]
    response = dynamodb.batch_get_item(RequestItems={table.name: {"Keys": keys}})
    items = {i["pk"]: from_dynamo(i) for i in response["Responses"].get(table.name, [])}
    machines = []
    for machine_id in machine_ids(machine_count()):
        item = items.get(machine_pk(machine_id), {})
        machines.append({
            "machine_id": machine_id,
            "latest": item.get("latest"),
            "pending_fault": item.get("pending_fault"),
            "tool_wear_min": item.get("tool_wear_min"),
        })
    schedule = scheduler.get_schedule(Name=os.environ["SCHEDULE_NAME"])
    return ok({"machines": machines, "simulator_enabled": schedule["State"] == "ENABLED"})


def list_readings(machine_id: str, limit: int) -> dict:
    response = table.query(
        KeyConditionExpression=Key("pk").eq(machine_pk(machine_id)) & Key("sk").begins_with("R#"),
        ScanIndexForward=False,
        Limit=limit,
    )
    readings = [from_dynamo(i) for i in response["Items"]]
    for r in readings:
        r.pop("pk", None)
        r.pop("sk", None)
    return ok({"machine_id": machine_id, "readings": list(reversed(readings))})


def list_alerts(limit: int) -> dict:
    response = table.query(
        KeyConditionExpression=Key("pk").eq(ALERTS_PK),
        ScanIndexForward=False,
        Limit=limit,
        ProjectionExpression="alert_id, ts, machine_id, failure_type, risk, grounded",
    )
    return ok({"alerts": [from_dynamo(i) for i in response["Items"]]})


def get_alert(alert_id: str) -> dict:
    item = table.get_item(Key={"pk": ALERTS_PK, "sk": alert_id}).get("Item")
    if not item:
        return error("alert not found", 404)
    alert = from_dynamo(item)
    alert.pop("pk", None)
    alert.pop("sk", None)
    return ok(alert)


def _limit(event: dict, default: int, maximum: int) -> int:
    raw = (event.get("queryStringParameters") or {}).get("limit", default)
    try:
        return max(1, min(int(raw), maximum))
    except (TypeError, ValueError):
        return default


def handler(event: dict, _context: object) -> dict:
    route = event.get("routeKey", "")
    params = event.get("pathParameters") or {}
    if route == "GET /api/machines":
        return list_machines()
    if route == "GET /api/machines/{machineId}/readings":
        machine_id = params.get("machineId", "")
        if not is_valid_machine(machine_id, machine_count()):
            return error("unknown machine", 404)
        return list_readings(machine_id, _limit(event, 60, MAX_READINGS))
    if route == "GET /api/alerts":
        return list_alerts(_limit(event, 20, MAX_ALERTS))
    if route == "GET /api/alerts/{alertId}":
        return get_alert(unquote(params.get("alertId", "")))
    return error("not found", 404)

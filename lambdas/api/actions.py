"""Demo actions (throttled at API Gateway): inject a fault, switch the simulator on/off."""

from __future__ import annotations

import json
import logging
import os

import boto3

from api.responses import error, ok
from common.features import FAILURE_TYPES
from common.store import STATE_SK, is_valid_machine, machine_pk
from simulator.faults import FAULT_TICKS

logger = logging.getLogger()
logger.setLevel(logging.INFO)

table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "maintainops"))
lambda_client = boto3.client("lambda")
scheduler = boto3.client("scheduler")

# fields GetSchedule returns that UpdateSchedule accepts
SCHEDULE_FIELDS = (
    "Name", "GroupName", "ScheduleExpression", "ScheduleExpressionTimezone", "FlexibleTimeWindow",
    "Target", "Description", "StartDate", "EndDate", "KmsKeyArn", "ActionAfterCompletion",
)


def _body(event: dict) -> dict:
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {}
    return body if isinstance(body, dict) else {}


def inject_fault(machine_id: str, fault: str) -> dict:
    table.update_item(
        Key={"pk": machine_pk(machine_id), "sk": STATE_SK},
        UpdateExpression="SET pending_fault = :f, fault_ticks = :t",
        ExpressionAttributeValues={":f": fault, ":t": FAULT_TICKS},
    )
    # emit a reading for this machine right away instead of waiting for the next tick
    lambda_client.invoke(
        FunctionName=os.environ["SIMULATOR_FUNCTION"],
        InvocationType="Event",
        Payload=json.dumps({"machine_ids": [machine_id]}).encode(),
    )
    logger.info("injected %s into %s", fault, machine_id)
    return ok({"machine_id": machine_id, "fault": fault, "ticks": FAULT_TICKS}, 202)


def set_simulator(enabled: bool) -> dict:
    current = scheduler.get_schedule(Name=os.environ["SCHEDULE_NAME"])
    update = {k: current[k] for k in SCHEDULE_FIELDS if k in current}
    scheduler.update_schedule(**update, State="ENABLED" if enabled else "DISABLED")
    logger.info("simulator enabled=%s", enabled)
    return ok({"simulator_enabled": enabled})


def handler(event: dict, _context: object) -> dict:
    route = event.get("routeKey", "")
    body = _body(event)
    if route == "POST /api/machines/{machineId}/fault":
        machine_id = (event.get("pathParameters") or {}).get("machineId", "")
        if not is_valid_machine(machine_id, int(os.environ["MACHINE_COUNT"])):
            return error("unknown machine", 404)
        fault = str(body.get("fault", "")).upper()
        if fault not in FAILURE_TYPES:
            return error(f"fault must be one of {', '.join(FAILURE_TYPES)}", 400)
        return inject_fault(machine_id, fault)
    if route == "POST /api/simulator":
        if not isinstance(body.get("enabled"), bool):
            return error("body must be {\"enabled\": true|false}", 400)
        return set_simulator(body["enabled"])
    return error("not found", 404)

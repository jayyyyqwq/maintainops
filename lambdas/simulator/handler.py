"""Simulator: every tick, emit one reading per machine and hand the batch to inference.

Sensor values are replayed from held-out AI4I rows the model never saw; each machine
keeps its own tool-wear counter so wear grows realistically and resets on tool change.
Invoked by EventBridge Scheduler ({}), or by the inject-fault API ({"machine_ids": [...]})
for an immediate reading.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time

import boto3

from common.store import STATE_SK, from_dynamo, machine_ids, machine_pk
from simulator.faults import apply_fault

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
lambda_client = boto3.client("lambda")
table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "maintainops"))

WEAR_PER_TICK = (1, 3)
TOOL_CHANGE_AT = 180  # replace the tool before the TWF window (200-240 min)
_replay_cache: list[dict] = []


def replay_pool() -> list[dict]:
    if not _replay_cache:
        obj = s3.get_object(Bucket=os.environ["DATA_BUCKET"], Key="replay/replay.json")
        _replay_cache.extend(json.loads(obj["Body"].read()))
    return _replay_cache


def next_reading(machine_id: str, state: dict, pool: list[dict], rng: random.Random) -> tuple[dict, dict]:
    """Return (reading, new_state_fields) for one machine."""
    cursor = int(state.get("cursor_pos", int(machine_id[1:]) * 97))
    base = pool[cursor % len(pool)]
    wear = int(state.get("tool_wear_min", rng.randint(0, 60))) + rng.randint(*WEAR_PER_TICK)
    if wear >= TOOL_CHANGE_AT:
        wear = 0
    reading = {k: base[k] for k in ("air_temp_k", "process_temp_k", "rpm", "torque_nm", "quality")}
    reading["tool_wear_min"] = wear

    fault = state.get("pending_fault")
    fault_ticks = int(state.get("fault_ticks", 0))
    if fault and fault_ticks > 0:
        reading = apply_fault(reading, fault, rng)
        fault_ticks -= 1
        if fault_ticks == 0 and fault in ("TWF", "OSF"):
            wear = 0  # technician changed the tool
    else:
        fault, fault_ticks = None, 0

    updates = {
        "cursor": cursor + 1,
        "tool_wear_min": wear,
        "pending_fault": fault if fault_ticks > 0 else None,
        "fault_ticks": fault_ticks,
    }
    reading |= {"machine_id": machine_id, "injected_fault": fault}
    return reading, updates


def handler(event: dict, _context: object) -> dict:
    count = int(os.environ["MACHINE_COUNT"])
    targets = event.get("machine_ids") or machine_ids(count)
    pool = replay_pool()
    rng = random.Random(time.time_ns())

    readings = []
    for machine_id in targets:
        key = {"pk": machine_pk(machine_id), "sk": STATE_SK}
        state = from_dynamo(table.get_item(Key=key).get("Item", {}))
        reading, updates = next_reading(machine_id, state, pool, rng)
        table.update_item(
            Key=key,
            UpdateExpression="SET cursor_pos = :c, tool_wear_min = :w, pending_fault = :f, fault_ticks = :t",
            ExpressionAttributeValues={
                ":c": updates["cursor"],
                ":w": updates["tool_wear_min"],
                ":f": updates["pending_fault"],
                ":t": updates["fault_ticks"],
            },
        )
        readings.append(reading)

    lambda_client.invoke(
        FunctionName=os.environ["INFERENCE_FUNCTION"],
        InvocationType="Event",
        Payload=json.dumps({"readings": readings}).encode(),
    )
    logger.info("emitted %d readings", len(readings))
    return {"emitted": len(readings)}


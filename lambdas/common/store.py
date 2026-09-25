"""Single-table DynamoDB layout.

    pk=MACHINE#<id>  sk=STATE          latest reading, risk, replay cursor, pending fault
    pk=MACHINE#<id>  sk=R#<iso-ts>     one reading + prediction (TTL)
    pk=ALERTS        sk=<iso-ts>#<id>  alert with Bedrock explanation + citations
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

MACHINE_ID = re.compile(r"^m[1-9][0-9]?$")
ALERTS_PK = "ALERTS"
STATE_SK = "STATE"


def machine_pk(machine_id: str) -> str:
    return f"MACHINE#{machine_id}"


def reading_sk(ts: str) -> str:
    return f"R#{ts}"


def alert_sk(ts: str, machine_id: str) -> str:
    return f"{ts}#{machine_id}"


def machine_ids(count: int) -> list[str]:
    return [f"m{i}" for i in range(1, count + 1)]


def is_valid_machine(machine_id: str, count: int) -> bool:
    return bool(MACHINE_ID.match(machine_id)) and int(machine_id[1:]) <= count


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def to_dynamo(value: Any) -> Any:
    """DynamoDB rejects floats; round-trip through JSON into Decimals."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def from_dynamo(value: Any) -> Any:
    if isinstance(value, list):
        return [from_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: from_dynamo(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value

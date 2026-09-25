"""HTTP API (payload v2) response helpers with a consistent envelope."""

from __future__ import annotations

import json
from typing import Any


def ok(data: Any, status: int = 200) -> dict:
    return _respond(status, {"success": True, "data": data, "error": None})


def error(message: str, status: int) -> dict:
    return _respond(status, {"success": False, "data": None, "error": message})


def _respond(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body, default=str),
    }

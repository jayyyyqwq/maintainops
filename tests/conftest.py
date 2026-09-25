"""Test setup: no AWS access. Clients are created at import, so give boto3 a region and fake creds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for sub in ("lambdas", "infra"):
    sys.path.insert(0, str(ROOT / sub))

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("TABLE_NAME", "maintainops-test")

DATASET = ROOT / "data" / "ai4i2020.csv"


@pytest.fixture(scope="session")
def dataset_text() -> str:
    return DATASET.read_text(encoding="utf-8")


@pytest.fixture
def healthy_reading() -> dict:
    return {
        "machine_id": "m1",
        "air_temp_k": 300.0,
        "process_temp_k": 310.2,
        "rpm": 1500.0,
        "torque_nm": 40.0,
        "tool_wear_min": 50.0,
        "quality": "M",
    }

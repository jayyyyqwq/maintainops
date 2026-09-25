"""Pipeline step 1: turn the raw AI4I CSV into SageMaker training/validation/test channels."""

from __future__ import annotations

import json
import os

import boto3

from common.dataset import Split, prepare
from common.features import to_csv_line

s3 = boto3.client("s3")

RAW_KEY = "raw/ai4i2020.csv"
REPLAY_KEY = "replay/replay.json"


def _put(bucket: str, key: str, body: str, content_type: str = "text/csv") -> str:
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode(), ContentType=content_type)
    return f"s3://{bucket}/{key}"


def weighted_csv(split: Split, weights: dict[int, float] | None) -> str:
    """Built-in XGBoost with csv_weights=1 expects rows of: label, weight, features..."""
    return "\n".join(
        to_csv_line([y, weights[y] if weights else 1.0, *x])
        for x, y in zip(split.features, split.labels, strict=True)
    )


def handler(event: dict, _context: object) -> dict:
    bucket = os.environ["DATA_BUCKET"]
    run_id = event["run_id"]
    raw = s3.get_object(Bucket=bucket, Key=RAW_KEY)["Body"].read().decode("utf-8")
    data = prepare(raw)

    prefix = f"runs/{run_id}"
    train_uri = _put(bucket, f"{prefix}/train/train.csv", weighted_csv(data.train, data.weights))
    # validation stays unweighted: early stopping must judge the real class distribution,
    # otherwise it stops ~5x earlier and precision collapses (0.83 -> 0.50 in experiments)
    validation_uri = _put(bucket, f"{prefix}/validation/validation.csv", weighted_csv(data.validation, None))
    test_uri = _put(bucket, f"{prefix}/test/test_features.csv", "\n".join(map(to_csv_line, data.test.features)))
    _put(bucket, f"{prefix}/test/test_labels.json", json.dumps(data.test.labels), "application/json")

    # held-out, never-trained rows that the simulator replays as live sensor data
    replay = [r for r, y in zip(data.test.readings, data.test.labels, strict=True) if y == 0]
    _put(bucket, REPLAY_KEY, json.dumps(replay), "application/json")

    return {
        "run_id": run_id,
        "train_uri": train_uri,
        "validation_uri": validation_uri,
        "test_uri": test_uri,
        "model_output_uri": f"s3://{bucket}/{prefix}/model",
        "transform_output_uri": f"s3://{bucket}/{prefix}/transform",
        "rows": {
            "train": len(data.train.labels),
            "validation": len(data.validation.labels),
            "test": len(data.test.labels),
            "dropped": data.dropped_rows,
        },
    }

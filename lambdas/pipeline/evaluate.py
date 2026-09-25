"""Pipeline quality gate: score batch-transform output against held-out labels."""

from __future__ import annotations

import json
import os

import boto3

from common.features import CLASSES
from common.metrics import evaluate
from common.predictions import parse_probabilities

s3 = boto3.client("s3")


def _read(bucket: str, key: str) -> str:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def handler(event: dict, _context: object) -> dict:
    bucket = os.environ["DATA_BUCKET"]
    run_id = event["run_id"]
    threshold = float(os.environ["RISK_THRESHOLD"])
    min_pr_auc = float(os.environ["MIN_PR_AUC"])
    min_recall = float(os.environ["MIN_RECALL"])
    min_precision = float(os.environ.get("MIN_PRECISION", "0"))

    prefix = f"runs/{run_id}"
    labels = json.loads(_read(bucket, f"{prefix}/test/test_labels.json"))
    probabilities = parse_probabilities(_read(bucket, f"{prefix}/transform/test_features.csv.out"))
    if len(probabilities) != len(labels):
        raise ValueError(f"{len(probabilities)} predictions for {len(labels)} labels")

    report = evaluate(labels, probabilities, CLASSES, threshold)
    passed = (
        report["pr_auc"] >= min_pr_auc
        and report["binary"]["recall"] >= min_recall
        and report["binary"]["precision"] >= min_precision  # guards against alert fatigue
    )
    report |= {
        "source": "sagemaker",
        "run_id": run_id,
        "quality_gate": {
            "min_pr_auc": min_pr_auc, "min_recall": min_recall, "min_precision": min_precision, "passed": passed,
        },
    }

    body = json.dumps(report, indent=2)
    for key in (f"{prefix}/metrics.json", "metrics/latest.json"):
        s3.put_object(Bucket=bucket, Key=key, Body=body.encode(), ContentType="application/json")

    return {
        "passed": passed,
        "pr_auc": report["pr_auc"],
        "recall": report["binary"]["recall"],
        "precision": report["binary"]["precision"],
        "f1": report["binary"]["f1"],
    }

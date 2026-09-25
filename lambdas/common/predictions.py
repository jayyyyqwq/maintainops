"""Parse SageMaker built-in XGBoost `multi:softprob` CSV responses.

Depending on container version a row comes back as `0.1,0.2,...` or `[0.1, 0.2, ...]`,
and a batch may be newline-separated or a JSON-style list of lists.
"""

from __future__ import annotations

import json

from common.features import CLASSES


def parse_probabilities(body: str, n_classes: int = len(CLASSES)) -> list[list[float]]:
    text = body.strip()
    if not text:
        return []
    if text.startswith("[["):
        rows = json.loads(text)
    else:
        rows = [
            [float(v) for v in line.strip().strip("[]").split(",") if v.strip()]
            for line in text.splitlines()
            if line.strip()
        ]
    for row in rows:
        if len(row) != n_classes:
            raise ValueError(f"expected {n_classes} probabilities, got {len(row)}: {row}")
    return [[float(v) for v in row] for row in rows]


def summarise(probabilities: list[float]) -> dict:
    """Risk = 1 - P(no failure); likely failure type = most probable non-NONE class."""
    risk = 1.0 - probabilities[0]
    best = max(range(1, len(CLASSES)), key=lambda k: probabilities[k])
    return {
        "risk": round(risk, 4),
        "failure_type": CLASSES[best],
        "probabilities": {name: round(p, 4) for name, p in zip(CLASSES, probabilities, strict=True)},
    }

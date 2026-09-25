"""AI4I 2020 dataset preparation shared by local training and the pipeline's prepare Lambda."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from common.features import class_weights, engineer, label_from_row, reading_from_row, stratified_split

SPLIT_FRACTIONS = (0.70, 0.15, 0.15)  # train / validation / test (test doubles as replay pool)
SEED = 42


@dataclass(frozen=True)
class Split:
    readings: list[dict]
    features: list[list[float]]
    labels: list[int]


@dataclass(frozen=True)
class PreparedData:
    train: Split
    validation: Split
    test: Split
    weights: dict[int, float]
    dropped_rows: int


def load_rows(csv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(csv_text.lstrip("﻿"))))


def prepare(csv_text: str) -> PreparedData:
    readings, labels, dropped = [], [], 0
    for row in load_rows(csv_text):
        label = label_from_row(row)
        if label is None:
            dropped += 1
            continue
        reading = reading_from_row(row)
        reading["product_id"] = row["Product ID"]
        readings.append(reading)
        labels.append(label)

    buckets = stratified_split(labels, SPLIT_FRACTIONS, seed=SEED)
    splits = [
        Split(
            readings=[readings[i] for i in idxs],
            features=[engineer(readings[i]) for i in idxs],
            labels=[labels[i] for i in idxs],
        )
        for idxs in buckets
    ]
    return PreparedData(
        train=splits[0],
        validation=splits[1],
        test=splits[2],
        weights=class_weights(splits[0].labels),
        dropped_rows=dropped,
    )

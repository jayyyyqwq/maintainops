"""Feature engineering and labelling shared by training, the pipeline and runtime Lambdas.

Pure Python on purpose: Lambdas ship with boto3 only, and the same code must produce
identical features at training and inference time.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping, Sequence

CLASSES: tuple[str, ...] = ("NONE", "TWF", "HDF", "PWF", "OSF")
FAILURE_TYPES: tuple[str, ...] = CLASSES[1:]

# When a row carries several failure flags we keep the most damaging mechanism:
# power and overstrain failures break the spindle/tool immediately, heat builds up,
# tool wear is gradual.
LABEL_PRIORITY: tuple[str, ...] = ("PWF", "OSF", "HDF", "TWF")

RAW_COLUMNS = {
    "air_temp_k": "Air temperature [K]",
    "process_temp_k": "Process temperature [K]",
    "rpm": "Rotational speed [rpm]",
    "torque_nm": "Torque [Nm]",
    "tool_wear_min": "Tool wear [min]",
    "quality": "Type",
}

FEATURE_NAMES: tuple[str, ...] = (
    "air_temp_k",
    "process_temp_k",
    "rpm",
    "torque_nm",
    "tool_wear_min",
    "quality_l",
    "quality_m",
    "quality_h",
    "temp_diff_k",
    "power_w",
    "strain_nm_min",
)

QUALITIES = ("L", "M", "H")


def power_watts(torque_nm: float, rpm: float) -> float:
    """Mechanical power P = torque * angular speed (rad/s)."""
    return torque_nm * rpm * 2.0 * math.pi / 60.0


def engineer(reading: Mapping[str, float | str]) -> list[float]:
    """Turn one sensor reading into the model's feature vector (order = FEATURE_NAMES)."""
    air = float(reading["air_temp_k"])
    proc = float(reading["process_temp_k"])
    rpm = float(reading["rpm"])
    torque = float(reading["torque_nm"])
    wear = float(reading["tool_wear_min"])
    quality = str(reading.get("quality", "M")).upper()
    if quality not in QUALITIES:
        raise ValueError(f"unknown product quality {quality!r}")
    return [
        air,
        proc,
        rpm,
        torque,
        wear,
        float(quality == "L"),
        float(quality == "M"),
        float(quality == "H"),
        proc - air,  # heat dissipation failure: diff < 8.6 K and rpm < 1380
        power_watts(torque, rpm),  # power failure: P < 3500 W or > 9000 W
        torque * wear,  # overstrain failure: wear*torque > 11k/12k/13k (L/M/H)
    ]


def reading_from_row(row: Mapping[str, str]) -> dict[str, float | str]:
    """Map a raw AI4I CSV row to the reading schema used across the system."""
    reading: dict[str, float | str] = {
        key: float(row[col]) for key, col in RAW_COLUMNS.items() if key != "quality"
    }
    reading["quality"] = row[RAW_COLUMNS["quality"]].strip()
    return reading


def label_from_row(row: Mapping[str, str]) -> int | None:
    """Return the class index, or None for rows we drop (failure with no recorded cause)."""
    if row["Machine failure"].strip() != "1":
        return 0
    for failure in LABEL_PRIORITY:
        if row[failure].strip() == "1":
            return CLASSES.index(failure)
    return None


def to_csv_line(values: Iterable[float]) -> str:
    return ",".join(f"{v:.6g}" for v in values)


def stratified_split(
    labels: Sequence[int], fractions: Sequence[float], seed: int = 42
) -> list[list[int]]:
    """Deterministic stratified split of row indices into len(fractions) buckets."""
    if not math.isclose(sum(fractions), 1.0):
        raise ValueError("fractions must sum to 1")
    by_class: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        by_class.setdefault(label, []).append(idx)
    rng = random.Random(seed)
    buckets: list[list[int]] = [[] for _ in fractions]
    for label in sorted(by_class):
        idxs = by_class[label][:]
        rng.shuffle(idxs)
        start = 0
        for b, frac in enumerate(fractions):
            end = len(idxs) if b == len(fractions) - 1 else start + round(frac * len(idxs))
            buckets[b].extend(idxs[start:end])
            start = end
    return [sorted(b) for b in buckets]


def class_weights(labels: Sequence[int], cap: float = 50.0) -> dict[int, float]:
    """Inverse-frequency weights normalised so the majority class weighs 1.0, capped."""
    counts: dict[int, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    majority = max(counts.values())
    return {label: min(majority / n, cap) for label, n in counts.items()}

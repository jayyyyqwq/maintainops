from __future__ import annotations

import math

import pytest

from common.dataset import prepare
from common.features import (
    CLASSES,
    FEATURE_NAMES,
    class_weights,
    engineer,
    label_from_row,
    power_watts,
    stratified_split,
)


def test_engineered_features_follow_physics(healthy_reading):
    features = dict(zip(FEATURE_NAMES, engineer(healthy_reading), strict=True))
    assert features["temp_diff_k"] == pytest.approx(10.2)
    assert features["power_w"] == pytest.approx(40.0 * 1500 * 2 * math.pi / 60)
    assert features["strain_nm_min"] == pytest.approx(2000.0)
    assert (features["quality_l"], features["quality_m"], features["quality_h"]) == (0.0, 1.0, 0.0)


def test_power_matches_ai4i_pwf_bounds():
    # 3500 W and 9000 W are the dataset's power-failure bounds
    assert power_watts(torque_nm=70, rpm=1400) > 9000
    assert power_watts(torque_nm=10, rpm=2800) < 3500


def test_unknown_quality_rejected(healthy_reading):
    with pytest.raises(ValueError):
        engineer(healthy_reading | {"quality": "X"})


def _row(failure: str = "0", **flags: str) -> dict:
    base = {k: "0" for k in ("TWF", "HDF", "PWF", "OSF", "RNF")}
    return {"Machine failure": failure, **base, **flags}


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (_row(), 0),
        (_row("0", RNF="1"), 0),  # random-failure flag without a machine failure
        (_row("1", HDF="1"), CLASSES.index("HDF")),
        (_row("1", PWF="1", OSF="1"), CLASSES.index("PWF")),  # priority: PWF > OSF
        (_row("1", TWF="1", OSF="1"), CLASSES.index("OSF")),
        (_row("1"), None),  # failure with no recorded cause is dropped
    ],
)
def test_label_priority(row, expected):
    assert label_from_row(row) == expected


def test_stratified_split_is_deterministic_and_preserves_ratio():
    labels = [0] * 900 + [1] * 100
    a = stratified_split(labels, (0.7, 0.15, 0.15), seed=7)
    b = stratified_split(labels, (0.7, 0.15, 0.15), seed=7)
    assert a == b
    assert sorted(i for bucket in a for i in bucket) == list(range(1000))
    for bucket in a:
        positives = sum(labels[i] for i in bucket)
        assert positives / len(bucket) == pytest.approx(0.1, abs=0.01)


def test_class_weights_upweight_rare_classes():
    weights = class_weights([0] * 100 + [1] * 10 + [2] * 1, cap=50)
    assert weights[0] == 1.0
    assert weights[1] == 10.0
    assert weights[2] == 50.0  # 100 capped at 50


def test_prepare_real_dataset(dataset_text):
    data = prepare(dataset_text)
    total = len(data.train.labels) + len(data.validation.labels) + len(data.test.labels)
    assert data.dropped_rows == 9
    assert total == 10_000 - 9
    assert len(data.test.labels) == pytest.approx(0.15 * total, abs=5)
    assert all(len(f) == len(FEATURE_NAMES) for f in data.train.features[:50])
    failure_rate = sum(1 for y in data.test.labels if y) / len(data.test.labels)
    assert 0.02 < failure_rate < 0.05

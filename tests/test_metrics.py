from __future__ import annotations

import random

import pytest

from common.metrics import average_precision, binary_report, confusion_matrix, evaluate
from common.predictions import parse_probabilities, summarise


def test_average_precision_matches_sklearn():
    sklearn = pytest.importorskip("sklearn.metrics")
    rng = random.Random(0)
    y = [int(rng.random() < 0.1) for _ in range(500)]
    scores = [round(rng.random() * 0.6 + 0.4 * t, 2) for t in y]  # rounded -> ties exercised
    assert average_precision(y, scores) == pytest.approx(sklearn.average_precision_score(y, scores))


def test_binary_report_counts():
    report = binary_report([1, 1, 0, 0], [1, 0, 1, 0])
    assert (report["tp"], report["fp"], report["fn"], report["tn"]) == (1, 1, 1, 1)
    assert report["precision"] == report["recall"] == report["f1"] == 0.5


def test_confusion_matrix_shape():
    assert confusion_matrix([0, 1, 2], [0, 2, 2], 3) == [[1, 0, 0], [0, 0, 1], [0, 0, 1]]


def test_evaluate_uses_risk_threshold_for_failure_type():
    probs = [
        [0.9, 0.02, 0.03, 0.03, 0.02],  # healthy
        [0.3, 0.05, 0.6, 0.03, 0.02],  # HDF, risk 0.7
        [0.6, 0.1, 0.25, 0.03, 0.02],  # risk 0.4 < 0.5 -> predicted NONE
    ]
    report = evaluate([0, 2, 2], probs, ("NONE", "TWF", "HDF", "PWF", "OSF"), threshold=0.5)
    assert report["confusion_matrix"]["matrix"][2] == [1, 0, 1, 0, 0]
    assert report["binary"]["recall"] == 0.5
    assert report["binary"]["precision"] == 1.0


@pytest.mark.parametrize(
    "body",
    [
        "0.9,0.02,0.03,0.03,0.02\n0.1,0.1,0.6,0.1,0.1\n",
        "[0.9, 0.02, 0.03, 0.03, 0.02]\n[0.1, 0.1, 0.6, 0.1, 0.1]",
        "[[0.9, 0.02, 0.03, 0.03, 0.02], [0.1, 0.1, 0.6, 0.1, 0.1]]",
    ],
)
def test_parse_probabilities_formats(body):
    rows = parse_probabilities(body)
    assert len(rows) == 2
    assert rows[1][2] == 0.6


def test_parse_probabilities_rejects_wrong_width():
    with pytest.raises(ValueError):
        parse_probabilities("0.5,0.5")


def test_summarise_picks_top_failure_type():
    summary = summarise([0.2, 0.1, 0.1, 0.5, 0.1])
    assert summary["risk"] == 0.8
    assert summary["failure_type"] == "PWF"

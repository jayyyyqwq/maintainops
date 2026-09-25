"""Trains the local model once and checks it on real data and on the demo fault profiles."""

from __future__ import annotations

import random

import pytest

pytest.importorskip("xgboost")

from common.dataset import prepare  # noqa: E402
from common.features import CLASSES  # noqa: E402
from common.metrics import evaluate  # noqa: E402
from simulator.faults import apply_fault  # noqa: E402


@pytest.fixture(scope="module")
def trained(dataset_text):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
    from train_local import load_config, train

    config = load_config()
    data = prepare(dataset_text)
    return train(data, config["sagemaker"]["hyperparameters"]), data


def test_model_beats_quality_gate(trained):
    pipeline, data = trained
    report = evaluate(data.test.labels, pipeline.predict_proba(data.test.readings).tolist(), CLASSES)
    assert report["pr_auc"] >= 0.70
    assert report["binary"]["recall"] >= 0.70


@pytest.mark.parametrize("fault", ["HDF", "PWF", "OSF"])
def test_injected_faults_are_detected(trained, fault):
    """The dashboard's 'Inject fault' demo must actually trip the model."""
    pipeline, data = trained
    rng = random.Random(11)
    healthy = [r for r, y in zip(data.test.readings, data.test.labels, strict=True) if y == 0][:30]
    faulty = [apply_fault(r | {"tool_wear_min": 60}, fault, rng) for r in healthy]
    probs = pipeline.predict_proba(faulty)
    risks = 1 - probs[:, 0]
    predicted = [CLASSES[1 + int(p[1:].argmax())] for p in probs]
    assert (risks >= 0.5).mean() >= 0.9
    assert predicted.count(fault) / len(predicted) >= 0.8

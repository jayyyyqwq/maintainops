"""Train the MaintainOps model locally (no AWS) and write metrics + confusion matrix to docs/.

Reproduces the SageMaker training job: same features, split, class weights and hyperparameters.

    python ml/train_local.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import FunctionTransformer  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lambdas"))

from common.dataset import PreparedData, prepare  # noqa: E402
from common.features import CLASSES, FEATURE_NAMES, engineer  # noqa: E402
from common.metrics import evaluate  # noqa: E402

DATA = ROOT / "data" / "ai4i2020.csv"
DOCS = ROOT / "docs"


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text())


def engineer_batch(readings: list[dict]) -> np.ndarray:
    return np.array([engineer(r) for r in readings], dtype=float)


def build_pipeline(hp: dict) -> Pipeline:
    classifier = XGBClassifier(
        objective=hp["objective"],
        n_estimators=hp["num_round"],
        max_depth=hp["max_depth"],
        learning_rate=hp["eta"],
        subsample=hp["subsample"],
        colsample_bytree=hp["colsample_bytree"],
        min_child_weight=hp["min_child_weight"],
        early_stopping_rounds=hp["early_stopping_rounds"],
        eval_metric=hp["eval_metric"],
        random_state=42,
    )
    return Pipeline([("features", FunctionTransformer(engineer_batch)), ("xgb", classifier)])


def train(data: PreparedData, hp: dict) -> Pipeline:
    pipeline = build_pipeline(hp)
    sample_weight = [data.weights[y] for y in data.train.labels]
    pipeline.fit(
        data.train.readings,
        data.train.labels,
        xgb__sample_weight=sample_weight,
        # the transformer is stateless, so pre-engineered validation features are equivalent
        xgb__eval_set=[(np.array(data.validation.features), data.validation.labels)],
        xgb__verbose=False,
    )
    return pipeline


def plot_confusion(matrix: list[list[int]], labels: list[str], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 4.6), dpi=150)
    arr = np.array(matrix)
    ax.imshow(np.log1p(arr), cmap="Blues")
    ax.set_xticks(range(len(labels)), labels)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("MaintainOps — held-out test set")
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, arr[i, j], ha="center", va="center",
                    color="white" if arr[i, j] > arr.max() / 4 else "black", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> dict:
    config = load_config()
    hp = config["sagemaker"]["hyperparameters"]
    data = prepare(DATA.read_text(encoding="utf-8"))
    pipeline = train(data, hp)

    probabilities = pipeline.predict_proba(data.test.readings).tolist()
    report = evaluate(data.test.labels, probabilities, CLASSES, config["runtime"]["risk_threshold"])
    booster = pipeline.named_steps["xgb"]
    importance = dict(zip(FEATURE_NAMES, booster.feature_importances_.round(4).tolist(), strict=True))
    report |= {
        "source": "local",
        "best_iteration": int(booster.best_iteration),
        "rows": {
            "train": len(data.train.labels),
            "validation": len(data.validation.labels),
            "test": len(data.test.labels),
            "dropped": data.dropped_rows,
        },
        "feature_importance": dict(sorted(importance.items(), key=lambda kv: -kv[1])),
    }

    DOCS.mkdir(exist_ok=True)
    (DOCS / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    plot_confusion(report["confusion_matrix"]["matrix"], list(CLASSES), DOCS / "confusion_matrix.png")

    b = report["binary"]
    print(f"test rows={report['n_test']}  failure rate={report['failure_rate']:.2%}")
    print(f"failure  precision={b['precision']:.3f} recall={b['recall']:.3f} "
          f"f1={b['f1']:.3f} pr_auc={report['pr_auc']:.3f}")
    for name, m in report["per_class"].items():
        print(f"  {name:4s} p={m['precision']:.3f} r={m['recall']:.3f} f1={m['f1']:.3f} n={m['support']}")
    return report


if __name__ == "__main__":
    main()

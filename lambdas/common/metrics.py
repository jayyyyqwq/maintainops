"""Dependency-free classification metrics (used by the evaluate Lambda and local training)."""

from __future__ import annotations

from collections.abc import Sequence


def average_precision(y_true: Sequence[int], scores: Sequence[float]) -> float:
    """PR-AUC as average precision (same definition as sklearn.average_precision_score)."""
    positives = sum(y_true)
    if positives == 0:
        return 0.0
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    ap, tp, fp, prev_recall = 0.0, 0, 0, 0.0
    i = 0
    while i < len(order):
        # group tied scores so ties are handled like sklearn
        j = i
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            if y_true[order[j]]:
                tp += 1
            else:
                fp += 1
            j += 1
        recall = tp / positives
        precision = tp / (tp + fp)
        ap += (recall - prev_recall) * precision
        prev_recall = recall
        i = j
    return ap


def confusion_matrix(y_true: Sequence[int], y_pred: Sequence[int], n_classes: int) -> list[list[int]]:
    matrix = [[0] * n_classes for _ in range(n_classes)]
    for t, p in zip(y_true, y_pred, strict=True):
        matrix[t][p] += 1
    return matrix


def binary_report(y_true: Sequence[int], y_pred: Sequence[int]) -> dict[str, float | int]:
    tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t and not p)
    tn = len(y_true) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1}


def evaluate(
    y_true: Sequence[int],
    probabilities: Sequence[Sequence[float]],
    class_names: Sequence[str],
    threshold: float = 0.5,
) -> dict:
    """Full report: binary failure metrics at `threshold`, PR-AUC, per-class F1, confusion matrix.

    Class 0 is "no failure"; failure risk = 1 - P(class 0).
    """
    n = len(class_names)
    risk = [1.0 - p[0] for p in probabilities]
    y_bin = [int(t != 0) for t in y_true]
    pred_bin = [int(r >= threshold) for r in risk]
    # predicted class: argmax over failure types when risk crosses threshold, else NONE
    y_pred = [
        (max(range(1, n), key=lambda k: p[k]) if flag else 0)
        for p, flag in zip(probabilities, pred_bin, strict=True)
    ]
    matrix = confusion_matrix(y_true, y_pred, n)
    per_class = {}
    for k, name in enumerate(class_names):
        report = binary_report([int(t == k) for t in y_true], [int(p == k) for p in y_pred])
        per_class[name] = {
            "precision": round(report["precision"], 4),
            "recall": round(report["recall"], 4),
            "f1": round(report["f1"], 4),
            "support": sum(1 for t in y_true if t == k),
        }
    binary = binary_report(y_bin, pred_bin)
    return {
        "threshold": threshold,
        "n_test": len(y_true),
        "failure_rate": round(sum(y_bin) / len(y_bin), 4),
        "binary": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in binary.items()},
        "pr_auc": round(average_precision(y_bin, risk), 4),
        "accuracy": round(sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p) / len(y_true), 4),
        "per_class": per_class,
        "confusion_matrix": {"labels": list(class_names), "matrix": matrix},
    }

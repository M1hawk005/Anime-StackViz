"""Shared, leakage-aware evaluation helpers for the predictive products."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    log_loss,
    roc_auc_score,
)


def chronological_split(
    dataset: pd.DataFrame, order_by: str, train_fraction: float = 0.8
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split oldest-to-newest by ``order_by`` so the test set is strictly later.

    A time-ordered holdout is more honest than a random split: it measures whether
    the model generalizes to titles that aired *after* everything it trained on.
    """
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between zero and one")
    ordered = dataset.sort_values(order_by, kind="stable").reset_index(drop=True)
    split_index = int(len(ordered) * train_fraction)
    if split_index == 0 or split_index >= len(ordered):
        raise ValueError("dataset is too small for the requested split")
    return ordered.iloc[:split_index].copy(), ordered.iloc[split_index:].copy()


def binary_metrics(y_true: pd.Series, probabilities: np.ndarray) -> dict[str, object]:
    """Threshold-free and thresholded metrics for a binary probability output."""
    y_true = pd.Series(y_true).reset_index(drop=True)
    predictions = (probabilities >= 0.5).astype(int)
    report = classification_report(y_true, predictions, output_dict=True, zero_division=0)
    single_class = y_true.nunique() < 2
    return {
        "roc_auc": None if single_class else roc_auc_score(y_true, probabilities),
        "average_precision": None if single_class else average_precision_score(y_true, probabilities),
        "brier_score": brier_score_loss(y_true, probabilities),
        "log_loss": log_loss(y_true, probabilities, labels=[0, 1]),
        "confusion_matrix": confusion_matrix(y_true, predictions, labels=[0, 1]).tolist(),
        "precision_at_0_5": report.get("1", {}).get("precision", 0.0),
        "recall_at_0_5": report.get("1", {}).get("recall", 0.0),
        "f1_at_0_5": report.get("1", {}).get("f1-score", 0.0),
        "positive_rate": float(y_true.mean()),
        "n": int(len(y_true)),
    }

"""Chronological evaluation for response-within-24-hours prediction."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features import NUMERIC_FEATURES


def chronological_split(dataset: pd.DataFrame, train_fraction: float = 0.8):
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between zero and one")
    split_index = int(len(dataset) * train_fraction)
    if split_index == 0 or split_index == len(dataset):
        raise ValueError("dataset is too small for the requested split")
    return dataset.iloc[:split_index].copy(), dataset.iloc[split_index:].copy()


def make_pipeline() -> Pipeline:
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    preprocess = ColumnTransformer(
        [
            (
                "text",
                TfidfVectorizer(
                    min_df=3,
                    max_df=0.98,
                    max_features=7_500,
                    ngram_range=(1, 2),
                    stop_words="english",
                    sublinear_tf=True,
                    strip_accents="unicode",
                ),
                "combined_text",
            ),
            (
                "tags",
                TfidfVectorizer(
                    token_pattern=r"(?u)\b[\w-]+\b",
                    binary=True,
                    use_idf=False,
                    norm=None,
                ),
                "tag_text",
            ),
            ("numeric", numeric, NUMERIC_FEATURES),
        ]
    )
    classifier = LogisticRegression(
        max_iter=2_000,
        solver="liblinear",
        random_state=42,
    )
    return Pipeline([("features", preprocess), ("classifier", classifier)])


def make_metadata_pipeline() -> Pipeline:
    """Build a deliberately simple baseline using no text or tag identity."""
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    return Pipeline([
        ("features", ColumnTransformer([("numeric", numeric, NUMERIC_FEATURES)])),
        (
            "classifier",
            LogisticRegression(max_iter=2_000, solver="liblinear", random_state=42),
        ),
    ])


def _metrics(y_true: pd.Series, probabilities: np.ndarray) -> dict[str, object]:
    predictions = (probabilities >= 0.5).astype(int)
    report = classification_report(y_true, predictions, output_dict=True, zero_division=0)
    return {
        "roc_auc": roc_auc_score(y_true, probabilities),
        "average_precision": average_precision_score(y_true, probabilities),
        "brier_score": brier_score_loss(y_true, probabilities),
        "log_loss": log_loss(y_true, probabilities),
        "confusion_matrix": confusion_matrix(y_true, predictions).tolist(),
        "precision_at_0_5": report["1"]["precision"],
        "recall_at_0_5": report["1"]["recall"],
        "f1_at_0_5": report["1"]["f1-score"],
    }


def train_and_evaluate(dataset: pd.DataFrame, output_dir: str | Path):
    train, test = chronological_split(dataset)
    target = "answered_within_24h"
    X_train, y_train = train.drop(columns=[target]), train[target]
    X_test, y_test = test.drop(columns=[target]), test[target]

    baseline = DummyClassifier(strategy="prior").fit(np.zeros((len(train), 1)), y_train)
    baseline_probabilities = baseline.predict_proba(np.zeros((len(test), 1)))[:, 1]

    metadata_pipeline = make_metadata_pipeline().fit(X_train, y_train)
    metadata_probabilities = metadata_pipeline.predict_proba(X_test)[:, 1]
    pipeline = make_pipeline().fit(X_train, y_train)
    probabilities = pipeline.predict_proba(X_test)[:, 1]

    feature_names = pipeline.named_steps["features"].get_feature_names_out()
    coefficients = pipeline.named_steps["classifier"].coef_[0]
    ranked = pd.DataFrame({"feature": feature_names, "coefficient": coefficients})
    top_features = {
        "increases_predicted_probability": ranked.nlargest(20, "coefficient").to_dict("records"),
        "decreases_predicted_probability": ranked.nsmallest(20, "coefficient").to_dict("records"),
    }
    results = {
        "target": "Any answer posted within 24 hours of the question",
        "split": "Oldest 80% train / newest 20% test",
        "train_rows": len(train),
        "test_rows": len(test),
        "train_end": train["CreationDate"].max().isoformat(),
        "test_start": test["CreationDate"].min().isoformat(),
        "test_end": test["CreationDate"].max().isoformat(),
        "train_positive_rate": y_train.mean(),
        "test_positive_rate": y_test.mean(),
        "prevalence_baseline": _metrics(y_test, baseline_probabilities),
        "metadata_logistic_regression": _metrics(y_test, metadata_probabilities),
        "logistic_regression": _metrics(y_test, probabilities),
    }

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (output / "top_features.json").write_text(json.dumps(top_features, indent=2), encoding="utf-8")
    predictions = test[["Id", "CreationDate", target]].copy()
    predictions["predicted_probability"] = probabilities
    predictions.to_csv(output / "predictions.csv", index=False)
    return pipeline, results, train, test, probabilities

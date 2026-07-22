"""Materialize the read-only serving artifact.

This is the boundary between the offline and online planes: it precomputes every
product the API serves — sequel probabilities, the hidden-gems ranking, and the
buzz leaderboard — into a compact set of Parquet files. The online API only ever
reads these, which is what keeps serving cheap and horizontally scalable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sklearn.model_selection import cross_val_predict

from ..analytics import build_hidden_gems, top_franchises
from ..analytics.gems import _has_table
from ..config import Settings
from ..models.sequel import TARGET, build_sequel_dataset, make_gradient_boosting_pipeline
from .warehouse import connect

SERVING_FILES = ("sequel_predictions.parquet", "hidden_gems.parquet", "buzz_top.parquet")


def _out_of_fold_probabilities(features, target):
    """Score each title with a model that never trained on it.

    In-sample probabilities would be near-perfect (leakage) and make the product
    look trivially good. Out-of-fold predictions reflect genuine generalization.
    Falls back to a single fit only when a class is too small to cross-validate.
    """
    smallest_class = target.value_counts().min()
    n_splits = min(5, int(smallest_class))
    if n_splits < 2:
        model = make_gradient_boosting_pipeline().fit(features, target)
        return model.predict_proba(features)[:, 1]
    return cross_val_predict(
        make_gradient_boosting_pipeline(), features, target, cv=n_splits, method="predict_proba"
    )[:, 1]


def _publish_sequel(connection, serving_dir: Path) -> int:
    dataset = build_sequel_dataset(connection)
    features = dataset.drop(columns=[TARGET])

    predictions = dataset[
        ["canonical_id", "title_romaji", "season_year", "average_score", "popularity", TARGET]
    ].copy()
    predictions["sequel_probability"] = _out_of_fold_probabilities(features, dataset[TARGET])
    predictions = predictions.sort_values("sequel_probability", ascending=False)
    predictions.to_parquet(serving_dir / "sequel_predictions.parquet", index=False)
    return len(predictions)


def _publish_gems(connection, serving_dir: Path) -> int:
    gems = build_hidden_gems(connection, limit=500)
    gems.to_parquet(serving_dir / "hidden_gems.parquet", index=False)
    return len(gems)


def _publish_buzz(connection, serving_dir: Path) -> int:
    if not _has_table(connection, "buzz"):
        return 0
    top = top_franchises(connection, limit=300)
    top.to_parquet(serving_dir / "buzz_top.parquet", index=False)
    return len(top)


def build_serving_artifact(settings: Settings) -> dict[str, object]:
    """Precompute all products into ``settings.serving_dir`` and write a manifest."""
    serving_dir = settings.serving_dir
    serving_dir.mkdir(parents=True, exist_ok=True)
    connection = connect(settings, read_only=True)
    try:
        counts = {
            "sequel_predictions": _publish_sequel(connection, serving_dir),
            "hidden_gems": _publish_gems(connection, serving_dir),
            "buzz_top": _publish_buzz(connection, serving_dir),
        }
    finally:
        connection.close()

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": counts,
    }
    (serving_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

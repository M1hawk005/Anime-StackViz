"""Sequel prediction: will a first-season anime get a continuation?

Labels come from AniList relation edges; the population is season-one TV titles
(no prequel) so the question is genuinely "does this opener continue?". Features
use signals a studio would have when greenlighting a sequel — reception and reach —
never the relation graph itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .evaluation import binary_metrics, chronological_split

# Season-one TV titles that have finished airing, labelled by whether they spawned
# a sequel. ``PREQUEL`` excludes titles that are themselves continuations.
_DATASET_SQL = """
WITH has_sequel AS (
    SELECT DISTINCT from_canonical_id AS canonical_id
    FROM relations WHERE relation_type = 'SEQUEL' AND to_type = 'ANIME'
),
is_continuation AS (
    SELECT DISTINCT from_canonical_id AS canonical_id
    FROM relations WHERE relation_type = 'PREQUEL' AND to_type = 'ANIME'
)
SELECT
    a.canonical_id,
    a.title_romaji,
    a.season_year,
    a.episodes,
    a.duration,
    a.average_score,
    a.mean_score,
    a.popularity,
    a.favourites,
    a.source_material,
    a.main_studio,
    a.genres,
    CAST(a.canonical_id IN (SELECT canonical_id FROM has_sequel) AS INTEGER) AS got_sequel
FROM anime a
WHERE a.format = 'TV'
  AND a.status = 'FINISHED'
  AND a.season_year IS NOT NULL
  AND a.canonical_id NOT IN (SELECT canonical_id FROM is_continuation)
ORDER BY a.season_year, a.canonical_id
"""

NUMERIC_FEATURES = [
    "episodes",
    "duration",
    "average_score",
    "mean_score",
    "popularity",
    "favourites",
    "season_year",
]
CATEGORICAL_FEATURES = ["source_material", "main_studio"]
TARGET = "got_sequel"


def build_sequel_dataset(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return the labelled season-one dataset from the warehouse."""
    return connection.execute(_DATASET_SQL).df()


def _preprocessor() -> ColumnTransformer:
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="UNKNOWN")),
        # Collapse rare studios so the encoding stays compact and generalizes.
        # sparse_output=False keeps the matrix dense for the gradient-boosting model,
        # which rejects sparse input (many real studios would otherwise trip it).
        ("onehot", OneHotEncoder(
            handle_unknown="infrequent_if_exist", min_frequency=5, sparse_output=False
        )),
    ])
    return ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ])


def make_logistic_pipeline() -> Pipeline:
    return Pipeline([
        ("features", _preprocessor()),
        ("classifier", LogisticRegression(max_iter=2_000, solver="liblinear", random_state=42)),
    ])


def make_gradient_boosting_pipeline() -> Pipeline:
    return Pipeline([
        ("features", _preprocessor()),
        ("classifier", HistGradientBoostingClassifier(random_state=42, max_iter=300)),
    ])


def _reception_only_pipeline() -> Pipeline:
    """A deliberately simple baseline: reception and reach, no studio/source."""
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    reception = ["average_score", "popularity", "favourites"]
    return Pipeline([
        ("features", ColumnTransformer([("numeric", numeric, reception)])),
        ("classifier", LogisticRegression(max_iter=2_000, solver="liblinear", random_state=42)),
    ])


def train_and_evaluate(dataset: pd.DataFrame, output_dir: str | Path) -> dict[str, object]:
    """Benchmark sequel prediction with a time-ordered holdout.

    Reports a prevalence floor, a reception-only baseline, and two full models
    (logistic regression and gradient boosting), so improvement over chance and
    over a naive signal is explicit rather than assumed.
    """
    train, test = chronological_split(dataset, order_by="season_year")
    x_train, y_train = train.drop(columns=[TARGET]), train[TARGET]
    x_test, y_test = test.drop(columns=[TARGET]), test[TARGET]

    prevalence = DummyClassifier(strategy="prior").fit(np.zeros((len(train), 1)), y_train)
    prevalence_proba = prevalence.predict_proba(np.zeros((len(test), 1)))[:, 1]

    models = {
        "reception_only_logreg": _reception_only_pipeline(),
        "full_logreg": make_logistic_pipeline(),
        "full_gradient_boosting": make_gradient_boosting_pipeline(),
    }
    results: dict[str, object] = {
        "target": "Season-one TV anime spawns a sequel",
        "split": "Oldest 80% by season_year / newest 20%",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_end_year": int(train["season_year"].max()),
        "test_start_year": int(test["season_year"].min()),
        "prevalence_baseline": binary_metrics(y_test, prevalence_proba),
    }
    for name, pipeline in models.items():
        pipeline.fit(x_train, y_train)
        proba = pipeline.predict_proba(x_test)[:, 1]
        results[name] = binary_metrics(y_test, proba)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "sequel_metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results

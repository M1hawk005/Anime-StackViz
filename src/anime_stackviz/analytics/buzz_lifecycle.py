"""Buzz-lifecycle analytics over the community discussion time-series.

Characterizes how attention on a franchise rises, peaks, and decays using the
``buzz`` table (per-tag monthly question counts).
"""

from __future__ import annotations

import duckdb
import pandas as pd


def top_franchises(connection: duckdb.DuckDBPyConnection, *, limit: int = 20) -> pd.DataFrame:
    """Rank franchises by total discussion volume, with peak and span summaries."""
    return connection.execute(
        """
        SELECT
            tag,
            sum(question_count)               AS total_questions,
            arg_max(period, question_count)   AS peak_period,
            max(question_count)               AS peak_count,
            count(*)                          AS active_months,
            min(period)                       AS first_period,
            max(period)                       AS last_period
        FROM buzz
        GROUP BY tag
        ORDER BY total_questions DESC
        LIMIT ?
        """,
        [limit],
    ).df()


def franchise_series(connection: duckdb.DuckDBPyConnection, tag: str) -> pd.DataFrame:
    """Return the monthly discussion series for one franchise tag."""
    return connection.execute(
        "SELECT period, question_count FROM buzz WHERE tag = ? ORDER BY period",
        [tag],
    ).df()


def lifecycle_metrics(series: pd.DataFrame) -> dict[str, object]:
    """Summarize the shape of a single franchise's discussion series.

    ``months_to_peak`` measures how quickly attention built; ``decay_ratio`` is the
    average post-peak volume as a fraction of the peak (lower = attention faded
    faster after cresting). Both are ``None`` when undefined.
    """
    if series.empty:
        return {
            "total_questions": 0,
            "peak_period": None,
            "peak_count": 0,
            "active_months": 0,
            "months_to_peak": None,
            "decay_ratio": None,
        }

    ordered = series.sort_values("period").reset_index(drop=True)
    counts = ordered["question_count"]
    peak_index = int(counts.idxmax())
    peak_count = int(counts.iloc[peak_index])
    post_peak = counts.iloc[peak_index + 1 :]

    return {
        "total_questions": int(counts.sum()),
        "peak_period": ordered["period"].iloc[peak_index],
        "peak_count": peak_count,
        "active_months": int(len(ordered)),
        "months_to_peak": peak_index,
        "decay_ratio": None if post_peak.empty else round(float(post_peak.mean()) / peak_count, 3),
    }

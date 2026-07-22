"""Hidden-gems scorer: highly rated titles with a small audience.

A gem is quantified as the gap between a title's *quality* percentile and its
*popularity* percentile. Ranking on percentiles (not raw values) is robust to the
different scales of AniList and MyAnimeList and to the heavy skew of popularity.
When MAL scores are present they are blended in, so the ranking draws on both
communities rather than a single site's taste.
"""

from __future__ import annotations

import duckdb
import pandas as pd

GEM_COLUMNS = [
    "canonical_id",
    "title_romaji",
    "title_english",
    "quality",
    "average_score",
    "mal_score",
    "popularity",
    "favourites",
    "season_year",
    "main_studio",
    "quality_pct",
    "popularity_pct",
    "gem_score",
]


def _has_table(connection: duckdb.DuckDBPyConnection, name: str) -> bool:
    return (
        connection.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [name]
        ).fetchone()[0]
        > 0
    )


def _load(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if _has_table(connection, "mal"):
        return connection.execute(
            """
            SELECT a.canonical_id, a.title_romaji, a.title_english,
                   a.average_score, m.mal_score, a.popularity, a.favourites,
                   a.season_year, a.main_studio
            FROM anime a
            LEFT JOIN mal m ON a.id_mal = m.id_mal
            """
        ).df()
    frame = connection.execute(
        """
        SELECT canonical_id, title_romaji, title_english, average_score,
               popularity, favourites, season_year, main_studio
        FROM anime
        """
    ).df()
    frame["mal_score"] = pd.NA
    return frame


def build_hidden_gems(
    connection: duckdb.DuckDBPyConnection,
    *,
    min_quality: float = 70.0,
    min_popularity: int = 5_000,
    limit: int | None = None,
) -> pd.DataFrame:
    """Rank hidden gems by ``quality_pct - popularity_pct``.

    ``min_quality`` keeps only genuinely well-scored titles (so the ranking cannot
    be gamed by merely-obscure mediocrity); ``min_popularity`` drops fluke scores
    on titles almost nobody has rated.
    """
    frame = _load(connection)

    # Blend the two communities onto a common 0-100 scale, using whatever is present.
    mal_on_100 = pd.to_numeric(frame["mal_score"], errors="coerce") * 10
    frame["quality"] = pd.concat(
        [frame["average_score"], mal_on_100], axis=1
    ).mean(axis=1, skipna=True)

    eligible = frame[
        (frame["quality"] >= min_quality) & (frame["popularity"] >= min_popularity)
    ].copy()

    eligible["quality_pct"] = eligible["quality"].rank(pct=True)
    eligible["popularity_pct"] = eligible["popularity"].rank(pct=True)
    eligible["gem_score"] = eligible["quality_pct"] - eligible["popularity_pct"]

    ranked = eligible.sort_values("gem_score", ascending=False).reset_index(drop=True)
    ranked = ranked.reindex(columns=GEM_COLUMNS)
    return ranked.head(limit) if limit else ranked

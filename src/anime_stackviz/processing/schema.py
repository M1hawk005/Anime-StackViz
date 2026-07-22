"""Canonical warehouse schema.

The warehouse is deliberately small: three tables that any source normalizes into,
so adding a source never widens the query surface downstream.
"""

from __future__ import annotations

#: One row per title.
ANIME_COLUMNS = [
    "canonical_id",     # stable cross-source id, e.g. "anilist:1"
    "source",           # originating source name
    "source_id",        # id within that source
    "id_mal",           # MyAnimeList id when known (cross-source join key)
    "title_romaji",
    "title_english",
    "format",           # TV, MOVIE, OVA, ...
    "status",           # FINISHED, RELEASING, ...
    "episodes",
    "duration",
    "season",           # WINTER/SPRING/SUMMER/FALL
    "season_year",
    "start_date",       # ISO date string when known
    "average_score",    # 0-100
    "mean_score",
    "popularity",       # audience size proxy
    "favourites",
    "source_material",  # MANGA, ORIGINAL, LIGHT_NOVEL, ...
    "genres",           # list[str]
    "is_adult",
    "main_studio",
]

#: Directed edges between titles (SEQUEL, PREQUEL, SIDE_STORY, ...).
RELATION_COLUMNS = [
    "from_canonical_id",
    "to_canonical_id",
    "relation_type",
    "to_type",          # ANIME / MANGA of the related node
    "to_format",
]

#: Long-format tags for gem/buzz joins.
TAG_COLUMNS = [
    "canonical_id",
    "tag",
    "rank",
    "is_spoiler",
]

#: MyAnimeList enrichment, keyed by ``id_mal`` (joins to ``anime.id_mal``).
MAL_COLUMNS = [
    "id_mal",
    "mal_score",       # 0-10 community score
    "mal_scored_by",   # number of scorers
    "mal_members",     # audience size on MAL
    "mal_favorites",
    "mal_rank",        # MAL's own quality rank
]


def canonical_id(source: str, source_id: object) -> str:
    """Build a stable cross-source identifier."""
    return f"{source}:{source_id}"

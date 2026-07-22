"""Processing plane: normalize raw source data into a canonical warehouse."""

from __future__ import annotations

from .buzz import build_buzz
from .normalize import normalize_anilist_pages, normalize_jikan_pages
from .schema import (
    ANIME_COLUMNS,
    MAL_COLUMNS,
    RELATION_COLUMNS,
    TAG_COLUMNS,
    canonical_id,
)
from .warehouse import build_warehouse, connect, write_tables

__all__ = [
    "ANIME_COLUMNS",
    "MAL_COLUMNS",
    "RELATION_COLUMNS",
    "TAG_COLUMNS",
    "build_buzz",
    "build_warehouse",
    "canonical_id",
    "connect",
    "normalize_anilist_pages",
    "normalize_jikan_pages",
    "write_tables",
]

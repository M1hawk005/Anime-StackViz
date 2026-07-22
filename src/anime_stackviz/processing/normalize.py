"""Normalize raw AniList pages into the canonical warehouse tables."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .schema import (
    ANIME_COLUMNS,
    MAL_COLUMNS,
    RELATION_COLUMNS,
    TAG_COLUMNS,
    canonical_id,
)

SOURCE = "anilist"


def _iso_date(node: dict | None) -> str | None:
    if not node:
        return None
    year, month, day = node.get("year"), node.get("month"), node.get("day")
    if not year:
        return None
    return f"{year:04d}-{(month or 1):02d}-{(day or 1):02d}"


def _main_studio(media: dict) -> str | None:
    nodes = (media.get("studios") or {}).get("nodes") or []
    return nodes[0]["name"] if nodes else None


def _anime_row(media: dict) -> dict:
    title = media.get("title") or {}
    return {
        "canonical_id": canonical_id(SOURCE, media["id"]),
        "source": SOURCE,
        "source_id": media["id"],
        "id_mal": media.get("idMal"),
        "title_romaji": title.get("romaji"),
        "title_english": title.get("english"),
        "format": media.get("format"),
        "status": media.get("status"),
        "episodes": media.get("episodes"),
        "duration": media.get("duration"),
        "season": media.get("season"),
        "season_year": media.get("seasonYear"),
        "start_date": _iso_date(media.get("startDate")),
        "average_score": media.get("averageScore"),
        "mean_score": media.get("meanScore"),
        "popularity": media.get("popularity"),
        "favourites": media.get("favourites"),
        "source_material": media.get("source"),
        "genres": media.get("genres") or [],
        "is_adult": media.get("isAdult"),
        "main_studio": _main_studio(media),
    }


def _relation_rows(media: dict) -> list[dict]:
    edges = (media.get("relations") or {}).get("edges") or []
    rows = []
    for edge in edges:
        node = edge.get("node") or {}
        if node.get("id") is None:
            continue
        rows.append(
            {
                "from_canonical_id": canonical_id(SOURCE, media["id"]),
                "to_canonical_id": canonical_id(SOURCE, node["id"]),
                "relation_type": edge.get("relationType"),
                "to_type": node.get("type"),
                "to_format": node.get("format"),
            }
        )
    return rows


def _tag_rows(media: dict) -> list[dict]:
    tags = media.get("tags") or []
    cid = canonical_id(SOURCE, media["id"])
    return [
        {
            "canonical_id": cid,
            "tag": tag.get("name"),
            "rank": tag.get("rank"),
            "is_spoiler": tag.get("isMediaSpoiler"),
        }
        for tag in tags
        if tag.get("name")
    ]


def _media_from_pages(pages: Iterable[dict]) -> Iterable[dict]:
    for page in pages:
        yield from page.get("media", [])


def normalize_anilist_pages(pages: Iterable[dict]) -> dict[str, pd.DataFrame]:
    """Turn raw AniList ``Page`` payloads into canonical tables.

    De-duplicates titles by ``canonical_id`` (AniList paginates by id, but a
    resumed run may re-emit a boundary page), so the step is idempotent.
    """
    anime_rows: list[dict] = []
    relation_rows: list[dict] = []
    tag_rows: list[dict] = []

    for media in _media_from_pages(pages):
        if media.get("id") is None:
            continue
        anime_rows.append(_anime_row(media))
        relation_rows.extend(_relation_rows(media))
        tag_rows.extend(_tag_rows(media))

    anime = pd.DataFrame(anime_rows, columns=ANIME_COLUMNS)
    anime = anime.drop_duplicates(subset="canonical_id", keep="last").reset_index(drop=True)
    relations = pd.DataFrame(relation_rows, columns=RELATION_COLUMNS)
    relations = relations.drop_duplicates().reset_index(drop=True)
    tags = pd.DataFrame(tag_rows, columns=TAG_COLUMNS)
    tags = tags.drop_duplicates(subset=["canonical_id", "tag"]).reset_index(drop=True)

    return {"anime": anime, "relations": relations, "tags": tags}


def _mal_row(entry: dict) -> dict:
    return {
        "id_mal": entry.get("mal_id"),
        "mal_score": entry.get("score"),
        "mal_scored_by": entry.get("scored_by"),
        "mal_members": entry.get("members"),
        "mal_favorites": entry.get("favorites"),
        "mal_rank": entry.get("rank"),
    }


def _entries_from_jikan(pages: Iterable[dict]) -> Iterable[dict]:
    for page in pages:
        yield from page.get("data", [])


def normalize_jikan_pages(pages: Iterable[dict]) -> pd.DataFrame:
    """Turn raw Jikan anime pages into a MAL enrichment table keyed by ``id_mal``."""
    rows = [_mal_row(entry) for entry in _entries_from_jikan(pages) if entry.get("mal_id")]
    frame = pd.DataFrame(rows, columns=MAL_COLUMNS)
    return frame.drop_duplicates(subset="id_mal", keep="last").reset_index(drop=True)

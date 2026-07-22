"""Materialize canonical tables as Parquet and expose them through DuckDB.

Tables are written as Parquet (columnar, portable, partition-friendly) and queried
through DuckDB views. Keeping the query layer as SQL-over-Parquet is the seam that
lets the same processing move to a cloud warehouse without rewriting callers.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import duckdb
import pandas as pd

from ..config import Settings
from ..data import load_posts
from ..storage import Storage
from .buzz import build_buzz
from .normalize import normalize_anilist_pages, normalize_jikan_pages

WAREHOUSE_TABLES = ("anime", "relations", "tags", "mal", "buzz")


def _table_path(warehouse_dir: Path, name: str) -> Path:
    return warehouse_dir / name / "data.parquet"


def write_tables(tables: dict[str, pd.DataFrame], warehouse_dir: Path) -> dict[str, Path]:
    """Persist each canonical table as Parquet under ``warehouse_dir``."""
    written: dict[str, Path] = {}
    for name, frame in tables.items():
        path = _table_path(warehouse_dir, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        written[name] = path
    return written


def _read_json_pages(storage: Storage, prefix: str) -> Iterable[dict]:
    for key in storage.list_keys(prefix):
        if key.endswith(".json"):
            yield storage.read_json(key)  # type: ignore[misc]


def build_warehouse(settings: Settings, storage: Storage) -> dict[str, Path]:
    """Read cached raw pages, normalize, and write the Parquet warehouse.

    Each source is optional: whichever raw caches are present are folded in, so the
    warehouse can be built from AniList alone or enriched with MyAnimeList. Fully
    idempotent - it rebuilds canonical tables from the raw cache with no duplicates.
    """
    settings.warehouse_dir.mkdir(parents=True, exist_ok=True)

    tables = normalize_anilist_pages(_read_json_pages(storage, "anilist/media"))

    if any(True for _ in storage.list_keys("jikan/anime")):
        tables["mal"] = normalize_jikan_pages(_read_json_pages(storage, "jikan/anime"))

    posts_csv = settings.data_dir / "processed" / "Posts.csv"
    if posts_csv.exists():
        tables["buzz"] = build_buzz(load_posts(settings.data_dir))

    return write_tables(tables, settings.warehouse_dir)


def connect(settings: Settings, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection with a view over each warehouse table.

    Views point at the Parquet files, so the warehouse stays queryable without
    loading everything into the database file. ``read_only`` mirrors how serving
    replicas open the artifact.
    """
    connection = duckdb.connect(":memory:" if read_only else str(settings.duckdb_path))
    for name in WAREHOUSE_TABLES:
        path = _table_path(settings.warehouse_dir, name)
        if path.exists():
            # DuckDB cannot bind parameters inside CREATE VIEW; the path is
            # internal (never user input), so inline it with quotes escaped.
            literal = str(path).replace("'", "''")
            connection.execute(
                f"CREATE OR REPLACE VIEW {name} AS "
                f"SELECT * FROM read_parquet('{literal}')"
            )
    return connection

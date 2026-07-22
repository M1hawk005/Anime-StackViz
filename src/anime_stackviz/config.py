"""Runtime configuration.

Settings are resolved from environment variables with portable defaults, so the
same code runs unchanged on a laptop, in CI, or in a container. Paths are built
with :mod:`pathlib` and never hard-coded to an operating system.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


ENV_PREFIX = "ANIME_STACKVIZ_"


def _env(name: str, default: str) -> str:
    return os.environ.get(f"{ENV_PREFIX}{name}", default)


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(f"{ENV_PREFIX}{name}")
    return Path(raw).expanduser() if raw else default


@dataclass(frozen=True)
class Settings:
    """Resolved paths and knobs for a single run.

    Attributes are derived once from ``data_dir`` so that overriding a single
    environment variable relocates the whole tree (useful for tests and for
    pointing the warehouse at a mounted volume in a container).
    """

    data_dir: Path = field(default_factory=lambda: _env_path("DATA_DIR", Path("data")))
    report_dir: Path = field(default_factory=lambda: _env_path("REPORT_DIR", Path("reports")))
    user_agent: str = field(
        default_factory=lambda: _env(
            "USER_AGENT",
            "anime-stackviz/2.0 (+https://github.com/M1hawk005/Anime-StackViz)",
        )
    )
    request_timeout: float = field(
        default_factory=lambda: float(_env("REQUEST_TIMEOUT", "30"))
    )

    @property
    def raw_dir(self) -> Path:
        """Cache of raw source responses (git-ignored)."""
        return self.data_dir / "raw"

    @property
    def warehouse_dir(self) -> Path:
        """Partitioned Parquet tables materialized from raw data."""
        return self.data_dir / "warehouse"

    @property
    def duckdb_path(self) -> Path:
        """Single-file DuckDB database that views the warehouse."""
        return self.data_dir / "warehouse" / "anime.duckdb"

    @property
    def serving_dir(self) -> Path:
        """Compact, read-only artifact the online API serves (baked into its image)."""
        return self.data_dir / "serving"

    def source_raw_dir(self, source: str) -> Path:
        return self.raw_dir / source

    def ensure_dirs(self) -> None:
        for path in (self.raw_dir, self.warehouse_dir, self.report_dir):
            path.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    """Return settings resolved from the current environment."""
    return Settings()

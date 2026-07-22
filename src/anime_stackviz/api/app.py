"""Stateless read-only API over the serving artifact.

The artifact is loaded into memory once at startup; every request is an in-memory
read with no shared writable state. That is what makes the service horizontally
scalable - run N identical replicas behind a load balancer, each with its own copy.
Product endpoints send cache headers so a CDN or reverse proxy can absorb load.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import Settings, load_settings

CACHE_HEADER = {"Cache-Control": "public, max-age=3600"}


def _read(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def _records(frame: pd.DataFrame) -> list[dict]:
    # to_json renders NaN as null, keeping the payload valid JSON.
    return json.loads(frame.to_json(orient="records"))


class Artifact:
    """In-memory snapshot of the precomputed products."""

    def __init__(self, settings: Settings) -> None:
        directory = settings.serving_dir
        self.sequels = _read(directory / "sequel_predictions.parquet")
        self.gems = _read(directory / "hidden_gems.parquet")
        self.buzz = _read(directory / "buzz_top.parquet")
        manifest = directory / "manifest.json"
        self.manifest = json.loads(manifest.read_text()) if manifest.exists() else {}


def _cached(frame: pd.DataFrame) -> JSONResponse:
    return JSONResponse(content=_records(frame), headers=CACHE_HEADER)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    artifact = Artifact(settings)

    app = FastAPI(title="Anime StackViz API", version="2.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # the SPA is served from a different origin/CDN
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "products": artifact.manifest.get("rows", {})}

    @app.get("/sequels")
    def sequels(
        limit: int = Query(50, ge=1, le=500),
        min_probability: float = Query(0.0, ge=0.0, le=1.0),
    ) -> JSONResponse:
        """Titles most likely to receive a sequel, highest probability first."""
        frame = artifact.sequels
        if not frame.empty:
            frame = frame[frame["sequel_probability"] >= min_probability].head(limit)
        return _cached(frame)

    @app.get("/gems")
    def gems(limit: int = Query(50, ge=1, le=500)) -> JSONResponse:
        """Highest-rated titles relative to their audience size."""
        return _cached(artifact.gems.head(limit))

    @app.get("/buzz")
    def buzz(limit: int = Query(50, ge=1, le=300)) -> JSONResponse:
        """Franchises ranked by total community discussion volume."""
        return _cached(artifact.buzz.head(limit))

    return app


app = create_app()

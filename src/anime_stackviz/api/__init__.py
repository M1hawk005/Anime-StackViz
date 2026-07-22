"""Online serving plane: a stateless FastAPI app over the read-only artifact."""

from __future__ import annotations

from .app import create_app

__all__ = ["create_app"]

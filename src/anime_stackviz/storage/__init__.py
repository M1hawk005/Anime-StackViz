"""Storage abstraction for the raw cache and the Parquet warehouse."""

from __future__ import annotations

from .base import Storage
from .local import LocalStorage

__all__ = ["Storage", "LocalStorage"]

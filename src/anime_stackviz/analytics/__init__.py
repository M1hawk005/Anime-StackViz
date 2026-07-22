"""Analytic products derived from the warehouse (non-trained rankings/series)."""

from __future__ import annotations

from .buzz_lifecycle import franchise_series, lifecycle_metrics, top_franchises
from .gems import build_hidden_gems

__all__ = [
    "build_hidden_gems",
    "franchise_series",
    "lifecycle_metrics",
    "top_franchises",
]

"""Multi-source ingestion engine.

Each connector implements :class:`Source`; the base class supplies rate limiting,
retry with backoff, response caching, and provenance manifests so a re-run resumes
instead of re-downloading.
"""

from __future__ import annotations

from .base import HttpClient, PageResult, RateLimiter, Source

__all__ = ["HttpClient", "PageResult", "RateLimiter", "Source"]

"""Jikan (MyAnimeList) connector.

Jikan is the unofficial MyAnimeList REST API. It supplies an independent second
opinion on quality and audience size (MAL score, members, favorites) that joins to
the AniList spine on ``id_mal`` - the basis for the hidden-gems score-vs-audience
gap. No authentication is required.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..storage import Storage
from .base import HttpClient, PageResult, RateLimiter, Source

BASE_URL = "https://api.jikan.moe/v4/anime"


class JikanSource(Source):
    """Paginate the MyAnimeList anime catalogue."""

    name = "jikan"

    def __init__(
        self,
        client: HttpClient,
        *,
        limit: int = 25,
        max_pages: int | None = None,
    ) -> None:
        self.client = client
        self.limit = limit
        self.max_pages = max_pages

    @classmethod
    def from_settings(cls, settings, **kwargs) -> "JikanSource":
        client = HttpClient(
            user_agent=settings.user_agent,
            timeout=settings.request_timeout,
            # Jikan allows 3 req/s and 60/min; stay well under both.
            rate_limiter=RateLimiter(calls_per_minute=45),
        )
        return cls(client, **kwargs)

    @staticmethod
    def _page_key(page: int) -> str:
        return f"jikan/anime/page-{page:04d}.json"

    def _fetch_page(self, page: int) -> dict:
        response = self.client.get(BASE_URL, params={"page": page, "limit": self.limit})
        return response.json()

    def fetch_pages(self, storage: Storage, *, resume: bool) -> Iterator[PageResult]:
        page = 1
        while self.max_pages is None or page <= self.max_pages:
            key = self._page_key(page)
            if resume and storage.exists(key):
                cached = storage.read_json(key)
            else:
                cached = self._fetch_page(page)
                storage.write_json(key, cached)

            data = cached.get("data", [])
            yield PageResult(key=key, records=len(data))

            if not cached.get("pagination", {}).get("has_next_page"):
                break
            page += 1

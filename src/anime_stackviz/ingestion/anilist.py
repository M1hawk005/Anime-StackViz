"""AniList GraphQL connector.

AniList is the backbone source: it provides scores, popularity, studios, source
type, airing metadata, tags, and - crucially - typed relation edges between titles
that serve as ground-truth labels for sequel prediction. No authentication is
required for public queries.

AniList caps offset pagination at 5,000 results, so a single paged scan cannot reach
the whole catalogue. We instead **shard by season year**: each year holds far fewer
than 5,000 titles, so paging within a year always stays under the cap, and the union
across years covers every seasoned title without bias toward the oldest ids.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

from ..storage import Storage
from .base import HttpClient, PageResult, RateLimiter, Source

ENDPOINT = "https://graphql.anilist.co"

# One page of anime (within a season year) plus the relation edges we label from.
MEDIA_QUERY = """
query ($seasonYear: Int, $page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage currentPage }
    media(type: ANIME, sort: ID, seasonYear: $seasonYear) {
      id
      idMal
      title { romaji english }
      format
      status
      episodes
      duration
      season
      seasonYear
      startDate { year month day }
      endDate { year month day }
      averageScore
      meanScore
      popularity
      favourites
      source
      genres
      isAdult
      tags { name rank isMediaSpoiler }
      studios(isMain: true) { nodes { id name } }
      relations {
        edges { relationType node { id type format } }
      }
    }
  }
}
""".strip()


class AniListSource(Source):
    """Fetch every seasoned anime title (and its relations), sharded by year."""

    name = "anilist"

    def __init__(
        self,
        client: HttpClient,
        *,
        per_page: int = 50,
        start_year: int = 1960,
        end_year: int | None = None,
        max_pages: int | None = None,
    ) -> None:
        self.client = client
        self.per_page = per_page
        self.start_year = start_year
        self.end_year = end_year
        self.max_pages = max_pages  # global cap across all years, for smoke runs

    @classmethod
    def from_settings(cls, settings, **kwargs) -> "AniListSource":
        client = HttpClient(
            user_agent=settings.user_agent,
            timeout=settings.request_timeout,
            # AniList publishes 90 req/min but degrades to 30; stay conservative.
            rate_limiter=RateLimiter(calls_per_minute=30),
        )
        return cls(client, **kwargs)

    @staticmethod
    def _page_key(year: int, page: int) -> str:
        return f"anilist/media/{year}/page-{page:03d}.json"

    def _fetch_page(self, year: int, page: int) -> dict:
        response = self.client.post(
            ENDPOINT,
            json={
                "query": MEDIA_QUERY,
                "variables": {"seasonYear": year, "page": page, "perPage": self.per_page},
            },
        )
        payload = response.json()
        if "errors" in payload:
            raise RuntimeError(f"AniList error for {year} page {page}: {payload['errors']}")
        return payload["data"]["Page"]

    def fetch_pages(self, storage: Storage, *, resume: bool) -> Iterator[PageResult]:
        end_year = self.end_year or datetime.now(timezone.utc).year
        fetched = 0
        for year in range(self.start_year, end_year + 1):
            page = 1
            while True:
                if self.max_pages is not None and fetched >= self.max_pages:
                    return
                key = self._page_key(year, page)
                if resume and storage.exists(key):
                    cached = storage.read_json(key)
                else:
                    cached = self._fetch_page(year, page)
                    storage.write_json(key, cached)
                fetched += 1

                media = cached.get("media", [])
                yield PageResult(key=key, records=len(media))
                if not media or not cached.get("pageInfo", {}).get("hasNextPage"):
                    break
                page += 1

"""Ingestion primitives shared by every source connector."""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from ..storage import Storage


@dataclass(frozen=True)
class PageResult:
    """One unit of fetched data written to storage by a connector."""

    key: str
    records: int


class RateLimiter:
    """Spacing-based limiter: guarantee a minimum interval between calls.

    A token-bucket would allow bursts; deliberate even spacing is friendlier to
    community APIs and keeps us comfortably under published limits.
    """

    def __init__(self, calls_per_minute: float) -> None:
        if calls_per_minute <= 0:
            raise ValueError("calls_per_minute must be positive")
        self._min_interval = 60.0 / calls_per_minute
        self._last: float | None = None

    def wait(self, *, _sleep=time.sleep, _now=time.monotonic) -> None:
        now = _now()
        if self._last is not None:
            elapsed = now - self._last
            if elapsed < self._min_interval:
                _sleep(self._min_interval - elapsed)
        self._last = _now()


class HttpClient:
    """A thin requests wrapper with a user agent, timeout, and retry/backoff.

    Retries on connection errors, HTTP 429, and 5xx responses using exponential
    backoff, and honours a ``Retry-After`` header when the server supplies one.
    """

    RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = 30.0,
        max_retries: int = 5,
        backoff_base: float = 1.5,
        rate_limiter: RateLimiter | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.rate_limiter = rate_limiter
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def _sleep_for_retry(self, response: requests.Response | None, attempt: int) -> None:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        if retry_after is not None:
            try:
                time.sleep(float(retry_after))
                return
            except ValueError:
                pass
        time.sleep(self.backoff_base**attempt)

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            if self.rate_limiter is not None:
                self.rate_limiter.wait()
            try:
                response = self.session.request(method, url, **kwargs)
            except requests.RequestException as error:
                last_error = error
                time.sleep(self.backoff_base**attempt)
                continue
            if response.status_code in self.RETRY_STATUS:
                self._sleep_for_retry(response, attempt)
                last_error = requests.HTTPError(f"{response.status_code} for {url}")
                continue
            response.raise_for_status()
            return response
        raise RuntimeError(f"Request to {url} failed after {self.max_retries} attempts") from last_error

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)


class Source(ABC):
    """Base class for a data source.

    Subclasses implement :meth:`fetch_pages`, writing each raw page to ``storage``
    and yielding a :class:`PageResult`. The base assembles an auditable manifest
    (row counts, a content checksum, and timestamps) after the run.
    """

    #: short, filesystem-safe identifier, e.g. ``"anilist"``.
    name: str

    @abstractmethod
    def fetch_pages(self, storage: Storage, *, resume: bool) -> Iterator[PageResult]:
        """Yield raw pages, writing their bodies to ``storage`` as a side effect."""

    def manifest_key(self) -> str:
        return f"{self.name}/manifest.json"

    def ingest(self, storage: Storage, *, resume: bool = True) -> dict[str, object]:
        started = datetime.now(timezone.utc)
        pages: list[PageResult] = list(self.fetch_pages(storage, resume=resume))
        finished = datetime.now(timezone.utc)

        digest = hashlib.sha256()
        for page in sorted(pages, key=lambda item: item.key):
            digest.update(storage.read_bytes(page.key))

        manifest = {
            "source": self.name,
            "started_at_utc": started.isoformat(),
            "finished_at_utc": finished.isoformat(),
            "pages": len(pages),
            "records": sum(page.records for page in pages),
            "sha256": digest.hexdigest(),
            "keys": [page.key for page in sorted(pages, key=lambda item: item.key)],
        }
        storage.write_json(self.manifest_key(), manifest)
        return manifest

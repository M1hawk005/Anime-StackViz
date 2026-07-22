import json

import responses

from anime_stackviz.ingestion.anilist import ENDPOINT, AniListSource
from anime_stackviz.ingestion.base import HttpClient, PageResult, RateLimiter, Source
from anime_stackviz.storage import LocalStorage


class _FakeSource(Source):
    """A source that emits two in-memory pages, recording fetch calls."""

    name = "fake"

    def __init__(self, pages):
        self.pages = pages
        self.fetched = []

    def fetch_pages(self, storage, *, resume):
        for index, records in enumerate(self.pages):
            key = f"fake/page-{index:04d}.json"
            if resume and storage.exists(key):
                cached = storage.read_json(key)
            else:
                self.fetched.append(index)
                cached = {"records": [{"i": n} for n in range(records)]}
                storage.write_json(key, cached)
            yield PageResult(key=key, records=len(cached["records"]))


def test_local_storage_roundtrip_and_listing(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.write_json("a/one.json", {"x": 1})
    storage.write_text("a/two.txt", "hello")

    assert storage.exists("a/one.json")
    assert storage.read_json("a/one.json") == {"x": 1}
    assert storage.read_text("a/two.txt") == "hello"
    assert list(storage.list_keys("a")) == ["a/one.json", "a/two.txt"]


def test_ingest_writes_manifest_with_provenance(tmp_path):
    storage = LocalStorage(tmp_path)
    source = _FakeSource(pages=[3, 2])

    manifest = source.ingest(storage, resume=False)

    assert manifest["source"] == "fake"
    assert manifest["pages"] == 2
    assert manifest["records"] == 5
    assert len(manifest["sha256"]) == 64
    stored = json.loads(storage.read_text("fake/manifest.json"))
    assert stored == manifest


def test_resume_skips_already_cached_pages(tmp_path):
    storage = LocalStorage(tmp_path)
    _FakeSource(pages=[3, 2]).ingest(storage, resume=False)

    resumed = _FakeSource(pages=[3, 2])
    resumed.ingest(storage, resume=True)

    assert resumed.fetched == []  # every page served from cache


@responses.activate
def test_anilist_shards_by_year_and_paginates(tmp_path):
    # One full page then a partial page for 2020; a single partial page for 2021.
    pages = {
        (2020, 1): ([{"id": 1}, {"id": 2}], True),
        (2020, 2): ([{"id": 3}], False),
        (2021, 1): ([{"id": 4}], False),
    }

    def callback(request):
        variables = json.loads(request.body)["variables"]
        media, has_next = pages.get((variables["seasonYear"], variables["page"]), ([], False))
        body = {"data": {"Page": {"pageInfo": {"hasNextPage": has_next}, "media": media}}}
        return (200, {}, json.dumps(body))

    responses.add_callback(responses.POST, ENDPOINT, callback=callback, content_type="application/json")

    source = AniListSource(
        HttpClient(user_agent="test"), per_page=2, start_year=2020, end_year=2021
    )
    manifest = source.ingest(LocalStorage(tmp_path), resume=False)

    assert manifest["pages"] == 3
    assert manifest["records"] == 4
    assert any("/2020/page-002" in key for key in manifest["keys"])
    assert any("/2021/page-001" in key for key in manifest["keys"])


@responses.activate
def test_anilist_max_pages_caps_global_fetch(tmp_path):
    def callback(request):
        page = json.loads(request.body)["variables"]["page"]
        body = {"data": {"Page": {"pageInfo": {"hasNextPage": True}, "media": [{"id": page}]}}}
        return (200, {}, json.dumps(body))

    responses.add_callback(responses.POST, ENDPOINT, callback=callback, content_type="application/json")

    source = AniListSource(
        HttpClient(user_agent="test"), per_page=1, start_year=2000, end_year=2005, max_pages=2
    )
    manifest = source.ingest(LocalStorage(tmp_path), resume=False)
    assert manifest["pages"] == 2  # stops at the global cap despite more years/pages


def test_rate_limiter_spaces_calls():
    slept = []
    limiter = RateLimiter(calls_per_minute=60)  # 1s spacing
    clock = iter([0.0, 0.0, 0.2, 0.2])
    limiter.wait(_sleep=slept.append, _now=lambda: next(clock))
    limiter.wait(_sleep=slept.append, _now=lambda: next(clock))

    assert slept == [0.8]  # second call waited the remaining 0.8s

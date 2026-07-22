from fastapi.testclient import TestClient

from anime_stackviz.api import create_app
from anime_stackviz.config import Settings
from anime_stackviz.processing import normalize_anilist_pages, write_tables
from anime_stackviz.processing.serving import build_serving_artifact


def _media(mal_id, year, *, got_sequel):
    relations = (
        [{"relationType": "SEQUEL", "node": {"id": mal_id + 500, "type": "ANIME", "format": "TV"}}]
        if got_sequel
        else []
    )
    return {
        "id": mal_id, "idMal": mal_id, "title": {"romaji": f"Title {mal_id}", "english": None},
        "format": "TV", "status": "FINISHED", "episodes": 12, "duration": 24,
        "season": "SPRING", "seasonYear": year, "startDate": {"year": year, "month": 4, "day": 1},
        "averageScore": 80, "meanScore": 80, "popularity": 12_000, "favourites": 500,
        "source": "MANGA", "genres": ["Action"], "isAdult": False, "tags": [],
        "studios": {"nodes": [{"id": 1, "name": "Studio X"}]},
        "relations": {"edges": relations},
    }


def _client(tmp_path):
    media = [_media(i, 2010 + i, got_sequel=(i % 2 == 0)) for i in range(6)]
    tables = normalize_anilist_pages([{"pageInfo": {"hasNextPage": False}, "media": media}])
    settings = Settings(data_dir=tmp_path)
    settings.warehouse_dir.mkdir(parents=True, exist_ok=True)
    write_tables(tables, settings.warehouse_dir)
    build_serving_artifact(settings)
    return TestClient(create_app(settings))


def test_health_reports_product_counts(tmp_path):
    response = _client(tmp_path).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["products"]["sequel_predictions"] == 6


def test_sequels_endpoint_sorts_and_filters(tmp_path):
    client = _client(tmp_path)
    response = client.get("/sequels", params={"limit": 3})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=3600"
    rows = response.json()
    assert len(rows) == 3
    probs = [r["sequel_probability"] for r in rows]
    assert probs == sorted(probs, reverse=True)  # highest probability first
    assert all(0.0 <= p <= 1.0 for p in probs)


def test_gems_and_buzz_endpoints(tmp_path):
    client = _client(tmp_path)
    assert client.get("/gems", params={"limit": 5}).status_code == 200
    buzz = client.get("/buzz")  # no Stack Exchange data -> empty list, still valid
    assert buzz.status_code == 200
    assert buzz.json() == []

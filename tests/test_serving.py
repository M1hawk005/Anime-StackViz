import pandas as pd

from anime_stackviz.config import Settings
from anime_stackviz.processing import normalize_anilist_pages, write_tables
from anime_stackviz.processing.serving import build_serving_artifact


def _media(mal_id, year, *, got_sequel):
    relations = []
    if got_sequel:
        relations = [{"relationType": "SEQUEL", "node": {"id": mal_id + 500, "type": "ANIME", "format": "TV"}}]
    return {
        "id": mal_id, "idMal": mal_id, "title": {"romaji": f"Title {mal_id}", "english": None},
        "format": "TV", "status": "FINISHED", "episodes": 12, "duration": 24,
        "season": "SPRING", "seasonYear": year, "startDate": {"year": year, "month": 4, "day": 1},
        "averageScore": 75, "meanScore": 75, "popularity": 10_000, "favourites": 500,
        "source": "MANGA", "genres": ["Action"], "isAdult": False, "tags": [],
        "studios": {"nodes": [{"id": 1, "name": "Studio X"}]},
        "relations": {"edges": relations},
    }


def test_build_serving_artifact_writes_products_and_manifest(tmp_path):
    media = [_media(i, 2010 + i, got_sequel=(i % 2 == 0)) for i in range(6)]
    tables = normalize_anilist_pages([{"pageInfo": {"hasNextPage": False}, "media": media}])

    settings = Settings(data_dir=tmp_path)
    settings.warehouse_dir.mkdir(parents=True, exist_ok=True)
    write_tables(tables, settings.warehouse_dir)

    manifest = build_serving_artifact(settings)

    assert manifest["rows"]["sequel_predictions"] == 6
    assert manifest["rows"]["hidden_gems"] == 6
    assert manifest["rows"]["buzz_top"] == 0  # no Stack Exchange data present

    preds = pd.read_parquet(settings.serving_dir / "sequel_predictions.parquet")
    assert "sequel_probability" in preds.columns
    assert preds["sequel_probability"].between(0, 1).all()
    assert (settings.serving_dir / "manifest.json").exists()

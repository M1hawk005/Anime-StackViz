import pandas as pd

from anime_stackviz.analytics import (
    build_hidden_gems,
    franchise_series,
    lifecycle_metrics,
    top_franchises,
)
from anime_stackviz.config import Settings
from anime_stackviz.processing import connect, write_tables


def _warehouse(tmp_path, tables):
    settings = Settings(data_dir=tmp_path)
    settings.warehouse_dir.mkdir(parents=True, exist_ok=True)
    write_tables(tables, settings.warehouse_dir)
    return connect(settings, read_only=True)


def test_hidden_gems_ranks_quality_over_reach_and_filters(tmp_path):
    anime = pd.DataFrame([
        {"canonical_id": "anilist:1", "title_romaji": "Gem", "title_english": None,
         "average_score": 82, "popularity": 8_000, "favourites": 400, "season_year": 2016,
         "main_studio": "S1", "id_mal": 1},
        {"canonical_id": "anilist:2", "title_romaji": "Blockbuster", "title_english": None,
         "average_score": 85, "popularity": 900_000, "favourites": 50_000, "season_year": 2016,
         "main_studio": "S2", "id_mal": 2},
        {"canonical_id": "anilist:3", "title_romaji": "Mediocre", "title_english": None,
         "average_score": 55, "popularity": 7_000, "favourites": 100, "season_year": 2016,
         "main_studio": "S3", "id_mal": 3},
        {"canonical_id": "anilist:4", "title_romaji": "Fluke", "title_english": None,
         "average_score": 95, "popularity": 200, "favourites": 10, "season_year": 2016,
         "main_studio": "S4", "id_mal": 4},
    ])
    mal = pd.DataFrame([{"id_mal": 1, "mal_score": 8.4, "mal_scored_by": 1000,
                         "mal_members": 9000, "mal_favorites": 400, "mal_rank": 500}])

    connection = _warehouse(tmp_path, {"anime": anime, "mal": mal})
    gems = build_hidden_gems(connection, min_quality=70, min_popularity=5_000)
    connection.close()

    titles = gems["title_romaji"].tolist()
    assert titles == ["Gem", "Blockbuster"]      # Mediocre (low score) and Fluke (tiny audience) filtered
    assert gems.iloc[0]["title_romaji"] == "Gem"  # high quality, low reach ranks first
    assert 79 <= gems.iloc[0]["quality"] <= 85    # blended AniList+MAL


def test_buzz_top_franchises_and_series(tmp_path):
    buzz = pd.DataFrame([
        {"tag": "naruto", "period": "2013-01", "question_count": 5},
        {"tag": "naruto", "period": "2013-02", "question_count": 9},
        {"tag": "naruto", "period": "2013-03", "question_count": 3},
        {"tag": "bleach", "period": "2013-01", "question_count": 2},
    ])
    connection = _warehouse(tmp_path, {"buzz": buzz})
    top = top_franchises(connection, limit=10)
    series = franchise_series(connection, "naruto")
    connection.close()

    assert top.iloc[0]["tag"] == "naruto"
    assert top.iloc[0]["total_questions"] == 17
    assert top.iloc[0]["peak_period"] == "2013-02"
    assert series["question_count"].tolist() == [5, 9, 3]


def test_lifecycle_metrics_shape():
    series = pd.DataFrame({
        "period": ["2013-01", "2013-02", "2013-03", "2013-04"],
        "question_count": [2, 10, 4, 2],
    })
    metrics = lifecycle_metrics(series)

    assert metrics["total_questions"] == 18
    assert metrics["peak_period"] == "2013-02"
    assert metrics["peak_count"] == 10
    assert metrics["months_to_peak"] == 1
    assert metrics["decay_ratio"] == round(3 / 10, 3)  # mean(4,2)=3 over peak 10


def test_lifecycle_metrics_empty():
    metrics = lifecycle_metrics(pd.DataFrame({"period": [], "question_count": []}))
    assert metrics["total_questions"] == 0
    assert metrics["peak_period"] is None

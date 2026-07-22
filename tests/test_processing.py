import pandas as pd

from anime_stackviz.config import Settings
from anime_stackviz.processing import (
    build_buzz,
    build_warehouse,
    canonical_id,
    connect,
    normalize_anilist_pages,
)
from anime_stackviz.storage import LocalStorage


def _page():
    return {
        "pageInfo": {"currentPage": 1, "hasNextPage": False},
        "media": [
            {
                "id": 1,
                "idMal": 1,
                "title": {"romaji": "Cowboy Bebop", "english": "Cowboy Bebop"},
                "format": "TV",
                "status": "FINISHED",
                "episodes": 26,
                "duration": 24,
                "season": "SPRING",
                "seasonYear": 1998,
                "startDate": {"year": 1998, "month": 4, "day": 3},
                "averageScore": 86,
                "meanScore": 86,
                "popularity": 500000,
                "favourites": 40000,
                "source": "ORIGINAL",
                "genres": ["Action", "Sci-Fi"],
                "isAdult": False,
                "tags": [{"name": "Space", "rank": 90, "isMediaSpoiler": False}],
                "studios": {"nodes": [{"id": 14, "name": "Sunrise"}]},
                "relations": {
                    "edges": [
                        {"relationType": "SIDE_STORY", "node": {"id": 5, "type": "ANIME", "format": "MOVIE"}}
                    ]
                },
            },
            {
                "id": 20,
                "idMal": 20,
                "title": {"romaji": "Naruto", "english": None},
                "format": "TV",
                "status": "FINISHED",
                "episodes": 220,
                "duration": 23,
                "season": "FALL",
                "seasonYear": 2002,
                "startDate": {"year": 2002, "month": 10, "day": 3},
                "averageScore": 79,
                "meanScore": 79,
                "popularity": 700000,
                "favourites": 60000,
                "source": "MANGA",
                "genres": ["Action"],
                "isAdult": False,
                "tags": [],
                "studios": {"nodes": [{"id": 1, "name": "Pierrot"}]},
                "relations": {
                    "edges": [
                        {"relationType": "SEQUEL", "node": {"id": 1735, "type": "ANIME", "format": "TV"}}
                    ]
                },
            },
        ],
    }


def test_normalize_builds_three_canonical_tables():
    tables = normalize_anilist_pages([_page()])

    anime = tables["anime"]
    assert list(anime["canonical_id"]) == ["anilist:1", "anilist:20"]
    naruto = anime.set_index("canonical_id").loc["anilist:20"]
    assert naruto["source_material"] == "MANGA"
    assert naruto["main_studio"] == "Pierrot"
    assert naruto["start_date"] == "2002-10-03"
    assert naruto["genres"] == ["Action"]

    relations = tables["relations"]
    sequel = relations[relations["relation_type"] == "SEQUEL"].iloc[0]
    assert sequel["from_canonical_id"] == canonical_id("anilist", 20)
    assert sequel["to_canonical_id"] == "anilist:1735"

    tags = tables["tags"]
    assert tags.iloc[0]["tag"] == "Space"


def test_normalize_is_idempotent_on_repeated_pages():
    tables = normalize_anilist_pages([_page(), _page()])
    assert len(tables["anime"]) == 2  # de-duplicated by canonical_id
    assert tables["relations"].duplicated().sum() == 0


def _jikan_page():
    return {
        "pagination": {"has_next_page": False, "current_page": 1},
        "data": [
            {"mal_id": 1, "title": "Cowboy Bebop", "score": 8.75, "scored_by": 900000,
             "members": 1600000, "favorites": 80000, "rank": 40},
            {"mal_id": 20, "title": "Naruto", "score": 7.99, "scored_by": 1800000,
             "members": 2600000, "favorites": 90000, "rank": 700},
        ],
    }


def test_build_warehouse_end_to_end_queryable_via_duckdb(tmp_path):
    # Arrange: a raw cache exactly as the AniList connector would leave it.
    storage = LocalStorage(tmp_path / "raw")
    storage.write_json("anilist/media/page-0001.json", _page())
    settings = Settings(data_dir=tmp_path)

    # Act: normalize + materialize Parquet, then query through DuckDB.
    build_warehouse(settings, storage)
    connection = connect(settings, read_only=True)

    anime_count = connection.execute("SELECT count(*) FROM anime").fetchone()[0]
    sequels = connection.execute(
        "SELECT count(*) FROM relations WHERE relation_type = 'SEQUEL'"
    ).fetchone()[0]
    top = connection.execute(
        "SELECT title_romaji FROM anime ORDER BY average_score DESC LIMIT 1"
    ).fetchone()[0]
    connection.close()

    assert anime_count == 2
    assert sequels == 1
    assert top == "Cowboy Bebop"


def test_warehouse_enriches_anilist_with_mal_via_id_mal_join(tmp_path):
    storage = LocalStorage(tmp_path / "raw")
    storage.write_json("anilist/media/page-0001.json", _page())
    storage.write_json("jikan/anime/page-0001.json", _jikan_page())
    settings = Settings(data_dir=tmp_path)

    build_warehouse(settings, storage)
    connection = connect(settings, read_only=True)
    rows = connection.execute(
        """
        SELECT a.title_romaji, a.popularity, m.mal_score
        FROM anime a JOIN mal m ON a.id_mal = m.id_mal
        ORDER BY a.title_romaji
        """
    ).fetchall()
    connection.close()

    assert rows == [("Cowboy Bebop", 500000, 8.75), ("Naruto", 700000, 7.99)]


def test_build_buzz_counts_questions_per_tag_per_month():
    posts = pd.DataFrame(
        [
            {"PostTypeId": 1, "CreationDate": "2013-01-05T00:00:00", "Tags": "|naruto|manga|"},
            {"PostTypeId": 1, "CreationDate": "2013-01-20T00:00:00", "Tags": "|naruto|"},
            {"PostTypeId": 1, "CreationDate": "2013-02-02T00:00:00", "Tags": "|naruto|"},
            {"PostTypeId": 2, "CreationDate": "2013-01-06T00:00:00", "Tags": None},  # answer, ignored
        ]
    )
    buzz = build_buzz(posts)

    naruto = buzz[buzz["tag"] == "naruto"].set_index("period")["question_count"]
    assert naruto.loc["2013-01"] == 2
    assert naruto.loc["2013-02"] == 1
    assert buzz[buzz["tag"] == "manga"]["question_count"].tolist() == [1]

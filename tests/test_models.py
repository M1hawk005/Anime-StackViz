import numpy as np
import pandas as pd

from anime_stackviz.config import Settings
from anime_stackviz.models import build_sequel_dataset, train_and_evaluate
from anime_stackviz.processing import build_warehouse, connect
from anime_stackviz.storage import LocalStorage


def _media(mal_id, *, fmt="TV", status="FINISHED", year=2010, relations=()):
    return {
        "id": mal_id,
        "idMal": mal_id,
        "title": {"romaji": f"Title {mal_id}", "english": None},
        "format": fmt,
        "status": status,
        "episodes": 12,
        "duration": 24,
        "season": "SPRING",
        "seasonYear": year,
        "startDate": {"year": year, "month": 4, "day": 1},
        "averageScore": 75,
        "meanScore": 75,
        "popularity": 10000,
        "favourites": 500,
        "source": "MANGA",
        "genres": ["Action"],
        "isAdult": False,
        "tags": [],
        "studios": {"nodes": [{"id": 1, "name": "Studio X"}]},
        "relations": {"edges": list(relations)},
    }


def _edge(relation_type, node_id):
    return {"relationType": relation_type, "node": {"id": node_id, "type": "ANIME", "format": "TV"}}


def _build(tmp_path, media):
    storage = LocalStorage(tmp_path / "raw")
    storage.write_json("anilist/media/page-0001.json", {"pageInfo": {"hasNextPage": False}, "media": media})
    settings = Settings(data_dir=tmp_path)
    build_warehouse(settings, storage)
    return connect(settings, read_only=True)


def test_sequel_dataset_labels_and_population(tmp_path):
    media = [
        _media(1, year=2010, relations=[_edge("SEQUEL", 99)]),   # season one that got a sequel
        _media(2, year=2011, relations=[]),                      # season one, no sequel
        _media(3, year=2012, relations=[_edge("PREQUEL", 1)]),   # a continuation -> excluded
        _media(4, fmt="MOVIE", relations=[]),                    # not TV -> excluded
    ]
    connection = _build(tmp_path, media)
    dataset = build_sequel_dataset(connection)
    connection.close()

    assert set(dataset["title_romaji"]) == {"Title 1", "Title 2"}
    labels = dataset.set_index("title_romaji")["got_sequel"].to_dict()
    assert labels == {"Title 1": 1, "Title 2": 0}


def test_sequel_dataset_excludes_unfinished_and_undated(tmp_path):
    media = [
        _media(1, status="RELEASING", relations=[_edge("SEQUEL", 99)]),  # still airing -> excluded
        _media(2, year=None),                                            # undated -> excluded
        _media(3, year=2015, relations=[]),                              # valid
    ]
    connection = _build(tmp_path, media)
    dataset = build_sequel_dataset(connection)
    connection.close()

    assert dataset["title_romaji"].tolist() == ["Title 3"]


def _synthetic_sequel_dataset(n=400, seed=0):
    rng = np.random.default_rng(seed)
    score = rng.normal(65, 12, n).clip(20, 95)
    popularity = rng.lognormal(9.5, 1.0, n)
    # Sequels follow reception + reach, with noise: a learnable but imperfect signal.
    logit = 2.4 * (score - 65) / 12 + 1.4 * (np.log(popularity) - 9.5) - 0.5
    prob = 1 / (1 + np.exp(-logit))
    got_sequel = (rng.random(n) < prob).astype(int)
    return pd.DataFrame({
        "canonical_id": [f"anilist:{i}" for i in range(n)],
        "title_romaji": [f"Title {i}" for i in range(n)],
        "season_year": rng.integers(2005, 2023, n),
        "episodes": rng.integers(1, 26, n),
        "duration": rng.choice([12, 24], n),
        "average_score": score,
        "mean_score": score,
        "popularity": popularity,
        "favourites": popularity * rng.uniform(0.02, 0.1, n),
        "source_material": rng.choice(["MANGA", "ORIGINAL", "LIGHT_NOVEL"], n),
        # High-cardinality studios (like real data) make the one-hot matrix sparse,
        # which would break the gradient-boosting model without a dense encoder.
        "main_studio": rng.choice([f"Studio {k}" for k in range(60)], n),
        "genres": [["Action"] for _ in range(n)],
        "got_sequel": got_sequel,
    })


def test_train_and_evaluate_beats_prevalence_and_writes_metrics(tmp_path):
    dataset = _synthetic_sequel_dataset()
    results = train_and_evaluate(dataset, tmp_path)

    assert results["train_rows"] + results["test_rows"] == len(dataset)
    for model in ("reception_only_logreg", "full_logreg", "full_gradient_boosting"):
        assert 0.0 <= results[model]["roc_auc"] <= 1.0
    # A learnable signal: the full models should rank better than the prevalence floor.
    assert results["full_logreg"]["roc_auc"] > 0.6
    assert (tmp_path / "sequel_metrics.json").exists()

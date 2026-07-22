# Anime StackViz

### An anime intelligence platform: multi-source ingestion, a DuckDB warehouse, and three analytic products behind a scalable API.

Anime StackViz ingests anime data from several public sources into a reproducible
DuckDB/Parquet warehouse and turns it into three products — **sequel prediction**,
a **hidden-gems finder**, and **community-buzz lifecycles** — served through a
stateless FastAPI backend and a static React front end.

It began as a university Stack Exchange study (still included, and now repurposed as
the buzz signal) and grew into an end-to-end platform designed to be
**platform-agnostic** and to **scale with both data and users**.

```
OFFLINE (batch)                                              ONLINE (serves users)
AniList ┐                                                    ┌ stateless FastAPI (N replicas)
Jikan   ┼─▶ ingest ─▶ DuckDB/Parquet ─▶ train ─▶ publish ─▶ │  read-only artifact + caching
StackEx ┘   (cache +   warehouse        models   read-only  └ static React SPA on a CDN
             manifest)                            artifact
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design, including the scaling
path (what would change if any single dimension grew, and what is deliberately not
built at this data scale).

## The three products

**1. Will a first season get a sequel?**
A gradient-boosting / logistic benchmark predicts whether a season-one TV anime
spawns a continuation. Labels come from AniList relation edges; the population is
season-one titles only (no prequel). Predictions served to users are **out-of-fold**,
so a title is scored by a model that never trained on it — no in-sample leakage.

**2. Hidden gems.**
Titles ranked by how far their *quality* percentile exceeds their *popularity*
percentile, blending AniList and MyAnimeList scores. On the ingested catalogue this
surfaces titles like *ARIA The Natural*, *Gundam 0080*, and *Honey & Clover II* —
acclaimed but comparatively niche.

**3. Buzz lifecycle.**
The Anime & Manga Stack Exchange dump becomes a discussion time-series: questions per
franchise per month. It shows, for example, Naruto dominating community discussion
(peaking December 2012) and Attack on Titan cresting with its final season.

## Data sources

| Source | Role | Auth |
|---|---|---|
| [AniList](https://anilist.co) (GraphQL) | Backbone: scores, popularity, studios, source, airing, **relation edges → sequel labels** | none |
| [Jikan](https://jikan.moe) (MyAnimeList) | Second opinion: MAL score, members, favorites | none |
| [Stack Exchange](https://archive.org/details/stackexchange) dump | Community buzz signal | none |

Each source implements one `Source` interface (rate limiting, retry/backoff,
response caching, provenance manifest). Adding a fourth source changes nothing
downstream.

## Quickstart

Python 3.11+ and Node 20+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev,api]"
```

Run the batch pipeline (each stage is idempotent and independently runnable):

```bash
anime-stackviz ingest  --source anilist --max-pages 40   # fetch → raw cache + manifest
anime-stackviz ingest  --source jikan   --max-pages 40   # optional MAL enrichment
anime-stackviz process                                    # raw → DuckDB/Parquet warehouse
anime-stackviz train   --product sequel                   # warehouse → metrics
anime-stackviz publish                                    # warehouse → read-only serving artifact
```

Serve it:

```bash
uvicorn anime_stackviz.api.app:app --port 8000            # online API over the artifact
cd web && npm install && npm run dev                      # React SPA (VITE_API_BASE defaults to :8000)
```

## Docker

The serving image bakes the read-only artifact in and runs the stateless API;
scale it by running more replicas behind a load balancer.

```bash
anime-stackviz process && anime-stackviz publish          # produce data/serving/
docker build -t anime-stackviz .
docker run -p 8000:8000 anime-stackviz
```

## Development

```bash
ruff check src tests
pytest
```

The suite (offline, no network or dump required) covers the ingestion engine and
resumable caching, source normalization, the DuckDB warehouse, sequel labels and
the model benchmark, the hidden-gems and buzz analytics, the serving artifact, and
the API endpoints. CI runs the Python suite and the web build on every push.

> On Windows, if the machine's `%TEMP%` is locked down, run
> `pytest --basetemp=<writable-dir>`.

## Results and honesty

On a full-catalogue crawl (14,636 titles across 1963–2026; 3,314 season-one TV
titles, 28% sequel rate; chronological split with the test set from 2021 onward):

| Model | ROC AUC | Avg precision |
|---|---:|---:|
| Prevalence baseline | 0.500 | 0.264 |
| Reception-only logistic regression | 0.709 | 0.525 |
| Full logistic regression | **0.712** | 0.505 |
| Gradient boosting | 0.668 | 0.452 |

- **Sequel prediction is moderately predictive (AUC ≈ 0.71),** but the honest finding
  is that a *reception-only* baseline (score + popularity) is essentially as strong as
  the full model — reach and reception carry the signal, and the heavier gradient
  boosting model actually does worse. This is reported, not hidden.
- Popularity is the dominant positive driver; controlling for it, high *favourites*
  is mildly negative (cult titles that never continue).
- Serving predictions are out-of-fold; the evaluation uses a chronological split so
  the test set is strictly later than training.
- **Limitations:** the AniList crawl shards by season year, so titles without a season
  (some films/OVAs) are outside the modelled population. Deleted posts are absent from
  the Stack Exchange dump (survivorship bias). Buzz tags (franchises) and content tags
  do not align perfectly, so buzz-to-title linkage is approximate. All findings are
  associational, not causal.

## Legacy Stack Exchange study

The platform's origin was a leakage-aware study predicting whether an Anime & Manga
Stack Exchange question is answered within 24 hours (chronological validation, honest
baselines). It is preserved and runnable:

```bash
anime-stackviz prepare --data-dir data   # stream Posts.xml → CSV
anime-stackviz analyse --data-dir data    # cohort + model + figures
```

The original notebook remains in [`notebooks/`](notebooks/) for provenance.

## Repository layout

```text
src/anime_stackviz/
├── config.py            # env-driven, portable settings
├── storage/             # Storage interface (local ↔ object store)
├── ingestion/           # Source engine + AniList / Jikan connectors
├── processing/          # normalize → DuckDB/Parquet warehouse → serving artifact
├── models/              # sequel predictor + shared evaluation
├── analytics/           # hidden gems + buzz lifecycle
├── api/                 # stateless FastAPI serving app
├── data.py / features.py / model.py / report.py / legacy.py   # Stack Exchange study
└── cli.py               # ingest / process / train / publish (+ legacy prepare/analyse)
web/                     # Vite + React + TypeScript SPA
Dockerfile               # serving image
ARCHITECTURE.md          # design + scaling path
```

## Tech stack

Python · pandas · scikit-learn · DuckDB · PyArrow · requests · FastAPI ·
React · TypeScript · Vite · Docker · GitHub Actions

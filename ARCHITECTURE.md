# Architecture

Anime StackViz is an anime intelligence platform: a multi-source ingestion and
processing engine feeding three analytic products from one warehouse.

The system is split into an **offline batch plane** and an **online serving plane**.
Everything a user touches is precomputed by the batch plane and served read-only, so
the serving plane is cheap, cacheable, and horizontally scalable.

```
OFFLINE  (batch - runs on a schedule, never in a user's request path)

  Sources          Ingestion        Processing        Products            Serving artifact
  AniList          fetch +           normalize         sequel predictor    read-only DuckDB
  Jikan (MAL)  ->  cache +       ->  -> canonical  ->  hidden gems     ->  + Parquet:
  StackExchange    manifest          -> DuckDB         buzz lifecycle      predictions,
                                                                           rankings, series
  raw JSON/XML     raw/ (cache)      warehouse/                            |
                                     (Parquet+DuckDB)                      | baked into image
                                                                          v
ONLINE  (serving - scales with users)

  users -> CDN -> [ static React SPA ] -> [ stateless FastAPI replicas (N behind LB) ]
                                          [ read-only artifact + HTTP/Redis caching   ]
```

Because predictions, rankings, and time-series are materialized ahead of time, a
request is a cheap cached read. The serving artifact is baked into each container
image, so identical stateless replicas scale horizontally with no shared database to
become a bottleneck.

## Design goals

- **Platform-agnostic.** Pure-Python, cross-platform paths, config via env/TOML, no
  OS-specific assumptions. Ships as a Docker image that runs identically anywhere.
- **Scalable, right-sized.** DuckDB + partitioned Parquet handles anime-scale data
  (~25k titles plus time-series) comfortably on one machine, while the DAG-of-steps
  structure, partitioned storage, and incremental loads demonstrate data-engineering
  patterns that would carry to a distributed backend without a rewrite.
- **Auditable.** Every ingestion writes a manifest (source, row counts, SHA-256,
  timestamp). Every processing step is idempotent and re-runnable.
- **Leakage-disciplined.** Features for prediction use only information available at
  decision time; this rule is enforced in the feature layer, not left to convention.

## Layers

### 1. Sources & ingestion (`ingestion/`)

Each source implements a `Source` interface: `fetch()` yields raw records, with
rate-limit handling, retries with backoff, and on-disk response caching so a re-run
resumes instead of re-downloading. Output is raw JSON/Parquet under `raw/<source>/`
plus a `manifest.json` recording provenance.

| Source | Role | Auth |
|---|---|---|
| **AniList** (GraphQL) | Backbone: scores, popularity, studios, source type, airing, tags, **relation edges -> sequel labels** | none |
| **Jikan** (MyAnimeList REST) | Second opinion: MAL score, members, favorites (score-vs-popularity gap) | none |
| **Stack Exchange** (data dump) | Community **buzz** signal: question volume per franchise over time | none |

Adding a fourth source means implementing one class - nothing downstream changes.

### 2. Storage abstraction (`storage/`)

A `Storage` interface backs both the raw cache and the warehouse. `LocalStorage`
uses the filesystem today; an object-store implementation (S3/GCS) can drop in
behind the same interface without touching callers. No vendor lock-in.

### 3. Processing (`processing/`)

A directed acyclic graph of idempotent steps normalizes heterogeneous source
records into a small canonical schema and materializes it as partitioned Parquet
loaded into a DuckDB file:

- `anime` - one row per title (canonical id, titles, scores, popularity, studio,
  source type, format, season, episodes, air dates).
- `relations` - directed edges between titles (SEQUEL, PREQUEL, SIDE_STORY, ...).
- `buzz` - time-series of discussion counts per franchise/tag.

DuckDB is the query engine for every product and for the dashboard.

### 4. Products (`features/`, `models/`, `analytics/`)

- **Sequel predictor** - binary classification: will a title get a continuation?
  Ground-truth labels come from AniList relation edges; features use only what is
  known when a season finishes airing. Reuses the chronological-split evaluation
  harness (prevalence / metadata / full-model benchmarks).
- **Hidden gems** - ranks titles by the divergence between critical score and
  audience size to surface under-watched, well-rated works.
- **Buzz lifecycle** - aligns per-franchise discussion time-series to airing and
  release events to characterize how attention rises and decays.

### 5. Serving artifact (`processing/serving.py`)

The batch plane's final step materializes a compact, **read-only** serving artifact
- predictions, gem rankings, and buzz series as Parquet plus a small DuckDB file -
separate from the full warehouse. This is the only data the online plane reads, and
it is versioned and baked into the API image.

### 6. API (`api/`)

A stateless **FastAPI** service answers product queries by reading the serving
artifact (no writes, no per-user session state). Statelessness is the property that
makes it horizontally scalable: run N identical replicas behind a load balancer and
add HTTP/Redis caching for hot endpoints. Because results are precomputed, every
endpoint is a cheap, cacheable read.

### 7. Frontend (`web/`)

A static React single-page app calls the API and renders the three products. Being
static, it deploys to any CDN and scales to users essentially for free.

## Orchestration

The CLI exposes the batch plane as discrete, composable, idempotent stages; the API
is a separate long-running service.

```bash
anime-stackviz ingest   --source anilist   # fetch -> raw/ + manifest
anime-stackviz process                     # raw/ -> warehouse (DuckDB + Parquet)
anime-stackviz train    --product sequel   # warehouse -> model + metrics
anime-stackviz publish                     # warehouse -> read-only serving artifact
uvicorn anime_stackviz.api.app:app         # online: serve the artifact (scale replicas)
```

Each batch stage is independently runnable and idempotent, so a scheduler (cron,
GitHub Actions, Airflow) can drive the same steps without code changes, while the API
scales independently of the batch work.

## Scaling path (and what is deliberately not built yet)

The system is right-sized for anime-scale data (bounded at ~25-30k titles, tens of
MB) and is architected so that **no layer is trapped**: each boundary is an interface,
so a layer can scale out without a rewrite. "No bottlenecks" is achieved not by
over-provisioning, but by keeping the user's hot path read-only and precomputed, and
by leaving clean seams for the day any single dimension actually grows.

| Layer | Today (right-sized) | If that dimension grows | Seam that enables it |
|---|---|---|---|
| Ingestion | Incremental, resumable, rate-limited single process | Parallel workers per source (still capped by upstream API limits) | `Source` interface; per-page cache keys |
| Raw + warehouse storage | Local partitioned Parquet | S3/GCS object store | `Storage` interface (`LocalStorage` -> object-store impl) |
| Analytics / query engine | Embedded DuckDB on one node | Cloud warehouse (BigQuery/Snowflake/MotherDuck) | Processing expressed as SQL over Parquet |
| Processing orchestration | CLI stages run in sequence | Airflow/Dagster DAG, parallel steps | Idempotent, independently runnable stages |
| Serving reads (users) | Stateless FastAPI + read-only artifact baked in | N replicas behind a load balancer + Redis/CDN cache | Statelessness; no shared writable DB |
| Frontend | Static SPA on a CDN | Same - CDNs already scale globally | Build-time static assets, API via HTTP |

**Deliberately not built:** message queues, a streaming layer, a distributed store, or
a container orchestrator. For bounded metadata and a read-only serving path these add
operational cost and complexity with no benefit at this data scale; introducing them
prematurely is an anti-pattern, not a signal of maturity. Each is reachable through
the seams above if the workload ever justifies it.

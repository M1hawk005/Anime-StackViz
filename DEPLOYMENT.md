# Deployment

> Deploys the Anime StackViz platform to a Linux VPS with Docker + Caddy. The steps
> are self-contained and ordered; each ends with a check. No secrets or paid API
> keys are required.

## What you are deploying

Two artifacts, from one repo:

1. **API** - a stateless FastAPI service (`anime_stackviz.api.app:app`) that serves a
   **read-only serving artifact** (`data/serving/*.parquet`) baked into its Docker
   image. Stateless => run N replicas behind the proxy to scale with traffic.
2. **Web** - a static React SPA (`web/dist/`) built to call the API, served by Caddy.

The serving artifact is produced **offline** by the batch pipeline before the image
is built. Runtime never ingests or writes; it only reads precomputed Parquet.

```
batch (once / scheduled):  ingest -> process -> publish -> data/serving/*.parquet
build:                     docker build  (bakes data/serving into the API image)
                           npm run build (produces web/dist, pointed at the API URL)
run:                       docker compose up  (API replicas + Caddy TLS proxy)
```

## Prerequisites on the VPS

- Docker Engine + Compose plugin (`docker --version`, `docker compose version`).
- Python 3.11+ and Node 20+ **to build** (only needed at build time, not runtime).
- Two DNS A/AAAA records pointing at the VPS, e.g. `api.<domain>` and `app.<domain>`.
- Ports 80 and 443 open (Caddy needs them for ACME/HTTPS).

## Step 1 - Get the code

```bash
git clone git@github.com:M1hawk005/Anime-StackViz.git
cd Anime-StackViz
git checkout feat/anime-intelligence-platform   # or main, once merged
```

**Check:** `ls Dockerfile deploy/docker-compose.yml` both exist.

## Step 2 - Build the serving artifact (batch)

Runs the pipeline that the API will serve. Needs outbound HTTPS (AniList/Jikan).

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .

anime-stackviz ingest  --source anilist    # full catalogue, ~10-15 min (resumable)
anime-stackviz ingest  --source jikan       # optional: adds MyAnimeList scores to gems
# Optional buzz product: put the Anime & Manga Stack Exchange Posts.xml in data/raw/
#   then:  anime-stackviz prepare
anime-stackviz process                       # build the DuckDB/Parquet warehouse
anime-stackviz publish                       # write data/serving/*.parquet
```

**Check:** `cat data/serving/manifest.json` shows non-zero `sequel_predictions` and
`hidden_gems` row counts.

> Re-running is idempotent and resumes from the on-disk cache, so scheduling this
> (Step 6) is safe.

## Step 3 - Build the web SPA (pointed at the API domain)

`VITE_API_BASE` is baked in at build time, so set it to the public API URL.

```bash
cd web
npm ci
VITE_API_BASE="https://api.<domain>" npm run build   # outputs web/dist/
cd ..
```

**Check:** `ls web/dist/index.html` exists.

## Step 4 - Deploy (API replicas + Caddy TLS proxy)

```bash
export APP_DOMAIN="app.<domain>"
export API_DOMAIN="api.<domain>"
docker compose -f deploy/docker-compose.yml up -d --build
```

Caddy automatically provisions Let's Encrypt certificates for both domains.

**Check:**
```bash
curl -fsS "https://api.<domain>/health"     # -> {"status":"ok","products":{...}}
curl -fsSI "https://app.<domain>/"           # -> 200, HTML
```

Open `https://app.<domain>` - the three tabs (Sequel odds, Hidden gems, Buzz) should
populate from the API.

## Step 5 - Scale (optional)

The API is stateless, so scale horizontally; Caddy round-robins across replicas:

```bash
docker compose -f deploy/docker-compose.yml up -d --scale api=3
```

No shared database, no sticky sessions - replicas are interchangeable.

## Step 6 - Keep data fresh (optional)

The artifact is a point-in-time snapshot. To refresh weekly, cron the rebuild:

```cron
# 04:00 every Monday: refresh data and redeploy the API image
0 4 * * 1  cd /path/Anime-StackViz && . .venv/bin/activate \
  && anime-stackviz ingest --source anilist && anime-stackviz process \
  && anime-stackviz publish \
  && APP_DOMAIN=app.<domain> API_DOMAIN=api.<domain> \
     docker compose -f deploy/docker-compose.yml up -d --build
```

## Reference

**Runtime env vars** (all optional; API reads the artifact from `ANIME_STACKVIZ_DATA_DIR`):

| Var | Default | Purpose |
|---|---|---|
| `ANIME_STACKVIZ_DATA_DIR` | `data` | Where the serving artifact lives (baked into the image) |
| `ANIME_STACKVIZ_USER_AGENT` | project UA | Sent to AniList/Jikan during ingest |
| `VITE_API_BASE` (build-time) | `http://localhost:8000` | API URL the SPA calls |
| `APP_DOMAIN`, `API_DOMAIN` (compose) | - | Public hostnames for Caddy |

**CORS:** the API currently allows all origins (`allow_origins=["*"]`). To lock it to
the SPA, edit `src/anime_stackviz/api/app.py` and rebuild.

**No secrets required** - AniList, Jikan, and the Stack Exchange dump are all public.

**Rollback:** images are tagged `anime-stackviz:latest`; keep the previous image
(`docker tag anime-stackviz:latest anime-stackviz:prev` before rebuilds) and
`docker compose up -d` against the prior tag to revert. The batch cache and warehouse
are untouched by a rollback.

**Health / observability:** `GET /health` returns `{"status":"ok","products":{...}}`
with per-product row counts - use it for the load balancer and uptime checks.

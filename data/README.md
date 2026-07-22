# Data

The platform draws on three public sources:

- **AniList** (GraphQL) and **Jikan / MyAnimeList** (REST) are fetched automatically into
  `data/raw/<source>/` by `anime-stackviz ingest`. No manual download is needed.
- The **Anime & Manga Stack Exchange** dump powers the community-buzz signal. Download the
  [Stack Exchange Data Dump](https://archive.org/details/stackexchange), place the extracted
  `Posts.xml` in `data/raw/`, and convert it to CSV:

  ```bash
  anime-stackviz prepare --data-dir data
  ```

Raw and processed records are excluded from Git because they are large and contain public
user-generated content. Ingestion records row counts, columns, file sizes, and SHA-256
hashes in a manifest.

## Privacy and attribution

Only aggregate community patterns are surfaced. Display names, profile locations, and
individual user rankings are not used. Stack Exchange contributions are provided under
Creative Commons terms; retain the required source attribution and consult the license for
the dump release you download.

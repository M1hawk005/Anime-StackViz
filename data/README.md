# Data

This project uses the public [Stack Exchange Data Dump](https://archive.org/details/stackexchange)
for the Anime & Manga community.

Place the extracted XML tables in `data/raw/`. Raw and processed records are intentionally excluded
from Git because they are large and contain public user-generated content. The preparation command
streams each XML file to CSV and records row counts, columns, file sizes, and SHA-256 hashes:

```bash
anime-stackviz prepare --data-dir data
```

The current analysis requires `Posts.xml`. Other dump tables are retained for potential extensions,
but are not required by the response-time model.

## Privacy and attribution

The analysis reports aggregate community patterns. Display names, profile locations, and individual
user rankings are deliberately excluded from the portfolio report. Stack Exchange user contributions
are made available under Creative Commons terms; downstream users should retain the required source
attribution and consult the applicable license for the dump release they download.

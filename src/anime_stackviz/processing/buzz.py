"""Build the community-buzz time-series from Stack Exchange questions.

The Anime & Manga Stack Exchange dump is repurposed as a discussion signal: how
many questions each franchise tag attracts per month. The result is the ``buzz``
table, the substrate for the buzz-lifecycle product.
"""

from __future__ import annotations

import pandas as pd

from ..features import parse_tags

BUZZ_COLUMNS = ["tag", "period", "question_count"]

QUESTION_POST_TYPE = 1


def build_buzz(posts: pd.DataFrame) -> pd.DataFrame:
    """Aggregate questions into per-tag, per-month counts.

    Expects the raw Stack Exchange posts frame (``PostTypeId``, ``CreationDate``,
    ``Tags``). Only questions are counted; each is attributed to every tag it
    carries, so a franchise's monthly volume is the sum across its tags.
    """
    required = {"PostTypeId", "CreationDate", "Tags"}
    missing = required.difference(posts.columns)
    if missing:
        raise ValueError(f"Posts data is missing required columns: {sorted(missing)}")

    frame = posts.copy()
    frame["PostTypeId"] = pd.to_numeric(frame["PostTypeId"], errors="coerce")
    questions = frame.loc[frame["PostTypeId"].eq(QUESTION_POST_TYPE)].copy()
    questions["CreationDate"] = pd.to_datetime(
        questions["CreationDate"], errors="coerce", utc=True
    )
    questions = questions.dropna(subset=["CreationDate"])

    questions["period"] = questions["CreationDate"].dt.strftime("%Y-%m")
    questions["tag"] = questions["Tags"].map(parse_tags)
    exploded = questions.explode("tag").dropna(subset=["tag"])

    buzz = (
        exploded.groupby(["tag", "period"], as_index=False)
        .size()
        .rename(columns={"size": "question_count"})
    )
    return buzz[BUZZ_COLUMNS].sort_values(["tag", "period"]).reset_index(drop=True)

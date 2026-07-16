"""Feature engineering for question-response modelling."""

from __future__ import annotations

import html
import re

import numpy as np
import pandas as pd


HTML_TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")
URL = re.compile(r"https?://|www\.", re.IGNORECASE)
CODE_BLOCK = re.compile(r"<code>|<pre>", re.IGNORECASE)


def clean_html(value: object) -> str:
    """Return readable plain text from a Stack Exchange HTML field."""
    if value is None or pd.isna(value):
        return ""
    text = html.unescape(str(value))
    text = HTML_TAG.sub(" ", text)
    return WHITESPACE.sub(" ", text).strip()


def parse_tags(value: object) -> list[str]:
    """Parse either pipe- or angle-bracket-delimited Stack Exchange tags."""
    if value is None or pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    angle_tags = re.findall(r"<([^>]+)>", text)
    if angle_tags:
        return [tag.strip().lower() for tag in angle_tags if tag.strip()]
    return [tag.strip().lower() for tag in text.split("|") if tag.strip()]


def build_question_dataset(posts: pd.DataFrame, observation_hours: int = 24) -> pd.DataFrame:
    """Create a leakage-safe question dataset with a response-within-window target.

    Questions too close to the end of the dump to receive the full observation
    window are excluded. Only question content and creation-time properties become
    model features.
    """
    required = {"Id", "PostTypeId", "CreationDate", "Title", "Body", "Tags"}
    missing = required.difference(posts.columns)
    if missing:
        raise ValueError(f"Posts data is missing required columns: {sorted(missing)}")

    frame = posts.copy()
    frame["CreationDate"] = pd.to_datetime(frame["CreationDate"], errors="coerce", utc=True)
    frame["PostTypeId"] = pd.to_numeric(frame["PostTypeId"], errors="coerce")
    frame["Id"] = pd.to_numeric(frame["Id"], errors="coerce")

    answers = frame.loc[frame["PostTypeId"].eq(2), ["ParentId", "CreationDate"]].copy()
    answers["ParentId"] = pd.to_numeric(answers["ParentId"], errors="coerce")
    first_answers = answers.groupby("ParentId", dropna=True)["CreationDate"].min()

    questions = frame.loc[frame["PostTypeId"].eq(1)].copy()
    questions = questions.dropna(subset=["Id", "CreationDate"])
    dump_end = frame["CreationDate"].max()
    cutoff = dump_end - pd.to_timedelta(observation_hours, unit="h")
    questions = questions.loc[questions["CreationDate"].le(cutoff)].copy()

    questions["first_answer_at"] = questions["Id"].map(first_answers)
    questions["hours_to_first_answer"] = (
        questions["first_answer_at"] - questions["CreationDate"]
    ).dt.total_seconds() / 3600
    questions["answered_within_24h"] = questions["hours_to_first_answer"].between(
        0, observation_hours, inclusive="both"
    ).astype("int8")

    raw_body = questions["Body"].fillna("").astype(str)
    questions["title_text"] = questions["Title"].map(clean_html)
    questions["body_text"] = questions["Body"].map(clean_html)
    questions["combined_text"] = (questions["title_text"] + " " + questions["body_text"]).str.strip()
    questions["tag_list"] = questions["Tags"].map(parse_tags)
    questions["tag_text"] = questions["tag_list"].map(" ".join)

    questions["title_words"] = questions["title_text"].str.split().str.len().fillna(0)
    questions["body_words"] = questions["body_text"].str.split().str.len().fillna(0)
    questions["tag_count"] = questions["tag_list"].str.len()
    questions["question_marks"] = questions["title_text"].str.count(r"\?")
    questions["code_blocks"] = raw_body.map(lambda text: len(CODE_BLOCK.findall(text)))
    questions["links"] = raw_body.map(lambda text: len(URL.findall(text)))

    created = questions["CreationDate"]
    questions["year"] = created.dt.year
    questions["hour_sin"] = np.sin(2 * np.pi * created.dt.hour / 24)
    questions["hour_cos"] = np.cos(2 * np.pi * created.dt.hour / 24)
    questions["weekday_sin"] = np.sin(2 * np.pi * created.dt.dayofweek / 7)
    questions["weekday_cos"] = np.cos(2 * np.pi * created.dt.dayofweek / 7)

    return questions.sort_values("CreationDate").reset_index(drop=True)


NUMERIC_FEATURES = [
    "title_words",
    "body_words",
    "tag_count",
    "question_marks",
    "code_blocks",
    "links",
    "year",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
]

"""Text utilities for Stack Exchange fields, used by the buzz signal."""

from __future__ import annotations

import html
import re

import pandas as pd

HTML_TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")


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

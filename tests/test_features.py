import pandas as pd

from anime_stackviz.features import build_question_dataset, clean_html, parse_tags


def test_parse_tags_supports_dump_formats():
    assert parse_tags("|naruto|anime-production|") == ["naruto", "anime-production"]
    assert parse_tags("<one-piece><manga>") == ["one-piece", "manga"]
    assert parse_tags(None) == []


def test_clean_html_decodes_and_removes_markup():
    assert clean_html("<p>A &amp; B</p><code>print()</code>") == "A & B print()"


def test_question_target_uses_first_answer_and_excludes_partial_window():
    posts = pd.DataFrame([
        {"Id": 1, "PostTypeId": 1, "CreationDate": "2024-01-01T00:00:00", "Title": "Q1", "Body": "<p>Body</p>", "Tags": "|naruto|"},
        {"Id": 2, "PostTypeId": 1, "CreationDate": "2024-01-02T00:00:00", "Title": "Q2", "Body": "Body", "Tags": "|bleach|"},
        {"Id": 3, "PostTypeId": 2, "ParentId": 1, "CreationDate": "2024-01-01T10:00:00", "Title": None, "Body": "Answer", "Tags": None},
        {"Id": 4, "PostTypeId": 2, "ParentId": 2, "CreationDate": "2024-01-03T06:00:00", "Title": None, "Body": "Answer", "Tags": None},
        {"Id": 6, "PostTypeId": 1, "CreationDate": "2024-01-04T12:00:00", "Title": "Partial window", "Body": "Body", "Tags": "|anime|"},
        {"Id": 5, "PostTypeId": 2, "ParentId": 99, "CreationDate": "2024-01-05T00:00:00", "Title": None, "Body": "Answer", "Tags": None},
    ])
    result = build_question_dataset(posts)
    assert result["Id"].tolist() == [1, 2]
    assert result["answered_within_24h"].tolist() == [1, 0]
    assert result["hours_to_first_answer"].tolist() == [10.0, 30.0]

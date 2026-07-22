from anime_stackviz.features import clean_html, parse_tags


def test_parse_tags_supports_dump_formats():
    assert parse_tags("|naruto|anime-production|") == ["naruto", "anime-production"]
    assert parse_tags("<one-piece><manga>") == ["one-piece", "manga"]
    assert parse_tags(None) == []


def test_clean_html_decodes_and_removes_markup():
    assert clean_html("<p>A &amp; B</p><code>print()</code>") == "A & B print()"

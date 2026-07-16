import csv

from anime_stackviz.data import convert_xml_to_csv


def test_xml_conversion_streams_rows_and_records_manifest(tmp_path):
    source = tmp_path / "Posts.xml"
    source.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<posts><row Id="1" Title="First"/><row Id="2" Score="3"/></posts>',
        encoding="utf-8",
    )
    destination = tmp_path / "Posts.csv"

    manifest = convert_xml_to_csv(source, destination)

    with destination.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {"Id": "1", "Score": "", "Title": "First"},
        {"Id": "2", "Score": "3", "Title": ""},
    ]
    assert manifest["rows"] == 2
    assert manifest["columns"] == ["Id", "Score", "Title"]
    assert len(manifest["sha256"]) == 64

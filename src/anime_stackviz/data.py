"""Data loading, audit, and memory-safe XML conversion."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd


POST_COLUMNS = [
    "Id", "PostTypeId", "ParentId", "AcceptedAnswerId", "CreationDate",
    "Score", "ViewCount", "Body", "OwnerUserId", "Title", "Tags",
    "AnswerCount", "CommentCount",
]


def load_posts(data_dir: str | Path) -> pd.DataFrame:
    path = Path(data_dir) / "processed" / "Posts.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist. Run the prepare command after placing Posts.xml in data/raw."
        )
    available = pd.read_csv(path, nrows=0).columns
    usecols = [column for column in POST_COLUMNS if column in available]
    return pd.read_csv(path, usecols=usecols, low_memory=False)


def _xml_columns(xml_path: Path) -> list[str]:
    columns: set[str] = set()
    for _, element in ET.iterparse(xml_path, events=("end",)):
        if element.tag == "row":
            columns.update(element.attrib)
        element.clear()
    return sorted(columns)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def convert_xml_to_csv(xml_path: str | Path, csv_path: str | Path) -> dict[str, object]:
    """Stream a Stack Exchange XML table to CSV without loading it into memory."""
    source, destination = Path(xml_path), Path(csv_path)
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    columns = _xml_columns(source)
    rows = 0
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for _, element in ET.iterparse(source, events=("end",)):
            if element.tag == "row":
                writer.writerow(element.attrib)
                rows += 1
            element.clear()
    return {
        "source": source.name,
        "bytes": source.stat().st_size,
        "sha256": _sha256(source),
        "rows": rows,
        "columns": columns,
    }


def prepare_raw_data(data_dir: str | Path) -> dict[str, object]:
    root = Path(data_dir)
    raw_dir, processed_dir = root / "raw", root / "processed"
    sources = sorted(raw_dir.glob("*.xml"))
    if not sources:
        raise FileNotFoundError(f"No XML files found in {raw_dir}")
    tables = [convert_xml_to_csv(path, processed_dir / f"{path.stem}.csv") for path in sources]
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }
    manifest_path = processed_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

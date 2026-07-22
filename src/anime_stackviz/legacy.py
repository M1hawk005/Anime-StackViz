"""Legacy Stack Exchange responsiveness study.

The platform's first incarnation predicted whether an Anime & Manga Stack Exchange
question is answered within 24 hours. It is preserved here as a self-contained,
runnable study; the Stack Exchange data now also feeds the platform's buzz signal.
"""

from __future__ import annotations

import json
from pathlib import Path

from .data import load_posts, prepare_raw_data
from .features import build_question_dataset
from .model import train_and_evaluate
from .report import create_model_evaluation, create_overview

__all__ = ["prepare_raw_data", "run_analysis"]


def run_analysis(data_dir: Path, report_dir: Path) -> dict[str, object]:
    posts = load_posts(data_dir)
    dataset = build_question_dataset(posts)
    report_dir.mkdir(parents=True, exist_ok=True)
    audit = {
        "questions": len(dataset),
        "start": dataset["CreationDate"].min().isoformat(),
        "end": dataset["CreationDate"].max().isoformat(),
        "answered_ever": int(dataset["first_answer_at"].notna().sum()),
        "answered_within_24h": int(dataset["answered_within_24h"].sum()),
        "response_rate_24h": float(dataset["answered_within_24h"].mean()),
        "median_hours_to_first_answer": float(dataset["hours_to_first_answer"].median()),
        "duplicate_question_ids": int(dataset["Id"].duplicated().sum()),
    }
    (report_dir / "data_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    _, metrics, _, test, probabilities = train_and_evaluate(dataset, report_dir)
    figures = report_dir / "figures"
    create_overview(dataset, figures / "portfolio_overview.png")
    create_model_evaluation(
        test, probabilities, report_dir / "metrics.json", figures / "model_evaluation.png"
    )
    return {"audit": audit, "metrics": metrics}

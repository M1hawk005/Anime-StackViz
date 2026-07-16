"""Command-line interface for the end-to-end project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .data import load_posts, prepare_raw_data
from .features import build_question_dataset
from .model import train_and_evaluate
from .report import create_model_evaluation, create_overview


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
    pipeline, metrics, _, test, probabilities = train_and_evaluate(dataset, report_dir)
    del pipeline
    figures = report_dir / "figures"
    create_overview(dataset, figures / "portfolio_overview.png")
    create_model_evaluation(test, probabilities, report_dir / "metrics.json", figures / "model_evaluation.png")
    return {"audit": audit, "metrics": metrics}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Anime StackViz reproducible pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "analyse", "all"):
        command = subparsers.add_parser(name)
        command.add_argument("--data-dir", type=Path, default=Path("data"))
        command.add_argument("--report-dir", type=Path, default=Path("reports"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command in {"prepare", "all"}:
        prepare_raw_data(args.data_dir)
    if args.command in {"analyse", "all"}:
        results = run_analysis(args.data_dir, args.report_dir)
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

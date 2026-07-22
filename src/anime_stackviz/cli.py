"""Command-line interface for the offline batch pipeline.

Each subcommand is an independently runnable, idempotent stage:

    anime-stackviz ingest  --source anilist   # fetch -> raw cache + manifest
    anime-stackviz process                    # raw -> DuckDB/Parquet warehouse
    anime-stackviz train   --product sequel   # warehouse -> model metrics
    anime-stackviz publish                     # warehouse -> read-only serving artifact

The legacy Stack Exchange study (``prepare`` / ``analyse``) is retained for provenance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings


def _settings(args: argparse.Namespace) -> Settings:
    return Settings(data_dir=args.data_dir, report_dir=args.report_dir)


def _cmd_ingest(args: argparse.Namespace) -> object:
    from .ingestion.anilist import AniListSource
    from .ingestion.jikan import JikanSource
    from .storage import LocalStorage

    settings = _settings(args)
    settings.ensure_dirs()
    sources = {"anilist": AniListSource, "jikan": JikanSource}
    source = sources[args.source].from_settings(settings, max_pages=args.max_pages)
    return source.ingest(LocalStorage(settings.raw_dir), resume=not args.no_resume)


def _cmd_process(args: argparse.Namespace) -> object:
    from .processing import build_warehouse
    from .storage import LocalStorage

    settings = _settings(args)
    written = build_warehouse(settings, LocalStorage(settings.raw_dir))
    return {"tables": sorted(written)}


def _cmd_train(args: argparse.Namespace) -> object:
    from .models import build_sequel_dataset, train_and_evaluate
    from .processing import connect

    settings = _settings(args)
    connection = connect(settings, read_only=True)
    try:
        dataset = build_sequel_dataset(connection)
    finally:
        connection.close()
    return train_and_evaluate(dataset, settings.report_dir)


def _cmd_publish(args: argparse.Namespace) -> object:
    from .processing.serving import build_serving_artifact

    return build_serving_artifact(_settings(args))


def _cmd_prepare(args: argparse.Namespace) -> object:
    from .data import prepare_raw_data

    return prepare_raw_data(args.data_dir)


def _cmd_analyse(args: argparse.Namespace) -> object:
    from .legacy import run_analysis

    return run_analysis(args.data_dir, args.report_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Anime intelligence platform pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--data-dir", type=Path, default=Path("data"))
        sub.add_argument("--report-dir", type=Path, default=Path("reports"))

    ingest = subparsers.add_parser("ingest", help="fetch a source into the raw cache")
    add_common(ingest)
    ingest.add_argument("--source", choices=["anilist", "jikan"], required=True)
    ingest.add_argument("--max-pages", type=int, default=None)
    ingest.add_argument("--no-resume", action="store_true")
    ingest.set_defaults(func=_cmd_ingest)

    process = subparsers.add_parser("process", help="build the warehouse from raw data")
    add_common(process)
    process.set_defaults(func=_cmd_process)

    train = subparsers.add_parser("train", help="train and evaluate a product model")
    add_common(train)
    train.add_argument("--product", choices=["sequel"], default="sequel")
    train.set_defaults(func=_cmd_train)

    publish = subparsers.add_parser("publish", help="materialize the read-only serving artifact")
    add_common(publish)
    publish.set_defaults(func=_cmd_publish)

    prepare = subparsers.add_parser("prepare", help="[legacy] stream Stack Exchange XML to CSV")
    add_common(prepare)
    prepare.set_defaults(func=_cmd_prepare)

    analyse = subparsers.add_parser("analyse", help="[legacy] run the Stack Exchange study")
    add_common(analyse)
    analyse.set_defaults(func=_cmd_analyse)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = args.func(args)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

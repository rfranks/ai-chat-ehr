"""Utility script for anonymizing fixture-backed Firestore documents."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Iterable

from services.anonymizer.firestore.client import (
    FixtureFirestoreDataSource,
    PATIENT_COLLECTION,
)
from services.anonymizer.firestore.fixtures import discover_fixture_paths
from services.anonymizer.presidio_engine import PresidioAnonymizerEngine
from services.anonymizer.reporting import summarize_transformations
from services.anonymizer.service import process_patient
from services.anonymizer.storage.postgres import PostgresStorage


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch a patient document from Firestore fixtures, anonymize it, and "
            "persist the result to Postgres."
        )
    )
    parser.add_argument(
        "collection",
        nargs="?",
        default=PATIENT_COLLECTION,
        help=f"Firestore collection containing the patient document (default: {PATIENT_COLLECTION}).",
    )
    parser.add_argument(
        "document_id",
        help="Firestore document identifier to anonymize.",
    )
    parser.add_argument(
        "--postgres-dsn",
        dest="postgres_dsn",
        required=True,
        help="Postgres DSN used for inserting the anonymized patient row.",
    )
    parser.add_argument(
        "--dump-summary",
        action="store_true",
        help="Emit a JSON summary of the transformations that were applied.",
    )
    parser.add_argument(
        "--bootstrap-schema",
        dest="bootstrap_schema",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Control whether the anonymizer patient schema should be bootstrapped before inserting rows.",
    )
    return parser


async def _run_async(args: argparse.Namespace) -> int:
    fixture_paths = discover_fixture_paths()
    firestore = FixtureFirestoreDataSource(
        collection=args.collection,
        fixture_paths=fixture_paths,
    )
    storage = PostgresStorage(
        args.postgres_dsn,
        bootstrap_schema=args.bootstrap_schema,
    )
    anonymizer = PresidioAnonymizerEngine()

    try:
        patient_id, transformation_events = await process_patient(
            args.collection,
            args.document_id,
            firestore=firestore,
            anonymizer=anonymizer,
            storage=storage,
        )
    finally:
        storage.close()

    print(f"Persisted anonymized patient {patient_id}")

    if args.dump_summary:
        summary = summarize_transformations(
            event.model_dump() if hasattr(event, "model_dump") else event
            for event in transformation_events
        )
        print("Transformation summary:")
        print(json.dumps(summary, indent=2))

    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run_async(args))
    except KeyboardInterrupt:  # pragma: no cover - manual cancellation guard
        return 130
    except Exception as exc:  # pragma: no cover - surface script errors cleanly
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

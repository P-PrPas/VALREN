import argparse
import json
from pathlib import Path
import sys
import sqlite3
import uuid

from .config import load, local_path
from .models import Candidate
from .store import Store


def emit(**values):
    print(json.dumps(values, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="valren")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--db", default="data/valren.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    radar = sub.add_parser("radar")
    radar.add_argument("--dry-run", action="store_true")
    radar.add_argument("--fixture", type=Path)
    args = parser.parse_args(argv)
    run_id = str(uuid.uuid4())
    try:
        settings = load(args.config)
        if args.command == "doctor":
            emit(run_id=run_id, ok=True, mode="offline", timezone=settings.timezone,
                 profile_confirmed=settings.interests.get("confirmed", False),
                 budget_usd=settings.monthly_budget_usd,
                 live_verified=False)
            return 0
        if not args.fixture:
            raise ValueError("foundation radar requires --fixture")
        items = [Candidate(**value) for value in json.loads(local_path(str(args.fixture)).read_text())]
        store = Store(":memory:" if args.dry_run else local_path(args.db))
        try:
            added = sum(store.add(item) for item in items[:settings.candidate_limit])
            emit(run_id=run_id, dry_run=args.dry_run, fetched=len(items), added=added,
                 truncated=max(0, len(items) - settings.candidate_limit),
                 duplicates=min(len(items), settings.candidate_limit) - added,
                 preview_scope="fixture-only" if args.dry_run else "local-ledger",
                 items=[item.as_dict() for item in store.pending(settings.candidate_limit)])
        finally:
            store.close()
        return 0
    except (ValueError, OSError, TypeError, KeyError, sqlite3.Error, RecursionError) as error:
        # Do not echo remote payloads or secrets through unhandled tracebacks.
        emit(run_id=run_id, ok=False, error_type=type(error).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())

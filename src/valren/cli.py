import argparse
import json
from pathlib import Path
import sys
import sqlite3
import uuid
from contextlib import nullcontext

from .config import load, local_path
from .models import Candidate
from .store import Store
from .notion import Notion
from .pipeline import ingest, worker_lock
from .sources import Sources


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
    radar.add_argument("--live", action="store_true", help="fetch public sources")
    radar.add_argument("--sync-notion", action="store_true", help="write New items to Library")
    sub.add_parser("sync-library")
    backup = sub.add_parser("backup")
    backup.add_argument("destination")
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
        dry = getattr(args, "dry_run", False)
        path = local_path(args.db)
        with nullcontext() if dry else worker_lock(path.with_suffix(".lock")):
            store = Store(":memory:" if dry else path)
            try:
                if args.command == "sync-library":
                    notion = Notion(settings, store)
                    notion.validate()
                    emit(run_id=run_id, synced=notion.sync())
                    return 0
                if args.command == "backup":
                    destination = local_path(args.destination)
                    if destination == path:
                        raise ValueError("backup destination must differ from live database")
                    store.backup(destination)
                    emit(run_id=run_id, backed_up=True)
                    return 0
                if args.fixture and args.live:
                    raise ValueError("choose fixture or live sources")
                if args.fixture:
                    items = [Candidate(**value) for value in json.loads(local_path(str(args.fixture)).read_text())]
                    health = {}
                elif args.live:
                    items, health = Sources(settings).collect()
                else:
                    raise ValueError("radar requires --fixture or --live")
                notion = Notion(settings, store) if args.sync_notion and not dry else None
                report = ingest(settings, store, items, health, notion)
                emit(run_id=run_id, dry_run=dry, preview_scope="isolated" if dry else "local-ledger",
                     **report, items=[item.as_dict() for item in store.pending(settings.candidate_limit)])
                return 0 if report["ok"] else 1
            finally:
                store.close()
    except (ValueError, OSError, TypeError, KeyError, sqlite3.Error, RuntimeError, RecursionError) as error:
        # Do not echo remote payloads or secrets through unhandled tracebacks.
        emit(run_id=run_id, ok=False, error_type=type(error).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())

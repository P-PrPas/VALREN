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
from .pipeline import ingest, worker_lock, WorkerBusy
from .sources import Sources
from .delivery import deliver, digest_text, init_outbox
from .llm import LLM, Budget, prune_cache
from .notion import read_profile
from .recommend import recommend
from .tutor import teach
from .telegram import Telegram
from dataclasses import replace
import time
from .feedback import record_feedback, feedback_buttons, button_feedback, taste
from .agent_net import receive, approve, run_approved, init_requests, read_envelope
from .scheduler import serve, status as scheduler_status


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
    rec = sub.add_parser("recommend", help="paid ranking/summaries; requires explicit LLM config and confirmed profile")
    rec.add_argument("--deliver", action="store_true")
    sub.add_parser("retry-deliveries")
    sub.add_parser("health")
    prune = sub.add_parser("prune-llm-cache", help="drop old settled bodies, retain no-rebilling tombstones")
    prune.add_argument("--older-than-days", type=int, default=30)
    preview = sub.add_parser("preview-digest", help="render supplied summaries without LLM/network")
    preview.add_argument("fixture", type=Path)
    resolution = sub.add_parser("resolve-delivery", help="operator action after checking remote delivery")
    resolution.add_argument("id")
    resolution.add_argument("--state", choices=["sent", "ready", "failed"], required=True)
    resolution.add_argument("--receipt", default="operator-confirmed")
    tutor = sub.add_parser("tutor", help="user-requested paid lesson, saved to Library")
    tutor.add_argument("target")
    tutor.add_argument("--retry-invalid", action="store_true", help="explicitly allow one fresh paid attempt for invalid output")
    poll = sub.add_parser("telegram-poll", help="one authenticated Telegram polling cycle")
    poll.add_argument("--once", action="store_true", help="deprecated alias: each invocation is one bounded cycle")
    sub.add_parser("telegram-serve", help="run the standalone bot loop; never alongside Hermes on the same token")
    feedback = sub.add_parser("feedback", help="trusted local user feedback")
    feedback.add_argument("key")
    feedback.add_argument("value", choices=["Liked", "Disliked"])
    agent = sub.add_parser("agent-request", help="receive one signed agent request envelope")
    agent.add_argument("envelope", type=Path)
    approval = sub.add_parser("approve-request", help="trusted local operator approval, not an agent tool")
    approval.add_argument("id")
    approval.add_argument("target", help="must match the reviewed stored target")
    run = sub.add_parser("run-approved", help="consume one current user approval and run its fixed target")
    run.add_argument("id")
    sub.add_parser("requests")
    schedule = sub.add_parser("schedule", help="local daily scheduler; starts no T3 task")
    schedule.add_argument("--once", action="store_true")
    schedule.add_argument("--enable-paid", action="store_true")
    schedule.add_argument("--enable-delivery", action="store_true")
    schedule.add_argument("--sync-notion", action="store_true")
    args = parser.parse_args(argv)
    run_id = str(uuid.uuid4())
    try:
        settings = load(args.config)
        if args.command == "schedule":
            return serve(settings, args.db, args.config, once=args.once, paid=args.enable_paid,
                         sending=args.enable_delivery, sync=args.sync_notion)
        if args.command == "telegram-serve":
            command = ["--db", args.db] + (["--config", str(args.config)] if args.config else []) + ["telegram-poll"]
            while True:
                main(command)
                time.sleep(30)
        if args.command == "preview-digest":
            entries = json.loads(local_path(str(args.fixture)).read_text())
            emit(run_id=run_id, content=digest_text("preview", entries), dry_run=True)
            return 0
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
                if args.command in ("tutor", "telegram-poll", "run-approved"):
                    def tutor_request(target, retry_invalid=False):
                        tutor_settings = replace(settings, llm=settings.tutor_llm or settings.llm)
                        profile = json.dumps(settings.interests, ensure_ascii=False)
                        if settings.notion_profile_page_id:
                            profile += "\n" + read_profile(settings)
                        return teach(tutor_settings, store, LLM(tutor_settings, store), Notion(settings, store), target, profile, retry_invalid=retry_invalid)
                    if args.command == "tutor":
                        emit(run_id=run_id, **tutor_request(args.target, args.retry_invalid))
                    elif args.command == "run-approved":
                        emit(run_id=run_id, **run_approved(store, args.id, tutor_request))
                    else:
                        def handler(text, identifier, message):
                            command, _, target = text.partition(" ")
                            if command in ("/tutor", "/tutor_retry") and target.strip():
                                return tutor_request(target.strip(), command == "/tutor_retry")["lesson"]
                            if command in ("/like", "/dislike"):
                                return record_feedback(store, Notion(settings, store), target.strip(), "Liked" if command == "/like" else "Disliked")
                            if command == "/feedback":
                                return feedback_buttons(store, target.strip(), message["chat"]["id"])
                            if command == "/approve":
                                identifier, _, reviewed_target = target.strip().partition(" ")
                                approve(store, identifier, "telegram:" + str(message["from"]["id"]), reviewed_target.strip())
                                return run_approved(store, identifier, tutor_request)["lesson"]
                            if command == "/requests":
                                init_requests(store)
                                return json.dumps([dict(row) for row in store.db.execute(
                                    "SELECT id,agent,target,state,expires FROM requests ORDER BY created DESC LIMIT 10")], ensure_ascii=False)
                            return "ใช้ /tutor ตามด้วย canonical ID หรือ https://arxiv.org/abs/ID เพื่อเริ่มบทเรียน"
                        emit(run_id=run_id, **Telegram(settings, store).poll_once(handler,
                            lambda query: button_feedback(store, Notion(settings, store), query)))
                    return 0
                if args.command == "feedback":
                    emit(run_id=run_id, result=record_feedback(store, Notion(settings, store), args.key, args.value))
                    return 0
                if args.command == "agent-request":
                    path = local_path(str(args.envelope))
                    emit(run_id=run_id, **receive(settings, store, read_envelope(path)))
                    return 0
                if args.command == "approve-request":
                    emit(run_id=run_id, **approve(store, args.id, "local-operator", args.target))
                    return 0
                if args.command == "requests":
                    init_requests(store)
                    emit(run_id=run_id, requests=[dict(row) for row in store.db.execute(
                        "SELECT id,agent,operation,target,state,expires FROM requests ORDER BY created DESC LIMIT 50")])
                    return 0
                if args.command == "prune-llm-cache":
                    Budget(settings, store)
                    emit(run_id=run_id, pruned=prune_cache(store, args.older_than_days))
                    return 0
                if args.command == "health":
                    init_outbox(store)
                    budget = Budget(settings, store)
                    init_requests(store)
                    emit(run_id=run_id, last_run=store.get_state("last_run"), last_success=store.get_state("last_success"),
                         library_conflicts=store.get_state("library_conflicts", []), budget_used_micros=budget.used(),
                         budget_blocked=bool(store.get_state("budget_blocked")),
                         llm_calls_held=store.db.execute("SELECT count(*) FROM state WHERE key LIKE 'llm-call:%' AND value LIKE '%\"inflight\"%'").fetchone()[0],
                         telegram_commands_held=store.db.execute("SELECT count(*) FROM state WHERE key LIKE 'telegram-command:%' AND value LIKE '%\"uncertain\"%'").fetchone()[0],
                         taste=taste(store), pending_requests=store.db.execute("SELECT count(*) FROM requests WHERE state='pending'").fetchone()[0],
                         executing_requests=store.db.execute("SELECT count(*) FROM requests WHERE state='executing'").fetchone()[0],
                         failed_requests=store.db.execute("SELECT count(*) FROM requests WHERE state='failed'").fetchone()[0],
                         scheduler=scheduler_status(path),
                         deliveries=[dict(row) for row in store.db.execute("SELECT id,state,attempts,updated FROM deliveries")])
                    return 0
                if args.command == "recommend":
                    profile = json.dumps(settings.interests, ensure_ascii=False)
                    if settings.notion_profile_page_id:
                        profile += "\n" + read_profile(settings)
                    result = recommend(settings, store, LLM(settings, store), Notion(settings, store), profile)
                    if args.deliver:
                        result["delivery"] = deliver(settings, store)
                    emit(run_id=run_id, **result)
                    return 0
                if args.command == "retry-deliveries":
                    emit(run_id=run_id, **deliver(settings, store))
                    return 0
                if args.command == "resolve-delivery":
                    init_outbox(store)
                    changed = store.db.execute("UPDATE deliveries SET state=?,receipt=?,attempts=0 WHERE id=? AND state='uncertain'",
                                               (args.state, args.receipt, args.id)).rowcount
                    if not changed:
                        raise ValueError("delivery is not uncertain")
                    emit(run_id=run_id, resolved=True)
                    return 0
                if args.command == "sync-library":
                    notion = Notion(settings, store)
                    notion.validate()
                    emit(run_id=run_id, synced=notion.sync())
                    return 0
                if args.command == "backup":
                    destination = local_path(args.destination)
                    if destination == path or destination.exists() or str(destination) in (str(path) + "-wal", str(path) + "-shm", str(path.with_suffix(".lock"))):
                        raise ValueError("backup destination must be a new, separate file")
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
                return 0 if report["ok"] else 10  # Distinct from argparse's usage-error exit 2.
            finally:
                store.close()
    except WorkerBusy:
        emit(run_id=run_id, ok=False, error_type="WorkerBusy")
        return 75
    except Exception as error:
        # Do not echo remote payloads or secrets through unhandled tracebacks.
        emit(run_id=run_id, ok=False, error_type=type(error).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())

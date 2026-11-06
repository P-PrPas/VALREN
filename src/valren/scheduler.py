from contextlib import closing
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from .config import ROOT, local_path
from .pipeline import worker_lock
from .store import Store


def control_path(path):
    return Path(str(path) + ".scheduler")


def pending_delivery(path):
    if not path.exists():
        return False
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            return bool(db.execute("SELECT 1 FROM deliveries WHERE state='ready' AND attempts<3 LIMIT 1").fetchone())
    except sqlite3.OperationalError:
        return False


def status(path):
    control = control_path(path)
    if not control.exists():
        return []
    with closing(sqlite3.connect(control.as_uri() + "?mode=ro", uri=True)) as db:
        return [{"id": row[0], **json.loads(row[1])} for row in db.execute(
            "SELECT key,value FROM state WHERE key LIKE 'schedule:%' ORDER BY key DESC LIMIT 7")]


def tick(settings, db_path, config_path=None, *, paid=False, sending=False, sync=False, runner=subprocess.run, at=None):
    def current_time():
        return at.astimezone(ZoneInfo(settings.timezone)) if at else datetime.now(ZoneInfo(settings.timezone))
    clock = current_time()
    if not 8 <= clock.hour < 23:
        return {"state": "waiting", "next_window": "08:00 " + settings.timezone}
    if paid and (settings.interests.get("confirmed") is not True or settings.monthly_budget_usd <= 0):
        raise ValueError("paid scheduling requires confirmed interests and positive budget")
    if paid and not sync:
        raise ValueError("paid scheduling requires Library synchronization")
    path = local_path(db_path)
    control = control_path(path)
    lock = Path(str(control) + ".lock")
    state_key = "schedule:" + clock.date().isoformat()

    def save(value):
        with worker_lock(lock), closing(Store(control)) as store:
            store.set_state(state_key, value)

    with worker_lock(lock), closing(Store(control)) as store:
        saved = store.get_state(state_key, {"state": "new", "steps": [], "attempts": 0})
        if saved["state"] == "running":
            claimed = datetime.fromisoformat(saved.get("claimed_at", (clock - timedelta(hours=2)).isoformat()))
            if (clock - claimed).total_seconds() < 3700:
                return {"state": "running", "attempts": saved["attempts"]}
            saved["state"] = "failed"  # Dead parent/child lease expired; paid work remains idempotent/held.
            store.set_state(state_key, saved)
        delivery_only = saved["state"] == "done" or saved.get("delivery_only", False)
        if delivery_only and (not sending or not pending_delivery(path)):
            return {"state": "done", "attempts": saved["attempts"]}
        if delivery_only and saved.get("delivery_attempts", 0) >= 3:
            return {"state": "done", "attempts": saved["attempts"], "delivery_attempts": saved["delivery_attempts"]}
        if not delivery_only and saved["attempts"] >= 3:
            return {"state": saved["state"], "attempts": saved["attempts"]}
        if saved.get("retry_at") and datetime.fromisoformat(saved["retry_at"]) > clock:
            return {"state": "retry-later"}
        if delivery_only:
            saved["steps"] = [step for step in saved["steps"] if step != "deliver"]
        saved.update(state="running", claimed_at=clock.isoformat(), delivery_only=delivery_only,
                     attempts=saved["attempts"] + (0 if delivery_only else 1))
        store.set_state(state_key, saved)

    base = [sys.executable, "-m", "valren.cli", "--db", str(path)]
    if config_path:
        base += ["--config", str(config_path)]
    steps = [("radar", ["radar", "--live"] + (["--sync-notion"] if sync else []))]
    if paid:
        steps.append(("recommend", ["recommend"]))
    if sending:
        steps.append(("deliver", ["retry-deliveries"]))
    if delivery_only:
        steps = [("deliver", ["retry-deliveries"])]
    failed = False
    try:
        for name, command in steps:
            if name in saved["steps"]:
                continue
            saved["claimed_at"] = current_time().isoformat()
            if name == "deliver":
                saved["delivery_attempts"] = saved.get("delivery_attempts", 0) + 1
            save(saved)
            result = runner(base + command, cwd=ROOT, env={**os.environ, "VALREN_HOME": str(ROOT)},
                            capture_output=True, text=True, timeout=3600, check=False)
            code = result.returncode
            if code == 75:
                # Contention is not a failed research attempt; bookkeeping has its own lock/database.
                if not delivery_only:
                    saved["attempts"] -= 1
                if name == "deliver":
                    saved["delivery_attempts"] -= 1
                saved["retry_at"] = (current_time() + timedelta(minutes=5)).isoformat()
                saved["error_step"] = name
                failed = True
                break
            if code == 10 and name == "radar":
                saved["partial_radar"] = True
            elif code:
                saved["error_step"] = name
                saved["error_code"] = code
                failed = True
                break
            saved["steps"].append(name)
            save(saved)
    except Exception as error:
        failed = True
        saved["error_type"] = type(error).__name__
    finally:
        saved["state"] = "failed" if failed else "done"
        if not saved.get("retry_at") or datetime.fromisoformat(saved["retry_at"]) <= current_time():
            saved["retry_at"] = (current_time() + timedelta(hours=1)).isoformat()
        save(saved)
    return {"state": saved["state"], "steps": saved["steps"], "attempts": saved["attempts"],
            "partial_radar": saved.get("partial_radar", False)}


def serve(settings, db_path, config_path=None, *, once=False, paid=False, sending=False, sync=False):
    while True:
        try:
            result = tick(settings, db_path, config_path, paid=paid, sending=sending, sync=sync)
        except Exception as error:
            result = {"state": "failed", "error_type": type(error).__name__}
        print(json.dumps({"scheduler": result}), flush=True)
        if once:
            return 0 if result["state"] != "failed" else 1
        time.sleep(60)

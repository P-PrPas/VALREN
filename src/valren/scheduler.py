from datetime import datetime, timedelta
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from .config import ROOT, local_path
from .pipeline import worker_lock
from .store import Store


def tick(settings, db_path, config_path=None, *, paid=False, sending=False, sync=False, runner=subprocess.run, at=None):
    clock = at or datetime.now(ZoneInfo(settings.timezone))
    clock = clock.astimezone(ZoneInfo(settings.timezone))
    if not 8 <= clock.hour < 23:
        return {"state": "waiting", "next_window": "08:00 Asia/Bangkok (configured timezone)"}
    if paid and (settings.interests.get("confirmed") is not True or settings.monthly_budget_usd <= 0):
        raise ValueError("paid scheduling requires confirmed interests and positive budget")
    if paid and not sync:
        raise ValueError("paid scheduling requires Library synchronization")
    path = local_path(db_path)
    state_key = "schedule:" + clock.date().isoformat()
    with worker_lock(path.with_suffix(".lock")):
        store = Store(path)
        try:
            saved = store.get_state(state_key, {"state": "new", "steps": [], "attempts": 0})
            if saved["state"] in ("done", "running") or saved["attempts"] >= 3:
                return {"state": saved["state"], "attempts": saved["attempts"]}
            if saved.get("retry_at") and datetime.fromisoformat(saved["retry_at"]) > clock:
                return {"state": "retry-later"}
            saved["state"] = "running"
            saved["attempts"] += 1
            store.set_state(state_key, saved)
        finally:
            store.close()
    base = [sys.executable, "-m", "valren.cli", "--db", str(path)]
    if config_path:
        base += ["--config", str(config_path)]
    steps = [("radar", ["radar", "--live"] + (["--sync-notion"] if sync else []))]
    if paid:
        steps.append(("recommend", ["recommend"]))
    if sending:
        steps.append(("deliver", ["retry-deliveries"]))
    result_state = "done"
    for name, command in steps:
        if name in saved["steps"]:
            continue
        try:
            result = runner(base + command, cwd=ROOT, env={**os.environ, "VALREN_HOME": str(ROOT)},
                            capture_output=True, text=True, timeout=3600, check=False)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
        if code:
            result_state = "failed"
            saved["error_step"] = name
            saved["retry_at"] = (clock + timedelta(hours=1)).isoformat()
            break
        saved["steps"].append(name)
        with worker_lock(path.with_suffix(".lock")):
            store = Store(path)
            try:
                store.set_state(state_key, saved)
            finally:
                store.close()
    saved["state"] = result_state
    with worker_lock(path.with_suffix(".lock")):
        store = Store(path)
        try:
            store.set_state(state_key, saved)
        finally:
            store.close()
    return {"state": result_state, "steps": saved["steps"], "attempts": saved["attempts"]}


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

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json

from .models import Candidate
from .notion import Notion
from .sources import Sources
from .store import now


class WorkerBusy(ValueError):
    pass


@contextmanager
def worker_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise WorkerBusy("another worker owns this database") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def ingest(settings, store, items, health=None, notion=None):
    added = 0
    for item in items:
        previous = store.db.execute("SELECT payload FROM items WHERE key=?", (item.key,)).fetchone()
        if previous and "stars" in item.metadata:
            old = json.loads(previous[0]).get("metadata", {})
            if "stars" in old:
                item.metadata["star_change_since_last_observation"] = item.metadata["stars"] - old["stars"]
        added += store.add(item)
    failures = 0
    if notion:
        try:
            notion.validate()
            notion.sync()
        except Exception:
            failures += 1
            notion = None
    if notion:
        for item in store.pending(settings.candidate_limit):
            try:
                notion.ensure_page(item)
            except Exception as error:
                failures += 1
                if getattr(error, "status", None) in (401, 403, 429):
                    break
        failures += len(store.get_state("library_conflicts", []))
    report = {"fetched": len(items), "added": added, "duplicates": len(items) - added,
              "sources": health or {}, "notion_failures": failures,
              "pending": len(store.pending(settings.candidate_limit)),
              "selection_clipped": store.db.execute("SELECT count(*) FROM items WHERE status='New'").fetchone()[0] > settings.candidate_limit}
    report["ok"] = not failures and all(value["ok"] for value in (health or {}).values())
    store.set_state("last_run", {"at": now(), **report})
    if report["ok"]:
        store.set_state("last_success", now())
    return report

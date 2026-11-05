from datetime import datetime
import json
import hashlib
from zoneinfo import ZoneInfo

from .delivery import digest_text, init_outbox
from .llm import BudgetExceeded, micros, rank, summary
from .notion import rich
from .store import now
from .feedback import apply_taste


def recommend(settings, store, llm, notion, profile):
    if settings.interests.get("confirmed") is not True or not settings.interests.get("topics"):
        raise ValueError("confirm a non-empty Interest Profile before paid ranking")
    if settings.daily_limit > 3:
        raise ValueError("MVP digest supports at most 3 daily items")
    init_outbox(store)
    day = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
    job_key = "digest:" + day
    current_delivery = store.db.execute("SELECT id,state FROM deliveries WHERE day=? LIMIT 1", (day,)).fetchone()
    if current_delivery:
        return {"day": day, "state": current_delivery["state"], "resumed": True}
    # Resume saved paid work even if a retry crosses midnight.
    for prior in store.db.execute("SELECT key,value FROM state WHERE key LIKE 'digest:%' ORDER BY key"):
        if not store.db.execute("SELECT 1 FROM deliveries WHERE id=?", (prior["key"],)).fetchone():
            value = json.loads(prior["value"])
            if isinstance(value, dict) and "entries" in value:
                job_key = prior["key"]  # Paid work keeps its identity; delivery belongs to today.
                break
    existing = store.db.execute("SELECT state FROM deliveries WHERE id=?", (job_key,)).fetchone()
    if existing:
        return {"day": day, "state": existing[0], "resumed": True}
    notion.validate()
    notion.sync()  # Always check durable recommendation history before paid calls.
    work = store.get_state(job_key)
    if work is None:
        candidates = store.pending(settings.candidate_limit)
        excluded = [term.casefold() for term in settings.interests.get("excluded", [])]
        candidates = [item for item in candidates if len(item.text.strip()) >= 10 and not any(term in (item.title + " " + item.text).casefold() for term in excluded)]
        ranking = rank(llm, candidates, profile)
        ranking["items"] = apply_taste(store, candidates, ranking["items"])
        selected, groups = [], set()
        by_key = {item.key: item for item in candidates}
        for row in ranking["items"]:
            if row["score"] < 3 or len(selected) >= settings.daily_limit:
                continue
            item = by_key[row["key"]]
            group = item.metadata.get("related_work") or item.key
            if group in groups:
                continue
            groups.add(group)
            selected.append({"item": item.as_dict(), "score": row["score"]})
        work = {"entries": selected, "budget_exhausted": ranking["budget_exhausted"], "failed_batches": ranking["failed_batches"]}
        store.set_state(job_key, work)
    from .models import Candidate
    entries = []
    for row in work["entries"]:
        item = Candidate(**row["item"])
        current = store.db.execute("SELECT status FROM items WHERE key=?", (item.key,)).fetchone()
        if current and current[0] in ("Skipped", "Reading", "Deep-dived"):
            continue
        if row.get("summary_failed") or row.get("notion_failed"):
            continue
        if "summary" not in row:
            try:
                row["summary"] = summary(llm, item, profile)
            except BudgetExceeded:
                work["budget_exhausted"] = True
                store.set_state(job_key, work)
                break
            except Exception as error:
                row["summary_failed"] = type(error).__name__
                store.set_state(job_key, work)
                continue
            store.set_state(job_key, work)  # Retry reuses paid work.
        result = row["summary"]
        provenance = json.dumps({"source_id": item.key, "source_url": item.url, "coverage": item.metadata.get("coverage", "unknown"),
            "observed_at": store.db.execute("SELECT discovered FROM items WHERE key=?", (item.key,)).fetchone()[0],
            "result": result}, ensure_ascii=False)
        try:
            notion.ensure_page(item)
            notion.save_managed(item.key, "summary-" + hashlib.sha256(provenance.encode()).hexdigest()[:24], provenance)
            notion.patch_owned(item.key, {
                "Status": {"select": {"name": "Recommended"}}, "Recommended on": {"date": {"start": day}},
                "Relevance": {"number": row["score"]}, "Summary": {"rich_text": rich(result["summary"] + "\n" + result["limitations"] +
                    "\nSource: " + item.url + "\nEvidence: " + "; ".join(c["quote"] for c in result["evidence"]))},
                "Why it matters to me": {"rich_text": rich(result["why"])},
                "Tags": {"multi_select": [{"name": tag} for tag in result["tags"]]},
                "Verification status": {"select": {"name": "Unverified"}}})
        except Exception as error:
            row["notion_failed"] = type(error).__name__
            store.set_state(job_key, work)
            continue
        store.db.execute("UPDATE items SET status='Recommended',recommended=coalesce(recommended,?) WHERE key=?", (day, item.key))
        store.set_state("tags:" + item.key, result["tags"])
        entries.append({"key": item.key, "title": item.title, "url": item.url, **result})
    warning = llm.budget.used() >= micros(settings.monthly_budget_usd) * .8
    content = digest_text(day, entries, warning or work.get("budget_exhausted", False))
    store.db.execute("INSERT INTO deliveries(id,day,payload,state,updated) VALUES(?,?,?,'ready',?)",
        (job_key, day, json.dumps({"content": content, "entries": entries}, ensure_ascii=False), now()))
    return {"day": day, "state": "ready", "selected": len(entries), "budget_warning": warning,
            "failed_rank_batches": work.get("failed_batches", 0),
            "failed_notion_items": sum(bool(row.get("notion_failed")) for row in work["entries"]),
            "failed_summaries": sum(bool(row.get("summary_failed")) for row in work["entries"])}

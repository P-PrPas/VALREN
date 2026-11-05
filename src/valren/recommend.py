from datetime import datetime
import json
from zoneinfo import ZoneInfo

from .delivery import digest_text, init_outbox
from .llm import BudgetExceeded, micros, rank, summary
from .notion import rich
from .store import now


def recommend(settings, store, llm, notion, profile):
    if settings.interests.get("confirmed") is not True or not settings.interests.get("topics"):
        raise ValueError("confirm a non-empty Interest Profile before paid ranking")
    if settings.daily_limit > 3:
        raise ValueError("MVP digest supports at most 3 daily items")
    init_outbox(store)
    day = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
    job_key = "digest:" + day
    existing = store.db.execute("SELECT state FROM deliveries WHERE id=?", (job_key,)).fetchone()
    if existing:
        return {"day": day, "state": existing[0], "resumed": True}
    notion.validate()
    notion.sync()  # Always check durable recommendation history before paid calls.
    work = store.get_state(job_key)
    if work is None:
        candidates = store.pending(settings.candidate_limit)
        excluded = [term.casefold() for term in settings.interests.get("excluded", [])]
        candidates = [item for item in candidates if not any(term in (item.title + " " + item.text).casefold() for term in excluded)]
        budget_exhausted = False
        try:
            ranked = rank(llm, candidates, profile)
        except BudgetExceeded:
            ranked, budget_exhausted = [], True
        selected, groups = [], set()
        by_key = {item.key: item for item in candidates}
        for row in ranked:
            if row["score"] < 3 or len(selected) >= settings.daily_limit:
                continue
            item = by_key[row["key"]]
            group = item.metadata.get("related_work") or item.key
            if group in groups:
                continue
            groups.add(group)
            selected.append({"item": item.as_dict(), "score": row["score"]})
        work = {"entries": selected, "budget_exhausted": budget_exhausted}
        store.set_state(job_key, work)
    from .models import Candidate
    entries = []
    for row in work["entries"]:
        item = Candidate(**row["item"])
        current = store.db.execute("SELECT status FROM items WHERE key=?", (item.key,)).fetchone()
        if current and current[0] in ("Skipped", "Reading", "Deep-dived"):
            continue
        if "summary" not in row:
            try:
                row["summary"] = summary(llm, item, profile)
            except BudgetExceeded:
                work["budget_exhausted"] = True
                store.set_state(job_key, work)
                break
            store.set_state(job_key, work)  # Retry reuses paid work.
        result = row["summary"]
        notion.ensure_page(item)
        notion.patch_owned(item.key, {
            "Status": {"select": {"name": "Recommended"}}, "Recommended on": {"date": {"start": day}},
            "Relevance": {"number": row["score"]}, "Summary": {"rich_text": rich(result["summary"] + "\n" + result["limitations"] +
                "\nSource: " + item.url + "\nEvidence: " + "; ".join(c["quote"] for c in result["evidence"]))},
            "Why it matters to me": {"rich_text": rich(result["why"])},
            "Tags": {"multi_select": [{"name": tag} for tag in result["tags"]]},
            "Verification status": {"select": {"name": "Unverified"}}})
        store.db.execute("UPDATE items SET status='Recommended',recommended=coalesce(recommended,?) WHERE key=?", (day, item.key))
        entries.append({"key": item.key, "title": item.title, "url": item.url, **result})
    warning = llm.budget.used() >= micros(settings.monthly_budget_usd) * .8
    content = digest_text(day, entries, warning or work.get("budget_exhausted", False))
    store.db.execute("INSERT INTO deliveries(id,day,payload,state,updated) VALUES(?,?,?,'ready',?)",
        (job_key, day, json.dumps({"content": content, "entries": entries}, ensure_ascii=False), now()))
    return {"day": day, "state": "ready", "selected": len(entries), "budget_warning": warning}

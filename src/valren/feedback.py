from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import secrets


def features(store, item):
    values = store.get_state("tags:" + item.key, []) + [item.metadata.get("topic", ""), item.metadata.get("task", "")]
    return {value.casefold().strip() for value in values if isinstance(value, str) and value.strip()}


def taste(store):
    liked, disliked = Counter(), Counter()
    from .models import Candidate
    for row in store.db.execute("SELECT payload,feedback FROM items WHERE feedback IN ('Liked','Disliked')"):
        try:
            item = Candidate(**json.loads(row[0]))
            (liked if row[1] == "Liked" else disliked).update(features(store, item))
        except (ValueError, KeyError, TypeError):
            continue
    result = {"liked": dict(liked.most_common(20)), "disliked": dict(disliked.most_common(20))}
    # Taste-only memory, bounded to one short block. Article content stays in Library.
    block = json.dumps(result, ensure_ascii=False)[:1800]
    store.set_state("taste_memory", block)
    return result


def apply_taste(store, items, ranked):
    preferences = taste(store)
    by_key = {item.key: item for item in items}
    for row in ranked:
        tags = features(store, by_key[row["key"]])
        signal = sum(preferences["liked"].get(tag, 0) - preferences["disliked"].get(tag, 0) for tag in tags)
        delta = 1 if signal > 0 else -1 if signal < 0 else 0
        row["score"] = max(1, min(5, row["score"] + delta))
    return sorted(ranked, key=lambda row: (-row["score"], row["key"]))


def record_feedback(store, notion, key, value):
    if value not in ("Liked", "Disliked"):
        raise ValueError("unknown feedback")
    row = store.db.execute("SELECT page_id FROM items WHERE key=?", (key,)).fetchone()
    if not row:
        raise ValueError("unknown feedback target")
    # This is an explicit authenticated user operation, separate from the automated owned-field writer.
    notion.user_feedback(key, value)
    store.db.execute("UPDATE items SET feedback=? WHERE key=?", (value, key))
    taste(store)
    return "บันทึก " + value + " แล้ว: " + key


def feedback_buttons(store, key, chat):
    if not store.db.execute("SELECT 1 FROM items WHERE key=?", (key,)).fetchone():
        raise ValueError("unknown feedback target")
    token = secrets.token_urlsafe(12)
    store.set_state("feedback-button:" + token, {"key": key, "chat": chat,
        "expires": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()})
    return {"text": "ให้ feedback: " + key, "reply_markup": {"inline_keyboard": [[
        {"text": "Liked", "callback_data": "fb:" + token + ":Liked"},
        {"text": "Disliked", "callback_data": "fb:" + token + ":Disliked"}]]}}


def button_feedback(store, notion, query):
    parts = query.get("data", "").split(":")
    if len(parts) != 3 or parts[0] != "fb" or parts[2] not in ("Liked", "Disliked"):
        raise ValueError("invalid feedback callback")
    saved = store.get_state("feedback-button:" + parts[1])
    if (not saved or datetime.fromisoformat(saved["expires"]) < datetime.now(timezone.utc)
            or saved["chat"] != query.get("message", {}).get("chat", {}).get("id")):
        raise ValueError("feedback button expired or belongs to another chat")
    return record_feedback(store, notion, saved["key"], parts[2])

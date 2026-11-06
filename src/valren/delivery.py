from datetime import datetime, timedelta
import json
import os
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .http import HTTP, RemoteError
from .store import now


def quiet(settings, at=None):
    local = (at or datetime.now(ZoneInfo(settings.timezone))).astimezone(ZoneInfo(settings.timezone))
    return local.hour >= 23 or local.hour < 7


def init_outbox(store):
    store.db.execute("""CREATE TABLE IF NOT EXISTS deliveries (
        id TEXT PRIMARY KEY, day TEXT NOT NULL, payload TEXT NOT NULL,
        state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        receipt TEXT, updated TEXT NOT NULL
    )""")


def safe_display(value):
    return re.sub(r"https?://\S+", "[link removed]", str(value)).replace("@", "＠").replace("`", "'").replace("<", "‹").replace(">", "›")


def digest_text(day, entries, budget_warning=False, source_warning=None):
    lines = [f"VARLEN · {day}"]
    if budget_warning:
        lines.append("งบ LLM ใช้ถึง 80% แล้ว — ตรวจงบก่อน deep-dive เพิ่ม")
    if source_warning:
        lines.append("ข้อมูล/การประมวลผลบางส่วนยังไม่ครบ: " + safe_display(source_warning)[:150])
    if len(entries) > 3:
        raise ValueError("MVP digest supports at most 3 daily items")
    available = 1900 - len("\n".join(lines)) - sum(len(entry["url"]) + 20 for entry in entries)
    per_item = max(0, available // max(1, len(entries)))
    for entry in entries:
        title_limit, summary_limit = min(100, per_item // 4), min(250, per_item // 2)
        lines.extend(["", safe_display(entry["title"])[:title_limit], safe_display(entry["summary"])[:summary_limit],
                      "ข้อจำกัด: " + safe_display(entry["limitations"])[:min(150, per_item // 4)], entry["url"]])
    if not entries:
        lines.append("รอบนี้ไม่มีรายการที่ผ่านเกณฑ์ความเกี่ยวข้อง")
    content = "\n".join(lines)
    if len(content) > 1950:
        raise ValueError("digest exceeds Discord content limit; shorten selected summaries")
    return content


def deliver(settings, store, http=None, at=None):
    init_outbox(store)
    if quiet(settings, at):
        return {"sent": 0, "deferred": "quiet-hours"}
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    parts = urlsplit(webhook)
    if (parts.scheme != "https" or parts.hostname != "discord.com" or parts.username or parts.password
            or parts.query or parts.fragment or not re.fullmatch(r"/api/webhooks/\d+/[A-Za-z0-9_.-]+", parts.path)):
        raise ValueError("valid dedicated Discord webhook required")
    client = http or HTTP({"discord.com"})
    local_day = (at or datetime.now(ZoneInfo(settings.timezone))).astimezone(ZoneInfo(settings.timezone)).date()
    store.db.execute("UPDATE deliveries SET state='expired' WHERE state='ready' AND day<?", ((local_day - timedelta(days=1)).isoformat(),))
    sent = 0
    rows = store.db.execute("SELECT * FROM deliveries WHERE state='ready' AND attempts<3 ORDER BY day LIMIT 1").fetchall()
    for row in rows:
        day_key = "discord-day:" + local_day.isoformat()
        previous = store.get_state(day_key)
        if previous and previous != row["id"]:
            return {"sent": 0, "deferred": "daily-limit"}
        store.set_state(day_key, row["id"])
        # After process death, sending remains uncertain; never automatically duplicate it.
        store.db.execute("UPDATE deliveries SET state='uncertain',attempts=attempts+1,updated=? WHERE id=?", (now(), row["id"]))
        try:
            data, _ = client.json("POST", webhook + "?wait=true", payload={
                "content": json.loads(row["payload"])["content"], "allowed_mentions": {"parse": []}})
        except RemoteError as error:
            if not error.uncertain:
                state = "ready" if error.status == 429 else "failed"
                store.db.execute("UPDATE deliveries SET state=?,updated=? WHERE id=?", (state, now(), row["id"]))
            continue
        store.db.execute("UPDATE deliveries SET state='sent',receipt=?,updated=? WHERE id=?", (str(data["id"]), now(), row["id"]))
        sent += 1
    return {"sent": sent, "uncertain": store.db.execute("SELECT count(*) FROM deliveries WHERE state='uncertain'").fetchone()[0]}

"""Signed request inbox. Other agents cannot grant approval or select write actions."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
import stat

from .models import canonical


def read_envelope(path):
    # Do not follow a swapped final symlink or block on a sender-created FIFO.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 16000:
            raise ValueError("agent envelope must be a small regular file")
        data = stream.read(16001)
        if len(data) > 16000:
            raise ValueError("agent envelope too large")
        return json.loads(data)


def init_requests(store):
    store.db.execute("""CREATE TABLE IF NOT EXISTS requests (
        id TEXT PRIMARY KEY, agent TEXT NOT NULL, nonce TEXT NOT NULL,
        fingerprint TEXT NOT NULL, operation TEXT NOT NULL, target TEXT NOT NULL,
        state TEXT NOT NULL, created TEXT NOT NULL, expires TEXT NOT NULL,
        approved_by TEXT, approved_until TEXT, response TEXT,
        executing_at TEXT,
        UNIQUE(agent,nonce)
    )""")
    if "executing_at" not in {row[1] for row in store.db.execute("PRAGMA table_info(requests)")}:
        store.db.execute("ALTER TABLE requests ADD COLUMN executing_at TEXT")


def search(store, query):
    if not isinstance(query, str) or not 1 <= len(query) <= 200:
        raise ValueError("invalid Library query")
    rows = store.db.execute("SELECT key,payload,status FROM items WHERE instr(lower(payload),lower(?))>0 LIMIT 10", (query,)).fetchall()
    return [{"key": row[0], "title": json.loads(row[1])["title"], "url": json.loads(row[1])["url"], "status": row[2]} for row in rows]


def receive(settings, store, envelope, at=None):
    if settings.agent_net.get("enabled") is not True:
        raise ValueError("agent_net is disabled")
    fields = {"version", "agent", "request_id", "nonce", "issued_at", "operation", "target", "signature"}
    if not isinstance(envelope, dict) or set(envelope) != fields or type(envelope["version"]) is not int or envelope["version"] != 1:
        raise ValueError("invalid agent request envelope")
    if any(not isinstance(envelope[key], str) for key in fields - {"version"}):
        raise ValueError("invalid agent request types")
    if envelope["agent"] not in settings.agent_net.get("allowed_agents", []):
        raise ValueError("agent is not allowlisted")
    keys = json.loads(os.environ.get("VALREN_AGENT_NET_KEYS_JSON", "{}"))
    key = keys.get(envelope["agent"], "")
    if not isinstance(key, str) or len(key) < 32:
        raise ValueError("dedicated agent signing credential required")
    unsigned = {key: value for key, value in envelope.items() if key != "signature"}
    payload = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    signature = hmac.new(key.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, envelope["signature"]):
        raise ValueError("invalid agent signature")
    init_requests(store)
    scoped_id = envelope["agent"] + "/" + envelope["request_id"]
    fingerprint = hashlib.sha256(payload).hexdigest()
    existing = store.db.execute("SELECT fingerprint,response FROM requests WHERE agent=? AND (id=? OR id=?)",
        (envelope["agent"], scoped_id, envelope["request_id"])).fetchone()
    if existing:
        if existing[0] != fingerprint:
            raise ValueError("request ID reused for different content")
        # An authenticated exact replay is a read-only status lookup, even after five minutes.
        return json.loads(existing[1])
    clock = at or datetime.now(timezone.utc)
    issued = datetime.fromisoformat(envelope["issued_at"].replace("Z", "+00:00"))
    if issued.tzinfo is None or abs((clock - issued).total_seconds()) > 300:
        raise ValueError("agent request timestamp outside allowed window")
    for name in ("request_id", "nonce"):
        if not re.fullmatch(r"[A-Za-z0-9-]{16,80}", envelope[name]):
            raise ValueError("invalid request identity")
    if envelope["operation"] not in ("search", "research"):
        raise ValueError("agent operation denied")
    target = envelope["target"]
    if len(target) > 1000 or any(ord(character) < 32 for character in target):
        raise ValueError("invalid request target length/control characters")
    if envelope["operation"] == "research":
        source, _, identifier = target.partition(":")
        if canonical(source, identifier) != target:
            raise ValueError("research target must be canonical")
    elif not 1 <= len(target) <= 200:
        raise ValueError("invalid search query")
    with store.transaction():
        existing = store.db.execute("SELECT fingerprint,response FROM requests WHERE id=?", (scoped_id,)).fetchone()
        if existing:
            if existing[0] != fingerprint:
                raise ValueError("request ID reused for different content")
            return json.loads(existing[1])
        recent = store.db.execute("SELECT count(*) FROM requests WHERE agent=? AND created>?",
            (envelope["agent"], (clock - timedelta(hours=1)).isoformat())).fetchone()[0]
        if recent >= 20:
            raise ValueError("agent request rate limit")
        response = {"request_id": scoped_id, "state": "pending_user_approval", "agent": envelope["agent"], "target": target}
        if envelope["operation"] == "search":
            response = {"request_id": scoped_id, "results": search(store, target), "state": "complete"}
        store.db.execute("INSERT INTO requests(id,agent,nonce,fingerprint,operation,target,state,created,expires,response) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (scoped_id, envelope["agent"], envelope["nonce"], fingerprint, envelope["operation"], target,
             "complete" if envelope["operation"] == "search" else "pending", clock.isoformat(),
             (clock + timedelta(hours=24)).isoformat(), json.dumps(response, ensure_ascii=False)))
        if envelope["operation"] == "research":
            for chat in settings.telegram.get("chat_ids", []):
                notification = "คำขอจาก " + envelope["agent"] + "\nเป้าหมาย: " + target + "\nหมดอายุ: " + (clock + timedelta(hours=24)).isoformat()
                notification += "\nWorker: /approve " + scoped_id + " " + target
                notification += "\nHermes: /valren_approve " + scoped_id + " " + target
                store.set_state("telegram-reply:agent-request-" + hashlib.sha256((scoped_id + str(chat)).encode()).hexdigest()[:24],
                    {"parts": [], "chat": chat, "body": notification, "state": "ready"})
    return response


def approve(store, request_id, actor, expected_target, at=None):
    init_requests(store)
    clock = at or datetime.now(timezone.utc)
    with store.transaction():
        row = store.db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        stale = row and row["state"] == "executing" and row["executing_at"] and (clock - datetime.fromisoformat(row["executing_at"])).total_seconds() >= 3700
        if not row or (row["state"] not in ("pending", "failed") and not stale) or datetime.fromisoformat(row["expires"]) < clock:
            raise ValueError("request cannot be approved")
        if expected_target != row["target"]:
            raise ValueError("approval target does not match the reviewed request")
        until = min(clock + timedelta(minutes=15), datetime.fromisoformat(row["expires"]))
        response = json.dumps({"request_id": request_id, "state": "approved", "target": row["target"]})
        store.db.execute("UPDATE requests SET state='approved',approved_by=?,approved_until=?,response=? WHERE id=?",
            (actor, until.isoformat(), response, request_id))
    return {"request_id": request_id, "state": "approved", "target": row["target"]}


def run_approved(store, request_id, handler, at=None):
    init_requests(store)
    clock = at or datetime.now(timezone.utc)
    with store.transaction():
        row = store.db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        if not row or row["state"] != "approved" or datetime.fromisoformat(row["approved_until"]) < clock:
            raise ValueError("no current unused user approval")
        if row["operation"] != "research":
            raise ValueError("only research requests can execute")
        store.db.execute("UPDATE requests SET state='executing',executing_at=?,response=? WHERE id=?",
            (clock.isoformat(), json.dumps({"request_id": request_id, "state": "executing", "target": row["target"]}), request_id))
    try:
        result = handler(row["target"])
    except Exception as error:
        store.db.execute("UPDATE requests SET state='failed',response=? WHERE id=?",
            (json.dumps({"request_id": request_id, "state": "failed", "error_type": type(error).__name__}), request_id))
        raise
    store.db.execute("UPDATE requests SET state='complete',response=? WHERE id=?", (json.dumps({"request_id": request_id, "state": "complete", "key": result["key"]}), request_id))
    return result

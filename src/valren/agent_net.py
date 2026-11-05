"""Signed request inbox. Other agents cannot grant approval or select write actions."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re

from .models import canonical


def init_requests(store):
    store.db.execute("""CREATE TABLE IF NOT EXISTS requests (
        id TEXT PRIMARY KEY, agent TEXT NOT NULL, nonce TEXT NOT NULL,
        fingerprint TEXT NOT NULL, operation TEXT NOT NULL, target TEXT NOT NULL,
        state TEXT NOT NULL, created TEXT NOT NULL, expires TEXT NOT NULL,
        approved_by TEXT, approved_until TEXT, response TEXT,
        UNIQUE(agent,nonce)
    )""")


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
    if envelope["operation"] == "research":
        source, _, identifier = target.partition(":")
        if canonical(source, identifier) != target:
            raise ValueError("research target must be canonical")
    elif not 1 <= len(target) <= 200:
        raise ValueError("invalid search query")
    init_requests(store)
    fingerprint = hashlib.sha256(payload).hexdigest()
    with store.transaction():
        existing = store.db.execute("SELECT fingerprint,response FROM requests WHERE id=?", (envelope["request_id"],)).fetchone()
        if existing:
            if existing[0] != fingerprint:
                raise ValueError("request ID reused for different content")
            return json.loads(existing[1])
        recent = store.db.execute("SELECT count(*) FROM requests WHERE agent=? AND created>?",
            (envelope["agent"], (clock - timedelta(hours=1)).isoformat())).fetchone()[0]
        if recent >= 20:
            raise ValueError("agent request rate limit")
        response = {"request_id": envelope["request_id"], "state": "pending_user_approval"}
        if envelope["operation"] == "search":
            response = {"request_id": envelope["request_id"], "results": search(store, target), "state": "complete"}
        store.db.execute("INSERT INTO requests(id,agent,nonce,fingerprint,operation,target,state,created,expires,response) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (envelope["request_id"], envelope["agent"], envelope["nonce"], fingerprint, envelope["operation"], target,
             "complete" if envelope["operation"] == "search" else "pending", clock.isoformat(),
             (clock + timedelta(hours=24)).isoformat(), json.dumps(response, ensure_ascii=False)))
    return response


def approve(store, request_id, actor, at=None):
    init_requests(store)
    clock = at or datetime.now(timezone.utc)
    with store.transaction():
        row = store.db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        if not row or row["state"] not in ("pending", "failed") or datetime.fromisoformat(row["expires"]) < clock:
            raise ValueError("request cannot be approved")
        store.db.execute("UPDATE requests SET state='approved',approved_by=?,approved_until=? WHERE id=?",
            (actor, (clock + timedelta(minutes=15)).isoformat(), request_id))
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
        store.db.execute("UPDATE requests SET state='executing' WHERE id=?", (request_id,))
    try:
        result = handler(row["target"])
    except Exception:
        store.db.execute("UPDATE requests SET state='failed' WHERE id=?", (request_id,))
        raise
    store.db.execute("UPDATE requests SET state='complete',response=? WHERE id=?", (json.dumps({"request_id": request_id, "state": "complete", "key": result["key"]}), request_id))
    return result

import os
import re
import time
from urllib.parse import quote, urlencode

from .http import HTTP, RemoteError
from .models import Candidate
from .store import now


SCHEMA = {"Title": "title", "Type": "select", "Canonical ID": "rich_text", "Source URL": "url",
          "Status": "select", "Recommended on": "date", "Relevance": "number", "Summary": "rich_text",
          "Why it matters to me": "rich_text", "Tags": "multi_select", "Feedback": "select",
          "My notes": "rich_text", "Published on": "date", "Discovered on": "date",
          "Verification status": "select"}


def rich(value):
    return [{"type": "text", "text": {"content": str(value)[start:start + 1900]}}
            for start in range(0, min(len(str(value)), 19000), 1900)]


def plain(prop):
    return "".join(value.get("plain_text", value.get("text", {}).get("content", ""))
                   for value in prop.get(prop.get("type", "rich_text"), []) or [])


def uuid(value):
    if not re.fullmatch(r"[a-fA-F0-9-]{32,36}", value or ""):
        raise ValueError("Notion ID must be a UUID")
    return value


class Notion:
    def __init__(self, settings, store, http=None):
        self.settings, self.store = settings, store
        self.source = uuid(settings.notion_data_source_id)
        self.token = os.environ.get("NOTION_LIBRARY_TOKEN", "")
        if not self.token:
            raise ValueError("NOTION_LIBRARY_TOKEN required")
        self.http = http or HTTP({"api.notion.com"})

    def request(self, method, path, payload=None, safe=False):
        time.sleep(.35)  # Stay below Notion's nominal per-integration request rate.
        data, _ = self.http.json(method, "https://api.notion.com/v1/" + path, payload=payload,
            headers={"Authorization": "Bearer " + self.token, "Notion-Version": self.settings.notion_version},
            retry_safe=safe)
        return data

    def validate(self):
        schema = self.request("GET", f"data_sources/{self.source}")["properties"]
        if any(schema.get(name, {}).get("type") != kind for name, kind in SCHEMA.items()):
            raise ValueError("Research Library schema does not match docs/notion-schema.md")

    def query(self, filter=None):
        cursor = None
        seen = set()
        for _ in range(1000):
            payload = {"page_size": 100}
            if filter:
                payload["filter"] = filter
            if cursor:
                payload["start_cursor"] = cursor
            data = self.request("POST", f"data_sources/{self.source}/query", payload, safe=True)
            yield from data["results"]
            if not data.get("has_more"):
                return
            cursor = data.get("next_cursor")
            if not cursor or cursor in seen:
                raise ValueError("Notion pagination did not advance")
            seen.add(cursor)
        raise ValueError("Library pagination limit reached")

    def sync(self):
        pages = list(self.query())  # Do not mark sync successful on a partial read.
        keys, conflicts = set(), []
        counts = {}
        for page in pages:
            try:
                key = plain(page["properties"]["Canonical ID"])
                counts[key] = counts.get(key, 0) + 1
            except (TypeError, KeyError, AttributeError):
                pass
        self.store.db.execute("UPDATE state SET value='false' WHERE key LIKE 'conflict:%'")
        for page in pages:
            key = ""
            try:
                props = page["properties"]
                key = plain(props["Canonical ID"])
                if not key or counts[key] > 1:
                    raise ValueError("duplicate/empty canonical key")
                item = Candidate(key, plain(props["Title"]), props["Type"]["select"]["name"],
                                 props["Source URL"]["url"], text=plain(props["Summary"]))
                status = (props["Status"].get("select") or {}).get("name", "New")
                if status not in {"New", "Recommended", "Reading", "Deep-dived", "Skipped"}:
                    raise ValueError("invalid Library status")
                date = (props.get("Recommended on", {}).get("date") or {}).get("start")
                feedback = (props.get("Feedback", {}).get("select") or {}).get("name")
                uuid(page["id"])
                if not self.store.db.execute("SELECT 1 FROM items WHERE key=?", (key,)).fetchone():
                    self.store.add(item)
                self.store.db.execute("UPDATE items SET page_id=?,status=?,recommended=?,feedback=? WHERE key=?",
                                      (page["id"], status, date, feedback, key))
                keys.add(key)
                self.store.set_state("conflict:" + key, False)
            except (ValueError, TypeError, KeyError, AttributeError):
                conflicts.append({"key": key, "page_id": page.get("id")})
                if key:
                    self.store.set_state("conflict:" + key, True)
        self.store.set_state("library_conflicts", conflicts)
        self.store.set_state("library_synced", now())
        return len(keys)

    def ensure_page(self, item):
        if self.store.get_state("conflict:" + item.key):
            raise ValueError("item blocked by Library conflict")
        # Query exact canonical ID even after a previous timeout; never blindly repeat create.
        matches = list(self.query({"property": "Canonical ID", "rich_text": {"equals": item.key}}))
        if len(matches) > 1:
            raise ValueError("duplicate Library pages")
        if matches:
            page_id = matches[0]["id"]
        elif self.store.get_state("create_uncertain:" + item.key):
            raise ValueError("uncertain Notion creation requires operator reconciliation")
        else:
            props = {"Title": {"title": rich(item.title)}, "Type": {"select": {"name": item.kind}},
                "Canonical ID": {"rich_text": rich(item.key)}, "Source URL": {"url": item.url},
                "Status": {"select": {"name": "New"}}, "Discovered on": {"date": {"start": now()}},
                "Verification status": {"select": {"name": "Unverified"}}}
            if item.published:
                try:
                    from datetime import datetime
                    parsed = datetime.fromisoformat(item.published.replace("Z", "+00:00"))
                    props["Published on"] = {"date": {"start": parsed.isoformat()}}
                except ValueError:
                    pass  # RSS dates stay in provenance until normalized.
            # Persist before sending, also covering process death after remote acceptance.
            self.store.set_state("create_uncertain:" + item.key, True)
            try:
                page = self.request("POST", "pages", {"parent": {"type": "data_source_id", "data_source_id": self.source},
                                                           "properties": props})
            except RemoteError as error:
                if not error.uncertain:
                    self.store.set_state("create_uncertain:" + item.key, False)
                raise
            page_id = page["id"]
        uuid(page_id)
        self.store.db.execute("UPDATE items SET page_id=? WHERE key=?", (page_id, item.key))
        self.store.set_state("create_uncertain:" + item.key, False)
        return page_id

    def patch_owned(self, key, properties):
        if not set(properties) <= {"Status", "Recommended on", "Relevance", "Summary", "Why it matters to me", "Tags", "Verification status"}:
            raise ValueError("attempt to write user-owned or identity fields")
        row = self.store.db.execute("SELECT page_id FROM items WHERE key=?", (key,)).fetchone()
        if not row or not row[0]:
            raise ValueError("item has no Library page")
        page = self.request("GET", "pages/" + uuid(row[0]))
        parent = page.get("parent", {})
        if parent.get("data_source_id", "").replace("-", "") != self.source.replace("-", ""):
            raise ValueError("page outside Research Library")
        self.request("PATCH", "pages/" + uuid(row[0]), {"properties": properties})


def read_profile(settings, http=None):
    page = uuid(settings.notion_profile_page_id)
    token = os.environ.get("NOTION_PROFILE_TOKEN", "")
    if not token:
        raise ValueError("separate NOTION_PROFILE_TOKEN required")
    client = http or HTTP({"api.notion.com"})
    data, _ = client.json("GET", f"https://api.notion.com/v1/blocks/{page}/children?page_size=100",
        headers={"Authorization": "Bearer " + token, "Notion-Version": settings.notion_version})
    if data.get("has_more") or any(block.get("has_children") for block in data["results"]):
        raise ValueError("Profile must be one flat page of at most 100 blocks")
    return "\n".join(plain({"type": "rich_text", "rich_text": block.get(block["type"], {}).get("rich_text", [])})
                     for block in data["results"])[:20000]

from datetime import datetime, timedelta, timezone
import re
import time
import signal
from urllib.parse import urlencode, urlsplit
import xml.etree.ElementTree as ET

from .http import HTTP, FetchDeadline
from .models import Candidate, canonical


ATOM = "{http://www.w3.org/2005/Atom}"


def xml_entries(data):
    decoded = data.decode("utf-8-sig")
    if "\x00" in decoded or re.search(r'encoding=[\'\"](?!utf-8)[^\'\"]+', decoded, re.I):
        raise ValueError("feed must use UTF-8")
    if "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
        raise ValueError("XML declarations are not allowed")
    root = ET.fromstring(decoded)
    return root.findall(f"{ATOM}entry") or root.findall("./channel/item")


def text(entry, atom_name, rss_name=None):
    return " ".join((entry.findtext(ATOM + atom_name) or entry.findtext(rss_name or atom_name) or "").split())


def parse_arxiv(data, skipped=lambda: None):
    for entry in xml_entries(data):
        try:
            key = canonical("arxiv", text(entry, "id"))
            yield Candidate(key, text(entry, "title"), "Paper", "https://arxiv.org/abs/" + key[6:],
                            text(entry, "published"), text(entry, "summary"),
                            metadata={"version_url": text(entry, "id"), "coverage": "abstract"})
        except (ValueError, TypeError, KeyError):
            skipped()


def parse_frontier(data, feed_url, skipped=lambda: None):
    host = urlsplit(feed_url).hostname
    for entry in xml_entries(data):
        links = entry.findall(ATOM + "link")
        url = next((node.get("href", "") for node in links if node.get("rel", "alternate") == "alternate"), "")
        url = url or entry.findtext("link", "")
        if urlsplit(url).hostname != host or urlsplit(url).scheme != "https":
            continue
        try:
            yield Candidate(canonical("frontier", url), text(entry, "title"), "Frontier LLM", url,
                            text(entry, "published", "pubDate") or text(entry, "updated"),
                            text(entry, "summary", "description"), metadata={"publisher": host, "coverage": "feed"})
        except (ValueError, TypeError, KeyError):
            skipped()


class Sources:
    def __init__(self, settings, http=None, sleep=time.sleep):
        self.settings = settings
        feeds = settings.sources.get("frontier_feeds", [])
        hosts = {"export.arxiv.org", "api.github.com", "huggingface.co"}
        hosts.update(urlsplit(url).hostname for url in feeds)
        self.http = http or HTTP(hosts)
        self.sleep = sleep
        self.skipped = 0
        self.feed_failures = 0

    def skip(self):
        self.skipped += 1

    def arxiv(self):
        categories = self.settings.sources.get("arxiv_categories", [])
        if not categories:
            return []
        since = (datetime.now(timezone.utc) - timedelta(days=self.settings.lookback_days)).strftime("%Y%m%d0000")
        query = "(" + " OR ".join("cat:" + c for c in categories) + ") AND submittedDate:[" + since + " TO 299912312359]"
        items = []
        # Bounded pages; truncation is exposed to the run report.
        for start in range(0, self.settings.candidate_limit + 1, 100):
            if start:
                self.sleep(3)
            url = "https://export.arxiv.org/api/query?" + urlencode({"search_query": query,
                "sortBy": "submittedDate", "sortOrder": "descending", "start": start, "max_results": 100})
            data, _ = self.http.request("GET", url)
            page = list(parse_arxiv(data, self.skip))
            items.extend(page)
            if len(xml_entries(data)) < 100 or len(items) >= self.settings.candidate_limit:
                break
        return items

    def github(self):
        items = []
        topics = self.settings.sources.get("github_topics", [])
        quota = max(1, self.settings.candidate_limit // max(1, len(topics) * 2))
        for topic in topics:
            since = (datetime.now(timezone.utc) - timedelta(days=self.settings.lookback_days)).date().isoformat()
            for mode in ("created", "pushed"):
                url = "https://api.github.com/search/repositories?" + urlencode({
                    "q": f"topic:{topic} {mode}:>={since} archived:false is:public", "sort": "stars",
                    "per_page": min(quota, 100), "page": 1})
                data, _ = self.http.json("GET", url)
                if data.get("incomplete_results"):
                    raise ValueError("GitHub search incomplete; narrow topics")
                for row in data["items"]:
                    try:
                        items.append(Candidate(canonical("github", str(row["id"])), row["full_name"], "Repo",
                            row["html_url"], row.get("created_at", ""), row.get("description") or "",
                            aliases=[row["full_name"]], metadata={"stars": row["stargazers_count"],
                                "pushed_at": row.get("pushed_at"), "coverage": "metadata", "topic": topic,
                                "discovery": mode, "query_total": data.get("total_count", 0), "query_limit": min(quota, 100)}))
                    except (ValueError, TypeError, KeyError):
                        self.skip()
                self.sleep(7)  # Public unauthenticated search quota.
        return items

    def huggingface(self):
        items = []
        tasks = self.settings.sources.get("hf_tasks", [])
        quota = max(1, self.settings.candidate_limit // max(1, len(tasks)))
        for task in tasks:
            url = "https://huggingface.co/api/models?" + urlencode({"pipeline_tag": task,
                "sort": "createdAt", "direction": -1, "limit": min(100, quota), "full": "true", "cardData": "true"})
            data, _ = self.http.json("GET", url)
            for row in data:
                try:
                    identifier = row.get("id") or row["modelId"]
                    card = row.get("cardData") or {}
                    license = card.get("license") or next((tag[8:] for tag in row.get("tags", []) if tag.startswith("license:")), None)
                    items.append(Candidate(canonical("hf", identifier), identifier,
                        "Open model (LLM)" if task in ("text-generation", "text2text-generation") else "Open model (CV)",
                        "https://huggingface.co/" + identifier, row.get("createdAt", ""),
                        f"Task: {task}. License metadata: {license or 'unknown'}. Availability needs verification.",
                        metadata={"license": license, "gated": row.get("gated"),
                                  "downloads": row.get("downloads"), "coverage": "metadata", "task": task}))
                except (ValueError, TypeError, KeyError):
                    self.skip()
        return items

    def frontier(self):
        items = []
        for feed in self.settings.sources.get("frontier_feeds", []):
            try:
                data, _ = self.http.request("GET", feed)
                items.extend(parse_frontier(data, feed, self.skip))
            except Exception:
                self.feed_failures += 1
        return items

    def collect(self):
        previous = signal.getsignal(signal.SIGALRM)
        def expired(*_):
            raise FetchDeadline()
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, 600)
        try:
            return self._collect()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)

    def _collect(self):
        items, health = [], {}
        started = time.monotonic()
        for name in ("arxiv", "github", "huggingface", "frontier"):
            if time.monotonic() - started >= 600:
                health[name] = {"ok": False, "error_type": "RunDeadline"}
                continue
            self.skipped = 0
            try:
                batch = getattr(self, name)()
                health[name] = {"ok": True, "fetched": len(batch),
                                "clipped": len(batch) > self.settings.candidate_limit,
                                "skipped": self.skipped}
                if name == "frontier":
                    health[name]["configured_feeds"] = len(self.settings.sources.get("frontier_feeds", []))
                    health[name]["failed_feeds"] = self.feed_failures
                    health[name]["ok"] = not self.feed_failures
                items.extend(batch[:self.settings.candidate_limit])
            except Exception as error:
                # A source outage must not discard successful sources or expose response text.
                health[name] = {"ok": False, "error_type": type(error).__name__}
        return list({item.key: item for item in items}.values()), health

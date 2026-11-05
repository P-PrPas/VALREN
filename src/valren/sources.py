from datetime import datetime, timedelta, timezone
import re
import time
from urllib.parse import urlencode, urlsplit
import xml.etree.ElementTree as ET

from .http import HTTP
from .models import Candidate, canonical


ATOM = "{http://www.w3.org/2005/Atom}"


def xml_entries(data):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML declarations are not allowed")
    root = ET.fromstring(data)
    return root.findall(f"{ATOM}entry") or root.findall("./channel/item")


def text(entry, atom_name, rss_name=None):
    return " ".join((entry.findtext(ATOM + atom_name) or entry.findtext(rss_name or atom_name) or "").split())


def parse_arxiv(data):
    for entry in xml_entries(data):
        key = canonical("arxiv", text(entry, "id"))
        yield Candidate(key, text(entry, "title"), "Paper", "https://arxiv.org/abs/" + key[6:],
                        text(entry, "published"), text(entry, "summary"),
                        metadata={"version_url": text(entry, "id"), "coverage": "abstract"})


def parse_frontier(data, feed_url):
    host = urlsplit(feed_url).hostname
    for entry in xml_entries(data):
        links = entry.findall(ATOM + "link")
        url = next((node.get("href", "") for node in links if node.get("rel", "alternate") == "alternate"), "")
        url = url or entry.findtext("link", "")
        if urlsplit(url).hostname != host or urlsplit(url).scheme != "https":
            continue
        yield Candidate(canonical("frontier", url), text(entry, "title"), "Frontier LLM", url,
                        text(entry, "published", "pubDate") or text(entry, "updated"),
                        text(entry, "summary", "description"), metadata={"publisher": host, "coverage": "feed"})


class Sources:
    def __init__(self, settings, http=None, sleep=time.sleep):
        self.settings = settings
        feeds = settings.sources.get("frontier_feeds", [])
        hosts = {"export.arxiv.org", "api.github.com", "huggingface.co"}
        hosts.update(urlsplit(url).hostname for url in feeds)
        self.http = http or HTTP(hosts)
        self.sleep = sleep

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
            page = list(parse_arxiv(data))
            items.extend(page)
            if len(page) < 100 or len(items) > self.settings.candidate_limit:
                break
        return items

    def github(self):
        items = []
        for topic in self.settings.sources.get("github_topics", []):
            since = (datetime.now(timezone.utc) - timedelta(days=self.settings.lookback_days)).date().isoformat()
            # Recently active, high-star repos; growth requires our own historical snapshots.
            for page in range(1, 4):
                url = "https://api.github.com/search/repositories?" + urlencode({
                    "q": f"topic:{topic} pushed:>={since} archived:false is:public", "sort": "stars",
                    "per_page": 100, "page": page})
                data, _ = self.http.json("GET", url)
                if data.get("incomplete_results"):
                    raise ValueError("GitHub search incomplete; narrow topics")
                for row in data["items"]:
                    items.append(Candidate(canonical("github", str(row["id"])), row["full_name"], "Repo",
                        row["html_url"], row.get("created_at", ""), row.get("description") or "",
                        aliases=[row["full_name"]], metadata={"stars": row["stargazers_count"],
                            "pushed_at": row.get("pushed_at"), "coverage": "metadata", "topic": topic}))
                if len(data["items"]) < 100 or len(items) > self.settings.candidate_limit:
                    break
                self.sleep(7)  # Public unauthenticated search quota.
            self.sleep(7)
        return items

    def huggingface(self):
        items = []
        for task in self.settings.sources.get("hf_tasks", []):
            url = "https://huggingface.co/api/models?" + urlencode({"pipeline_tag": task,
                "sort": "createdAt", "direction": -1, "limit": min(100, self.settings.candidate_limit), "full": "true"})
            data, _ = self.http.json("GET", url)
            for row in data:
                identifier = row.get("id") or row["modelId"]
                card = row.get("cardData") or {}
                items.append(Candidate(canonical("hf", identifier), identifier,
                    "Open model (LLM)" if task in ("text-generation", "text2text-generation") else "Open model (CV)",
                    "https://huggingface.co/" + identifier, row.get("createdAt", ""),
                    f"Task: {task}. License metadata: {card.get('license', 'unknown')}. Availability needs verification.",
                    metadata={"license": card.get("license"), "gated": row.get("gated"),
                              "downloads": row.get("downloads"), "coverage": "metadata", "task": task}))
        return items

    def frontier(self):
        items = []
        for feed in self.settings.sources.get("frontier_feeds", []):
            data, _ = self.http.request("GET", feed)
            items.extend(parse_frontier(data, feed))
        return items

    def collect(self):
        items, health = [], {}
        for name in ("arxiv", "github", "huggingface", "frontier"):
            try:
                batch = getattr(self, name)()
                health[name] = {"ok": True, "fetched": len(batch),
                                "clipped": len(batch) > self.settings.candidate_limit}
                items.extend(batch[:self.settings.candidate_limit])
            except Exception as error:
                # A source outage must not discard successful sources or expose response text.
                health[name] = {"ok": False, "error_type": type(error).__name__}
        return list({item.key: item for item in items}.values()), health

from unittest.mock import patch
import unittest

from valren.config import Settings
from valren.http import HTTP, public_address, RemoteError
from valren.models import Candidate
from valren.notion import Notion, rich
from valren.pipeline import ingest
from valren.sources import parse_arxiv, parse_frontier, Sources
from valren.store import Store


class RadarTests(unittest.TestCase):
    def test_arxiv_version_and_xml_injection(self):
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2401.12345v2</id><title>AI</title><summary>Abstract</summary></entry></feed>'
        item = list(parse_arxiv(atom))[0]
        self.assertEqual(item.key, "arxiv:2401.12345")
        self.assertTrue(item.metadata["version_url"].endswith("v2"))
        with self.assertRaises(ValueError):
            list(parse_arxiv(b'<!DOCTYPE x><feed/>'))

    def test_public_dns_and_redirect_policy(self):
        for address in ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1"]:
            with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", (address, 443))]):
                with self.assertRaises(ValueError):
                    public_address("example.com")
        for url in ["http://api.github.com/x", "https://user:pw@api.github.com/x", "https://localhost/x"]:
            with self.assertRaises(ValueError):
                HTTP({"api.github.com"}).request("GET", url)

    def test_frontier_filters_untrusted_links(self):
        rss = b'<rss><channel><item><title>New</title><link>https://evil.com/x</link></item><item><title>Release</title><link>https://lab.example/release</link></item></channel></rss>'
        self.assertEqual(len(list(parse_frontier(rss, "https://lab.example/rss"))), 1)

    def test_partial_sources_and_rerun(self):
        settings = Settings()
        sources = Sources(settings, http=object(), sleep=lambda _: None)
        with patch.object(sources, "arxiv", side_effect=RemoteError(503)):
            items, health = sources.collect()
        self.assertFalse(health["arxiv"]["ok"])
        store = Store(":memory:")
        item = Candidate("github:1", "a/b", "Repo", "https://github.com/a/b")
        self.assertEqual(ingest(settings, store, [item])["added"], 1)
        self.assertEqual(ingest(settings, store, [item])["duplicates"], 1)
        store.close()

    def test_notion_create_timeout_is_not_blindly_retried(self):
        store = Store(":memory:")
        item = Candidate("github:1", "a/b", "Repo", "https://github.com/a/b")
        store.add(item)
        with patch.dict("os.environ", {"NOTION_LIBRARY_TOKEN": "test"}):
            client = Notion(Settings(notion_data_source_id="a" * 32), store, http=object())
        with patch.object(client, "query", return_value=iter([])), patch.object(client, "request", side_effect=RemoteError(uncertain=True)) as request:
            with self.assertRaises(RemoteError):
                client.ensure_page(item)
            self.assertEqual(request.call_count, 1)
        with patch.object(client, "query", return_value=iter([])), patch.object(client, "request") as request:
            with self.assertRaises(ValueError):
                client.ensure_page(item)
            request.assert_not_called()
        with self.assertRaises(ValueError):
            client.patch_owned(item.key, {"My notes": {"rich_text": rich("overwrite")}})
        store.close()

from unittest.mock import patch
import unittest

from valren.config import Settings
from valren.http import HTTP, public_address, RemoteError
from valren.models import Candidate
from valren.notion import Notion, rich
from valren.pipeline import ingest
from valren.sources import parse_arxiv, parse_frontier, Sources
from valren.store import Store
from valren.pipeline import worker_lock
from valren.config import local_path
from pathlib import Path
import tempfile


class RadarTests(unittest.TestCase):
    def test_recommendation_does_not_overwrite_new_user_status(self):
        store = Store(":memory:")
        item = Candidate("github:1", "a/b", "Repo", "https://github.com/a/b")
        store.add(item)
        store.db.execute("UPDATE items SET page_id=?", ("a" * 32,))
        with patch.dict("os.environ", {"NOTION_LIBRARY_TOKEN": "test"}):
            client = Notion(Settings(notion_data_source_id="b" * 32), store, http=object())
        page = {"parent": {"data_source_id": "b" * 32}, "properties": {"Status": {"select": {"name": "Reading"}}}}
        with patch.object(client, "request", return_value=page) as request:
            with self.assertRaises(ValueError):
                client.patch_owned(item.key, {"Status": {"select": {"name": "Recommended"}}})
            self.assertEqual(request.call_count, 1)
        store.close()
    def test_lock_contention(self):
        with tempfile.TemporaryDirectory(dir=local_path(".")) as directory:
            path = Path(directory)/"worker.lock"
            with worker_lock(path):
                with self.assertRaises(ValueError):
                    with worker_lock(path):
                        pass

    def test_http_retry_and_redirect_rejection(self):
        from unittest.mock import MagicMock
        response = MagicMock(status=429)
        response.getheaders.return_value = [("Retry-After", "1")]
        response.read.return_value = b'{}'
        success = MagicMock(status=200)
        success.getheaders.return_value = []
        success.read.return_value = b'{}'
        connection = MagicMock()
        connection.getresponse.side_effect = [response, success]
        delays = []
        with patch("valren.http.public_address", return_value="1.1.1.1"), patch("valren.http.PinnedHTTPS", return_value=connection):
            HTTP({"example.com"}, sleep=delays.append).json("GET", "https://example.com/x")
        self.assertEqual(delays, [1])
        response.status = 302
        connection.getresponse.side_effect = [response]
        with patch("valren.http.public_address", return_value="1.1.1.1"), patch("valren.http.PinnedHTTPS", return_value=connection):
            with self.assertRaises(RemoteError):
                HTTP({"example.com"}).request("GET", "https://example.com/x")

    def test_hf_license_and_bad_record_isolation(self):
        from unittest.mock import MagicMock
        http = MagicMock()
        http.json.return_value = ([{"id": "../.."}, {"id": "gpt2", "cardData": {"license": "mit"}}], {})
        source = Sources(Settings(sources={"hf_tasks": ["text-generation"]}), http=http)
        items = source.huggingface()
        self.assertEqual([item.key for item in items], ["hf:gpt2"])
        self.assertEqual(items[0].metadata["license"], "mit")
        self.assertIn("cardData=true", http.json.call_args.args[1])
        self.assertEqual(source.skipped, 1)

    def test_sync_conflicts_dont_drop_fetched_data(self):
        from unittest.mock import MagicMock
        store = Store(":memory:")
        notion = MagicMock()
        notion.sync.side_effect = RemoteError(401)
        item = Candidate("github:1", "a/b", "Repo", "https://github.com/a/b")
        report = ingest(Settings(), store, [item], notion=notion)
        self.assertFalse(report["ok"])
        self.assertEqual(len(store.pending()), 1)
        store.close()

    def test_notion_definite_failure_can_retry(self):
        store = Store(":memory:")
        item = Candidate("github:1", "a/b", "Repo", "https://github.com/a/b")
        store.add(item)
        with patch.dict("os.environ", {"NOTION_LIBRARY_TOKEN": "test"}):
            client = Notion(Settings(notion_data_source_id="a" * 32), store, http=object())
        with patch.object(client, "query", side_effect=lambda *_: iter([])), patch.object(client, "request", side_effect=RemoteError(429)):
            for _ in range(2):
                with self.assertRaises(RemoteError):
                    client.ensure_page(item)
                self.assertFalse(store.get_state("create_uncertain:" + item.key))
        store.close()

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
        from unittest.mock import MagicMock
        sources = Sources(settings, http=MagicMock(), sleep=lambda _: None)
        with patch.object(sources, "arxiv", side_effect=RemoteError(503)):
            items, health = sources.collect()
        self.assertFalse(health["arxiv"]["ok"])
        store = Store(":memory:")
        item = Candidate("github:1", "a/b", "Repo", "https://github.com/a/b")
        self.assertEqual(ingest(settings, store, [item])["added"], 1)
        self.assertEqual(ingest(settings, store, [item])["duplicates"], 1)
        store.close()

    def test_removed_conflicts_can_recover(self):
        store = Store(":memory:")
        store.set_state("conflict:github:1", True)
        with patch.dict("os.environ", {"NOTION_LIBRARY_TOKEN": "test"}):
            client = Notion(Settings(notion_data_source_id="a" * 32), store, http=object())
        with patch.object(client, "query", return_value=iter([])):
            client.sync()
        self.assertFalse(store.get_state("conflict:github:1"))
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

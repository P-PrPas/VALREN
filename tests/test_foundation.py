import json
from pathlib import Path
import tempfile
import unittest

from valren.cli import main
from valren.config import Settings, local_path
from valren.models import Candidate, canonical
from valren.store import Store


class FoundationTests(unittest.TestCase):
    def test_untrusted_metadata_and_nested_config(self):
        for settings in [dict(interests={"confirmed": "false"}), dict(monthly_budget_usd=True),
                         dict(sources={"unknown": []}), dict(sources={"github_topics": "ai"})]:
            with self.assertRaises(ValueError):
                Settings(**settings)
        with self.assertRaises(ValueError):
            canonical("hf", "../..")
        with self.assertRaises(ValueError):
            canonical("frontier", "https://user:secret@example.com/release")
        self.assertEqual(canonical("frontier", "https://Example.com:443/release/#fragment"),
                         "frontier:https://example.com/release")
        with self.assertRaises(ValueError):
            Candidate("github:1", "wrong", "Paper", "https://github.com/a/b")

    def test_alias_reuse_and_backup(self):
        store = Store(":memory:")
        for key in ["github:1", "github:2", "hf:a/b"]:
            kind = "Repo" if key.startswith("github") else "Open model (LLM)"
            host = "github.com" if kind == "Repo" else "huggingface.co"
            store.add(Candidate(key, "a/b", kind, f"https://{host}/a/b", aliases=["a/b"]))
        self.assertEqual(store.db.execute("SELECT count(*) FROM aliases").fetchone()[0], 3)
        with tempfile.TemporaryDirectory(dir=local_path(".")) as directory:
            path = Path(directory)/"backup.sqlite3"
            store.backup(path)
            restored = Store(path)
            self.assertEqual(len(restored.pending()), 3)
            restored.close()
        store.close()

    def test_canonical_versions_and_rename(self):
        self.assertEqual(canonical("arxiv", "https://arxiv.org/pdf/2401.12345v2.pdf"), "arxiv:2401.12345")
        self.assertEqual(canonical("github", "00123"), "github:123")
        self.assertEqual(canonical("hf", "Lab/Model-A"), "hf:Lab/Model-A")
        with self.assertRaises(ValueError):
            canonical("github", "owner/repo")

    def test_config_rejects_invalid_limits_and_paths(self):
        for value in [0, -1, True, 1.5, 21]:
            with self.assertRaises(ValueError):
                Settings(daily_limit=value)
        with self.assertRaises(ValueError):
            Settings(monthly_budget_usd=float("nan"))
        with self.assertRaises(ValueError):
            local_path("../other-agent/secrets")

    def test_dedup_preserves_user_state_and_aliases(self):
        store = Store(":memory:")
        item = Candidate("github:123", "old/name", "Repo", "https://github.com/old/name", aliases=["old/name"])
        self.assertTrue(store.add(item))
        store.db.execute("UPDATE items SET status='Reading',feedback='Liked' WHERE key=?", (item.key,))
        item.title = "new/name"
        item.aliases = ["new/name"]
        self.assertFalse(store.add(item))
        row = store.db.execute("SELECT status,feedback FROM items").fetchone()
        self.assertEqual(tuple(row), ("Reading", "Liked"))
        self.assertEqual(store.db.execute("SELECT count(*) FROM aliases").fetchone()[0], 2)
        store.close()

    def test_fixture_dry_run_does_not_create_db(self):
        with tempfile.TemporaryDirectory(dir=local_path(".")) as directory:
            db = Path(directory)/"unused.sqlite3"
            fixture = Path(__file__).parent/"fixtures/candidates.json"
            self.assertEqual(main(["--db", str(db), "radar", "--dry-run", "--fixture", str(fixture)]), 0)
            self.assertFalse(db.exists())

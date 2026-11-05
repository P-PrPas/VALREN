import json
from pathlib import Path
import tempfile
import unittest

from valren.cli import main
from valren.config import Settings, local_path
from valren.models import Candidate, canonical
from valren.store import Store


class FoundationTests(unittest.TestCase):
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

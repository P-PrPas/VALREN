import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from valren.config import Settings
from valren.http import RemoteError
from valren.models import Candidate
from valren.store import Store
from valren.telegram import authorized, Telegram
from valren.tutor import source_chunks, teach


class TutorTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.settings = Settings(interests={"confirmed": True, "topics": ["AI"]}, telegram={"user_ids": [1], "chat_ids": [2]})

    def test_telegram_authorization(self):
        self.assertTrue(authorized(self.settings, {"from": {"id": 1}, "chat": {"id": 2}}))
        for message in [{"from": {"id": 3}, "chat": {"id": 2}}, {"from": {"id": 1}, "chat": {"id": 3}},
                        {"from": {"id": 1, "is_bot": True}, "chat": {"id": 2}}]:
            self.assertFalse(authorized(self.settings, message))

    def test_full_text_failure_discloses_abstract(self):
        http = MagicMock()
        http.request.side_effect = RemoteError(404)
        item = Candidate("arxiv:2401.12345", "paper", "Paper", "https://arxiv.org/abs/2401.12345", text="actual abstract")
        chunks, coverage = source_chunks(item, http)
        self.assertEqual(chunks, ["actual abstract"])
        self.assertIn("abstract-only", coverage)

    def test_lesson_reuses_paid_work_and_marks_status_after_persist(self):
        item = Candidate("github:1", "a/b", "Repo", "https://github.com/a/b", text="actual source", metadata={"coverage": "description"})
        self.store.add(item)
        llm = MagicMock()
        evidence = [{"source_id": item.key, "quote": "actual source"}]
        llm.complete.side_effect = [{"notes": "โน้ต", "evidence": evidence}, {"overview": "ภาพรวม", "glossary": [{"term": "AI", "meaning": "ปัญญาประดิษฐ์"}],
            "technical": {"problem": "ปัญหา", "method": "วิธี", "results": "ผล", "limitations": "ข้อจำกัด"}, "application": "เกี่ยวข้องกับงาน", "evidence": evidence}]
        notion = MagicMock()
        notion.save_lesson.side_effect = RemoteError(uncertain=True)
        with self.assertRaises(RemoteError):
            teach(self.settings, self.store, llm, notion, item.key, "AI")
        self.assertEqual(self.store.db.execute("SELECT status FROM items").fetchone()[0], "New")
        notion.save_lesson.side_effect = None
        lesson = teach(self.settings, self.store, llm, notion, item.key, "AI")
        self.assertTrue(lesson["persisted"])
        self.assertEqual(llm.complete.call_count, 2)
        self.assertEqual(self.store.db.execute("SELECT status FROM items").fetchone()[0], "Deep-dived")

    @patch("valren.telegram.quiet", return_value=False)
    def test_telegram_send_timeout_holds_reply(self, _quiet):
        http = MagicMock()
        http.json.side_effect = RemoteError(uncertain=True)
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "123:test"}):
            telegram = Telegram(self.settings, self.store, http)
        self.assertEqual(telegram.send(1, 2, "lesson"), "uncertain")
        self.assertEqual(telegram.send(1, 2, "lesson"), "uncertain")
        self.assertEqual(http.json.call_count, 1)

    def test_plugin_only_exposes_search_as_model_tool(self):
        path = Path(__file__).parents[1]/"hermes/valren_plugin/__init__.py"
        spec = importlib.util.spec_from_file_location("valren_test_plugin", path)
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        ctx = MagicMock()
        plugin.register(ctx)
        self.assertEqual(ctx.register_tool.call_count, 1)
        self.assertEqual(ctx.register_tool.call_args.kwargs["name"], "valren_library_search")
        with patch.object(plugin.subprocess, "run") as process:
            result = plugin.tutor_command("arxiv:2401.12345", platform="telegram", source=None)
            self.assertIn("ValueError", result)
            process.assert_not_called()

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import unittest

from valren.agent_net import receive, approve, run_approved
from valren.config import Settings, local_path
from valren.feedback import apply_taste, record_feedback, feedback_buttons, button_feedback
from valren.models import Candidate
from valren.scheduler import tick, control_path
from valren.store import Store


class FeedbackRequestTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.settings = Settings(agent_net={"enabled": True, "allowed_agents": ["Malren"]})
        self.at = datetime(2026, 11, 6, 1, tzinfo=timezone.utc)
        self.signing_key = "test-only-not-a-real-signing-key-12345678"

    def envelope(self, operation="research", target="arxiv:2401.12345", request_id="request-0000000001"):
        result = {"version": 1, "agent": "Malren", "request_id": request_id, "nonce": request_id,
                  "issued_at": self.at.isoformat(), "operation": operation, "target": target}
        result["signature"] = hmac.new(self.signing_key.encode(), json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(), hashlib.sha256).hexdigest()
        return result

    def receive(self, envelope):
        with patch.dict("os.environ", {"VALREN_AGENT_NET_KEYS_JSON": json.dumps({"Malren": self.signing_key})}):
            return receive(self.settings, self.store, envelope, self.at)

    def test_signed_research_needs_single_use_expiring_user_approval(self):
        response = self.receive(self.envelope())
        self.assertEqual(response["state"], "pending_user_approval")
        handler = MagicMock(return_value={"key": "arxiv:2401.12345"})
        with self.assertRaises(ValueError):
            run_approved(self.store, response["request_id"], handler, self.at)
        handler.assert_not_called()
        approve(self.store, response["request_id"], "telegram:1", "arxiv:2401.12345", self.at)
        result = run_approved(self.store, response["request_id"], handler, self.at)
        self.assertEqual(result["key"], "arxiv:2401.12345")
        with self.assertRaises(ValueError):
            run_approved(self.store, response["request_id"], handler, self.at)
        self.assertEqual(handler.call_count, 1)

    def test_signature_replay_scope_and_expiry(self):
        envelope = self.envelope()
        envelope["target"] = "arxiv:2401.99999"
        with self.assertRaises(ValueError):
            self.receive(envelope)
        response = self.receive(self.envelope())
        self.assertEqual(self.receive(self.envelope()), response)
        with self.assertRaises(ValueError):
            self.receive(self.envelope(operation="write_file", request_id="request-0000000002"))
        approve(self.store, response["request_id"], "local-operator", "arxiv:2401.12345", self.at)
        with self.assertRaises(ValueError):
            run_approved(self.store, response["request_id"], MagicMock(), self.at + timedelta(minutes=16))

    def test_disliked_reduces_related_score_and_buttons_bind_chat(self):
        items = [Candidate(f"github:{i}", f"a/repo{i}", "Repo", f"https://github.com/a/repo{i}", metadata={"topic": topic})
                 for i, topic in [(1, "agents"), (2, "agents"), (3, "vision")]]
        for item in items:
            self.store.add(item)
        record_feedback(self.store, MagicMock(), items[0].key, "Disliked")
        result = apply_taste(self.store, items[1:], [{"key": item.key, "score": 4} for item in items[1:]])
        self.assertEqual({row["key"]: row["score"] for row in result}, {"github:2": 3, "github:3": 4})
        buttons = feedback_buttons(self.store, items[1].key, 2)
        data = buttons["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.assertLess(len(data.encode()), 64)
        with self.assertRaises(ValueError):
            button_feedback(self.store, MagicMock(), {"data": data, "message": {"chat": {"id": 99}}})
        self.assertIn("Liked", button_feedback(self.store, MagicMock(), {"data": data, "message": {"chat": {"id": 2}}}))

    def test_scheduler_claims_day_and_reuses_completed_steps(self):
        with tempfile.TemporaryDirectory(dir=local_path(".")) as directory:
            db = str(Path(directory)/"test.sqlite3")
            runner = MagicMock(return_value=MagicMock(returncode=0))
            first = tick(Settings(), db, runner=runner, at=self.at)
            second = tick(Settings(), db, runner=runner, at=self.at)
            self.assertEqual(first["state"], "done")
            self.assertEqual(second["state"], "done")
            self.assertEqual(runner.call_count, 1)
            self.assertNotIn("recommend", runner.call_args.args[0])

    def test_scheduler_partial_radar_still_recommends_and_delivers(self):
        with tempfile.TemporaryDirectory(dir=local_path(".")) as directory:
            db = str(Path(directory)/"test.sqlite3")
            runner = MagicMock(side_effect=[MagicMock(returncode=code) for code in (2, 0, 0)])
            settings = Settings(monthly_budget_usd=1, interests={"confirmed": True})
            result = tick(settings, db, paid=True, sending=True, sync=True, runner=runner, at=self.at)
            self.assertEqual(result["state"], "done")
            self.assertTrue(result["partial_radar"])
            self.assertEqual(result["steps"], ["radar", "recommend", "deliver"])

    def test_scheduler_runner_failure_and_stale_lease_recover(self):
        with tempfile.TemporaryDirectory(dir=local_path(".")) as directory:
            path = Path(directory)/"test.sqlite3"
            failed = tick(Settings(), str(path), runner=MagicMock(side_effect=OSError()), at=self.at)
            self.assertEqual(failed["state"], "failed")
            control = Store(control_path(path))
            control.set_state("schedule:2026-11-06", {"state": "running", "attempts": 1, "steps": [], "claimed_at": self.at.isoformat()})
            control.close()
            recovered = tick(Settings(), str(path), runner=MagicMock(return_value=MagicMock(returncode=0)), at=self.at + timedelta(hours=2))
            self.assertEqual((recovered["state"], recovered["attempts"]), ("done", 2))

    def test_scheduler_busy_does_not_spend_attempt(self):
        with tempfile.TemporaryDirectory(dir=local_path(".")) as directory:
            db = str(Path(directory)/"test.sqlite3")
            runner = MagicMock(side_effect=[MagicMock(returncode=75), MagicMock(returncode=0)])
            busy = tick(Settings(), db, runner=runner, at=self.at)
            self.assertEqual(busy["attempts"], 0)
            recovered = tick(Settings(), db, runner=runner, at=self.at + timedelta(minutes=6))
            self.assertEqual((recovered["state"], recovered["attempts"]), ("done", 1))

    def test_stale_executing_requires_target_confirmation_and_can_recover(self):
        envelope = self.envelope()
        response = self.receive(envelope)
        identifier = response["request_id"]
        with self.assertRaises(ValueError):
            approve(self.store, identifier, "local", "arxiv:2401.99999", self.at)
        approve(self.store, identifier, "local", "arxiv:2401.12345", self.at)
        with self.assertRaises(SystemExit):
            run_approved(self.store, identifier, MagicMock(side_effect=SystemExit()), self.at)
        with self.assertRaises(ValueError):
            approve(self.store, identifier, "local", "arxiv:2401.12345", self.at + timedelta(minutes=1))
        later = self.at + timedelta(hours=2)
        approve(self.store, identifier, "local", "arxiv:2401.12345", later)
        run_approved(self.store, identifier, lambda _: {"key": "arxiv:2401.12345"}, later)
        with patch.dict("os.environ", {"VALREN_AGENT_NET_KEYS_JSON": json.dumps({"Malren": self.signing_key})}):
            status = receive(self.settings, self.store, envelope, later)
        self.assertEqual(status["state"], "complete")

    def test_request_rate_limit_boundary(self):
        for number in range(20):
            self.receive(self.envelope(operation="search", target="AI", request_id=f"request-{number:016}"))
        with self.assertRaises(ValueError):
            self.receive(self.envelope(operation="search", target="AI", request_id="request-9999999999999999"))

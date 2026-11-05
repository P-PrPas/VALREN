import json
import os
import re

from .delivery import quiet
from .http import HTTP, RemoteError


def authorized(settings, message):
    return (type(message.get("from", {}).get("id")) is int
            and message["from"]["id"] in settings.telegram.get("user_ids", [])
            and message.get("chat", {}).get("id") in settings.telegram.get("chat_ids", [])
            and not message["from"].get("is_bot", False)
            and not message.get("forward_origin"))


class Telegram:
    def __init__(self, settings, store, http=None):
        self.settings, self.store = settings, store
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
            raise ValueError("dedicated TELEGRAM_BOT_TOKEN required")
        if not settings.telegram.get("user_ids") or not settings.telegram.get("chat_ids"):
            raise ValueError("Telegram user and chat allowlists required")
        self.base = "https://api.telegram.org/bot" + token + "/"
        self.http = http or HTTP({"api.telegram.org"})

    def request(self, method, payload):
        data, _ = self.http.json("POST", self.base + method, payload=payload, retry_safe=method == "getUpdates")
        if not data.get("ok"):
            status = data.get("error_code", 0)
            raise RemoteError(status, uncertain=status >= 500)
        return data["result"]

    def send(self, update_id, chat, body):
        state_key = f"telegram-reply:{update_id}"
        saved = self.store.get_state(state_key, {"parts": [], "chat": chat, "body": body, "state": "ready"})
        self.store.set_state(state_key, saved)
        if saved["state"] in ("sent", "uncertain", "failed"):
            return saved["state"]
        # Keep all parts small by Unicode code points, never parse untrusted markup.
        parts = [body[start:start + 3500] for start in range(0, len(body), 3500)]
        for index, part in enumerate(parts):
            if quiet(self.settings):
                return "deferred"
            if index < len(saved["parts"]):
                if saved["parts"][index] == "uncertain":
                    return "uncertain"
                continue
            saved["parts"].append("uncertain")
            self.store.set_state(state_key, saved)
            try:
                receipt = self.request("sendMessage", {"chat_id": chat, "text": part,
                    "link_preview_options": {"is_disabled": True}})
            except RemoteError as error:
                saved["state"] = "uncertain" if error.uncertain else "ready" if error.status == 429 else "failed"
                if saved["state"] == "ready":
                    saved["parts"].pop()
                self.store.set_state(state_key, saved)
                return saved["state"]
            saved["parts"][index] = str(receipt["message_id"])
            self.store.set_state(state_key, saved)
        saved["state"] = "sent"
        self.store.set_state(state_key, saved)
        return "sent"

    def poll_once(self, handler):
        if quiet(self.settings):
            return {"deferred": "quiet-hours", "handled": 0}
        pending = self.store.db.execute("SELECT key,value FROM state WHERE key LIKE 'telegram-reply:%'").fetchall()
        for row in pending:
            reply = json.loads(row["value"])
            if reply.get("state") == "ready":
                self.send(row["key"].split(":", 1)[1], reply["chat"], reply["body"])
        offset = self.store.get_state("telegram_offset", 0)
        updates = self.request("getUpdates", {"offset": offset, "timeout": 20, "limit": 10, "allowed_updates": ["message"]})
        handled = 0
        for update in updates:
            identifier = update["update_id"]
            message = update.get("message", {})
            if authorized(self.settings, message) and isinstance(message.get("text"), str):
                key = f"telegram-command:{identifier}"
                saved = self.store.get_state(key)
                if saved is None:
                    # Claim before invoking paid work; process death requires operator inspection.
                    self.store.set_state(key, {"state": "uncertain"})
                    try:
                        response = handler(message["text"], identifier)
                    except Exception as error:
                        response = "คำขอยังไม่สำเร็จ: " + type(error).__name__ + " — ตรวจ health หรือสั่งซ้ำหลังแก้สาเหตุ"
                    saved = {"state": "done", "response": response}
                    self.store.set_state(key, saved)
                if saved["state"] == "done":
                    self.send(identifier, message["chat"]["id"], saved["response"])
                handled += 1
            self.store.set_state("telegram_offset", identifier + 1)
        return {"handled": handled}

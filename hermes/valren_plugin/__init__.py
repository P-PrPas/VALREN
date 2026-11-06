"""Hermes plugin: no model-callable paid actions, arbitrary shell, or raw writers."""
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing


def library_search(args, **kwargs):
    try:
        from valren.config import local_path
        query = args.get("query", "")
        if not isinstance(query, str) or not 1 <= len(query) <= 200:
            raise ValueError("query length")
        path = local_path("data/valren.sqlite3")
        # Read-only connection: no Store initialization, schema changes, writes or paid calls.
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            rows = db.execute("SELECT key,payload,status FROM items WHERE instr(lower(payload),lower(?))>0 LIMIT 10", (query,)).fetchall()
        return json.dumps({"results": [{"key": row[0], "title": json.loads(row[1])["title"],
            "url": json.loads(row[1])["url"], "status": row[2]} for row in rows]}, ensure_ascii=False)
    except Exception as error:
        return json.dumps({"error_type": type(error).__name__})


def authenticated_settings():
    from valren.config import load
    from valren.telegram import authorized
    try:
        from gateway import session_context
    except ImportError:
        raise ValueError("pinned Hermes session context required") from None
    # Pinned runtime dispatches only raw_args. Read task-local bindings directly:
    # get_session_env has an environment fallback that cannot prove a live caller.
    platform = session_context._SESSION_PLATFORM.get()
    user = session_context._SESSION_USER_ID.get()
    chat = session_context._SESSION_CHAT_ID.get()
    if platform != "telegram" or not isinstance(user, str) or not isinstance(chat, str):
        raise ValueError("authenticated Telegram context required")
    settings = load()
    if not authorized(settings, {"from": {"id": int(user)}, "chat": {"id": int(chat)}}):
        raise ValueError("unauthorized command caller")
    return settings


def tutor_command(raw_args, *, retry_invalid=False, **kwargs):
    try:
        from valren.config import ROOT
        authenticated_settings()
        # Fixed argv, no shell. The subprocess runs HTTP on its main thread with normal worker locks/budget.
        environment = {key: value for key, value in os.environ.items()
                       if key in {"LLM_API_KEY", "NOTION_LIBRARY_TOKEN", "NOTION_PROFILE_TOKEN", "VALREN_HOME", "PYTHONPATH", "PATH"}}
        environment["VALREN_HOME"] = str(ROOT)
        command = [sys.executable, "-m", "valren.cli", "tutor"] + (["--retry-invalid"] if retry_invalid else []) + ["--", raw_args.strip()]
        completed = subprocess.run(command,
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=1800, check=False)
        result = json.loads(completed.stdout)
        return result.get("lesson", "คำขอยังไม่สำเร็จ: " + result.get("error_type", "WorkerError"))
    except Exception as error:
        return "คำขอยังไม่สำเร็จ: " + type(error).__name__


def register(ctx):
    ctx.register_tool(name="valren_library_search", toolset="valren", schema={
        "name": "valren_library_search", "description": "Search existing research Library cache; read-only, no research or paid calls.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}},
        handler=library_search)
    ctx.register_command("valren-tutor", handler=tutor_command,
                         description="Teach an existing research key or arXiv paper; authenticated user command only")
    def retry(raw_args, **kwargs):
        return tutor_command(raw_args, retry_invalid=True, **kwargs)
    ctx.register_command("valren-tutor-retry", handler=retry,
                         description="Explicitly authorize one fresh paid attempt after invalid/uncertain Tutor output")

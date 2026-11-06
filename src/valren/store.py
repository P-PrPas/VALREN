from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .models import Candidate


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if self.db.execute("PRAGMA user_version").fetchone()[0] > 1:
            self.db.close()
            raise ValueError("database created by a newer worker")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                key TEXT PRIMARY KEY, payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'New', page_id TEXT UNIQUE,
                discovered TEXT NOT NULL, recommended TEXT,
                feedback TEXT, lesson TEXT
            );
            CREATE TABLE IF NOT EXISTS aliases (
                alias TEXT NOT NULL, key TEXT NOT NULL REFERENCES items(key), PRIMARY KEY(alias,key)
            );
            CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        self.db.execute("PRAGMA user_version=1")

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.rollback()
            raise
        else:
            self.db.commit()

    def add(self, item: Candidate) -> bool:
        with self.transaction():
            created = self.db.execute(
                "INSERT OR IGNORE INTO items(key,payload,discovered) VALUES(?,?,?)",
                (item.key, json.dumps(item.as_dict(), ensure_ascii=False), now()),
            ).rowcount == 1
            self.db.execute("UPDATE items SET payload=? WHERE key=?",
                            (json.dumps(item.as_dict(), ensure_ascii=False), item.key))
            for alias in item.aliases:
                namespaced = item.key.partition(":")[0] + ":name:" + alias
                self.db.execute("INSERT OR IGNORE INTO aliases VALUES(?,?)", (namespaced, item.key))
            return created

    def pending(self, limit=100):
        return [Candidate(**json.loads(row[0])) for row in self.db.execute(
            "SELECT payload FROM items WHERE status='New' ORDER BY discovered DESC,key LIMIT ?", (limit,))]

    def get_state(self, key, default=None):
        row = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_state(self, key, value):
        self.db.execute("INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, json.dumps(value, ensure_ascii=False)))

    def backup(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as destination:
            self.db.backup(destination)

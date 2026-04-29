"""
Local SQLite store for Akshara.

Persists the library, pomodoro sessions, page-by-page dwell time, bookmarks,
and TTS segments. Local-only — no network. Default location is
~/.local/share/akshara/akshara.db (overridable via AKSHARA_DB env var).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


# ---------- Location ---------------------------------------------------------

def default_db_path() -> Path:
    override = os.environ.get("AKSHARA_DB")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "akshara" / "akshara.db"


# ---------- Schema -----------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    author      TEXT,
    path        TEXT NOT NULL,
    pages       INTEGER NOT NULL,
    added_at    INTEGER NOT NULL,
    last_opened INTEGER,
    last_page   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  TEXT NOT NULL REFERENCES documents(id),
    started_at   INTEGER NOT NULL,
    ended_at     INTEGER,
    phase        TEXT NOT NULL,           -- focus | break | long
    duration_s   INTEGER NOT NULL,
    completed    INTEGER NOT NULL DEFAULT 0,
    pages_read   INTEGER NOT NULL DEFAULT 0,
    words_heard  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sessions_doc_started
    ON sessions(document_id, started_at);

CREATE TABLE IF NOT EXISTS page_views (
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    page_no     INTEGER NOT NULL,
    dwell_s     INTEGER NOT NULL,
    PRIMARY KEY (session_id, page_no)
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id),
    page_no     INTEGER NOT NULL,
    note        TEXT,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tts_segments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    page_no     INTEGER NOT NULL,
    char_start  INTEGER NOT NULL,
    char_end    INTEGER NOT NULL,
    spoken_at   INTEGER NOT NULL
);
"""


# ---------- Helpers ----------------------------------------------------------

def _hash_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------- Store ------------------------------------------------------------

@dataclass
class DocumentRow:
    id: str
    title: str
    author: Optional[str]
    path: str
    pages: int
    last_page: int


class Store:
    """Thin SQLite wrapper. One Store per app instance is fine."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # context-manager for atomic blocks
    @contextmanager
    def tx(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ---- documents ----
    def upsert_document(self, file_path: str, title: str, author: Optional[str], pages: int) -> str:
        doc_id = _hash_file(file_path)
        now = int(time.time())
        with self.tx() as c:
            row = c.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if row:
                c.execute(
                    "UPDATE documents SET path = ?, title = ?, author = ?, pages = ?, last_opened = ? WHERE id = ?",
                    (file_path, title, author, pages, now, doc_id),
                )
            else:
                c.execute(
                    "INSERT INTO documents (id, title, author, path, pages, added_at, last_opened) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (doc_id, title, author, file_path, pages, now, now),
                )
        return doc_id

    def update_last_page(self, doc_id: str, page_no: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE documents SET last_page = ? WHERE id = ?", (page_no, doc_id))

    def list_documents(self) -> list[DocumentRow]:
        rows = self._conn.execute(
            "SELECT id, title, author, path, pages, last_page FROM documents ORDER BY last_opened DESC"
        ).fetchall()
        return [DocumentRow(**dict(r)) for r in rows]

    # ---- sessions ----
    def start_session(self, doc_id: str, phase: str, planned_s: int) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO sessions (document_id, started_at, phase, duration_s) VALUES (?, ?, ?, ?)",
                (doc_id, int(time.time()), phase, planned_s),
            )
            return int(cur.lastrowid)

    def end_session(self, session_id: int, completed: bool, actual_s: int, pages_read: int = 0) -> None:
        with self.tx() as c:
            c.execute(
                "UPDATE sessions SET ended_at = ?, completed = ?, duration_s = ?, pages_read = ? WHERE id = ?",
                (int(time.time()), 1 if completed else 0, actual_s, pages_read, session_id),
            )

    def add_page_view(self, session_id: int, page_no: int, dwell_s: int) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO page_views (session_id, page_no, dwell_s) VALUES (?, ?, ?) "
                "ON CONFLICT(session_id, page_no) DO UPDATE SET dwell_s = dwell_s + excluded.dwell_s",
                (session_id, page_no, dwell_s),
            )

    # ---- analytics queries ----
    def daily_totals(self, days: int = 28) -> list[dict]:
        cutoff = int(time.time()) - days * 86400
        rows = self._conn.execute(
            """
            SELECT date(started_at, 'unixepoch', 'localtime') AS d,
                   SUM(CASE WHEN phase='focus' THEN duration_s ELSE 0 END) AS focus_s,
                   SUM(CASE WHEN phase!='focus' THEN duration_s ELSE 0 END) AS break_s,
                   COUNT(*) AS n
            FROM sessions
            WHERE started_at >= ?
            GROUP BY d
            ORDER BY d
            """,
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def session_length_histogram(self, days: int = 28) -> list[tuple[str, int]]:
        cutoff = int(time.time()) - days * 86400
        rows = self._conn.execute(
            """
            SELECT
              CASE
                WHEN duration_s <= 900  THEN '5–15 min'
                WHEN duration_s <= 1500 THEN '15–25 min'
                WHEN duration_s <= 2100 THEN '25–35 min'
                WHEN duration_s <= 2700 THEN '35–45 min'
                ELSE '45+ min'
              END AS bucket,
              COUNT(*) AS n
            FROM sessions
            WHERE phase = 'focus' AND started_at >= ?
            GROUP BY bucket
            """,
            (cutoff,),
        ).fetchall()
        return [(r["bucket"], r["n"]) for r in rows]

    def per_document_time(self) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT d.id, d.title, d.author, d.pages, d.last_page,
                   COALESCE(SUM(s.duration_s), 0) AS total_s,
                   COUNT(s.id)                    AS session_n
            FROM documents d
            LEFT JOIN sessions s
              ON s.document_id = d.id AND s.phase = 'focus'
            GROUP BY d.id
            ORDER BY total_s DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def summary(self, days: int = 28) -> dict:
        cutoff = int(time.time()) - days * 86400
        r = self._conn.execute(
            """
            SELECT
              COALESCE(SUM(duration_s), 0)                                 AS total_s,
              COUNT(*)                                                     AS n,
              SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END)               AS done,
              CAST(AVG(duration_s) AS INTEGER)                             AS avg_s
            FROM sessions
            WHERE phase = 'focus' AND started_at >= ?
            """,
            (cutoff,),
        ).fetchone()
        return dict(r) if r else {"total_s": 0, "n": 0, "done": 0, "avg_s": 0}

    def file_size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0

    def close(self) -> None:
        self._conn.close()

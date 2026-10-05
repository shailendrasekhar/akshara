"""
Local SQLite store for Akshara.

Persists the library, pomodoro sessions, page-by-page dwell time, bookmarks,
highlights and TTS statistics. Local-only — no network. Default location is
$XDG_DATA_HOME/akshara/akshara.db (overridable via the AKSHARA_DB env var).

Schema changes are applied as numbered migrations tracked in
``PRAGMA user_version`` so existing user databases upgrade in place.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

# ---------- Location ---------------------------------------------------------


def default_db_path() -> Path:
    override = os.environ.get("AKSHARA_DB")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "akshara" / "akshara.db"


# ---------- Migrations -------------------------------------------------------

# v1 is the schema shipped before migrations existed. It is written with
# IF NOT EXISTS so it is a no-op on legacy databases (user_version == 0 but
# tables present) and creates everything on a fresh install.
_V1 = """
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
    phase        TEXT NOT NULL,
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

# v2:
#  * sessions.document_id becomes nullable so a pomodoro can run before any
#    PDF is open (previously it inserted 'unattached', which violated the FK).
#  * Child rows cascade when a document is removed from the library.
#  * documents gain a per-book zoom.
#  * New highlights table; unused tts_segments dropped (words_heard on the
#    session row covers the statistic).
_V2 = """
CREATE TABLE sessions_new (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  TEXT REFERENCES documents(id) ON DELETE SET NULL,
    started_at   INTEGER NOT NULL,
    ended_at     INTEGER,
    phase        TEXT NOT NULL CHECK (phase IN ('focus', 'break', 'long')),
    duration_s   INTEGER NOT NULL,
    completed    INTEGER NOT NULL DEFAULT 0,
    pages_read   INTEGER NOT NULL DEFAULT 0,
    words_heard  INTEGER NOT NULL DEFAULT 0
);
INSERT INTO sessions_new
    SELECT id, NULLIF(document_id, 'unattached'), started_at, ended_at, phase,
           duration_s, completed, pages_read, words_heard
    FROM sessions;

CREATE TABLE page_views_new (
    session_id  INTEGER NOT NULL REFERENCES sessions_new(id) ON DELETE CASCADE,
    page_no     INTEGER NOT NULL,
    dwell_s     INTEGER NOT NULL,
    PRIMARY KEY (session_id, page_no)
);
INSERT INTO page_views_new SELECT * FROM page_views;

CREATE TABLE bookmarks_new (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no     INTEGER NOT NULL,
    note        TEXT,
    created_at  INTEGER NOT NULL,
    UNIQUE (document_id, page_no)
);
INSERT OR IGNORE INTO bookmarks_new SELECT * FROM bookmarks;

DROP TABLE tts_segments;
DROP TABLE page_views;
DROP TABLE bookmarks;
DROP TABLE sessions;
ALTER TABLE sessions_new   RENAME TO sessions;
ALTER TABLE page_views_new RENAME TO page_views;
ALTER TABLE bookmarks_new  RENAME TO bookmarks;

CREATE INDEX idx_sessions_doc_started ON sessions(document_id, started_at);
CREATE INDEX idx_sessions_started     ON sessions(started_at);

ALTER TABLE documents ADD COLUMN zoom REAL;

CREATE TABLE highlights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no     INTEGER NOT NULL,
    text        TEXT NOT NULL,
    rects       TEXT NOT NULL,          -- JSON [[x0, y0, x1, y1], ...] in PDF points
    color       TEXT NOT NULL DEFAULT '#facc15',
    note        TEXT,
    created_at  INTEGER NOT NULL
);
CREATE INDEX idx_highlights_doc_page ON highlights(document_id, page_no);
"""

MIGRATIONS: list[str] = [_V1, _V2]
SCHEMA_VERSION = len(MIGRATIONS)


def _migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema v{current} is newer than this build supports "
            f"(v{SCHEMA_VERSION}). Please update Akshara."
        )
    for version in range(current + 1, SCHEMA_VERSION + 1):
        # Table rebuilds must run with FK enforcement off (SQLite docs §7).
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.executescript(
                "BEGIN;\n"
                + MIGRATIONS[version - 1]
                + f"\nPRAGMA user_version = {version};\nCOMMIT;"
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute("PRAGMA foreign_keys=ON")


# ---------- Helpers ----------------------------------------------------------


def hash_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def _now() -> int:
    return int(time.time())


# ---------- Rows -------------------------------------------------------------


@dataclass
class DocumentRow:
    id: str
    title: str
    author: str | None
    path: str
    pages: int
    last_page: int
    last_opened: int | None = None
    added_at: int = 0
    zoom: float | None = None

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.path)

    @property
    def progress(self) -> float:
        return min(1.0, self.last_page / self.pages) if self.pages > 0 else 0.0


@dataclass
class BookmarkRow:
    id: int
    document_id: str
    page_no: int
    note: str | None
    created_at: int


@dataclass
class HighlightRow:
    id: int
    document_id: str
    page_no: int
    text: str
    rects: list[tuple[float, float, float, float]]
    color: str
    note: str | None
    created_at: int


# ---------- Store ------------------------------------------------------------


class Store:
    """Thin SQLite wrapper. One Store per app instance; used from the GUI thread."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        _migrate(self._conn)

    @property
    def schema_version(self) -> int:
        return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """Atomic block. Nested use is not supported."""
        self._conn.execute("BEGIN")
        try:
            yield self._conn
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    # ---- documents ----

    def upsert_document(
        self,
        file_path: str,
        title: str,
        author: str | None,
        pages: int,
        doc_id: str | None = None,
    ) -> str:
        doc_id = doc_id or hash_file(file_path)
        now = _now()
        with self.tx() as c:
            c.execute(
                """
                INSERT INTO documents (id, title, author, path, pages, added_at, last_opened)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    path = excluded.path, title = excluded.title, author = excluded.author,
                    pages = excluded.pages, last_opened = excluded.last_opened
                """,
                (doc_id, title, author, file_path, pages, now, now),
            )
        return doc_id

    def get_document(self, doc_id: str) -> DocumentRow | None:
        r = self._conn.execute(
            "SELECT id, title, author, path, pages, last_page, last_opened, added_at, zoom "
            "FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        return DocumentRow(**dict(r)) if r else None

    def update_last_page(self, doc_id: str, page_no: int) -> None:
        self._conn.execute("UPDATE documents SET last_page = ? WHERE id = ?", (page_no, doc_id))

    def update_zoom(self, doc_id: str, zoom: float) -> None:
        self._conn.execute("UPDATE documents SET zoom = ? WHERE id = ?", (zoom, doc_id))

    def relocate_document(self, doc_id: str, new_path: str) -> None:
        self._conn.execute("UPDATE documents SET path = ? WHERE id = ?", (new_path, doc_id))

    def remove_document(self, doc_id: str) -> None:
        """Forget a document. Sessions are kept (detached) so totals stay honest."""
        with self.tx() as c:
            c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def list_documents(self) -> list[DocumentRow]:
        rows = self._conn.execute(
            "SELECT id, title, author, path, pages, last_page, last_opened, added_at, zoom "
            "FROM documents ORDER BY last_opened DESC"
        ).fetchall()
        return [DocumentRow(**dict(r)) for r in rows]

    # ---- sessions ----

    def start_session(self, doc_id: str | None, phase: str, planned_s: int) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions (document_id, started_at, phase, duration_s) VALUES (?, ?, ?, ?)",
            (doc_id, _now(), phase, planned_s),
        )
        return int(cur.lastrowid or 0)

    def attach_session(self, session_id: int, doc_id: str) -> None:
        """Tie a running session to a document opened after it started."""
        self._conn.execute(
            "UPDATE sessions SET document_id = ? WHERE id = ? AND document_id IS NULL",
            (doc_id, session_id),
        )

    def end_session(
        self,
        session_id: int,
        completed: bool,
        actual_s: int,
        pages_read: int | None = None,
    ) -> None:
        if pages_read is None:
            pages_read = self._conn.execute(
                "SELECT COUNT(*) FROM page_views WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
        self._conn.execute(
            "UPDATE sessions SET ended_at = ?, completed = ?, duration_s = ?, pages_read = ? "
            "WHERE id = ?",
            (_now(), 1 if completed else 0, actual_s, pages_read, session_id),
        )

    def add_page_view(self, session_id: int, page_no: int, dwell_s: int) -> None:
        self._conn.execute(
            "INSERT INTO page_views (session_id, page_no, dwell_s) VALUES (?, ?, ?) "
            "ON CONFLICT(session_id, page_no) DO UPDATE SET dwell_s = dwell_s + excluded.dwell_s",
            (session_id, page_no, dwell_s),
        )

    def add_words_heard(self, session_id: int, words: int) -> None:
        self._conn.execute(
            "UPDATE sessions SET words_heard = words_heard + ? WHERE id = ?", (words, session_id)
        )

    # ---- bookmarks ----

    def toggle_bookmark(self, doc_id: str, page_no: int, note: str | None = None) -> bool:
        """Add a bookmark, or remove it if one exists. Returns True if now bookmarked."""
        with self.tx() as c:
            cur = c.execute(
                "DELETE FROM bookmarks WHERE document_id = ? AND page_no = ?", (doc_id, page_no)
            )
            if cur.rowcount:
                return False
            c.execute(
                "INSERT INTO bookmarks (document_id, page_no, note, created_at) VALUES (?, ?, ?, ?)",
                (doc_id, page_no, note, _now()),
            )
            return True

    def set_bookmark_note(self, bookmark_id: int, note: str | None) -> None:
        self._conn.execute("UPDATE bookmarks SET note = ? WHERE id = ?", (note, bookmark_id))

    def list_bookmarks(self, doc_id: str) -> list[BookmarkRow]:
        rows = self._conn.execute(
            "SELECT id, document_id, page_no, note, created_at FROM bookmarks "
            "WHERE document_id = ? ORDER BY page_no",
            (doc_id,),
        ).fetchall()
        return [BookmarkRow(**dict(r)) for r in rows]

    # ---- highlights ----

    def add_highlight(
        self,
        doc_id: str,
        page_no: int,
        text: str,
        rects: list[tuple[float, float, float, float]],
        color: str = "#facc15",
        note: str | None = None,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO highlights (document_id, page_no, text, rects, color, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc_id, page_no, text, json.dumps(rects), color, note, _now()),
        )
        return int(cur.lastrowid or 0)

    def set_highlight_note(self, highlight_id: int, note: str | None) -> None:
        self._conn.execute("UPDATE highlights SET note = ? WHERE id = ?", (note, highlight_id))

    def remove_highlight(self, highlight_id: int) -> None:
        self._conn.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))

    def list_highlights(self, doc_id: str, page_no: int | None = None) -> list[HighlightRow]:
        sql = (
            "SELECT id, document_id, page_no, text, rects, color, note, created_at "
            "FROM highlights WHERE document_id = ?"
        )
        args: tuple = (doc_id,)
        if page_no is not None:
            sql += " AND page_no = ?"
            args += (page_no,)
        rows = self._conn.execute(sql + " ORDER BY page_no, id", args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["rects"] = [tuple(x) for x in json.loads(d["rects"])]
            out.append(HighlightRow(**d))
        return out

    # ---- analytics queries ----

    def daily_totals(self, days: int = 28) -> list[dict]:
        cutoff = _now() - days * 86400
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
        cutoff = _now() - days * 86400
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
        cutoff = _now() - days * 86400
        r = self._conn.execute(
            """
            SELECT
              COALESCE(SUM(duration_s), 0)                         AS total_s,
              COUNT(*)                                             AS n,
              COALESCE(SUM(completed), 0)                          AS done,
              COALESCE(CAST(AVG(duration_s) AS INTEGER), 0)        AS avg_s,
              COALESCE(SUM(pages_read), 0)                         AS pages,
              COALESCE(SUM(words_heard), 0)                        AS words
            FROM sessions
            WHERE phase = 'focus' AND started_at >= ?
            """,
            (cutoff,),
        ).fetchone()
        return dict(r)

    def streak_days(self) -> int:
        """Consecutive days (ending today or yesterday) with at least one focus session."""
        rows = self._conn.execute(
            "SELECT DISTINCT date(started_at, 'unixepoch', 'localtime') AS d FROM sessions "
            "WHERE phase = 'focus' ORDER BY d DESC"
        ).fetchall()

        days = [dt.date.fromisoformat(r["d"]) for r in rows]
        if not days:
            return 0
        today = dt.date.today()
        if days[0] < today - dt.timedelta(days=1):
            return 0
        streak = 1
        for prev, cur in itertools.pairwise(days):
            if prev - cur == dt.timedelta(days=1):
                streak += 1
            else:
                break
        return streak

    def daily_series(self, days: int = 28, today: dt.date | None = None) -> list[dict]:
        """One row per calendar day (oldest first), including days with no activity."""
        today = today or dt.date.today()
        by_day = {r["d"]: r for r in self.daily_totals(days + 1)}
        out = []
        for i in range(days - 1, -1, -1):
            d = (today - dt.timedelta(days=i)).isoformat()
            r = by_day.get(d)
            out.append(
                {
                    "d": d,
                    "focus_s": (r["focus_s"] or 0) if r else 0,
                    "break_s": (r["break_s"] or 0) if r else 0,
                    "n": r["n"] if r else 0,
                }
            )
        return out

    def best_streak_days(self) -> int:
        rows = self._conn.execute(
            "SELECT DISTINCT date(started_at, 'unixepoch', 'localtime') AS d FROM sessions "
            "WHERE phase = 'focus' ORDER BY d"
        ).fetchall()
        best = run = 0
        prev: dt.date | None = None
        for r in rows:
            day = dt.date.fromisoformat(r["d"])
            run = run + 1 if prev and day - prev == dt.timedelta(days=1) else 1
            best = max(best, run)
            prev = day
        return best

    def export_sessions_csv(self, path: str) -> int:
        """Write every session to CSV. Returns the number of rows written."""
        import csv

        rows = self._conn.execute(
            """
            SELECT s.id, datetime(s.started_at, 'unixepoch', 'localtime') AS started,
                   datetime(s.ended_at, 'unixepoch', 'localtime') AS ended,
                   s.phase, s.duration_s, s.completed, s.pages_read, s.words_heard,
                   d.title, d.author, d.path
            FROM sessions s LEFT JOIN documents d ON d.id = s.document_id
            ORDER BY s.started_at
            """
        ).fetchall()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "id",
                    "started",
                    "ended",
                    "phase",
                    "duration_s",
                    "completed",
                    "pages_read",
                    "words_heard",
                    "title",
                    "author",
                    "path",
                ]
            )
            for r in rows:
                w.writerow(list(r))
        return len(rows)

    def file_size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0

    def close(self) -> None:
        self._conn.close()

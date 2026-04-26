import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class LeadDraft:
    chat_id: str
    name: str | None
    phone: str | None
    saved_at: str | None


@dataclass(frozen=True)
class Lead:
    id: int
    chat_id: str
    username: str | None
    name: str
    phone: str
    created_at: str
    sheets_synced_at: str | None


class SQLiteStorage:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def init(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_chat_id_id
                ON messages(chat_id, id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lead_drafts (
                    chat_id TEXT PRIMARY KEY,
                    name TEXT,
                    phone TEXT,
                    saved_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    username TEXT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sheets_synced_at TEXT
                )
                """
            )
            self._add_column_if_missing(conn, "leads", "sheets_synced_at", "TEXT")

    def add_message(self, chat_id: str, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages(chat_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, role, content, _now()),
            )

    def get_recent_messages(self, chat_id: str, limit: int) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content
                FROM (
                    SELECT id, role, content
                    FROM messages
                    WHERE chat_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                ORDER BY id ASC
                """,
                (chat_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def clear_chat(self, chat_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            conn.execute("DELETE FROM lead_drafts WHERE chat_id = ?", (chat_id,))

    def touch_lead_draft(self, chat_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO lead_drafts(chat_id, updated_at)
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (chat_id, _now()),
            )

    def start_new_lead_draft(self, chat_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO lead_drafts(chat_id, name, phone, saved_at, updated_at)
                VALUES (?, NULL, NULL, NULL, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    name = NULL,
                    phone = NULL,
                    saved_at = NULL,
                    updated_at = excluded.updated_at
                """,
                (chat_id, _now()),
            )

    def get_lead_draft(self, chat_id: str) -> LeadDraft | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT chat_id, name, phone, saved_at
                FROM lead_drafts
                WHERE chat_id = ?
                """,
                (chat_id,),
            ).fetchone()

        if not row:
            return None
        return LeadDraft(
            chat_id=row["chat_id"],
            name=row["name"],
            phone=row["phone"],
            saved_at=row["saved_at"],
        )

    def upsert_lead_draft(
        self,
        chat_id: str,
        name: str | None = None,
        phone: str | None = None,
    ) -> None:
        current = self.get_lead_draft(chat_id)
        next_name = name or (current.name if current else None)
        next_phone = phone or (current.phone if current else None)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO lead_drafts(chat_id, name, phone, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    name = excluded.name,
                    phone = excluded.phone,
                    saved_at = NULL,
                    updated_at = excluded.updated_at
                """,
                (chat_id, next_name, next_phone, _now()),
            )

    def mark_lead_saved(self, chat_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE lead_drafts
                SET saved_at = ?
                WHERE chat_id = ?
                """,
                (_now(), chat_id),
            )

    def save_lead(
        self,
        chat_id: str,
        username: str | None,
        name: str,
        phone: str,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO leads(chat_id, username, name, phone, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (chat_id, username, name, phone, _now()),
            )
            return int(cursor.lastrowid)

    def mark_lead_sheets_synced(self, lead_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE leads
                SET sheets_synced_at = ?
                WHERE id = ?
                """,
                (_now(), lead_id),
            )

    def get_unsynced_leads(self) -> list[Lead]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, chat_id, username, name, phone, created_at, sheets_synced_at
                FROM leads
                WHERE sheets_synced_at IS NULL
                ORDER BY id ASC
                """
            ).fetchall()

        return [
            Lead(
                id=row["id"],
                chat_id=row["chat_id"],
                username=row["username"],
                name=row["name"],
                phone=row["phone"],
                created_at=row["created_at"],
                sheets_synced_at=row["sheets_synced_at"],
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _add_column_if_missing(
        conn: sqlite3.Connection, table: str, column: str, column_type: str
    ) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

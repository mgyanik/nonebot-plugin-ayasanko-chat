# storage/sqlite.py
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

try:
    from nonebot.log import logger
except ImportError:
    import logging
    logger = logging.getLogger("nonebot_plugin_ayasanko_chat")

from .base import BaseStorageBackend


class SqliteStorageBackend(BaseStorageBackend):
    """基于轻量级 SQLite 的持久化会话存储后端（服务重启会话不丢失）"""

    def __init__(self, db_path: str = "data/ayasanko_chat.db", default_ttl: float = 1800.0) -> None:
        self.db_path = db_path
        self.default_ttl = default_ttl
        self._ensure_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _ensure_db(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    last_active REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_session ON chat_messages(session_id, id);")
            conn.commit()
        logger.debug(f"SQLite storage initialized at: {self.db_path}")

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        now = time.time()
        with self._get_connection() as conn:
            # 检查会话是否存在及是否过期
            row = conn.execute(
                "SELECT last_active FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()

            if not row:
                return []

            last_active: float = row["last_active"]
            if self.default_ttl > 0 and (now - last_active) > self.default_ttl:
                # 已超时失效，清理历史
                conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
                conn.commit()
                return []

            # 刷新最后交互时间
            conn.execute(
                "UPDATE chat_sessions SET last_active = ? WHERE session_id = ?",
                (now, session_id),
            )
            rows = conn.execute(
                "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            conn.commit()

            history: list[dict[str, Any]] = []
            for r in rows:
                c = r["content"]
                # 尝试解析多模态 JSON 结构，若非 JSON 则保留原字符串
                if c.startswith("[") or c.startswith("{"):
                    try:
                        c = json.loads(c)
                    except json.JSONDecodeError:
                        pass
                history.append({"role": r["role"], "content": c})
            return history

    def add_turn(
        self,
        session_id: str,
        user_msg: Any,
        assistant_msg: str,
        max_history: int = 10,
    ) -> None:
        now = time.time()
        u_content = json.dumps(user_msg, ensure_ascii=False) if isinstance(user_msg, (list, dict)) else str(user_msg)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (session_id, last_active)
                VALUES (?, ?)
                ON CONFLICT(session_id) DO UPDATE SET last_active = excluded.last_active
                """,
                (session_id, now),
            )
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, "user", u_content, now),
            )
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, "assistant", assistant_msg, now),
            )

            # 修剪超出 max_history * 2 的旧消息
            max_entries = max_history * 2
            count_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM chat_messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            total_msgs = count_row["cnt"] if count_row else 0

            if total_msgs > max_entries:
                overflow = total_msgs - max_entries
                conn.execute(
                    """
                    DELETE FROM chat_messages
                    WHERE id IN (
                        SELECT id FROM chat_messages
                        WHERE session_id = ?
                        ORDER BY id ASC LIMIT ?
                    )
                    """,
                    (session_id, overflow),
                )
            conn.commit()

    def clear(self, session_id: str | None = None) -> int:
        with self._get_connection() as conn:
            if session_id is not None:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM chat_messages WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                count = row["cnt"] if row else 0
                conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
                conn.commit()
                return 1 if count > 0 else 0

            count_row = conn.execute("SELECT COUNT(*) as cnt FROM chat_sessions").fetchone()
            total = count_row["cnt"] if count_row else 0
            conn.execute("DELETE FROM chat_messages")
            conn.execute("DELETE FROM chat_sessions")
            conn.commit()
            return total

    def count_active(self) -> int:
        now = time.time()
        with self._get_connection() as conn:
            if self.default_ttl > 0:
                min_time = now - self.default_ttl
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM chat_sessions WHERE last_active >= ?",
                    (min_time,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as cnt FROM chat_sessions").fetchone()
            return row["cnt"] if row else 0

    def cleanup_expired(self, ttl: float | None = None) -> int:
        actual_ttl = ttl if ttl is not None else self.default_ttl
        if actual_ttl <= 0:
            return 0
        min_time = time.time() - actual_ttl
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT session_id FROM chat_sessions WHERE last_active < ?",
                (min_time,),
            ).fetchall()
            expired_ids = [r["session_id"] for r in rows]
            if expired_ids:
                placeholders = ",".join("?" for _ in expired_ids)
                conn.execute(f"DELETE FROM chat_messages WHERE session_id IN ({placeholders})", expired_ids)
                conn.execute(f"DELETE FROM chat_sessions WHERE session_id IN ({placeholders})", expired_ids)
                conn.commit()
            return len(expired_ids)

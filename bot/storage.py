"""FSM-хранилище поверх той же SQLite.

MemoryStorage теряет состояние при перезапуске процесса: уже отправленный вопрос
теста остаётся в чате, но его кнопки перестают что-либо делать — ни один хендлер
не проходит по состоянию. Здесь состояние переживает рестарт.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fsm (
    key   TEXT PRIMARY KEY,
    state TEXT,
    data  TEXT NOT NULL DEFAULT '{}'
);
"""


class SqliteStorage(BaseStorage):
    def __init__(self, db) -> None:
        self._db = db

    @property
    def conn(self):
        return self._db.conn

    @staticmethod
    def _key(key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id}:{key.destiny}"

    async def set_state(self, key: StorageKey, state: State | str | None = None) -> None:
        value = state.state if isinstance(state, State) else state
        await self.conn.execute(
            "INSERT INTO fsm (key, state) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET state = excluded.state",
            (self._key(key), value),
        )
        await self.conn.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        async with self.conn.execute(
            "SELECT state FROM fsm WHERE key = ?", (self._key(key),)
        ) as cur:
            row = await cur.fetchone()
        return row["state"] if row else None

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        await self.conn.execute(
            "INSERT INTO fsm (key, data) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET data = excluded.data",
            (self._key(key), json.dumps(data, ensure_ascii=False)),
        )
        await self.conn.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self.conn.execute(
            "SELECT data FROM fsm WHERE key = ?", (self._key(key),)
        ) as cur:
            row = await cur.fetchone()
        if not row or not row["data"]:
            return {}
        try:
            return json.loads(row["data"])
        except json.JSONDecodeError:
            log.warning("Повреждённые данные FSM для %s — сбрасываю", self._key(key))
            return {}

    async def close(self) -> None:
        """Соединение принадлежит Db — закрывать здесь нечего."""

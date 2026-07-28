"""Слой доступа к SQLite (aiosqlite, прямой SQL — проект маленький, ORM не нужен).

Схема создаётся при старте, миграция — идемпотентные ``CREATE TABLE IF NOT EXISTS``.
Времена хранятся как unix-секунды UTC (INTEGER): сравнения по ним однозначны и не
зависят от формата строк.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import aiosqlite

from . import cards
from .storage import SCHEMA as FSM_SCHEMA

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS progress (
    user_id INTEGER NOT NULL,
    card_id TEXT    NOT NULL,
    box     INTEGER NOT NULL DEFAULT 0,
    due_at  INTEGER NOT NULL DEFAULT 0,   -- unix-секунды UTC
    PRIMARY KEY (user_id, card_id)
);

CREATE INDEX IF NOT EXISTS idx_progress_due ON progress(user_id, due_at);

CREATE TABLE IF NOT EXISTS file_cache (
    card_id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz_results (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    category TEXT    NOT NULL,
    score    INTEGER NOT NULL,
    total    INTEGER NOT NULL,
    ts       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quiz_user ON quiz_results(user_id, ts DESC);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id     INTEGER PRIMARY KEY,
    answer_lang TEXT NOT NULL DEFAULT 'en'   -- язык изучаемых названий: en | el
);
"""


@dataclass(frozen=True)
class Stats:
    studied: int      # box >= 1
    learned: int      # box == MAX_BOX
    due_today: int    # due_at <= now


@dataclass(frozen=True)
class QuizResult:
    category: str
    score: int
    total: int
    ts: int


def now_ts() -> int:
    return int(time.time())


class Db:
    """Обёртка над одним соединением aiosqlite."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Db.connect() не вызван")
        return self._conn

    async def connect(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(SCHEMA + FSM_SCHEMA)
        await self._conn.commit()
        log.info("SQLite готова: %s", self.path)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            log.info("SQLite закрыта")

    # --- прогресс / Лейтнер -------------------------------------------------

    async def get_box(self, user_id: int, card_key: str) -> int | None:
        async with self.conn.execute(
            "SELECT box FROM progress WHERE user_id = ? AND card_id = ?",
            (user_id, card_key),
        ) as cur:
            row = await cur.fetchone()
        return row["box"] if row else None

    async def due_keys(self, user_id: int, keys: list[str], now: int | None = None) -> list[str]:
        """Ключи карточек из ``keys``, у которых подошёл срок повторения."""
        if not keys:
            return []
        now = now_ts() if now is None else now
        placeholders = ",".join("?" * len(keys))
        sql = (
            f"SELECT card_id FROM progress "
            f"WHERE user_id = ? AND due_at <= ? AND card_id IN ({placeholders}) "
            f"ORDER BY due_at"
        )
        async with self.conn.execute(sql, (user_id, now, *keys)) as cur:
            return [row["card_id"] for row in await cur.fetchall()]

    async def seen_keys(self, user_id: int) -> set[str]:
        """Карточки, у которых уже есть запись прогресса (то есть не новые)."""
        async with self.conn.execute(
            "SELECT card_id FROM progress WHERE user_id = ?", (user_id,)
        ) as cur:
            return {row["card_id"] for row in await cur.fetchall()}

    async def advance(self, user_id: int, card_key: str) -> int:
        """Отмечает карточку просмотренной и возвращает новую коробку."""
        box = await self.get_box(user_id, card_key) or 0
        new_box = cards.next_box(box)
        due = now_ts() + cards.interval_seconds(new_box)
        await self.conn.execute(
            "INSERT INTO progress (user_id, card_id, box, due_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, card_id) DO UPDATE SET box = excluded.box, "
            "due_at = excluded.due_at",
            (user_id, card_key, new_box, due),
        )
        await self.conn.commit()
        return new_box

    async def reset_cards(self, user_id: int, card_keys: list[str]) -> None:
        """Сбрасывает карточки в коробку 0 — ошибки теста возвращаются в повторение."""
        if not card_keys:
            return
        now = now_ts()
        await self.conn.executemany(
            "INSERT INTO progress (user_id, card_id, box, due_at) VALUES (?, ?, 0, ?) "
            "ON CONFLICT(user_id, card_id) DO UPDATE SET box = 0, due_at = excluded.due_at",
            [(user_id, key, now) for key in card_keys],
        )
        await self.conn.commit()

    # --- настройки пользователя ---------------------------------------------

    async def get_lang(self, user_id: int) -> str:
        """Язык изучаемых названий; по умолчанию английский."""
        async with self.conn.execute(
            "SELECT answer_lang FROM user_settings WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if row and row["answer_lang"] in cards.LANGS:
            return row["answer_lang"]
        return cards.DEFAULT_LANG

    async def set_lang(self, user_id: int, lang: str) -> None:
        if lang not in cards.LANGS:
            raise ValueError(f"неизвестный язык: {lang}")
        await self.conn.execute(
            "INSERT INTO user_settings (user_id, answer_lang) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET answer_lang = excluded.answer_lang",
            (user_id, lang),
        )
        await self.conn.commit()

    # --- кэш file_id --------------------------------------------------------

    async def get_file_id(self, card_key: str) -> str | None:
        async with self.conn.execute(
            "SELECT file_id FROM file_cache WHERE card_id = ?", (card_key,)
        ) as cur:
            row = await cur.fetchone()
        return row["file_id"] if row else None

    async def set_file_id(self, card_key: str, file_id: str) -> None:
        await self.conn.execute(
            "INSERT INTO file_cache (card_id, file_id) VALUES (?, ?) "
            "ON CONFLICT(card_id) DO UPDATE SET file_id = excluded.file_id",
            (card_key, file_id),
        )
        await self.conn.commit()

    # --- тесты и статистика -------------------------------------------------

    async def add_quiz_result(self, user_id: int, category: str, score: int, total: int) -> None:
        await self.conn.execute(
            "INSERT INTO quiz_results (user_id, category, score, total, ts) VALUES (?, ?, ?, ?, ?)",
            (user_id, category, score, total, now_ts()),
        )
        await self.conn.commit()

    async def recent_quiz_results(self, user_id: int, limit: int = 5) -> list[QuizResult]:
        async with self.conn.execute(
            "SELECT category, score, total, ts FROM quiz_results "
            "WHERE user_id = ? ORDER BY ts DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            return [
                QuizResult(r["category"], r["score"], r["total"], r["ts"])
                for r in await cur.fetchall()
            ]

    async def stats(self, user_id: int) -> Stats:
        async with self.conn.execute(
            "SELECT "
            "  SUM(box >= 1)  AS studied, "
            "  SUM(box >= ?)  AS learned, "
            "  SUM(due_at <= ?) AS due_today "
            "FROM progress WHERE user_id = ?",
            (cards.MAX_BOX, now_ts(), user_id),
        ) as cur:
            row = await cur.fetchone()
        return Stats(
            studied=row["studied"] or 0,
            learned=row["learned"] or 0,
            due_today=row["due_today"] or 0,
        )

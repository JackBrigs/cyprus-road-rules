"""Точка входа: long polling.

Запуск: ``python -m bot.main`` (нужен BOT_TOKEN в окружении или .env).
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from . import cards
from .config import load_config
from .db import Db
from .handlers import fallback, flashcards, menu, quiz
from .storage import SqliteStorage

log = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Начало и главное меню"),
    BotCommand(command="cards", description="Карточки с повторением"),
    BotCommand(command="quiz", description="Тест"),
    BotCommand(command="stats", description="Мой прогресс"),
]


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
    )


async def run() -> None:
    config = load_config()
    setup_logging(config.log_level)

    loaded = cards.decks()
    for deck in loaded.values():
        log.info("Колода %s: %d карточек, %d категорий",
                 deck.name, len(deck.cards), len(deck.used_categories()))

    db = Db(config.db_path)
    await db.connect()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # db доступна хендлерам как аргумент `db: Db`;
    # состояние в SQLite, чтобы сессия пережила перезапуск бота
    dispatcher = Dispatcher(storage=SqliteStorage(db), db=db)
    dispatcher.include_router(menu.router)
    dispatcher.include_router(flashcards.router)
    dispatcher.include_router(quiz.router)
    # последним — перехват кнопок из завершённых сессий
    dispatcher.include_router(fallback.router)

    try:
        await bot.set_my_commands(COMMANDS)
        await bot.delete_webhook(drop_pending_updates=True)
        log.info("Запуск long polling")
        # aiogram сам вешает обработчики SIGINT/SIGTERM и корректно
        # доигрывает текущие апдейты — этого достаточно для Docker.
        await dispatcher.start_polling(bot)
    finally:
        log.info("Остановка")
        await bot.session.close()
        await db.close()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        log.info("Прервано")


if __name__ == "__main__":
    main()

"""Конфигурация из переменных окружения."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: str
    log_level: str


def load_config() -> Config:
    """Читает .env (если есть) и переменные окружения. BOT_TOKEN обязателен."""
    load_dotenv(os.path.join(ROOT, ".env"))

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN не задан. Получите токен у @BotFather и положите его в .env "
            "(см. .env.example)."
        )

    db_path = os.getenv("DB_PATH", "var/bot.db").strip()
    if not os.path.isabs(db_path):
        db_path = os.path.join(ROOT, db_path)

    return Config(
        bot_token=token,
        db_path=db_path,
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
    )

"""Профиль бота: имя, описания, меню команд, аватар.

Это то, что человек видит до первого ``/start``: описание на экране пустого чата
и текст «о боте» на странице профиля. Держим их в коде, а не в настройках
@BotFather, чтобы правки жили в репозитории вместе с остальным.

Значения выставляются при запуске, но только если они реально отличаются от
текущих: Telegram ограничивает частоту смены имени, а бот перезапускается часто.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BotCommand, FSInputFile, InputProfilePhotoStatic

from .config import ROOT

log = logging.getLogger(__name__)

NAME = "Знаки Кипра"  # до 64 символов

# До 120 символов. Видно на странице профиля бота и в списке результатов поиска.
SHORT_DESCRIPTION = (
    "Карточки и тесты по дорожным знакам Кипра. "
    "Подготовка к теории на права — на английском или греческом."
)

# До 512 символов. Видно в пустом чате до нажатия «Начать».
DESCRIPTION = (
    "Помогу выучить дорожные знаки Кипра и сдать теоретический экзамен на права.\n\n"
    "📚 Карточки — знак без подписи, вы вспоминаете название. "
    "Интервальное повторение само решает, что и когда показать снова.\n"
    "✍️ Тест — четыре варианта, разбор каждого ответа. "
    "Ошибки автоматически возвращаются в карточки.\n"
    "📊 Прогресс — что уже выучено и что пора повторить.\n\n"
    "234 знака полного каталога и 63 карточки экзаменационного минимума "
    "с пояснениями. Язык названий — английский или греческий.\n\n"
    "Нажмите «Начать» 👇"
)

COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="cards", description="📚 Учить карточки"),
    BotCommand(command="quiz", description="✍️ Пройти тест"),
    BotCommand(command="stats", description="📊 Мой прогресс"),
]

AVATAR = ROOT + "/assets/brand/avatar.png"

MAX_NAME = 64
MAX_SHORT = 120
MAX_DESCRIPTION = 512


def _check_lengths() -> None:
    """Лучше упасть на старте, чем получить ошибку от Telegram в проде."""
    for value, limit, label in (
        (NAME, MAX_NAME, "NAME"),
        (SHORT_DESCRIPTION, MAX_SHORT, "SHORT_DESCRIPTION"),
        (DESCRIPTION, MAX_DESCRIPTION, "DESCRIPTION"),
    ):
        if len(value) > limit:
            raise ValueError(f"{label}: {len(value)} символов при лимите {limit}")


async def apply(bot: Bot) -> None:
    _check_lengths()

    if (await bot.get_my_name()).name != NAME:
        await bot.set_my_name(NAME)
        log.info("Имя бота обновлено: %s", NAME)

    if (await bot.get_my_short_description()).short_description != SHORT_DESCRIPTION:
        await bot.set_my_short_description(SHORT_DESCRIPTION)
        log.info("Короткое описание обновлено")

    if (await bot.get_my_description()).description != DESCRIPTION:
        await bot.set_my_description(DESCRIPTION)
        log.info("Описание обновлено")

    await bot.set_my_commands(COMMANDS)
    await _ensure_avatar(bot)


async def _ensure_avatar(bot: Bot) -> None:
    """Ставит аватар, только если его нет.

    Загрузка при каждом запуске добавляла бы боту новое фото в профиль поверх
    прежних, а не заменяла его.
    """
    me = await bot.get_me()
    photos = await bot.get_user_profile_photos(me.id, limit=1)
    if photos.total_count:
        return
    await bot.set_my_profile_photo(
        photo=InputProfilePhotoStatic(photo=FSInputFile(AVATAR))
    )
    log.info("Аватар установлен: %s", AVATAR)

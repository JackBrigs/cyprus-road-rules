"""Отправка изображений знаков с кэшем ``file_id``.

Каждый файл уходит в Telegram один раз: полученный ``file_id`` кладётся в таблицу
``file_cache`` и дальше используется вместо байтов. Загрузка логируется на INFO,
попадание в кэш — на DEBUG, чтобы кэш было видно в ``docker logs``.
"""
from __future__ import annotations

import logging

from aiogram.types import FSInputFile, InlineKeyboardMarkup, InputMediaPhoto, Message

from .cards import Card
from .db import Db

log = logging.getLogger(__name__)


async def _media_for(db: Db, card: Card) -> tuple[str | FSInputFile, bool]:
    """Возвращает (что отправлять, была ли это загрузка файла)."""
    file_id = await db.get_file_id(card.key)
    if file_id:
        log.debug("file_id из кэша: %s", card.key)
        return file_id, False
    log.info("Загрузка файла в Telegram: %s (%s)", card.key, card.image)
    return FSInputFile(card.image), True


async def _remember(db: Db, card: Card, message: Message, uploaded: bool) -> None:
    if uploaded and message.photo:
        await db.set_file_id(card.key, message.photo[-1].file_id)


async def send_card(
    message: Message,
    db: Db,
    card: Card,
    caption: str,
    markup: InlineKeyboardMarkup,
) -> Message:
    """Новое сообщение с фото знака."""
    media, uploaded = await _media_for(db, card)
    sent = await message.answer_photo(media, caption=caption, reply_markup=markup)
    await _remember(db, card, sent, uploaded)
    return sent


async def replace_card(
    message: Message,
    db: Db,
    card: Card,
    caption: str,
    markup: InlineKeyboardMarkup,
) -> Message | None:
    """Заменяет фото в уже отправленном сообщении — чат не засоряется."""
    media, uploaded = await _media_for(db, card)
    edited = await message.edit_media(
        InputMediaPhoto(media=media, caption=caption),
        reply_markup=markup,
    )
    if isinstance(edited, Message):
        await _remember(db, card, edited, uploaded)
        return edited
    return None

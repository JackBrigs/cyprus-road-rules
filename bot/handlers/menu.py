"""Главное меню, /start и /stats."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import cards, keyboards as kb
from ..db import Db

log = logging.getLogger(__name__)
router = Router(name="menu")

GREETING = (
    "🇨🇾 <b>Дорожные знаки Кипра</b>\n\n"
    "Подготовка к теоретическому экзамену: {full} знаков в полном каталоге "
    "и {mini} карточек экзаменационного минимума с пояснениями.\n\n"
    "• 📚 <b>Карточки</b> — учить с интервальным повторением\n"
    "• ✍️ <b>Тест</b> — проверить себя на время экзамена\n"
    "• 📊 <b>Прогресс</b> — что уже выучено\n\n"
    "Выберите режим:"
)


def greeting() -> str:
    return GREETING.format(
        full=len(cards.get_deck(cards.DECK_FULL).cards),
        mini=len(cards.get_deck(cards.DECK_MINI).cards),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(greeting(), reply_markup=kb.main_menu())


@router.callback_query(F.data == kb.cb(kb.A_MENU))
async def show_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message is None:
        return
    # Меню могло прийти из сообщения с фото — тогда текст не отредактировать.
    if callback.message.photo:
        await callback.message.answer(greeting(), reply_markup=kb.main_menu())
    else:
        await callback.message.edit_text(greeting(), reply_markup=kb.main_menu())


SETTINGS_TEXT = (
    "⚙️ <b>Настройки</b>\n\n"
    "<b>Язык названий</b> — на нём показываются названия в карточках и варианты "
    "ответа в тесте.\n\n"
    "Сейчас: {current}"
)


@router.callback_query(F.data == kb.cb(kb.A_SETTINGS))
async def show_settings(callback: CallbackQuery, db: Db) -> None:
    await callback.answer()
    if callback.message is None:
        return
    lang = await db.get_lang(callback.from_user.id)
    await callback.message.edit_text(
        SETTINGS_TEXT.format(current=_lang_title(lang)),
        reply_markup=kb.settings_menu(lang),
    )


@router.callback_query(F.data.startswith(kb.cb(kb.A_LANG, "")))
async def set_language(callback: CallbackQuery, db: Db) -> None:
    _, _, lang = callback.data.split(":", 2)
    if lang not in cards.LANGS:
        await callback.answer("Неизвестный язык")
        return

    await db.set_lang(callback.from_user.id, lang)
    await callback.answer(f"Язык названий: {_lang_title(lang)}")
    if callback.message is None:
        return
    await callback.message.edit_text(
        SETTINGS_TEXT.format(current=_lang_title(lang)),
        reply_markup=kb.settings_menu(lang),
    )


def _lang_title(lang: str) -> str:
    meta = cards.LANGS[lang]
    return f"{meta['flag']} {meta['title']}"


@router.callback_query(F.data == kb.cb(kb.A_STOP))
async def stop_session(callback: CallbackQuery, state: FSMContext) -> None:
    """Выход из карточек/теста в меню."""
    await state.clear()
    await callback.answer("Сессия завершена")
    if callback.message is None:
        return
    # Сообщение с карточкой убираем — оно уже не активно.
    await callback.message.delete()
    await callback.message.answer(greeting(), reply_markup=kb.main_menu())


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Db) -> None:
    await message.answer(await _stats_text(db, message.from_user.id),
                         reply_markup=kb.back_to_menu())


@router.callback_query(F.data == kb.cb(kb.A_STATS))
async def show_stats(callback: CallbackQuery, db: Db) -> None:
    await callback.answer()
    if callback.message is None:
        return
    text = await _stats_text(db, callback.from_user.id)
    if callback.message.photo:
        await callback.message.answer(text, reply_markup=kb.back_to_menu())
    else:
        await callback.message.edit_text(text, reply_markup=kb.back_to_menu())


async def _stats_text(db: Db, user_id: int) -> str:
    stats = await db.stats(user_id)
    results = await db.recent_quiz_results(user_id)

    lines = [
        "📊 <b>Ваш прогресс</b>\n",
        f"Изучается: <b>{stats.studied}</b>",
        f"Выучено: <b>{stats.learned}</b>",
        f"К повторению сейчас: <b>{stats.due_today}</b>",
    ]

    if results:
        lines.append("\n<b>Последние тесты</b>")
        for r in results:
            percent = round(r.score / r.total * 100) if r.total else 0
            lines.append(f"• {r.score}/{r.total} ({percent}%) — {r.category}")
    else:
        lines.append("\nТестов пока не было — попробуйте ✍️ Тест.")

    return "\n".join(lines)

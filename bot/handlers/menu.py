"""Главное меню, /start и /stats."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.text_decorations import html_decoration as html

from .. import cards, keyboards as kb
from ..db import Db

log = logging.getLogger(__name__)
router = Router(name="menu")

WELCOME = (
    "🇨🇾 <b>Привет, {name}!</b>\n\n"
    "Помогу выучить дорожные знаки Кипра и подготовиться к теоретическому экзамену "
    "на права. Он сдаётся на греческом или английском — названия учим сразу на "
    "нужном языке.\n\n"
    "<b>Что внутри</b>\n"
    "• Полный каталог кодекса — {full} {card_word} в {categories} {cat_word}\n"
    "• «Экзаменационный минимум» — {mini} {sign_word} с пояснениями, "
    "которые встречаются чаще всего\n"
    "• Не только знаки: разметка и сигналы регулировщика тоже\n\n"
    "<b>Как это работает</b>\n"
    "📚 <b>Карточки</b> — показываю знак без подписи, вы вспоминаете название и "
    "открываете ответ. Что уже видели, вернётся не сразу, а через день, три, "
    "неделю и три недели — так запоминается прочнее.\n\n"
    "✍️ <b>Тест</b> — 10, 20 или все вопросы категории, четыре варианта на выбор. "
    "Ошибки сами вернутся в карточки, отдельно отслеживать не нужно.\n\n"
    "📊 <b>Прогресс</b> — сколько выучено и что пора повторить.\n\n"
    "⚙️ <b>Настройки</b> — язык названий: 🇬🇧 English или 🇬🇷 Ελληνικά.\n\n"
    "Начните с карточек, если знаки пока незнакомы, или сразу с теста, "
    "если хотите проверить себя 👇"
)

MENU = "🇨🇾 <b>Главное меню</b>\n\n{status}\n\nЧто дальше?"


def plural(n: int, one: str, few: str, many: str) -> str:
    """Русское склонение после числительного: 1 карточка, 2 карточки, 5 карточек."""
    if n % 100 in range(11, 15):
        return many
    if n % 10 == 1:
        return one
    if n % 10 in (2, 3, 4):
        return few
    return many


def welcome(name: str) -> str:
    full = cards.get_deck(cards.DECK_FULL)
    total = len(full.cards)
    categories = len(full.used_categories())
    mini = len(cards.get_deck(cards.DECK_MINI).cards)
    return WELCOME.format(
        name=html.quote(name),
        full=total,
        card_word=plural(total, "карточка", "карточки", "карточек"),
        categories=categories,
        cat_word=plural(categories, "категории", "категориях", "категориях"),
        mini=mini,
        sign_word=plural(mini, "знак", "знака", "знаков"),
    )


async def menu_text(db: Db, user_id: int) -> str:
    """Короткий текст для возврата в меню: длинное приветствие каждый раз утомляет."""
    stats = await db.stats(user_id)
    if stats.due_today:
        status = f"🔔 К повторению сейчас: <b>{stats.due_today}</b>"
    elif stats.studied:
        status = f"✅ Всё повторено. Изучается: <b>{stats.studied}</b>"
    else:
        status = "Вы ещё не начинали — самое время 📚"
    return MENU.format(status=status)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        welcome(message.from_user.first_name), reply_markup=kb.main_menu()
    )


@router.callback_query(F.data == kb.cb(kb.A_MENU))
async def show_menu(callback: CallbackQuery, state: FSMContext, db: Db) -> None:
    await state.clear()
    await callback.answer()
    if callback.message is None:
        return
    text = await menu_text(db, callback.from_user.id)
    # Меню могло прийти из сообщения с фото — тогда текст не отредактировать.
    if callback.message.photo:
        await callback.message.answer(text, reply_markup=kb.main_menu())
    else:
        await callback.message.edit_text(text, reply_markup=kb.main_menu())


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
async def stop_session(callback: CallbackQuery, state: FSMContext, db: Db) -> None:
    """Выход из карточек/теста в меню."""
    await state.clear()
    await callback.answer("Сессия завершена")
    if callback.message is None:
        return
    # Сообщение с карточкой убираем — оно уже не активно.
    await callback.message.delete()
    await callback.message.answer(
        await menu_text(db, callback.from_user.id), reply_markup=kb.main_menu()
    )


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

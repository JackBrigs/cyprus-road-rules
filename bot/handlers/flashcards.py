"""Режим карточек: показ знака → самооценка → интервальное повторение."""
from __future__ import annotations

import logging
import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.markdown import hbold, hitalic

from .. import cards, keyboards as kb, media
from ..cards import Card, Deck
from ..db import Db

log = logging.getLogger(__name__)
router = Router(name="flashcards")

MODE = "cards"

DONE_TEXT = (
    "🎉 <b>На сегодня всё повторено</b>\n\n"
    "Новых карточек в этой категории не осталось, а повторение придёт по расписанию.\n"
    "Загляните позже или выберите другую категорию."
)


class Flashcards(StatesGroup):
    """Состояния сессии карточек."""
    showing_card = State()
    viewing_answer = State()


@router.message(Command("cards"))
async def cmd_cards(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("📚 Выберите колоду:", reply_markup=kb.deck_menu(MODE))


@router.callback_query(F.data == kb.cb(kb.A_CARDS))
async def start_cards(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_text("📚 Выберите колоду:", reply_markup=kb.deck_menu(MODE))


@router.callback_query(F.data.startswith(kb.cb(kb.A_DECK, f"{MODE}|")))
async def choose_category(callback: CallbackQuery) -> None:
    _, _, payload = callback.data.split(":", 2)
    _, deck_name = payload.split("|")
    await callback.answer()
    if callback.message is not None:
        deck = cards.get_deck(deck_name)
        await callback.message.edit_text(
            f"📚 <b>{deck.title}</b>\nВыберите категорию:",
            reply_markup=kb.category_menu(MODE, deck_name),
        )


@router.callback_query(F.data.startswith(kb.cb(kb.A_CATEGORY, f"{MODE}|")))
async def begin_session(callback: CallbackQuery, state: FSMContext, db: Db) -> None:
    _, _, payload = callback.data.split(":", 2)
    _, deck_name, category = payload.split("|")
    deck = cards.get_deck(deck_name)

    await callback.answer()
    if callback.message is None:
        return

    card = await _next_card(db, callback.from_user.id, deck, category)
    if card is None:
        await callback.message.edit_text(DONE_TEXT, reply_markup=kb.back_to_menu())
        return

    await state.set_state(Flashcards.showing_card)
    await state.update_data(deck=deck_name, category=category, card_key=card.key)

    # Меню — текстовое сообщение, фото в него не вставить: убираем и шлём карточку.
    await callback.message.delete()
    await media.send_card(
        callback.message, db, card, _question_caption(deck, category, card), kb.card_question()
    )


@router.callback_query(Flashcards.showing_card, F.data == kb.cb(kb.A_SHOW))
async def show_answer(callback: CallbackQuery, state: FSMContext, db: Db) -> None:
    data = await state.get_data()
    card = cards.get_card(data["card_key"])
    await callback.answer()
    if callback.message is None or card is None:
        return
    lang = await db.get_lang(callback.from_user.id)
    await state.set_state(Flashcards.viewing_answer)
    await callback.message.edit_caption(
        caption=_answer_caption(card, lang), reply_markup=kb.card_answer()
    )


@router.callback_query(Flashcards.viewing_answer, F.data == kb.cb(kb.A_NEXT))
async def next_card(callback: CallbackQuery, state: FSMContext, db: Db) -> None:
    data = await state.get_data()
    deck = cards.get_deck(data["deck"])
    category = data["category"]
    current_key = data["card_key"]

    # Самооценки нет: просмотренная карточка продвигается на коробку вперёд, то есть
    # показывается всё реже. Возвращают карточку в начало ошибки в тесте.
    box = await db.advance(callback.from_user.id, current_key)
    await callback.answer(_next_toast(box))

    if callback.message is None:
        return

    card = await _next_card(db, callback.from_user.id, deck, category, exclude=current_key)
    if card is None:
        await state.clear()
        await callback.message.delete()
        await callback.message.answer(DONE_TEXT, reply_markup=kb.back_to_menu())
        return

    await state.set_state(Flashcards.showing_card)
    await state.update_data(card_key=card.key)
    await media.replace_card(
        callback.message, db, card, _question_caption(deck, category, card), kb.card_question()
    )


# --- выборка карточек ------------------------------------------------------

async def _next_card(
    db: Db, user_id: int, deck: Deck, category: str, exclude: str | None = None
) -> Card | None:
    """Сначала то, что пора повторить, затем ещё не показанное.

    ``exclude`` — карточка, которую только что показали: её срок может наступить
    сразу (например, после сброса ошибкой в тесте), и без этого фильтра она бы
    показалась второй раз подряд.
    """
    pool = deck.in_category(category)
    if not pool:
        return None

    due = await db.due_keys(user_id, [c.key for c in pool])
    for key in due:
        if key != exclude:
            return deck.by_key(key)

    seen = await db.seen_keys(user_id)
    fresh = [c for c in pool if c.key not in seen and c.key != exclude]
    if fresh:
        return random.choice(fresh)

    # Ничего кроме только что оценённой карточки не осталось — показываем её.
    if exclude and due:
        return deck.by_key(exclude)
    return None


# --- тексты ----------------------------------------------------------------

def _question_caption(deck: Deck, category: str, card: Card) -> str:
    """Вопрос формулируется по типу объекта: знак, разметка или сигнал."""
    return (
        f"📚 {deck.title} · {deck.category_title(category)}\n\n"
        f"{hbold(cards.KIND_PROMPTS[card.kind])}"
    )


def _answer_caption(card: Card, lang: str) -> str:
    deck = cards.get_deck(card.deck)
    lines = [
        f"{cards.KIND_TITLES[card.kind]} · {deck.category_title(card.category)}",
        "",
        cards.name_line(card, lang),
    ]
    if card.explanation_ru:
        lines.append(hitalic(card.explanation_ru))
    return "\n".join(lines)


def _next_toast(box: int) -> str:
    days = cards.BOX_INTERVAL_DAYS[box]
    if days == 0:
        return "Повторим сегодня"
    if box == cards.MAX_BOX:
        return f"Выучено! Повтор через {days} дн."
    return f"Следующий показ через {days} дн."

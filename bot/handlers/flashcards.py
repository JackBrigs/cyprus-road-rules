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
from ..db import Db, now_ts

log = logging.getLogger(__name__)
router = Router(name="flashcards")

MODE = "cards"

EMPTY_TEXT = (
    "В этой категории нет карточек — выберите другую."
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

    picked = await _next_card(db, callback.from_user.id, deck, category)
    if picked is None:
        await callback.message.edit_text(EMPTY_TEXT, reply_markup=kb.back_to_menu())
        return
    card, scheduled = picked

    await state.set_state(Flashcards.showing_card)
    await state.update_data(
        deck=deck_name,
        category=category,
        card_key=card.key,
        scheduled=scheduled,
        shown=[card.key],
    )

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

    # Самооценки нет: просмотренная по расписанию карточка продвигается на коробку
    # вперёд и показывается всё реже. Вернуть её в начало может только ошибка в тесте.
    # Карточку, открытую вне расписания, не трогаем: пролистывание колоды не должно
    # раздувать интервалы.
    if data.get("scheduled", True):
        box = await db.advance(callback.from_user.id, current_key)
        toast = _next_toast(box)
    else:
        toast = "Вне расписания — срок повторения не сдвигаем"
    await callback.answer(toast)

    if callback.message is None:
        return

    # Обошли всю категорию — начинаем круг заново.
    shown = data.get("shown", [])
    if len(shown) >= deck.count(category):
        shown = []

    picked = await _next_card(
        db, callback.from_user.id, deck, category, exclude=current_key, skip=set(shown)
    )
    if picked is None:
        await state.clear()
        await callback.message.delete()
        await callback.message.answer(EMPTY_TEXT, reply_markup=kb.back_to_menu())
        return
    card, scheduled = picked

    await state.set_state(Flashcards.showing_card)
    await state.update_data(card_key=card.key, scheduled=scheduled, shown=[*shown, card.key])
    await media.replace_card(
        callback.message, db, card, _question_caption(deck, category, card), kb.card_question()
    )


# --- выборка карточек ------------------------------------------------------

async def _next_card(
    db: Db,
    user_id: int,
    deck: Deck,
    category: str,
    exclude: str | None = None,
    skip: set[str] | None = None,
) -> tuple[Card, bool] | None:
    """Следующая карточка и признак «показана по расписанию».

    Карточки доступны всегда — режим не упирается в «на сегодня всё повторено».
    Расписание задаёт лишь порядок:

    1. то, что пора повторить (раньше подошёл срок — раньше покажем);
    2. то, что ещё ни разу не открывали;
    3. всё остальное, начиная с ближайших к сроку.

    Третья группа — просмотр вне расписания. Такие карточки возвращаются с
    ``False``, и интервал повторения по ним не сдвигается: иначе пролистывание
    колоды раздувало бы сроки и ломало повторение.

    ``exclude`` — только что показанная карточка: без этого фильтра она бы
    выпадала второй раз подряд, когда в категории почти нечего показывать.
    ``skip`` — показанные в этой сессии: у карточек вне расписания сроки часто
    совпадают, и без обхода по кругу бот крутил бы одни и те же две штуки.
    """
    skip = set(skip or ())
    pool = deck.in_category(category)
    if not pool:
        return None

    progress = await db.progress_for(user_id, [c.key for c in pool])
    now = now_ts()

    due, fresh, later = [], [], []
    for card in pool:
        seen_at = progress.get(card.key)
        if seen_at is None:
            fresh.append(card)
        elif seen_at <= now:
            due.append(card)
        else:
            later.append(card)

    due.sort(key=lambda c: progress[c.key])
    later.sort(key=lambda c: progress[c.key])
    random.shuffle(fresh)

    groups = ((due, True), (fresh, True), (later, False))
    for group, scheduled in groups:
        for card in group:
            if card.key != exclude and card.key not in skip:
                return card, scheduled

    # Круг пройден — начинаем заново, избегая только текущей карточки.
    for group, scheduled in groups:
        for card in group:
            if card.key != exclude:
                return card, scheduled

    # В категории всего одна карточка — показываем её же.
    only = deck.by_key(exclude) if exclude else None
    return (only, False) if only else None


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

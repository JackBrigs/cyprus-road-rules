"""Режим теста: фото знака + 4 варианта, подсчёт результата."""
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
from ..cards import Deck
from ..db import Db

log = logging.getLogger(__name__)
router = Router(name="quiz")

MODE = "quiz"
OPTIONS = 4
PASS_PERCENT = 90       # ориентир реального экзамена на Кипре
MAX_LISTED_ERRORS = 20  # сколько ошибок перечислять в итоге теста


class Quiz(StatesGroup):
    """Состояния сессии теста."""
    choosing_length = State()
    answering = State()


@router.message(Command("quiz"))
async def cmd_quiz(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("✍️ Выберите колоду:", reply_markup=kb.deck_menu(MODE))


@router.callback_query(F.data == kb.cb(kb.A_QUIZ))
async def start_quiz(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_text("✍️ Выберите колоду:", reply_markup=kb.deck_menu(MODE))


@router.callback_query(F.data.startswith(kb.cb(kb.A_DECK, f"{MODE}|")))
async def choose_category(callback: CallbackQuery) -> None:
    _, _, payload = callback.data.split(":", 2)
    _, deck_name = payload.split("|")
    await callback.answer()
    if callback.message is not None:
        deck = cards.get_deck(deck_name)
        await callback.message.edit_text(
            f"✍️ <b>{deck.title}</b>\nВыберите категорию:",
            reply_markup=kb.category_menu(MODE, deck_name),
        )


@router.callback_query(F.data.startswith(kb.cb(kb.A_CATEGORY, f"{MODE}|")))
async def choose_length(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, payload = callback.data.split(":", 2)
    _, deck_name, category = payload.split("|")
    deck = cards.get_deck(deck_name)
    total = deck.count(category)

    await callback.answer()
    if callback.message is None:
        return

    if total < 2:
        await callback.message.edit_text(
            "В этой категории слишком мало знаков для теста — выберите другую.",
            reply_markup=kb.category_menu(MODE, deck_name),
        )
        return

    await state.set_state(Quiz.choosing_length)
    await state.update_data(deck=deck_name, category=category)
    await callback.message.edit_text(
        f"✍️ <b>{deck.category_title(category)}</b> — {total} знаков\n"
        f"Сколько вопросов?",
        reply_markup=kb.quiz_length(total),
    )


@router.callback_query(Quiz.choosing_length, F.data.startswith(kb.cb(kb.A_LENGTH, "")))
async def begin_quiz(callback: CallbackQuery, state: FSMContext, db: Db) -> None:
    _, _, payload = callback.data.split(":", 2)
    data = await state.get_data()
    deck = cards.get_deck(data["deck"])
    category = data["category"]

    limit = None if payload == kb.ALL_LENGTH else int(payload)
    # Язык фиксируется на старте: смена настройки посреди теста не должна
    # рассогласовать уже составленные варианты ответа.
    lang = await db.get_lang(callback.from_user.id)
    questions = _build_questions(deck, category, limit, random.Random(), lang)

    await callback.answer()
    if callback.message is None:
        return

    await state.set_state(Quiz.answering)
    await state.update_data(questions=questions, index=0, score=0, wrong=[], lang=lang)

    await callback.message.delete()
    await media.send_card(
        callback.message,
        db,
        cards.get_card(questions[0]["key"]),
        _question_caption(deck, category, questions[0], 1, len(questions)),
        kb.quiz_options(len(questions[0]["options"])),
    )


@router.callback_query(Quiz.answering, F.data == kb.cb(kb.A_ANSWER, "done"))
async def already_answered(callback: CallbackQuery) -> None:
    await callback.answer("Вы уже ответили на этот вопрос")


@router.callback_query(Quiz.answering, F.data.startswith(kb.cb(kb.A_ANSWER, "")))
async def answer_question(callback: CallbackQuery, state: FSMContext, db: Db) -> None:
    _, _, payload = callback.data.split(":", 2)
    chosen = int(payload)

    data = await state.get_data()
    questions = data.get("questions") or []
    index = data.get("index", 0)
    if index >= len(questions):
        # Состояние есть, а вопросов нет — сессия испорчена, а не активна.
        await state.clear()
        await callback.answer("Тест уже завершён — начните заново", show_alert=True)
        return

    question = questions[index]
    card = cards.get_card(question["key"])
    correct = question["correct"]

    is_right = chosen == correct
    score = data["score"] + (1 if is_right else 0)
    wrong = list(data["wrong"])
    if not is_right:
        wrong.append(question["key"])
    await state.update_data(score=score, wrong=wrong)

    await callback.answer("✅ Верно" if is_right else "❌ Мимо")
    if callback.message is None:
        return

    last = index == len(questions) - 1
    await callback.message.edit_caption(
        caption=_verdict_caption(card, is_right, index + 1, len(questions), data["lang"]),
        reply_markup=kb.quiz_answered(len(question["options"]), correct, chosen, last),
    )


@router.callback_query(Quiz.answering, F.data == kb.cb(kb.A_NEXT))
async def next_question(callback: CallbackQuery, state: FSMContext, db: Db) -> None:
    data = await state.get_data()
    questions = data["questions"]
    index = data["index"] + 1

    await callback.answer()
    if callback.message is None:
        return

    if index >= len(questions):
        await _finish(callback, state, db)
        return

    await state.update_data(index=index)
    deck = cards.get_deck(data["deck"])
    question = questions[index]
    await media.replace_card(
        callback.message,
        db,
        cards.get_card(question["key"]),
        _question_caption(deck, data["category"], question, index + 1, len(questions)),
        kb.quiz_options(len(question["options"])),
    )


async def _finish(callback: CallbackQuery, state: FSMContext, db: Db) -> None:
    data = await state.get_data()
    deck = cards.get_deck(data["deck"])
    total = len(data["questions"])
    score = data["score"]
    wrong = data["wrong"]

    # Ошибки возвращаются в повторение: тест и карточки — одна система прогресса.
    await db.reset_cards(callback.from_user.id, wrong)
    label = f"{deck.title} · {deck.category_title(data['category'])}"
    await db.add_quiz_result(callback.from_user.id, label, score, total)

    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        _result_text(label, score, total, wrong, data["lang"]),
        reply_markup=kb.back_to_menu(),
    )


# --- составление вопросов --------------------------------------------------

def _build_questions(
    deck: Deck, category: str, limit: int | None, rng: random.Random, lang: str
) -> list[dict]:
    pool = deck.in_category(category)
    rng.shuffle(pool)
    if limit is not None:
        pool = pool[:limit]

    questions = []
    field = cards.name_field(lang)
    for card in pool:
        # Варианты на изучаемом языке: экзамен сдаётся на греческом/английском,
        # узнавать нужно именно эти формулировки.
        distractors = cards.pick_distractors(deck, card, OPTIONS - 1, rng, field=field)
        right = cards.name_in(card, lang)
        options = [*distractors, right]
        rng.shuffle(options)
        questions.append(
            {
                "key": card.key,
                "options": options,
                "correct": options.index(right),
            }
        )
    return questions


# --- тексты ----------------------------------------------------------------

def _question_caption(
    deck: Deck, category: str, question: dict, number: int, total: int
) -> str:
    card = cards.get_card(question["key"])
    lines = [
        f"✍️ Вопрос {number} из {total} · {deck.category_title(category)}",
        "",
        hbold(cards.KIND_PROMPTS[card.kind]),
        "",
    ]
    lines += [f"{i + 1}) {name}" for i, name in enumerate(question["options"])]
    return "\n".join(lines)


def _verdict_caption(card, is_right: bool, number: int, total: int, lang: str) -> str:
    head = "✅ <b>Верно!</b>" if is_right else "❌ <b>Неверно.</b> Правильный ответ:"
    lines = [
        f"Вопрос {number} из {total}",
        "",
        head,
        cards.name_line(card, lang),
    ]
    if card.explanation_ru:
        lines.append(hitalic(card.explanation_ru))
    return "\n".join(lines)


def _result_text(label: str, score: int, total: int, wrong: list[str], lang: str) -> str:
    percent = round(score / total * 100) if total else 0
    mark = "🎉" if percent >= PASS_PERCENT else "📉"

    lines = [
        "🏁 <b>Тест завершён</b>",
        label,
        "",
        f"{mark} Результат: <b>{score} из {total}</b> ({percent}%)",
        f"<i>На реальном экзамене нужно ~{PASS_PERCENT}% правильных ответов.</i>",
    ]

    if wrong:
        lines.append("\n<b>Ошибки</b> — вернули в повторение:")
        # Тест «на все вопросы» может дать сотни ошибок, а сообщение Telegram
        # ограничено 4096 символами — показываем начало списка.
        for key in wrong[:MAX_LISTED_ERRORS]:
            card = cards.get_card(key)
            if card:
                lines.append(f"• {cards.name_in(card, lang)}")
        if len(wrong) > MAX_LISTED_ERRORS:
            lines.append(f"…и ещё {len(wrong) - MAX_LISTED_ERRORS}")
    else:
        lines.append("\nБез единой ошибки 👏")

    return "\n".join(lines)

"""Режим теста: фото знака + 4 варианта, подсчёт результата."""
from __future__ import annotations

import asyncio
import logging
import random

from aiogram import Bot, F, Router
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
NEXT_DELAY = 3.0        # пауза на чтение разбора перед следующим вопросом

# Ссылки на фоновые таймеры автоперехода: без них задачу соберёт сборщик мусора.
_TIMERS: set[asyncio.Task] = set()


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
        f"✍️ <b>{deck.category_title(category)}</b> — {total} карточек\n"
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
    sent = await media.send_card(
        callback.message,
        db,
        cards.get_card(questions[0]["key"]),
        _question_caption(deck, category, questions[0], 1, len(questions)),
        kb.quiz_options(len(questions[0]["options"])),
    )
    # id сообщения с вопросом нужен, чтобы отредактировать его при ответе цифрой
    await state.update_data(question_msg_id=sent.message_id)


@router.callback_query(Quiz.answering, F.data == kb.cb(kb.A_ANSWER, "done"))
async def already_answered(callback: CallbackQuery) -> None:
    await callback.answer("Вы уже ответили на этот вопрос")


@router.callback_query(Quiz.answering, F.data.startswith(kb.cb(kb.A_ANSWER, "")))
async def answer_question(
    callback: CallbackQuery, state: FSMContext, db: Db, bot: Bot
) -> None:
    _, _, payload = callback.data.split(":", 2)
    result = await _apply_answer(state, bot, callback.message.chat.id, int(payload))
    if result is None:
        await state.clear()
        await callback.answer("Тест уже завершён — начните заново", show_alert=True)
        return
    is_right, index = result
    await callback.answer("✅ Верно" if is_right else "❌ Мимо")
    _start_timer(bot, callback.message.chat.id, callback.from_user.id, state, db, index)


@router.message(Quiz.answering, F.text.regexp(r"^\s*[1-4]\s*$"))
async def answer_by_text(
    message: Message, state: FSMContext, db: Db, bot: Bot
) -> None:
    """Ответ набранной цифрой — не все нажимают кнопку под фото."""
    chosen = int(message.text.strip()) - 1
    result = await _apply_answer(state, bot, message.chat.id, chosen)
    if result is None:
        await state.clear()
        await message.answer("Тест уже завершён — начните заново", reply_markup=kb.main_menu())
        return
    _start_timer(bot, message.chat.id, message.from_user.id, state, db, result[1])


async def _apply_answer(
    state: FSMContext, bot: Bot, chat_id: int, chosen: int
) -> tuple[bool, int] | None:
    """Засчитывает ответ и переписывает сообщение с вопросом.

    Возвращает (верно ли, номер вопроса) либо None, если активного вопроса нет.
    """
    data = await state.get_data()
    questions = data.get("questions") or []
    index = data.get("index", 0)
    message_id = data.get("question_msg_id")
    if index >= len(questions) or message_id is None:
        return None

    question = questions[index]
    if not 0 <= chosen < len(question["options"]):
        return None

    card = cards.get_card(question["key"])
    correct = question["correct"]
    is_right = chosen == correct

    wrong = list(data["wrong"])
    if not is_right:
        wrong.append(question["key"])
    await state.update_data(score=data["score"] + (1 if is_right else 0), wrong=wrong)

    last = index == len(questions) - 1
    await bot.edit_message_caption(
        chat_id=chat_id,
        message_id=message_id,
        caption=_verdict_caption(card, is_right, index + 1, len(questions), data["lang"]),
        reply_markup=kb.quiz_answered(len(question["options"]), correct, chosen, last),
    )
    return is_right, index


@router.callback_query(Quiz.answering, F.data == kb.cb(kb.A_NEXT))
async def next_question(
    callback: CallbackQuery, state: FSMContext, db: Db, bot: Bot
) -> None:
    """Кнопка «Дальше» — способ не ждать автоматического перехода."""
    await callback.answer()
    if callback.message is None:
        return
    data = await state.get_data()
    await _advance(bot, callback.message.chat.id, callback.from_user.id, state, db,
                   from_index=data.get("index", 0))


async def _advance(
    bot: Bot, chat_id: int, user_id: int, state: FSMContext, db: Db, from_index: int
) -> None:
    """Показывает следующий вопрос или итог.

    ``from_index`` — номер вопроса, с которого уходим. Если в состоянии уже другой
    номер, значит переход состоялся раньше (нажали «Дальше», не дождавшись таймера,
    или наоборот) — второй раз не двигаем, иначе вопрос проскочит.
    """
    data = await state.get_data()
    questions = data.get("questions") or []
    index = data.get("index", 0)
    if not questions or index != from_index:
        return

    index += 1
    await state.update_data(index=index)

    if index >= len(questions):
        await _finish(bot, chat_id, user_id, state, db)
        return

    deck = cards.get_deck(data["deck"])
    question = questions[index]
    shown = await media.replace_card_by_id(
        bot,
        chat_id,
        data["question_msg_id"],
        db,
        cards.get_card(question["key"]),
        _question_caption(deck, data["category"], question, index + 1, len(questions)),
        kb.quiz_options(len(question["options"])),
    )
    if shown is not None:
        await state.update_data(question_msg_id=shown.message_id)


async def _schedule_advance(
    bot: Bot, chat_id: int, user_id: int, state: FSMContext, db: Db, from_index: int
) -> None:
    """Автопереход к следующему вопросу — даёт прочитать разбор ответа."""
    await asyncio.sleep(NEXT_DELAY)
    try:
        await _advance(bot, chat_id, user_id, state, db, from_index)
    except Exception:  # фоновая задача: исключение иначе потеряется
        log.exception("Не удалось перейти к следующему вопросу")


def _start_timer(bot: Bot, chat_id: int, user_id: int, state: FSMContext,
                 db: Db, from_index: int) -> None:
    task = asyncio.create_task(
        _schedule_advance(bot, chat_id, user_id, state, db, from_index)
    )
    # Без ссылки задачу может собрать сборщик мусора до её завершения.
    _TIMERS.add(task)
    task.add_done_callback(_TIMERS.discard)


async def _finish(
    bot: Bot, chat_id: int, user_id: int, state: FSMContext, db: Db
) -> None:
    data = await state.get_data()
    deck = cards.get_deck(data["deck"])
    total = len(data["questions"])
    score = data["score"]
    wrong = data["wrong"]

    # Ошибки возвращаются в повторение: тест и карточки — одна система прогресса.
    await db.reset_cards(user_id, wrong)
    label = f"{deck.title} · {deck.category_title(data['category'])}"
    await db.add_quiz_result(user_id, label, score, total)

    message_id = data.get("question_msg_id")
    await state.clear()
    if message_id is not None:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    await bot.send_message(
        chat_id,
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
    tail = "итог" if number == total else "следующий вопрос"
    lines.append(f"\n<i>Через {NEXT_DELAY:.0f} с — {tail}…</i>")
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

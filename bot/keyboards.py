"""Inline-клавиатуры.

Callback data — формат ``c:<action>:<payload>``, лимит Telegram 64 байта.
Длинные значения (id карточки) в callback не кладём: текущая карточка и состояние
теста живут в FSM, в кнопках только действие и короткий payload.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import cards

CB_PREFIX = "c"

# Действия
A_CARDS = "cards"
A_QUIZ = "quiz"
A_STATS = "stats"
A_MENU = "menu"
A_DECK = "deck"        # payload: <mode>|<deck>
A_CATEGORY = "cat"     # payload: <mode>|<deck>|<category>
A_LENGTH = "len"       # payload: <n> либо "all"
A_SHOW = "show"
A_NEXT = "next"
A_ANSWER = "ans"       # payload: индекс варианта
A_STOP = "stop"
A_SETTINGS = "cfg"
A_LANG = "lang"        # payload: en | el


def cb(action: str, payload: str = "") -> str:
    return f"{CB_PREFIX}:{action}:{payload}"


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Карточки", callback_data=cb(A_CARDS))],
            [InlineKeyboardButton(text="✍️ Тест", callback_data=cb(A_QUIZ))],
            [InlineKeyboardButton(text="📊 Прогресс", callback_data=cb(A_STATS))],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data=cb(A_SETTINGS))],
        ]
    )


def settings_menu(current_lang: str) -> InlineKeyboardMarkup:
    """Выбор языка изучаемых названий."""
    builder = InlineKeyboardBuilder()
    for code, meta in cards.LANGS.items():
        mark = "✅ " if code == current_lang else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{mark}{meta['flag']} {meta['title']}",
                callback_data=cb(A_LANG, code),
            )
        )
    builder.row(InlineKeyboardButton(text="⬅️ Меню", callback_data=cb(A_MENU)))
    return builder.as_markup()


def deck_menu(mode: str) -> InlineKeyboardMarkup:
    """Выбор колоды: полный каталог или экзаменационный минимум."""
    builder = InlineKeyboardBuilder()
    for name in (cards.DECK_FULL, cards.DECK_MINI):
        deck = cards.get_deck(name)
        builder.row(
            InlineKeyboardButton(
                text=f"{deck.title} ({len(deck.cards)})",
                callback_data=cb(A_DECK, f"{mode}|{name}"),
            )
        )
    builder.row(InlineKeyboardButton(text="⬅️ Меню", callback_data=cb(A_MENU)))
    return builder.as_markup()


def category_menu(mode: str, deck_name: str) -> InlineKeyboardMarkup:
    """Категории выбранной колоды + «Все»."""
    deck = cards.get_deck(deck_name)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🎯 Все ({len(deck.cards)})",
            callback_data=cb(A_CATEGORY, f"{mode}|{deck_name}|{cards.ALL_CATEGORIES}"),
        )
    )
    for key in deck.used_categories():
        builder.row(
            InlineKeyboardButton(
                text=f"{deck.category_title(key)} ({deck.count(key)})",
                callback_data=cb(A_CATEGORY, f"{mode}|{deck_name}|{key}"),
            )
        )
    builder.row(InlineKeyboardButton(text="⬅️ Меню", callback_data=cb(A_MENU)))
    return builder.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Меню", callback_data=cb(A_MENU))]]
    )


_STOP = InlineKeyboardButton(text="⏹ Стоп", callback_data=cb(A_STOP))


# --- карточки --------------------------------------------------------------

def card_question() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Показать ответ", callback_data=cb(A_SHOW))],
            [_STOP],
        ]
    )


def card_answer() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Дальше", callback_data=cb(A_NEXT))],
            [_STOP],
        ]
    )


# --- тест ------------------------------------------------------------------

ALL_LENGTH = "all"

# Варианты ответа перечислены в подписи к фото — на кнопках только цифры:
# названия знаков бывают длиной под 60 символов и на кнопке обрезаются.
DIGITS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣")


def quiz_length(total: int) -> InlineKeyboardMarkup:
    """Длина теста: предлагаем только то, что помещается в выбранную категорию."""
    builder = InlineKeyboardBuilder()
    for n in (10, 20):
        if total > n:
            builder.row(
                InlineKeyboardButton(text=f"{n} вопросов", callback_data=cb(A_LENGTH, str(n)))
            )
    builder.row(
        InlineKeyboardButton(
            text=f"Все ({total})", callback_data=cb(A_LENGTH, ALL_LENGTH)
        )
    )
    builder.row(InlineKeyboardButton(text="⬅️ Меню", callback_data=cb(A_MENU)))
    return builder.as_markup()


def quiz_options(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=DIGITS[i], callback_data=cb(A_ANSWER, str(i)))
                for i in range(count)
            ],
            [_STOP],
        ]
    )


def quiz_answered(count: int, correct: int, chosen: int, last: bool) -> InlineKeyboardMarkup:
    """Клавиатура после ответа: верный вариант помечен ✅, ошибочный выбор — ❌."""
    row = []
    for i in range(count):
        if i == correct:
            text = f"✅ {i + 1}"
        elif i == chosen:
            text = f"❌ {i + 1}"
        else:
            text = DIGITS[i]
        # Кнопки уже отработали, но callback_data обязателен — вешаем no-op.
        row.append(InlineKeyboardButton(text=text, callback_data=cb(A_ANSWER, "done")))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            row,
            [
                InlineKeyboardButton(
                    text="🏁 Результат" if last else "➡️ Дальше", callback_data=cb(A_NEXT)
                )
            ],
            [_STOP],
        ]
    )

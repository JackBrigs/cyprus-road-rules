"""Колоды знаков и логика интервального повторения (система Лейтнера).

Две независимые колоды:
  * ``full`` — полный каталог из ``data/signs_full.json`` (234 знака, 13 категорий);
  * ``mini`` — «экзаменационный минимум» из ``data/signs.json`` (63 карточки с пояснениями).

Сопоставление между колодами не делается — они самостоятельны, прогресс по ним
разделён префиксом в ``Card.key``.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DECK_FULL = "full"
DECK_MINI = "mini"

# Система Лейтнера: 5 коробок, интервал в днях до следующего показа.
BOX_INTERVAL_DAYS = (0, 1, 3, 7, 21)
MAX_BOX = len(BOX_INTERVAL_DAYS) - 1


ALL_CATEGORIES = "all"

# Язык названий, которые нужно выучить. Русский показывается всегда как перевод.
LANG_EN = "en"
LANG_EL = "el"
DEFAULT_LANG = LANG_EN
LANGS = {
    LANG_EN: {"title": "English", "flag": "🇬🇧", "field": "name_en"},
    LANG_EL: {"title": "Ελληνικά", "flag": "🇬🇷", "field": "name_el"},
}


# Тип объекта. Знак, разметка и сигнал — разные сущности: подмешивать разметку
# в варианты ответа про знак бессмысленно, поэтому дистракторы берутся только
# внутри своего типа, а вопрос формулируется по типу.
KIND_SIGN = "sign"
KIND_MARKING = "marking"
KIND_SIGNAL = "signal"

KIND_PROMPTS = {
    KIND_SIGN: "Что это за знак?",
    KIND_MARKING: "Что это за разметка?",
    KIND_SIGNAL: "Что означает сигнал?",
}
KIND_TITLES = {
    KIND_SIGN: "Знак",
    KIND_MARKING: "Разметка",
    KIND_SIGNAL: "Сигнал",
}

# Категории, которые не являются знаками. Остальные — знаки.
CATEGORY_KINDS = {
    "marking": KIND_MARKING,              # дорожная разметка
    "additional_markings": KIND_MARKING,  # дополнительная маркировка
    "roundabout": KIND_MARKING,           # схемы движения по кругу
    "warden": KIND_SIGNAL,                # жесты регулировщика
    "light": KIND_SIGNAL,                 # фазы светофора (колода-минимум)
}


def kind_of(category: str) -> str:
    return CATEGORY_KINDS.get(category, KIND_SIGN)


@dataclass(frozen=True)
class Card:
    key: str            # "<deck>:<id>" — идентификатор в БД, уникален между колодами
    deck: str
    id: str
    category: str
    kind: str
    name_ru: str
    name_en: str
    name_el: str
    explanation_ru: str | None
    image: str          # абсолютный путь к файлу, который принимает Telegram (png/jpg)


@dataclass(frozen=True)
class Deck:
    name: str
    title: str
    cards: tuple[Card, ...]
    categories: dict[str, dict[str, str]]   # ключ -> {"ru": ..., "en": ...}

    def __post_init__(self) -> None:
        by_key = {c.key: c for c in self.cards}
        by_category: dict[str, tuple[Card, ...]] = {ALL_CATEGORIES: self.cards}
        for category in self.categories:
            by_category[category] = tuple(c for c in self.cards if c.category == category)
        object.__setattr__(self, "_by_key", by_key)
        object.__setattr__(self, "_by_category", by_category)

    def by_key(self, key: str) -> Card | None:
        return self._by_key.get(key)

    def in_category(self, category: str) -> list[Card]:
        return list(self._by_category.get(category, ()))

    def count(self, category: str) -> int:
        return len(self._by_category.get(category, ()))

    def used_categories(self) -> list[str]:
        """Ключи категорий, в которых есть хотя бы одна карточка — в порядке из JSON."""
        return [c for c in self.categories if self._by_category.get(c)]

    def category_title(self, category: str) -> str:
        if category == ALL_CATEGORIES:
            return "Все категории"
        meta = self.categories.get(category)
        return meta["ru"] if meta else category


def _sendable_image(path: str) -> str:
    """Путь к файлу, который Telegram отрендерит как фото.

    Telegram не показывает SVG в сообщениях, поэтому если рядом с исходником лежит
    одноимённый ``.png`` (его делает ``scripts/convert_full_images.sh``) — берём его.
    Оригиналы ``.jpg``/``.png`` используются как есть.
    """
    absolute = path if os.path.isabs(path) else os.path.join(ROOT, path)
    png = os.path.splitext(absolute)[0] + ".png"
    if os.path.exists(png):
        return png
    return absolute


def _load_full() -> Deck:
    with open(os.path.join(ROOT, "data", "signs_full.json"), encoding="utf-8") as f:
        raw = json.load(f)
    cards = tuple(
        Card(
            key=f"{DECK_FULL}:{c['id']}",
            deck=DECK_FULL,
            id=c["id"],
            category=c["category"],
            kind=kind_of(c["category"]),
            name_ru=c["name_ru"],
            name_en=c["name_en"],
            name_el=c["name_el"],
            explanation_ru=c.get("explanation_ru"),
            image=_sendable_image(c["image"]),
        )
        for c in raw["cards"]
    )
    return Deck(DECK_FULL, "Полный каталог", cards, raw["categories"])


def _load_mini() -> Deck:
    with open(os.path.join(ROOT, "data", "signs.json"), encoding="utf-8") as f:
        raw = json.load(f)
    cards = tuple(
        Card(
            key=f"{DECK_MINI}:{c['id']}",
            deck=DECK_MINI,
            id=c["id"],
            category=c["category"],
            kind=kind_of(c["category"]),
            name_ru=c["name_ru"],
            name_en=c["name_en"],
            name_el=c["name_el"],
            explanation_ru=c.get("explanation_ru"),
            image=_sendable_image(c.get("png") or c["svg"]),
        )
        for c in raw["cards"]
    )
    return Deck(DECK_MINI, "Экзаменационный минимум", cards, raw["categories"])


@lru_cache(maxsize=1)
def decks() -> dict[str, Deck]:
    """Обе колоды, загружаются один раз при первом обращении."""
    return {DECK_FULL: _load_full(), DECK_MINI: _load_mini()}


def get_deck(name: str) -> Deck:
    return decks()[name]


def get_card(key: str) -> Card | None:
    deck_name = key.split(":", 1)[0]
    deck = decks().get(deck_name)
    return deck.by_key(key) if deck else None


# --- языки -----------------------------------------------------------------

def name_field(lang: str) -> str:
    return LANGS.get(lang, LANGS[DEFAULT_LANG])["field"]


def name_in(card: Card, lang: str) -> str:
    return getattr(card, name_field(lang))


def name_line(card: Card, lang: str) -> str:
    """Название только на изучаемом языке — учить нужно одну формулировку."""
    meta = LANGS.get(lang, LANGS[DEFAULT_LANG])
    return f"{meta['flag']} <b>{getattr(card, meta['field'])}</b>"


# --- Лейтнер ---------------------------------------------------------------

def next_box(box: int) -> int:
    """Коробка после просмотра карточки: интервал до следующего показа растёт.

    Обратно в нулевую коробку карточку возвращает только ошибка в тесте
    (``Db.reset_cards``) — самооценки в режиме карточек нет.
    """
    return min(box + 1, MAX_BOX)


def interval_seconds(box: int) -> int:
    """Через сколько секунд карточка из коробки ``box`` появится снова."""
    return BOX_INTERVAL_DAYS[max(0, min(box, MAX_BOX))] * 86400


# --- Тест ------------------------------------------------------------------

def pick_distractors(
    deck: Deck, card: Card, count: int, rng: random.Random, field: str = "name_ru"
) -> list[str]:
    """Неверные варианты — приоритетно из той же категории.

    Варианты из одной категории похожи между собой, поэтому вопрос получается
    осмысленнее. Если в категории не хватает карточек — добираем из колоды, но
    только среди объектов того же типа: предлагать названия разметки в вопросе
    про знак бессмысленно.
    ``field`` — какое название брать: ``name_ru``, ``name_en`` или ``name_el``.
    """
    right = getattr(card, field)
    taken = {right}
    pool = [
        getattr(c, field)
        for c in deck.in_category(card.category)
        if getattr(c, field) not in taken
    ]
    rng.shuffle(pool)

    options: list[str] = []
    for name in pool:
        if len(options) == count:
            break
        if name not in taken:
            options.append(name)
            taken.add(name)

    if len(options) < count:
        rest = [
            getattr(c, field)
            for c in deck.cards
            if c.kind == card.kind and getattr(c, field) not in taken
        ]
        rng.shuffle(rest)
        for name in rest:
            if len(options) == count:
                break
            options.append(name)
            taken.add(name)

    return options

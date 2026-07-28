"""Перехват всего, для чего не нашлось обработчика.

Без этого роутера нажатие кнопки из завершённой сессии или неожиданное сообщение
не делали бы ровно ничего: пользователь видит молчание и считает, что бот завис.
Роутер подключается последним, поэтому сюда попадает только неразобранное.
Каждый такой случай пишется в лог с содержимым — иначе причину не найти.
"""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from .menu import greeting

log = logging.getLogger(__name__)
router = Router(name="fallback")


@router.callback_query()
async def expired_session(callback: CallbackQuery, state: FSMContext) -> None:
    log.info(
        "Кнопка без обработчика: data=%r состояние=%s", callback.data, await state.get_state()
    )
    await state.clear()
    await callback.answer("Эта сессия уже завершена — начните заново", show_alert=True)
    if callback.message is None:
        return
    await callback.message.answer(greeting(), reply_markup=kb.main_menu())


@router.message()
async def unexpected_message(message: Message, state: FSMContext) -> None:
    log.info(
        "Сообщение без обработчика: text=%r состояние=%s", message.text, await state.get_state()
    )
    await message.answer(
        "Не понял. Пользуйтесь кнопками под сообщением — или начните заново:",
        reply_markup=kb.main_menu(),
    )

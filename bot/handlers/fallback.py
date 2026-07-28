"""Перехват кнопок, для которых не нашлось обработчика.

Такое бывает, когда сессия из старого сообщения уже завершена: без этого роутера
нажатие не делало бы ровно ничего — Telegram оставляет кнопку «крутиться», а
пользователь видит молчание. Роутер подключается последним, поэтому сюда попадает
только то, что не разобрали остальные.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from .. import keyboards as kb
from .menu import greeting

log = logging.getLogger(__name__)
router = Router(name="fallback")


@router.callback_query(F.data.startswith(f"{kb.CB_PREFIX}:"))
async def expired_session(callback: CallbackQuery, state: FSMContext) -> None:
    log.info("Кнопка без активной сессии: %s", callback.data)
    await state.clear()
    await callback.answer("Эта сессия уже завершена — начните заново", show_alert=True)
    if callback.message is None:
        return
    await callback.message.answer(greeting(), reply_markup=kb.main_menu())

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def plan_selection_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ Быстрый", callback_data="plan_fast"),
            ],
            [
                InlineKeyboardButton(text="⚖️ Средний", callback_data="plan_medium"),
            ],
            [
                InlineKeyboardButton(text="🐢 Долгий", callback_data="plan_slow"),
            ],
        ]
    )
    return keyboard


def execution_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выполнил", callback_data="step_done"),
                InlineKeyboardButton(text="❌ Не выполнил", callback_data="step_failed"),
            ]
        ]
    )
    return keyboard

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def confirm_plan_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data="accept_plan"),
            ],
            [
                InlineKeyboardButton(text="🔁 Переделать", callback_data="reject_plan"),
            ],
        ]
    )
    return keyboard
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def coach_style_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Жесткий", callback_data="coach_aggressive")],
            [InlineKeyboardButton(text="⚖️ Баланс", callback_data="coach_balanced")],
            [InlineKeyboardButton(text="🤝 Мягкий", callback_data="coach_soft")],
        ]
    )
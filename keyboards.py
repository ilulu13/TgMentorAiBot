from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================
# PROFILE OPTIONS
# =========================
def build_options_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    buttons = []

    for index, option in enumerate(options):
        buttons.append(
            [
                InlineKeyboardButton(
                    text=option,
                    callback_data=f"profile_option:{index}"
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================
# PLAN TYPE
# =========================
def plan_selection_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Быстрый", callback_data="plan_fast")],
            [InlineKeyboardButton(text="⚖️ Средний", callback_data="plan_medium")],
            [InlineKeyboardButton(text="🐢 Долгий", callback_data="plan_slow")],
        ]
    )


# =========================
# EXECUTION (старый flow)
# =========================
def execution_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выполнил", callback_data="step_done"),
                InlineKeyboardButton(text="❌ Не выполнил", callback_data="step_failed"),
            ]
        ]
    )


# =========================
# PLAN CONFIRM
# =========================
def confirm_plan_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять", callback_data="accept_plan")],
            [InlineKeyboardButton(text="🔁 Переделать", callback_data="reject_plan")],
        ]
    )


# =========================
# COACH STYLE
# =========================
def coach_style_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Жесткий", callback_data="coach_aggressive")],
            [InlineKeyboardButton(text="⚖️ Баланс", callback_data="coach_balanced")],
            [InlineKeyboardButton(text="🤝 Мягкий", callback_data="coach_soft")],
        ]
    )


# =========================
# 🔥 DAILY EXECUTION (NEW LOGIC)
# =========================
def daily_execution_keyboard(tasks: list[dict]) -> InlineKeyboardMarkup:
    current_task = None

    for task in tasks:
        status = task.get("status", "pending")
        if status not in {"done", "skipped", "failed"}:
            current_task = task
            break

    if not current_task:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="daily_refresh")]
            ]
        )

    proof_required = current_task.get("proof_required", False)
    proofs = current_task.get("proofs") or []
    proof_accepted = any(p.get("status") == "accepted" for p in proofs)

    rows = []

    if proof_required:
        if proof_accepted:
            rows.append([
                InlineKeyboardButton(text="✅ Done", callback_data="daily_task_done"),
                InlineKeyboardButton(text="⏭ Skip", callback_data="daily_task_skip"),
            ])
        else:
            rows.append([
                InlineKeyboardButton(text="📎 Proof", callback_data="daily_task_proof"),
                InlineKeyboardButton(text="⏭ Skip", callback_data="daily_task_skip"),
            ])
    else:
        rows.append([
            InlineKeyboardButton(text="✅ Done", callback_data="daily_task_done"),
            InlineKeyboardButton(text="⏭ Skip", callback_data="daily_task_skip"),
        ])

    rows.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="daily_refresh")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
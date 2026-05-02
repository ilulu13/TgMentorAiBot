from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================
# PROFILE OPTIONS
# =========================
def build_options_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for index, option in enumerate(options):
        buttons.append([
            InlineKeyboardButton(
                text=option,
                callback_data=f"profile_option:{index}"
            )
        ])
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
# DAY LIST — кнопки выбора задач
# Callback: dt_sel:{index}  (dt_sel = daily task select)
# Max tasks: 9, index 0-8 → callback "dt_sel:0" = 8 bytes, хорошо
# =========================
def day_list_keyboard(tasks: list[dict]) -> InlineKeyboardMarkup:
    """
    Показывает кнопки [1] [2] [3] ... для выбора задачи,
    плюс [➡ Следующий день] если все обязательные задачи закрыты,
    плюс [🔄 Обновить] всегда.
    """
    rows = []

    # Кнопки номеров задач — по 4 в ряд
    number_buttons = []
    for i, task in enumerate(tasks):
        status = task.get("status", "pending")
        # Визуальный маркер на кнопке
        if status == "done":
            label = f"✅{i + 1}"
        elif status in {"skipped", "failed"}:
            label = f"⏭{i + 1}"
        else:
            # проверяем proof статус
            proof_required = task.get("proof_required", False)
            proofs = task.get("proofs") or []
            if proof_required and proofs:
                last_status = proofs[-1].get("status")
                if last_status == "accepted":
                    label = f"🔓{i + 1}"
                elif last_status in {"uploaded", "checking"}:
                    label = f"⏳{i + 1}"
                elif last_status in {"rejected", "needs_more"}:
                    label = f"⚠️{i + 1}"
                else:
                    label = f"⭕{i + 1}"
            else:
                label = f"⭕{i + 1}"

        number_buttons.append(
            InlineKeyboardButton(text=label, callback_data=f"dt_sel:{i}")
        )

    # Разбиваем по 4 в ряд
    for i in range(0, len(number_buttons), 4):
        rows.append(number_buttons[i:i + 4])

    # Кнопка "следующий день" если все обязательные задачи завершены
    if _all_required_tasks_closed(tasks):
        rows.append([
            InlineKeyboardButton(
                text="➡ Следующий день",
                callback_data="dl_next_day"
            )
        ])

    rows.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="dl_refresh")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _all_required_tasks_closed(tasks: list[dict]) -> bool:
    """Все обязательные задачи имеют финальный статус."""
    for task in tasks:
        if not task.get("is_required", True):
            continue
        status = task.get("status", "pending")
        if status not in {"done", "skipped", "failed"}:
            return False
    return True


# =========================
# TASK DETAIL — кнопки действий с задачей
# =========================
def task_detail_keyboard(task: dict) -> InlineKeyboardMarkup:
    """
    Кнопки зависят от статуса задачи и наличия proof.
    Всегда есть [⬅ Назад].
    """
    rows = []
    status = task.get("status", "pending")

    # Задача уже закрыта — только Назад
    if status in {"done", "skipped", "failed"}:
        rows.append([
            InlineKeyboardButton(text="⬅ Назад к списку", callback_data="dt_back")
        ])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    proof_required = task.get("proof_required", False)
    proofs = task.get("proofs") or []
    proof_accepted = any(p.get("status") == "accepted" for p in proofs)

    if not proof_required:
        # Proof не нужен — сразу Done или Skip
        rows.append([
            InlineKeyboardButton(text="✅ Done", callback_data="dt_done"),
            InlineKeyboardButton(text="⏭ Пропустить", callback_data="dt_skip"),
        ])
    elif proof_accepted:
        # Proof принят — можно Done
        rows.append([
            InlineKeyboardButton(text="✅ Done", callback_data="dt_done"),
            InlineKeyboardButton(text="⏭ Пропустить", callback_data="dt_skip"),
        ])
    else:
        # Нужен proof, но ещё нет accepted
        rows.append([
            InlineKeyboardButton(text="📎 Отправить proof", callback_data="dt_proof"),
            InlineKeyboardButton(text="⏭ Пропустить", callback_data="dt_skip"),
        ])

    rows.append([
        InlineKeyboardButton(text="⬅ Назад к списку", callback_data="dt_back")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# =========================
# NEXT DAY — после завершения всех задач
# =========================
def next_day_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡ Следующий день", callback_data="dl_next_day")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="dl_refresh")],
        ]
    )
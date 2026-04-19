from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import random

from states import GoalFlow
from keyboards import (
    confirm_plan_keyboard,
    coach_style_keyboard,
    build_options_keyboard,
    daily_execution_keyboard,
)
from api_client import (
    get_or_create_user,
    create_goal,
    start_profiling,
    submit_profiling_answer,
    generate_plan,
    get_current_plan,
    accept_plan,
    get_next_daily_plan,
    set_daily_task_status,
    create_daily_task_proof,
)

router = Router()

def render_profiling_question_text(result: dict) -> str:
    needs_follow_up = result.get("needs_follow_up", False)
    feedback_message = result.get("feedback_message")
    follow_up_question = result.get("follow_up_question")
    current_question_text = result.get("current_question_text", "Следующий вопрос")
    example_answer = result.get("example_answer")

    answered = result.get("questions_answered_count")
    total = result.get("questions_total_count")

    if needs_follow_up:
        parts = ["⚠️ Нужно уточнить"]

        if feedback_message:
            parts.append(feedback_message)

        parts.append(follow_up_question or current_question_text)

        if example_answer:
            parts.append(f"💡 Пример:\n{example_answer}")

        return "\n\n".join(parts)

    parts = []

    if isinstance(answered, int) and isinstance(total, int) and total > 0:
        parts.append(f"📊 Вопрос {answered + 1}/{total}")

    parts.append(current_question_text)

    if feedback_message:
        parts.append(feedback_message)

    parts.append("💡 Подсказка:\nОтветь конкретно, с цифрами или фактами")

    if example_answer:
        parts.append(f"📌 Пример:\n{example_answer}")

    return "\n\n".join(parts)


def get_positive_feedback():
    phrases = [
        "🔥 Понял, двигаемся дальше",
        "👌 Отлично, фиксирую",
        "💪 Хорошо, идем дальше",
        "🚀 Принял, продолжаем",
        "👍 Ок, двигаемся"
    ]
    return random.choice(phrases)

def get_question_type(result: dict) -> str:
    question_type = result.get("question_type")

    if not question_type:
        current_question_key = result.get("current_question_key")

        if current_question_key == "coach_style":
            return "choice"

        return "text"

    return question_type

async def send_profiling_response(
    message_obj,
    result: dict,
    state: FSMContext,
    *,
    show_positive_feedback: bool = True,
):
    current_question_key = result.get("current_question_key")
    question_type = get_question_type(result)
    text = render_profiling_question_text(result)

    needs_follow_up = result.get("needs_follow_up", False)
    answer_accepted = result.get("answer_accepted", False)
    suggested_options = result.get("suggested_options") or []

    async def answer_with_optional_keyboard():
        if suggested_options:
            await message_obj.answer(
                text,
                reply_markup=build_options_keyboard(suggested_options)
            )
        else:
            await message_obj.answer(text)

    if needs_follow_up:
        if question_type == "choice" and current_question_key == "coach_style":
            await message_obj.answer(
                text,
                reply_markup=coach_style_keyboard()
            )
            await state.set_state(GoalFlow.choosing_coach_style)
            return

        await answer_with_optional_keyboard()
        await state.set_state(GoalFlow.clarifying_goal)
        return

    if show_positive_feedback and answer_accepted:
        feedback = get_positive_feedback()
        await message_obj.answer(feedback)

    if question_type == "choice":
        if current_question_key == "coach_style":
            await message_obj.answer(
                text,
                reply_markup=coach_style_keyboard()
            )
            await state.set_state(GoalFlow.choosing_coach_style)
            return

        await answer_with_optional_keyboard()
        await state.set_state(GoalFlow.clarifying_goal)
        return

    if question_type == "choice_or_text":
        if current_question_key == "coach_style":
            await message_obj.answer(
                text,
                reply_markup=coach_style_keyboard()
            )
            await state.set_state(GoalFlow.choosing_coach_style)
            return

        await answer_with_optional_keyboard()
        await state.set_state(GoalFlow.clarifying_goal)
        return

    if question_type == "special":
        if current_question_key == "coach_style":
            await message_obj.answer(
                text,
                reply_markup=coach_style_keyboard()
            )
            await state.set_state(GoalFlow.choosing_coach_style)
            return

        await answer_with_optional_keyboard()
        await state.set_state(GoalFlow.clarifying_goal)
        return

    await answer_with_optional_keyboard()
    await state.set_state(GoalFlow.clarifying_goal)

def render_profiling_summary(summary: dict | None) -> str:
    if not summary or not isinstance(summary, dict):
        return ""

    field_map = [
        ("goal_clarity", "🎯 Цель"),
        ("current_state", "📍 Текущая точка"),
        ("deadline", "⏳ Срок"),
        ("resources", "🛠 Ресурсы"),
        ("constraints", "🚧 Ограничения"),
        ("motivation", "🔥 Мотивация"),
    ]

    lines = []

    for key, label in field_map:
        value = summary.get(key)

        if not value:
            continue

        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)

        if isinstance(value, dict):
            parts = []
            for sub_key, sub_value in value.items():
                if sub_value:
                    parts.append(f"{sub_key}: {sub_value}")
            value = ", ".join(parts)

        if value:
            lines.append(f"{label}: {value}")

    if not lines:
        return ""

    return "Вот что я зафиксировал по твоей цели:\n\n" + "\n".join(lines)

async def send_plan_preview(message_obj, goal_id: str, state: FSMContext, profiling_result: dict | None = None):
    profiling_summary = None
    if profiling_result:
        profiling_summary = profiling_result.get("profiling_summary")

    summary_text = render_profiling_summary(profiling_summary)

    if summary_text:
        await message_obj.answer(
            f"Профилирование завершено ✅\n\n{summary_text}"
        )
        await message_obj.answer("Генерирую план... ⏳")
    else:
        await message_obj.answer(
            "Профилирование завершено ✅\n\n"
            "Генерирую план... ⏳"
        )

    await generate_plan(goal_id)
    plan = await get_current_plan(goal_id)

    summary = plan.get("summary") or plan.get("summary_text") or "План готов"
    roadmap = plan.get("roadmap") or plan.get("content", {}).get("roadmap", [])

    roadmap_text = ""
    if roadmap:
        roadmap_items = "\n".join([f"• {item}" for item in roadmap])
        roadmap_text = f"\n\n📋 Общий путь:\n{roadmap_items}"

    await message_obj.answer(
        f"📌 Коротко:\n{summary}"
        f"{roadmap_text}\n\n"
        f"👉 Принять этот план?",
        reply_markup=confirm_plan_keyboard()
    )

    await state.set_state(GoalFlow.confirming_plan)




# ======================================================
# SEND NEXT DAILY PLAN
# ======================================================

# ======================================================
# SEND NEXT DAILY PLAN
# ======================================================

async def send_next_daily_plan(message_obj, state: FSMContext, source: str = "general"):
    data = await state.get_data()
    goal_id = data.get("goal_id")
    current_message_id = data.get("current_daily_message_id")

    if not goal_id:
        await message_obj.answer("Не нашел активную цель. Начни заново через /start")
        return

    next_response = await get_next_daily_plan(goal_id)

    if not next_response:
        await message_obj.answer("Не смог получить задачи на день. Попробуй еще раз.")
        return

    if next_response.get("error") == "timeout":
        await message_obj.answer("Обновляю следующий шаг...")
        return

    daily_plan = next_response.get("daily_plan")

    # =========================
    # НЕТ АКТИВНОГО ПЛАНА
    # =========================
    if not daily_plan:
        if source == "accept":
            text = "План принят ✅\n\nСледующий день пришлю по расписанию."
        elif source == "execution":
            text = "✅ День завершён\n\nСледующий день пришлю позже."
        else:
            text = "Сейчас нет активных задач."

        if current_message_id:
            try:
                await message_obj.bot.edit_message_text(
                    chat_id=message_obj.chat.id,
                    message_id=current_message_id,
                    text=text,
                )
            except Exception:
                await message_obj.answer(text)
        else:
            await message_obj.answer(text)

        await state.update_data(
            current_daily_plan=None,
            current_daily_plan_id=None,
            current_daily_tasks=[],
            current_daily_message_id=None,
        )
        return

    # =========================
    # НОРМАЛЬНЫЙ FLOW
    # =========================
    daily_plan_id = daily_plan.get("id") or daily_plan.get("daily_plan_id")
    tasks = daily_plan.get("tasks") or []

    await state.update_data(
        current_daily_plan=daily_plan,
        current_daily_plan_id=daily_plan_id,
        current_daily_tasks=tasks,
    )

    state_data = await state.get_data()
    streak = state_data.get("streak", 0)
    coaching_mode = state_data.get("coaching_mode", "normal")
    last_skip_reason = state_data.get("last_skip_reason")

    text = render_daily_plan_text(
        daily_plan,
        streak=streak,
        coaching_mode=coaching_mode,
        last_skip_reason=last_skip_reason,
    )

    # =========================
    # РЕДАКТИРУЕМ ИЛИ СОЗДАЕМ
    # =========================
    if current_message_id:
        try:
            await message_obj.bot.edit_message_text(
                chat_id=message_obj.chat.id,
                message_id=current_message_id,
                text=text,
                reply_markup=daily_execution_keyboard(tasks),
            )
            return
        except Exception:
            pass

    sent = await message_obj.answer(
        text,
        reply_markup=daily_execution_keyboard(tasks),
    )

    await state.update_data(current_daily_message_id=sent.message_id)


# ======================================================
# TEXT RENDER
# ======================================================

def render_daily_plan_text(
    daily_plan: dict,
    streak: int = 0,
    coaching_mode: str = "normal",
    last_skip_reason: str | None = None,
) -> str:
    parts = []

    headline = daily_plan.get("headline")
    focus = daily_plan.get("focus") or daily_plan.get("focus_message")
    summary = daily_plan.get("summary")
    main_task_title = daily_plan.get("main_task_title")
    tasks = daily_plan.get("tasks") or []

    proofs_required = daily_plan.get("proofs_required_count")
    proofs_accepted = daily_plan.get("proofs_accepted_count")

    # =========================
    # ТОН
    # =========================
    if coaching_mode == "recovery":
        parts.append("Возвращаемся в ритм 👇")
        if last_skip_reason:
            parts.append(f"Причина: {last_skip_reason}")
    elif coaching_mode == "momentum":
        parts.append(f"🔥 Серия: {streak}")
    else:
        if streak == 0:
            parts.append("Начинаем спокойно 👇")
        else:
            parts.append(f"Серия: {streak} 👇")

    parts.append("")

    # =========================
    # 📊 ПРОГРЕСС ДНЯ
    # =========================
    if proofs_required is not None:
        parts.append(f"📊 Прогресс: {proofs_accepted or 0} / {proofs_required}")
        parts.append("")

    # =========================
    # ЗАГОЛОВОК
    # =========================
    if headline:
        parts.append(f"🔥 {headline}")

    if focus:
        parts.append(f"Фокус: {focus}")

    if summary:
        parts.append(summary)

    if main_task_title:
        parts.append("")
        parts.append("🎯 Главное:")
        parts.append(main_task_title)

    # =========================
    # TASKS
    # =========================
    if tasks:
        parts.append("")
        parts.append("📋 Задачи:")

        current_task = get_next_pending_daily_task(tasks)

        for i, task in enumerate(tasks, start=1):
            title = task.get("title") or "Задача"
            instructions = task.get("instructions") or task.get("description") or ""
            proof_required = task.get("proof_required", False)
            proof_prompt = task.get("proof_prompt")
            proofs = task.get("proofs") or []

            prefix = "👉 " if task == current_task else ""
            parts.append(f"{prefix}{i}. {title}")

            if instructions:
                parts.append(f"   — {instructions}")

            # =========================
            # PROOF STATUS
            # =========================
            if proof_required:
                proof_accepted = any(p.get("status") == "accepted" for p in proofs)

                if proof_accepted:
                    parts.append("   — ✅ proof принят")
                elif proofs:
                    last = proofs[-1]
                    last_status = last.get("status")
                    review_message = (last.get("review_message") or "").strip()

                    if last_status == "rejected":
                        parts.append("   — ❌ proof отклонён")
                        if review_message:
                            parts.append(f"   — 💬 {review_message}")
                    elif last_status == "needs_more":
                        parts.append("   — ⚠️ нужно доработать")
                        if review_message:
                            parts.append(f"   — 💬 {review_message}")
                    else:
                        parts.append("   — ⏳ проверяется")
                else:
                    parts.append("   — 📌 требуется proof")

                if proof_prompt:
                    parts.append(f"   — 👉 {proof_prompt}")

    return "\n".join(parts)


# ======================================================
# TASK HELPERS
# ======================================================

def get_next_pending_daily_task(tasks: list[dict]) -> dict | None:
    """
    Возвращает следующую задачу, на которой должен быть фокус пользователя.
    """

    if not tasks:
        return None

    for task in tasks:
        status = task.get("status", "pending")

        if status in {"done", "skipped", "failed"}:
            continue

        proof_required = task.get("proof_required", False)
        proofs = task.get("proofs") or []

        # если proof не нужен — задача сразу активна
        if not proof_required:
            return task

        # если proof нужен, но его еще нет
        if not proofs:
            return task

        # если proof есть, смотрим последний статус
        last_proof_status = proofs[-1].get("status")

        if last_proof_status in {"rejected", "needs_more", "accepted", "uploaded", "checking", None}:
            return task

    return None


def is_task_actionable(task: dict | None) -> bool:
    """
    Можно ли нажимать DONE для этой задачи.
    """

    if not task:
        return False

    status = task.get("status", "pending")

    if status in {"done", "skipped", "failed"}:
        return False

    proof_required = task.get("proof_required", False)

    if proof_required:
        proofs = task.get("proofs") or []
        return any(proof.get("status") == "accepted" for proof in proofs)

    return True

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    telegram_user = message.from_user

    user = await get_or_create_user(
        {
            "telegram_user_id": telegram_user.id,
            "telegram_chat_id": message.chat.id,
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name,
            "language_code": telegram_user.language_code,
        }
    )

    db_user_id = user["user_id"]

    await state.update_data(db_user_id=db_user_id)

    await state.set_state(GoalFlow.waiting_goal)
    await message.answer(
        "Привет. Напиши свою цель одним сообщением.\n\n"
        "Например:\n"
        "- Хочу 6 кубиков пресса\n"
        "- Хочу заработать 1 000 000 рублей\n"
        "- Хочу научиться играть на гитаре"
    )



@router.message(GoalFlow.waiting_goal)
async def get_goal(message: Message, state: FSMContext):
    data = await state.get_data()
    db_user_id = data.get("db_user_id")

    goal = await create_goal(
        {
            "user_id": db_user_id,
            "title": message.text,
            "description": message.text,
            "category": "general",
            "target_date": None,
            "priority": 1,
        }
    )

    goal_id = goal["goal_id"]

    profiling = await start_profiling(goal_id)

    await state.update_data(
        raw_goal=message.text,
        goal_id=goal_id,
        profiling_result=profiling,
    )

    await send_profiling_response(
        message,
        profiling,
        state,
        show_positive_feedback=False,
    )


@router.message(GoalFlow.clarifying_goal)
async def clarify_goal(message: Message, state: FSMContext):
    data = await state.get_data()
    goal_id = data.get("goal_id")
    profiling_result = data.get("profiling_result") or {}

    question_type = get_question_type(profiling_result)
    allow_free_text = profiling_result.get("allow_free_text", True)
    suggested_options = profiling_result.get("suggested_options") or []

    if question_type == "choice" and suggested_options:
        text = render_profiling_question_text(profiling_result)
        await message.answer("Для этого вопроса выбери один из вариантов ниже 👇")
        await message.answer(
            text,
            reply_markup=build_options_keyboard(suggested_options)
        )
        return

    if not allow_free_text and suggested_options:
        text = render_profiling_question_text(profiling_result)
        await message.answer("Для этого вопроса выбери один из вариантов ниже 👇")
        await message.answer(
            text,
            reply_markup=build_options_keyboard(suggested_options)
        )
        return

    result = await submit_profiling_answer(goal_id, message.text)
    await state.update_data(profiling_result=result)

    if result.get("is_completed"):
        await send_plan_preview(message, goal_id, state, profiling_result=result)
        return

    await send_profiling_response(message, result, state)

@router.callback_query(GoalFlow.choosing_coach_style)
async def choose_coach_style_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "coach_aggressive":
        coach_style = "aggressive"
        coach_style_label = "Жесткий"
    elif data == "coach_balanced":
        coach_style = "balanced"
        coach_style_label = "Баланс"
    elif data == "coach_soft":
        coach_style = "soft"
        coach_style_label = "Мягкий"
    else:
        await callback.answer("Ошибка выбора")
        return

    await callback.answer()  # ✅ СРАЗУ

    user_data = await state.get_data()
    goal_id = user_data.get("goal_id")

    # 🔥 ФИКС: ловим ситуацию, когда profiling уже завершен
    try:
        result = await submit_profiling_answer(goal_id, coach_style)
    except Exception:
        # 👉 profiling уже завершен — просто выходим
        return

    await state.update_data(profiling_result=result)

    await callback.message.answer(
        f"Стиль коуча выбран: {coach_style_label} ✅"
    )

    if result.get("is_completed"):
        await send_plan_preview(
            callback.message,
            goal_id,
            state,
            profiling_result=result
        )
        return

    await send_profiling_response(callback.message, result, state)
@router.callback_query(lambda c: c.data.startswith("profile_option:"))
async def profile_option_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # ✅ СРАЗУ

    raw_index = callback.data.replace("profile_option:", "", 1)

    try:
        selected_index = int(raw_index)
    except ValueError:
        await callback.message.answer("Некорректный вариант")
        return

    user_data = await state.get_data()
    goal_id = user_data.get("goal_id")
    profiling_result = user_data.get("profiling_result") or {}
    suggested_options = profiling_result.get("suggested_options") or []

    if selected_index < 0 or selected_index >= len(suggested_options):
        await callback.message.answer("Вариант больше не актуален")
        return

    selected_value = suggested_options[selected_index]

    result = await submit_profiling_answer(goal_id, selected_value)
    await state.update_data(profiling_result=result)

    await callback.message.answer(f"Выбрано: {selected_value} ✅")

    if result.get("is_completed"):
        await send_plan_preview(
            callback.message,
            goal_id,
            state,
            profiling_result=result,
        )
        return

    await send_profiling_response(callback.message, result, state)


@router.callback_query(
    GoalFlow.executing_plan,
    lambda c: c.data in {"daily_task_done", "daily_task_skip", "daily_task_proof"},
)
async def daily_execution_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    state_data = await state.get_data()

    # =========================
    # 🔒 защита от спама кликов
    # =========================
    if state_data.get("daily_action_in_progress"):
        return

    await state.update_data(daily_action_in_progress=True)

    try:
        data = callback.data
        user_data = await state.get_data()

        current_daily_tasks = user_data.get("current_daily_tasks") or []
        current_task = get_next_pending_daily_task(current_daily_tasks)

        if not current_task:
            return

        task_id = current_task.get("id") or current_task.get("task_id")
        if not task_id:
            return

        # =========================
        # 🧱 защита от старых сообщений
        # =========================
        current_message_id = user_data.get("current_daily_message_id")
        if current_message_id and callback.message.message_id != current_message_id:
            return

        proof_required = current_task.get("proof_required", False)
        proofs = current_task.get("proofs") or []
        proof_accepted = any(p.get("status") == "accepted" for p in proofs)

        # =========================
        # 📎 PROOF
        # =========================
        if data == "daily_task_proof":

            if state_data.get("waiting_proof"):
                return

            # 🔥 сразу блокируем кнопки
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

            await state.update_data(
                current_daily_task_id=task_id,
                waiting_proof=True,
            )

            await callback.message.answer(
                "Отправь proof по текущей задаче: текст, фото или файл."
            )

            await state.set_state(GoalFlow.waiting_daily_proof)
            return

        # =========================
        # ✅ DONE
        # =========================
        if data == "daily_task_done":

            # уже закрыта
            if current_task.get("status") == "done":
                return

            # ❗ сначала проверка proof (без блокировки кнопок)
            if proof_required and not proof_accepted:
                proof_prompt = current_task.get("proof_prompt") or "Сначала отправь подтверждение выполнения."
                recommended_proof_type = current_task.get("recommended_proof_type") or "proof"

                await state.update_data(current_daily_task_id=task_id)

                await callback.message.answer(
                    "❌ Эту задачу нельзя закрыть без подтвержденного proof.\n\n"
                    f"Что нужно: {recommended_proof_type}\n"
                    f"{proof_prompt}"
                )

                await state.set_state(GoalFlow.waiting_daily_proof)
                return

            # 🔥 ТОЛЬКО ТЕПЕРЬ блокируем кнопки (правильный момент)
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

            # API
            await set_daily_task_status(task_id, "done")

            fresh_state = await state.get_data()
            streak = fresh_state.get("streak", 0) + 1

            coaching_mode = "momentum" if streak >= 3 else "normal"

            await state.update_data(
                streak=streak,
                coaching_mode=coaching_mode,
                last_skip_reason=None,
                skip_streak=0,
            )

            await callback.message.answer(f"🔥 Отлично. Серия: {streak}.")

            await send_next_daily_plan(callback.message, state, source="execution")
            return

        # =========================
        # ⏭ SKIP
        # =========================
        if data == "daily_task_skip":

            # 🔥 сразу блокируем кнопки
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

            await set_daily_task_status(task_id, "skipped")

            fresh_state = await state.get_data()
            streak = fresh_state.get("streak", 0)
            skip_streak = fresh_state.get("skip_streak", 0) + 1

            await state.update_data(
                streak=0,
                coaching_mode="recovery",
                skip_streak=skip_streak,
            )

            if skip_streak >= 3:
                text = (
                    "Ты пропускаешь уже несколько задач подряд ❌\n\n"
                    "Это уже не случайность — ты начинаешь выпадать из процесса.\n"
                    "Напиши честно: ты действительно хочешь достичь этой цели?"
                )
            elif skip_streak == 2:
                text = (
                    "Второй пропуск подряд.\n\n"
                    "Сейчас критический момент — либо возвращаешься, либо начинаешь откатываться.\n"
                    "Почему пропустил?"
                )
            elif streak >= 3:
                text = (
                    f"Ты прервал серию из {streak} ❌\n\n"
                    "Это откат назад.\n"
                    "Напиши, что пошло не так."
                )
            else:
                text = (
                    "Ты пропустил задачу.\n\n"
                    "Важно не входить в паттерн пропусков.\n"
                    "Напиши, почему."
                )

            await callback.message.answer(text)

            await state.set_state(GoalFlow.waiting_skip_reason)
            return

    finally:
        await state.update_data(daily_action_in_progress=False)

@router.message(GoalFlow.waiting_daily_proof)
async def daily_proof_handler(message: Message, state: FSMContext):
    state_data = await state.get_data()
    task_id = state_data.get("current_daily_task_id")

    if not task_id:
        await message.answer("Ошибка: не нашел задачу для proof.")
        return

    # =========================
    # ⏳ мгновенный feedback
    # =========================
    loading_msg = await message.answer("⏳ Проверяю proof...")

    try:
        # =========================
        # 📦 подготовка данных
        # =========================
        file_id = None
        text = None

        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document:
            file_id = message.document.file_id
        elif message.text:
            text = message.text.strip()
        else:
            await loading_msg.edit_text(
                "❌ Не удалось распознать proof.\n\n"
                "Отправь текст, фото или файл."
            )
            return

        # =========================
        # 🚀 собираем payload и отправляем в backend
        # =========================
        payload = {}

        if file_id:
            payload["telegram_file_id"] = file_id

        if text:
            payload["text"] = text

        response = await create_daily_task_proof(task_id, payload)

        # =========================
        # 📊 разбор ответа
        # =========================
        proof_status = response.get("status")
        review_message = (response.get("review_message") or "").strip()

        # =========================
        # 🎯 реакция
        # =========================
        if proof_status == "accepted":
            await loading_msg.edit_text(
                "🔥 Принято.\n\n"
                "Теперь можешь нажать Done."
            )

        elif proof_status == "rejected":
            await loading_msg.edit_text(
                "❌ Proof отклонён.\n\n"
                f"{review_message or 'Попробуй еще раз и отправь более понятное подтверждение.'}"
            )

        elif proof_status == "needs_more":
            await loading_msg.edit_text(
                "⚠️ Нужно доработать proof.\n\n"
                f"{review_message or 'Добавь больше деталей или более четкий скрин/описание.'}"
            )

        else:
            await loading_msg.edit_text(
                "⚠️ Не удалось определить результат проверки.\n"
                "Попробуй отправить proof еще раз."
            )

        # =========================
        # 🔄 возврат в execution + обновление
        # =========================
        await state.set_state(GoalFlow.executing_plan)
        await send_next_daily_plan(message, state, source="execution")

    except Exception as e:
        print("PROOF ERROR:", e)

        await loading_msg.edit_text(
            "❌ Ошибка при отправке proof.\n"
            "Попробуй еще раз."
        )

    finally:
        # =========================
        # 🔓 обязательно снимаем блок
        # =========================
        await state.update_data(waiting_proof=False)

@router.callback_query(GoalFlow.confirming_plan)
async def confirm_plan_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "accept_plan":
        await callback.answer()

        user_data = await state.get_data()
        goal_id = user_data.get("goal_id")

        if not goal_id:
            await callback.message.answer(
                "Не нашел активную цель. Начни заново через /start"
            )
            return

        await accept_plan(goal_id)

        plan = await get_current_plan(goal_id)

        await state.update_data(
    plan=plan,
    streak=0,
    last_skip_reason=None,
    coaching_mode="normal",
    skip_streak=0,
    daily_action_in_progress=False,
)

        await state.set_state(GoalFlow.executing_plan)
        await send_next_daily_plan(callback.message, state, source="accept")
        return

    if data == "reject_plan":
        await callback.answer()

        await callback.message.answer("Ок, переделаю план...")

        user_data = await state.get_data()
        goal_id = user_data.get("goal_id")

        if not goal_id:
            await callback.message.answer(
                "Не нашел активную цель. Начни заново через /start"
            )
            return

        await generate_plan(goal_id)

        plan = await get_current_plan(goal_id)
        summary = plan.get("summary") or plan.get("summary_text") or "План готов"
        roadmap = plan.get("roadmap") or plan.get("content", {}).get("roadmap", [])

        roadmap_text = ""
        if roadmap:
            roadmap_items = "\n".join([f"• {item}" for item in roadmap])
            roadmap_text = f"\n\n📋 Общий путь:\n{roadmap_items}"

        await callback.message.answer(
            f"📌 Коротко:\n{summary}"
            f"{roadmap_text}\n\n"
            f"👉 Принять этот план?",
            reply_markup=confirm_plan_keyboard(),
        )
        await state.set_state(GoalFlow.confirming_plan)
        return

    await callback.answer("Неизвестное действие")

@router.message(GoalFlow.waiting_skip_reason)
async def skip_reason_handler(message: Message, state: FSMContext):
    reason = (message.text or "").strip()

    await state.update_data(
    last_skip_reason=reason,
    coaching_mode="recovery"
)

    if reason:
        await message.answer(
            "Ок, понял.\n\n"
            "Главное — не выпадать из процесса.\n"
            "Сейчас возвращаемся в ритм 👇"
        )
    else:
        await message.answer(
            "Принял.\n\n"
            "Возвращаемся в ритм 👇"
        )

    await state.set_state(GoalFlow.executing_plan)
    await send_next_daily_plan(message, state, source="execution")
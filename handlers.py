import logging
import random

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from api_client import (
    accept_plan,
    create_daily_task_proof,
    create_goal,
    generate_plan,
    get_current_plan,
    get_next_daily_plan,
    get_or_create_user,
    set_daily_task_status,
    start_profiling,
    submit_profiling_answer,
)
from keyboards import (
    build_options_keyboard,
    coach_style_keyboard,
    confirm_plan_keyboard,
    day_list_keyboard,
    task_detail_keyboard,
)
from states import GoalFlow

logger = logging.getLogger(__name__)
router = Router()


# ======================================================
# PROFILING HELPERS (без изменений)
# ======================================================

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
        "👍 Ок, двигаемся",
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
            await message_obj.answer(text, reply_markup=build_options_keyboard(suggested_options))
        else:
            await message_obj.answer(text)

    if needs_follow_up:
        if question_type == "choice" and current_question_key == "coach_style":
            await message_obj.answer(text, reply_markup=coach_style_keyboard())
            await state.set_state(GoalFlow.choosing_coach_style)
            return
        await answer_with_optional_keyboard()
        await state.set_state(GoalFlow.clarifying_goal)
        return

    if show_positive_feedback and answer_accepted:
        await message_obj.answer(get_positive_feedback())

    if question_type in {"choice", "choice_or_text", "special"}:
        if current_question_key == "coach_style":
            await message_obj.answer(text, reply_markup=coach_style_keyboard())
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


async def send_plan_preview(
    message_obj, goal_id: str, state: FSMContext, profiling_result: dict | None = None
):
    profiling_summary = None
    if profiling_result:
        profiling_summary = profiling_result.get("profiling_summary")

    summary_text = render_profiling_summary(profiling_summary)
    if summary_text:
        await message_obj.answer(f"Профилирование завершено ✅\n\n{summary_text}")
        await message_obj.answer("Генерирую план... ⏳")
    else:
        await message_obj.answer("Профилирование завершено ✅\n\nГенерирую план... ⏳")

    await generate_plan(goal_id)
    plan = await get_current_plan(goal_id)

    summary = plan.get("summary") or plan.get("summary_text") or "План готов"
    roadmap = plan.get("roadmap") or plan.get("content", {}).get("roadmap", [])

    roadmap_text = ""
    if roadmap:
        roadmap_items = "\n".join([f"• {item}" for item in roadmap])
        roadmap_text = f"\n\n📋 Общий путь:\n{roadmap_items}"

    await message_obj.answer(
        f"📌 Коротко:\n{summary}{roadmap_text}\n\n👉 Принять этот план?",
        reply_markup=confirm_plan_keyboard(),
    )
    await state.set_state(GoalFlow.confirming_plan)


# ======================================================
# DAY LIST RENDER
# ======================================================

TASK_STATUS_ICON = {
    "done": "✅",
    "skipped": "⏭",
    "failed": "❌",
}


def get_task_display_icon(task: dict) -> str:
    status = task.get("status", "pending")
    if status in TASK_STATUS_ICON:
        return TASK_STATUS_ICON[status]

    proof_required = task.get("proof_required", False)
    proofs = task.get("proofs") or []

    if proof_required and proofs:
        last_status = proofs[-1].get("status")
        if last_status == "accepted":
            return "🔓"
        if last_status in {"uploaded", "checking"}:
            return "⏳"
        if last_status in {"rejected", "needs_more"}:
            return "⚠️"

    return "⭕"


def render_day_list_text(daily_plan: dict) -> str:
    parts = []

    day_number = daily_plan.get("day_number", "?")
    focus = daily_plan.get("focus") or daily_plan.get("focus_message") or ""
    headline = daily_plan.get("headline") or ""
    tasks = daily_plan.get("tasks") or []

    required_tasks = [t for t in tasks if t.get("is_required", True)]
    closed_tasks = [
        t for t in required_tasks if t.get("status") in {"done", "skipped", "failed"}
    ]

    parts.append(f"📅 День {day_number}")

    if headline:
        parts.append(f"🔥 {headline}")
    if focus:
        parts.append(f"Фокус: {focus}")

    parts.append(f"\nПрогресс: {len(closed_tasks)}/{len(required_tasks)}")
    parts.append("")

    for i, task in enumerate(tasks, start=1):
        icon = get_task_display_icon(task)
        title = task.get("title") or "Задача"
        estimated = task.get("estimated_minutes")
        suffix = f" ({estimated} мин)" if estimated else ""
        parts.append(f"{icon} {i}. {title}{suffix}")

    # Если все обязательные закрыты
    if required_tasks and len(closed_tasks) == len(required_tasks):
        parts.append("\n🔥 Все задачи выполнены!")

    return "\n".join(parts)


# ======================================================
# TASK DETAIL RENDER
# ======================================================

def render_task_detail_text(task: dict, index: int) -> str:
    parts = []

    title = task.get("title") or "Задача"
    objective = task.get("objective") or ""
    description = task.get("description") or ""
    instructions = task.get("instructions") or ""
    why_today = task.get("why_today") or ""
    success_criteria = task.get("success_criteria") or ""
    estimated = task.get("estimated_minutes")
    proof_required = task.get("proof_required", False)
    proof_prompt = task.get("proof_prompt") or ""
    recommended_proof_type = task.get("recommended_proof_type") or ""
    tips = task.get("tips") or []
    proofs = task.get("proofs") or []
    status = task.get("status", "pending")

    parts.append(f"📌 Задача {index + 1}: {title}")

    if status == "done":
        parts.append("✅ Выполнено")
    elif status == "skipped":
        parts.append("⏭ Пропущено")
    elif status == "failed":
        parts.append("❌ Не выполнено")

    if estimated:
        parts.append(f"⏱ ~{estimated} мин")

    if objective:
        parts.append(f"\n🎯 Цель:\n{objective}")

    if description:
        parts.append(f"\n📝 Описание:\n{description}")

    if instructions:
        parts.append(f"\n📋 Инструкция:\n{instructions}")

    if why_today:
        parts.append(f"\n💡 Почему сегодня:\n{why_today}")

    if success_criteria:
        parts.append(f"\n🏁 Критерий успеха:\n{success_criteria}")

    if tips:
        tips_text = "\n".join(f"• {t}" for t in tips)
        parts.append(f"\n💬 Советы:\n{tips_text}")

    # Proof статус
    if proof_required:
        parts.append("")
        if recommended_proof_type:
            parts.append(f"📎 Требуется proof: {recommended_proof_type}")
        else:
            parts.append("📎 Требуется proof")

        if proof_prompt:
            parts.append(f"👉 {proof_prompt}")

        if proofs:
            last_proof = proofs[-1]
            last_status = last_proof.get("status")
            review_message = (last_proof.get("review_message") or "").strip()

            if last_status == "accepted":
                parts.append("✅ Proof принят — можно нажать Done")
            elif last_status == "rejected":
                parts.append("❌ Proof отклонён")
                if review_message:
                    parts.append(f"💬 {review_message}")
            elif last_status == "needs_more":
                parts.append("⚠️ Нужно доработать proof")
                if review_message:
                    parts.append(f"💬 {review_message}")
            elif last_status in {"uploaded", "checking"}:
                parts.append("⏳ Proof проверяется...")
        else:
            parts.append("Proof ещё не отправлен")
    else:
        parts.append("\n✅ Proof не требуется")

    return "\n".join(parts)


# ======================================================
# SEND DAY LIST — основная функция показа дня
# ======================================================

async def send_day_list(message_obj, state: FSMContext, daily_plan: dict):
    """
    Показывает список задач дня и сохраняет состояние.
    Всегда создаёт новое сообщение (не редактирует).
    """
    tasks = daily_plan.get("tasks") or []
    daily_plan_id = daily_plan.get("id") or daily_plan.get("daily_plan_id")

    await state.update_data(
        current_daily_plan=daily_plan,
        current_daily_plan_id=daily_plan_id,
        current_daily_tasks=tasks,
        selected_daily_task_index=None,
        current_daily_message_id=None,
    )

    text = render_day_list_text(daily_plan)
    sent = await message_obj.answer(text, reply_markup=day_list_keyboard(tasks))
    await state.update_data(current_daily_message_id=sent.message_id)


async def refresh_day_list_message(message_obj, state: FSMContext):
    """
    Запрашивает свежий daily plan с backend и обновляет сообщение со списком.
    """
    data = await state.get_data()
    goal_id = data.get("goal_id")

    if not goal_id:
        await message_obj.answer("Не нашел активную цель. Начни заново через /start")
        return

    try:
        response = await get_next_daily_plan(goal_id)
    except Exception as e:
        logger.error(f"[refresh_day_list] get_next_daily_plan error: {e}")
        await message_obj.answer("❌ Не удалось обновить задачи. Попробуй ещё раз.")
        return

    if not response or response.get("error") == "timeout":
        await message_obj.answer("⏳ Обновляем план, попробуй через несколько секунд.")
        return

    daily_plan = response.get("daily_plan")

    if not daily_plan:
        await message_obj.answer(
            "🔥 День завершён!\n\nСледующий день появится завтра или нажми «Следующий день».",
        )
        await state.update_data(
            current_daily_plan=None,
            current_daily_plan_id=None,
            current_daily_tasks=[],
            current_daily_message_id=None,
        )
        return

    tasks = daily_plan.get("tasks") or []
    daily_plan_id = daily_plan.get("id") or daily_plan.get("daily_plan_id")

    await state.update_data(
        current_daily_plan=daily_plan,
        current_daily_plan_id=daily_plan_id,
        current_daily_tasks=tasks,
        selected_daily_task_index=None,
    )

    text = render_day_list_text(daily_plan)
    current_message_id = data.get("current_daily_message_id")

    if current_message_id:
        try:
            await message_obj.bot.edit_message_text(
                chat_id=message_obj.chat.id,
                message_id=current_message_id,
                text=text,
                reply_markup=day_list_keyboard(tasks),
            )
            return
        except Exception:
            pass

    sent = await message_obj.answer(text, reply_markup=day_list_keyboard(tasks))
    await state.update_data(current_daily_message_id=sent.message_id)


# ======================================================
# BOT FLOW HANDLERS
# ======================================================

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    telegram_user = message.from_user

    user = await get_or_create_user({
        "telegram_user_id": telegram_user.id,
        "telegram_chat_id": message.chat.id,
        "username": telegram_user.username,
        "first_name": telegram_user.first_name,
        "last_name": telegram_user.last_name,
        "language_code": telegram_user.language_code,
    })

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

    goal = await create_goal({
        "user_id": db_user_id,
        "title": message.text,
        "description": message.text,
        "category": "general",
        "target_date": None,
        "priority": 1,
    })

    goal_id = goal["goal_id"]
    profiling = await start_profiling(goal_id)

    await state.update_data(
        raw_goal=message.text,
        goal_id=goal_id,
        profiling_result=profiling,
    )

    await send_profiling_response(message, profiling, state, show_positive_feedback=False)


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
        await message.answer(text, reply_markup=build_options_keyboard(suggested_options))
        return

    if not allow_free_text and suggested_options:
        text = render_profiling_question_text(profiling_result)
        await message.answer("Для этого вопроса выбери один из вариантов ниже 👇")
        await message.answer(text, reply_markup=build_options_keyboard(suggested_options))
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

    coach_labels = {
        "coach_aggressive": ("aggressive", "Жесткий"),
        "coach_balanced": ("balanced", "Баланс"),
        "coach_soft": ("soft", "Мягкий"),
    }

    if data not in coach_labels:
        await callback.answer("Ошибка выбора")
        return

    coach_style, coach_style_label = coach_labels[data]
    await callback.answer()

    user_data = await state.get_data()
    goal_id = user_data.get("goal_id")

    try:
        result = await submit_profiling_answer(goal_id, coach_style)
    except Exception:
        return

    await state.update_data(profiling_result=result)
    await callback.message.answer(f"Стиль коуча выбран: {coach_style_label} ✅")

    if result.get("is_completed"):
        await send_plan_preview(callback.message, goal_id, state, profiling_result=result)
        return

    await send_profiling_response(callback.message, result, state)


@router.callback_query(lambda c: c.data.startswith("profile_option:"))
async def profile_option_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    try:
        selected_index = int(callback.data.replace("profile_option:", "", 1))
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
        await send_plan_preview(callback.message, goal_id, state, profiling_result=result)
        return

    await send_profiling_response(callback.message, result, state)


# ======================================================
# PLAN CONFIRM
# ======================================================

@router.callback_query(GoalFlow.confirming_plan)
async def confirm_plan_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    state_data = await state.get_data()

    if state_data.get("plan_action_in_progress"):
        await callback.answer()
        return

    await state.update_data(plan_action_in_progress=True)

    try:
        if data == "accept_plan":
            await callback.answer()

            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

            user_data = await state.get_data()
            goal_id = user_data.get("goal_id")

            if not goal_id:
                await callback.message.answer("Не нашел активную цель. Начни заново через /start")
                return

            try:
                await accept_plan(goal_id)
            except Exception as e:
                logger.error(f"[accept_plan] goal_id={goal_id} error={e}")
                await callback.message.answer("❌ Не удалось принять план. Попробуй ещё раз.")
                return

            try:
                plan = await get_current_plan(goal_id)
            except Exception as e:
                logger.error(f"[get_current_plan after accept] goal_id={goal_id} error={e}")
                plan = {}

            await state.update_data(
                plan=plan,
                streak=0,
                last_skip_reason=None,
                coaching_mode="normal",
                skip_streak=0,
                daily_action_in_progress=False,
                selected_daily_task_index=None,
            )

            await state.set_state(GoalFlow.executing_plan)
            await callback.message.answer("✅ План принят! Загружаю задачи на сегодня...")

            try:
                response = await get_next_daily_plan(goal_id)
            except Exception as e:
                logger.error(f"[get_next_daily_plan after accept] goal_id={goal_id} error={e}")
                await callback.message.answer("❌ Не удалось загрузить задачи. Попробуй /start")
                return

            daily_plan = response.get("daily_plan") if response else None

            if not daily_plan:
                await callback.message.answer(
                    "📅 План принят!\n\nЗадачи на первый день скоро появятся."
                )
                return

            await send_day_list(callback.message, state, daily_plan)
            return

        if data == "reject_plan":
            await callback.answer()

            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

            user_data = await state.get_data()
            goal_id = user_data.get("goal_id")

            if not goal_id:
                await callback.message.answer("Не нашел активную цель. Начни заново через /start")
                return

            await callback.message.answer("Ок, переделаю план...")

            try:
                await generate_plan(goal_id)
                plan = await get_current_plan(goal_id)
            except Exception as e:
                logger.error(f"[reject_plan] goal_id={goal_id} error={e}")
                await callback.message.answer("❌ Не удалось перегенерировать план. Попробуй ещё раз.")
                return

            summary = plan.get("summary") or plan.get("summary_text") or "План готов"
            roadmap = plan.get("roadmap") or plan.get("content", {}).get("roadmap", [])

            roadmap_text = ""
            if roadmap:
                roadmap_items = "\n".join([f"• {item}" for item in roadmap])
                roadmap_text = f"\n\n📋 Общий путь:\n{roadmap_items}"

            await callback.message.answer(
                f"📌 Коротко:\n{summary}{roadmap_text}\n\n👉 Принять этот план?",
                reply_markup=confirm_plan_keyboard(),
            )

            await state.set_state(GoalFlow.confirming_plan)
            return

        await callback.answer("Неизвестное действие")

    finally:
        await state.update_data(plan_action_in_progress=False)


# ======================================================
# DAY LIST CALLBACKS
# Префиксы: dl_ = day list level
# ======================================================

@router.callback_query(
    GoalFlow.executing_plan,
    lambda c: c.data == "dl_refresh",
)
async def day_list_refresh_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await refresh_day_list_message(callback.message, state)


@router.callback_query(
    GoalFlow.executing_plan,
    lambda c: c.data == "dl_next_day",
)
async def day_list_next_day_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    data = await state.get_data()
    goal_id = data.get("goal_id")

    if not goal_id:
        await callback.message.answer("Не нашел активную цель. Начни заново через /start")
        return

    await callback.message.answer("⏳ Загружаю следующий день...")

    try:
        response = await get_next_daily_plan(goal_id)
    except Exception as e:
        logger.error(f"[next_day] get_next_daily_plan error: {e}")
        await callback.message.answer("❌ Не удалось загрузить следующий день. Попробуй позже.")
        return

    if not response or response.get("error") == "timeout":
        await callback.message.answer("⏳ Следующий день ещё генерируется. Попробуй через минуту.")
        return

    daily_plan = response.get("daily_plan")

    if not daily_plan:
        await callback.message.answer(
            "🏆 Все дни плана выполнены!\n\nОтличная работа!"
        )
        return

    await send_day_list(callback.message, state, daily_plan)


@router.callback_query(
    GoalFlow.executing_plan,
    lambda c: c.data.startswith("dt_sel:"),
)
async def task_select_callback(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал на номер задачи — показываем detail screen."""
    await callback.answer()

    raw_index = callback.data.replace("dt_sel:", "", 1)
    try:
        index = int(raw_index)
    except ValueError:
        await callback.message.answer("Некорректный номер задачи.")
        return

    data = await state.get_data()
    tasks = data.get("current_daily_tasks") or []

    # Защита от несоответствия индекса
    if index < 0 or index >= len(tasks):
        await callback.message.answer(
            "Список задач обновился. Нажми 🔄 Обновить."
        )
        return

    task = tasks[index]
    await state.update_data(selected_daily_task_index=index)

    # Скрываем кнопки на day list
    current_message_id = data.get("current_daily_message_id")
    if current_message_id and callback.message.message_id == current_message_id:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    text = render_task_detail_text(task, index)
    sent = await callback.message.answer(text, reply_markup=task_detail_keyboard(task))
    await state.update_data(current_task_detail_message_id=sent.message_id)


# ======================================================
# TASK DETAIL CALLBACKS
# Префиксы: dt_ = daily task detail level
# ======================================================

@router.callback_query(
    GoalFlow.executing_plan,
    lambda c: c.data == "dt_back",
)
async def task_detail_back_callback(callback: CallbackQuery, state: FSMContext):
    """Назад к списку дня."""
    await callback.answer()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(selected_daily_task_index=None, current_task_detail_message_id=None)
    await refresh_day_list_message(callback.message, state)


@router.callback_query(
    GoalFlow.executing_plan,
    lambda c: c.data == "dt_done",
)
async def task_detail_done_callback(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал Done на task detail."""
    data = await state.get_data()

    if data.get("daily_action_in_progress"):
        await callback.answer()
        return

    await state.update_data(daily_action_in_progress=True)

    try:
        await callback.answer()

        index = data.get("selected_daily_task_index")
        tasks = data.get("current_daily_tasks") or []

        if index is None or index < 0 or index >= len(tasks):
            await callback.message.answer("Ошибка: задача не выбрана. Вернись к списку.")
            return

        task = tasks[index]
        task_id = task.get("id")

        if not task_id:
            await callback.message.answer("Ошибка: не найден ID задачи.")
            return

        # Повторная проверка proof на случай рассинхрона
        proof_required = task.get("proof_required", False)
        proofs = task.get("proofs") or []
        proof_accepted = any(p.get("status") == "accepted" for p in proofs)

        if proof_required and not proof_accepted:
            await callback.message.answer(
                "❌ Нельзя закрыть без принятого proof.\n\n"
                "Нажми «📎 Отправить proof» и отправь подтверждение."
            )
            return

        # Убираем кнопки
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Вызов backend
        updated_plan = await set_daily_task_status(task_id, "done")

        # Обновляем tasks из ответа backend
        if updated_plan and updated_plan.get("tasks"):
            tasks = updated_plan["tasks"]
            await state.update_data(
                current_daily_tasks=tasks,
                current_daily_plan=updated_plan,
            )
        else:
            # Обновляем локально если backend не вернул план
            task["status"] = "done"
            tasks[index] = task
            await state.update_data(current_daily_tasks=tasks)

        # Обновляем streak
        streak = data.get("streak", 0) + 1
        coaching_mode = "momentum" if streak >= 3 else "normal"
        await state.update_data(
            streak=streak,
            coaching_mode=coaching_mode,
            last_skip_reason=None,
            skip_streak=0,
            selected_daily_task_index=None,
        )

        await callback.message.answer(f"✅ Готово! Серия: {streak} 🔥")
        await refresh_day_list_message(callback.message, state)

    except Exception as e:
        logger.error(f"[dt_done] error: {e}")
        await callback.message.answer("❌ Ошибка. Попробуй ещё раз.")
    finally:
        await state.update_data(daily_action_in_progress=False)


@router.callback_query(
    GoalFlow.executing_plan,
    lambda c: c.data == "dt_skip",
)
async def task_detail_skip_callback(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал Пропустить на task detail."""
    data = await state.get_data()

    if data.get("daily_action_in_progress"):
        await callback.answer()
        return

    await state.update_data(daily_action_in_progress=True)

    try:
        await callback.answer()

        index = data.get("selected_daily_task_index")
        tasks = data.get("current_daily_tasks") or []

        if index is None or index < 0 or index >= len(tasks):
            await callback.message.answer("Ошибка: задача не выбрана. Вернись к списку.")
            return

        task = tasks[index]
        task_id = task.get("id")

        if not task_id:
            await callback.message.answer("Ошибка: не найден ID задачи.")
            return

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        updated_plan = await set_daily_task_status(task_id, "skipped")

        if updated_plan and updated_plan.get("tasks"):
            tasks = updated_plan["tasks"]
            await state.update_data(
                current_daily_tasks=tasks,
                current_daily_plan=updated_plan,
            )
        else:
            task["status"] = "skipped"
            tasks[index] = task
            await state.update_data(current_daily_tasks=tasks)

        streak = data.get("streak", 0)
        skip_streak = data.get("skip_streak", 0) + 1

        await state.update_data(
            streak=0,
            coaching_mode="recovery",
            skip_streak=skip_streak,
            selected_daily_task_index=None,
        )

        if skip_streak >= 3:
            skip_text = (
                "Ты пропускаешь уже несколько задач подряд ❌\n\n"
                "Напиши честно: ты действительно хочешь достичь этой цели?"
            )
        elif skip_streak == 2:
            skip_text = "Второй пропуск подряд.\n\nПочему пропустил?"
        elif streak >= 3:
            skip_text = (
                f"Ты прервал серию из {streak} ❌\n\nНапиши, что пошло не так."
            )
        else:
            skip_text = "Задача пропущена.\n\nНапиши, почему."

        await callback.message.answer(skip_text)
        await state.set_state(GoalFlow.waiting_skip_reason)

    except Exception as e:
        logger.error(f"[dt_skip] error: {e}")
        await callback.message.answer("❌ Ошибка. Попробуй ещё раз.")
    finally:
        await state.update_data(daily_action_in_progress=False)


@router.callback_query(
    GoalFlow.executing_plan,
    lambda c: c.data == "dt_proof",
)
async def task_detail_proof_callback(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал 'Отправить proof' на task detail."""
    data = await state.get_data()

    if data.get("waiting_proof"):
        await callback.answer()
        return

    await callback.answer()

    index = data.get("selected_daily_task_index")
    tasks = data.get("current_daily_tasks") or []

    if index is None or index < 0 or index >= len(tasks):
        await callback.message.answer("Ошибка: задача не выбрана. Вернись к списку.")
        return

    task = tasks[index]
    task_id = task.get("id")

    if not task_id:
        await callback.message.answer("Ошибка: не найден ID задачи.")
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await state.update_data(
        current_daily_task_id=task_id,
        waiting_proof=True,
    )

    proof_prompt = task.get("proof_prompt") or "Отправь подтверждение выполнения."
    recommended_proof_type = task.get("recommended_proof_type") or ""

    prompt_text = "📎 Отправь proof:\n\n"
    if recommended_proof_type:
        prompt_text += f"Тип: {recommended_proof_type}\n"
    prompt_text += proof_prompt

    await callback.message.answer(prompt_text)
    await state.set_state(GoalFlow.waiting_daily_proof)


# ======================================================
# PROOF HANDLER
# ======================================================

@router.message(GoalFlow.waiting_daily_proof)
async def daily_proof_handler(message: Message, state: FSMContext):
    state_data = await state.get_data()
    task_id = state_data.get("current_daily_task_id")
    selected_index = state_data.get("selected_daily_task_index")

    if not task_id:
        await message.answer("Ошибка: не нашел задачу для proof.")
        return

    loading_msg = await message.answer("⏳ Проверяю proof...")

    try:
        if message.photo:
            payload = {
                "proof_type": "photo",
                "telegram_file_id": message.photo[-1].file_id,
            }
        elif message.document:
            payload = {
                "proof_type": "file",
                "telegram_file_id": message.document.file_id,
            }
        elif message.text:
            payload = {
                "proof_type": "text",
                "text": message.text.strip(),
            }
        else:
            await loading_msg.edit_text(
                "❌ Не удалось распознать proof.\n\nОтправь текст, фото или файл."
            )
            return

        response = await create_daily_task_proof(task_id, payload)
        logger.info(f"[proof] task_id={task_id} response={response}")

        proof_status = response.get("status")
        review_message = (response.get("review_message") or "").strip()

        status_texts = {
            "accepted": "🔥 Proof принят!\n\nВернись к задаче и нажми ✅ Done.",
            "rejected": f"❌ Proof отклонён.\n\n{review_message or 'Попробуй ещё раз с более чётким подтверждением.'}",
            "needs_more": f"⚠️ Нужно доработать proof.\n\n{review_message or 'Добавь больше деталей.'}",
            "uploaded": "⏳ Proof загружен и отправлен на проверку.\n\nСтатус обновится при следующем обновлении.",
        }

        text = status_texts.get(
            proof_status,
            f"⚠️ Статус proof: {proof_status}\n\nОбнови список задач."
        )
        await loading_msg.edit_text(text)

        # Обновляем proof в локальном состоянии
        tasks = state_data.get("current_daily_tasks") or []
        if selected_index is not None and 0 <= selected_index < len(tasks):
            task = tasks[selected_index]
            proofs = list(task.get("proofs") or [])
            proofs.append(response)
            task["proofs"] = proofs
            tasks[selected_index] = task
            await state.update_data(current_daily_tasks=tasks)

    except Exception as e:
        logger.error(f"[proof_handler] task_id={task_id} error={e}")
        await loading_msg.edit_text("❌ Ошибка при отправке proof.\n\nПопробуй ещё раз.")
    finally:
        await state.update_data(waiting_proof=False)
        await state.set_state(GoalFlow.executing_plan)

    # После proof показываем detail screen с обновлённым статусом
    data = await state.get_data()
    tasks = data.get("current_daily_tasks") or []
    index = data.get("selected_daily_task_index")

    if index is not None and 0 <= index < len(tasks):
        task = tasks[index]
        text = render_task_detail_text(task, index)
        await message.answer(text, reply_markup=task_detail_keyboard(task))
    else:
        await refresh_day_list_message(message, state)


# ======================================================
# SKIP REASON HANDLER
# ======================================================

@router.message(GoalFlow.waiting_skip_reason)
async def skip_reason_handler(message: Message, state: FSMContext):
    reason = (message.text or "").strip()

    await state.update_data(last_skip_reason=reason, coaching_mode="recovery")

    if reason:
        await message.answer(
            "Ок, понял.\n\nГлавное — не выпадать из процесса.\nСейчас возвращаемся в ритм 👇"
        )
    else:
        await message.answer("Принял.\n\nВозвращаемся в ритм 👇")

    await state.set_state(GoalFlow.executing_plan)
    await refresh_day_list_message(message, state)
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
        await message_obj.answer(
            "Чек-лист дня готовится чуть дольше обычного. Попробуй через несколько секунд."
        )
        return

    daily_plan = next_response.get("daily_plan")

    if not daily_plan:
        if source == "accept":
            text = (
                "План принят ✅\n\n"
                "Следующий день по расписанию пока не наступил. "
                "Я пришлю задачи, когда придет подходящий день."
            )
        elif source == "execution":
            text = (
                "✅ День завершён\n\n"
                "Ты закрыл все задачи на сегодня.\n"
                "Следующий день пришлю по расписанию."
            )
        else:
            text = (
                "Сейчас активных задач нет.\n"
                "Следующий день пришлю, когда придет время."
            )

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
    daily_plan_id = daily_plan.get("id") or daily_plan.get("daily_plan_id")
    tasks = daily_plan.get("tasks") or []

    await state.update_data(
        current_daily_plan=daily_plan,
        current_daily_plan_id=daily_plan_id,
        current_daily_tasks=tasks,
    )

    data = await state.get_data()
    streak = data.get("streak", 0)
    coaching_mode = data.get("coaching_mode", "normal")
    last_skip_reason = data.get("last_skip_reason")

    text = render_daily_plan_text(
        daily_plan,
        streak=streak,
        coaching_mode=coaching_mode,
        last_skip_reason=last_skip_reason,
    )

    if current_message_id:
        try:
            await message_obj.bot.edit_message_text(
                chat_id=message_obj.chat.id,
                message_id=current_message_id,
                text=text,
                reply_markup=daily_execution_keyboard(),
            )
            return
        except Exception:
            pass

    sent_message = await message_obj.answer(
        text,
        reply_markup=daily_execution_keyboard(),
    )

    await state.update_data(
        current_daily_message_id=sent_message.message_id
    )
def render_daily_plan_text(
    daily_plan: dict,
    streak: int = 0,
    coaching_mode: str = "normal",
    last_skip_reason: str | None = None,
) -> str:
    parts = []

    headline = daily_plan.get("headline")
    focus = daily_plan.get("focus")
    summary = daily_plan.get("summary")
    main_task_title = daily_plan.get("main_task_title")
    tasks = daily_plan.get("tasks") or []

       # =========================
    # 🔥 АДАПТИВНЫЙ ТОН (NEW)
    # =========================
    if coaching_mode == "recovery":
        parts.append("Возвращаемся в ритм. Сегодня без перегруза — главное снова войти в процесс 👇")
        if last_skip_reason:
            parts.append(f"Причина прошлого пропуска: {last_skip_reason}")

    elif coaching_mode == "momentum":
        if streak >= 6:
            parts.append(f"⚡ Ты на уровне дисциплины. Серия: {streak}")
        else:
            parts.append(f"🔥 Ты в ритме. Серия: {streak}")

    else:  # normal
        if streak == 0:
            parts.append("Начинаем спокойно. Главное — задать темп 👇")
        else:
            parts.append(f"Хорошее движение. Серия: {streak} 👇")

    parts.append("")

    # 🔥 Заголовок дня
    if headline:
        parts.append(f"🔥 {headline}")

    # 🎯 Фокус дня
    if focus:
        parts.append(f"Фокус дня: {focus}")

    # 🧠 Контекст
    if summary:
        parts.append(summary)

    # 🎯 Главное действие дня
    if main_task_title:
        parts.append("")
        parts.append("🎯 Главное сегодня:")
        parts.append(main_task_title)

    # 📋 Задачи
    if tasks:
        must_tasks = []
        should_tasks = []
        bonus_tasks = []

        for task in tasks:
            task_type = task.get("type", "must")

            if task_type == "must":
                must_tasks.append(task)
            elif task_type == "should":
                should_tasks.append(task)
            else:
                bonus_tasks.append(task)

        def render_task(task: dict, index: int) -> list[str]:
            lines = []

            title = task.get("title") or "Задача"
            instructions = task.get("instructions") or task.get("description") or ""
            estimated_minutes = task.get("estimated_minutes")
            proof_required = task.get("proof_required")

            line = f"{index}. {title}"

            if estimated_minutes:
                line += f" ({estimated_minutes} мин)"

            lines.append(line)

            if instructions:
                lines.append(f"   — {instructions}")

            if proof_required:
                lines.append("   — Понадобится подтверждение выполнения")

            return lines

        if must_tasks:
            parts.append("")
            parts.append("📌 Обязательные:")

            for i, task in enumerate(must_tasks, start=1):
                parts.extend(render_task(task, i))

        if should_tasks:
            parts.append("")
            parts.append("➕ Дополнительно:")

            for i, task in enumerate(should_tasks, start=1):
                parts.extend(render_task(task, i))

        if bonus_tasks:
            parts.append("")
            parts.append("🚀 Если есть энергия:")

            for i, task in enumerate(bonus_tasks, start=1):
                parts.extend(render_task(task, i))

    return "\n".join(parts)


def get_next_pending_daily_task(tasks: list[dict]) -> dict | None:
    if not tasks:
        return None

    for task in tasks:
        status = task.get("status", "pending")

        if status not in {"done", "skipped", "failed"}:
            return task

    return None

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

    data = callback.data
    user_data = await state.get_data()

    current_daily_tasks = user_data.get("current_daily_tasks") or []
    current_task = get_next_pending_daily_task(current_daily_tasks)

    # =========================
    # DONE / SKIP
    # =========================
    if data in {"daily_task_done", "daily_task_skip"}:
        if not current_task:
            return

        task_id = current_task.get("id") or current_task.get("task_id")

        if not task_id:
            await callback.message.answer("Не удалось определить задачу для обновления.")
            return

        new_status = "done" if data == "daily_task_done" else "skipped"

        await set_daily_task_status(task_id, new_status)

        # =========================
        # DONE
        # =========================
        if new_status == "done":
            state_data = await state.get_data()
            streak = state_data.get("streak", 0) + 1

            coaching_mode = "normal"
            if streak >= 3:
                coaching_mode = "momentum"

            await state.update_data(
                streak=streak,
                coaching_mode=coaching_mode,
                last_skip_reason=None,
                skip_streak=0,
            )

            await callback.message.answer(
                f"🔥 Отлично. Серия: {streak} дней подряд.\n\n"
                "Не сбавляй темп 👇"
            )

            await send_next_daily_plan(callback.message, state, source="execution")
            return

        # =========================
        # SKIP
        # =========================
        if new_status == "skipped":
            state_data = await state.get_data()
            streak = state_data.get("streak", 0)
            skip_streak = state_data.get("skip_streak", 0) + 1

            await state.update_data(
                streak=0,
                coaching_mode="recovery",
                skip_streak=skip_streak,
            )

            if skip_streak >= 3:
                await callback.message.answer(
                    "Ты пропускаешь уже несколько задач подряд ❌\n\n"
                    "Это уже не случайность — ты начинаешь выпадать из процесса.\n"
                    "Напиши честно: ты действительно хочешь достичь этой цели?"
                )
            elif skip_streak == 2:
                await callback.message.answer(
                    "Второй пропуск подряд.\n\n"
                    "Сейчас критический момент — либо возвращаешься, либо начинаешь откатываться.\n"
                    "Почему пропустил?"
                )
            elif streak >= 3:
                await callback.message.answer(
                    f"Ты прервал серию из {streak} дней ❌\n\n"
                    "Это откат назад.\n"
                    "Напиши, что пошло не так."
                )
            else:
                await callback.message.answer(
                    "Ты пропустил задачу.\n\n"
                    "Важно не входить в паттерн пропусков.\n"
                    "Напиши, почему."
                )

            await state.set_state(GoalFlow.waiting_skip_reason)
            return

    # =========================
    # PROOF
    # =========================
    if data == "daily_task_proof":
        if not current_task:
            return

        task_id = current_task.get("id") or current_task.get("task_id")

        await state.update_data(current_daily_task_id=task_id)

        await callback.message.answer(
            "Отправь proof по текущей задаче: текст, фото или файл."
        )

        await state.set_state(GoalFlow.waiting_daily_proof)
        return

@router.message(GoalFlow.waiting_daily_proof)
async def daily_proof_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    current_daily_task_id = data.get("current_daily_task_id")

    if not current_daily_task_id:
        await message.answer("Не нашел активную задачу для proof. Попробуй открыть текущий день заново.")
        await state.set_state(GoalFlow.executing_plan)
        return

    if message.photo:
        proof_type = "photo"
        proof_label = "📸 Фото получено"
    elif message.document:
        proof_type = "file"
        proof_label = "📎 Файл получен"
    else:
        proof_type = "text"
        proof_label = "📝 Текст получен"

    await state.update_data(
        pending_daily_proof_type=proof_type,
        current_daily_task_id=None,
    )

    await message.answer(
        f"{proof_label}\n\nProof принят. Возвращаю тебя к плану на сегодня 👇"
    )

    await state.set_state(GoalFlow.executing_plan)
    await send_next_daily_plan(message, state, source="execution")

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
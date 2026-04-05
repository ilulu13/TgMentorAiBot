from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import random

from states import GoalFlow
from keyboards import (
    execution_keyboard,
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
    create_today_checkin,
    get_today_checkin,
    submit_checkin_report,
    set_step_status,
    complete_checkin,
    create_step_proof,
    get_daily_plans,
    get_today_daily_plan,
    get_daily_plan_by_day,
    set_daily_task_status,
    set_daily_plan_status,
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
    steps = plan.get("steps") or plan.get("content", {}).get("steps", [])

    roadmap_text = ""
    if roadmap:
        roadmap_items = "\n".join([f"• {item}" for item in roadmap])
        roadmap_text = f"\n\n📋 Общий путь:\n{roadmap_items}"

    steps_preview = ""
    if steps:
        preview_lines = []
        for i, step in enumerate(steps, start=1):
            title = step.get("title", "Без названия")
            description = step.get("description", "")
            line = f"{i}. {title}"
            if description:
                line += f"\n   {description}"
            preview_lines.append(line)
        steps_preview = "\n\n🧩 Ближайшие шаги:\n" + "\n".join(preview_lines)

    await message_obj.answer(
        f"📌 Коротко:\n{summary}"
        f"{roadmap_text}"
        f"{steps_preview}\n\n"
        f"Принять план?",
        reply_markup=confirm_plan_keyboard()
    )

    await state.set_state(GoalFlow.confirming_plan)

async def send_current_step(message_obj, state: FSMContext):
    data = await state.get_data()

    steps = data.get("steps", [])
    current_task_index = data.get("current_task_index", 0)

    if not steps:
        await message_obj.answer("В плане пока нет шагов.")
        return

    if current_task_index >= len(steps):
        done_count = data.get("done_count", 0)
        failed_count = data.get("failed_count", 0)

        await message_obj.answer(
            f"🎉 План завершен\n\n"
            f"Ты прошел весь цикл — это уже результат.\n\n"
            f"📊 Итог:\n"
            f"• Выполнено: {done_count}\n"
            f"• Не выполнено: {failed_count}\n\n"
            f"Готов идти дальше? Напиши новую цель 🚀"
        )
        return

    step = steps[current_task_index]

    current_step_id = step.get("id") or step.get("step_id")
    title = step.get("title", "Без названия")
    description = step.get("description")

    await state.update_data(current_step_id=current_step_id)

    total_steps = len(steps)
    current_index = current_task_index
    progress_percent = int((current_index / total_steps) * 100)

    text = (
        f"📍 Шаг {current_index + 1} из {total_steps}\n"
        f"📊 Прогресс: {progress_percent}%\n\n"
        f"{title}\n\n"
    )

    if description:
        text += description

    await message_obj.answer(
        text,
        reply_markup=execution_keyboard()
    )

    await state.set_state(GoalFlow.executing_plan)

async def send_today_daily_plan(message_obj, state: FSMContext):
    data = await state.get_data()
    goal_id = data.get("goal_id")

    today_response = await get_today_daily_plan(goal_id)

    if not today_response:
        await message_obj.answer("На сегодня пока нет плана.")
        return

    daily_plan = today_response.get("daily_plan") or {}

    if not daily_plan:
        await message_obj.answer("На сегодня пока нет плана.")
        return

    daily_plan_id = daily_plan.get("id") or daily_plan.get("daily_plan_id")
    day_number = daily_plan.get("day_number")
    tasks = daily_plan.get("tasks") or daily_plan.get("daily_tasks") or []

    await state.update_data(
        current_daily_plan=daily_plan,
        current_daily_plan_id=daily_plan_id,
        current_daily_tasks=tasks,
    )

    if not tasks:
        await message_obj.answer(
            f"📅 День {day_number}\n\nНа сегодня задач пока нет."
        )
        return

    lines = []
    for index, task in enumerate(tasks, start=1):
        title = task.get("title", "Без названия")
        description = task.get("description", "")
        status = task.get("status", "pending")

        status_emoji = "⬜️"
        if status == "done":
            status_emoji = "✅"
        elif status == "skipped":
            status_emoji = "⏭"
        elif status == "failed":
            status_emoji = "❌"

        line = f"{status_emoji} {index}. {title}"
        if description:
            line += f"\n   {description}"

        lines.append(line)

    text = (
        f"📅 План на сегодня"
        + (f" — день {day_number}" if day_number is not None else "")
        + "\n\n"
        + "\n\n".join(lines)
    )

    await message_obj.answer(
        text,
        reply_markup=daily_execution_keyboard()
    )

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

    user_data = await state.get_data()
    goal_id = user_data.get("goal_id")

    result = await submit_profiling_answer(goal_id, coach_style)
    await state.update_data(profiling_result=result)

    await callback.message.answer(
        f"Стиль коуча выбран: {coach_style_label} ✅"
    )

    if result.get("is_completed"):
        await send_plan_preview(callback.message, goal_id, state, profiling_result=result)
        await callback.answer()
        return

    await send_profiling_response(callback.message, result, state)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("profile_option:"))
async def profile_option_callback(callback: CallbackQuery, state: FSMContext):
    raw_index = callback.data.replace("profile_option:", "", 1)

    try:
        selected_index = int(raw_index)
    except ValueError:
        await callback.answer("Некорректный вариант")
        return

    user_data = await state.get_data()
    goal_id = user_data.get("goal_id")
    profiling_result = user_data.get("profiling_result") or {}
    suggested_options = profiling_result.get("suggested_options") or []

    if selected_index < 0 or selected_index >= len(suggested_options):
        await callback.answer("Вариант больше не актуален")
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
        await callback.answer()
        return

    await send_profiling_response(callback.message, result, state)
    await callback.answer()

@router.message(GoalFlow.collecting_profile)
async def collect_profile(message: Message, state: FSMContext):
    await message.answer(
        "Этот этап теперь обрабатывается через backend profiling."
    )



@router.callback_query(GoalFlow.executing_plan)
async def execution_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    if data in {"daily_task_done", "daily_task_skip", "daily_task_proof"}:
        await callback.answer()
        return

    if data == "step_done":
        await callback.message.answer(
            "Отлично. Напиши короткий комментарий, что именно ты сделал, или отправь proof."
        )
        await state.set_state(GoalFlow.waiting_done_comment)
        await callback.answer()
        return

    if data == "step_failed":
        await callback.message.answer(
            "Окей. Напиши, почему не получилось выполнить задачу."
        )
        await state.set_state(GoalFlow.waiting_fail_comment)
        await callback.answer()
        return

    await callback.answer("Неизвестное действие")

@router.callback_query(GoalFlow.executing_plan)
async def daily_execution_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    user_data = await state.get_data()

    current_daily_tasks = user_data.get("current_daily_tasks") or []
    goal_id = user_data.get("goal_id")

    current_task = get_next_pending_daily_task(current_daily_tasks)

    if data in {"daily_task_done", "daily_task_skip"}:
        if not current_task:
            await callback.message.answer("На сегодня больше нет активных задач ✅")
            await callback.answer()
            return

        task_id = current_task.get("id") or current_task.get("task_id")

        if not task_id:
            await callback.message.answer("Не удалось определить задачу для обновления.")
            await callback.answer()
            return

        new_status = "done" if data == "daily_task_done" else "skipped"

        await set_daily_task_status(task_id, new_status)

        today_response = await get_today_daily_plan(goal_id)
        daily_plan = today_response.get("daily_plan") or {}
        tasks = daily_plan.get("tasks") or daily_plan.get("daily_tasks") or []

        await state.update_data(
            current_daily_plan=daily_plan,
            current_daily_plan_id=daily_plan.get("id") or daily_plan.get("daily_plan_id"),
            current_daily_tasks=tasks,
        )

        status_text = (
            "✅ Задача отмечена как выполненная"
            if new_status == "done"
            else "⏭ Задача отмечена как пропущенная"
        )

        await callback.message.answer(status_text)
        await send_today_daily_plan(callback.message, state)
        await callback.answer()
        return

    if data == "daily_task_proof":
        current_task = get_next_pending_daily_task(current_daily_tasks)

        if not current_task:
            await callback.message.answer("На сегодня нет активной задачи для proof.")
            await callback.answer()
            return

        task_id = current_task.get("id") or current_task.get("task_id")

        await state.update_data(current_daily_task_id=task_id)

        await callback.message.answer(
            "Отправь proof по текущей задаче: текст, фото или файл."
        )
        await state.set_state(GoalFlow.waiting_daily_proof)
        await callback.answer()
        return

@router.message(GoalFlow.waiting_done_comment)
async def done_comment_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    done_count = data.get("done_count", 0)
    await state.update_data(done_count=done_count + 1)

    current_task_index = data.get("current_task_index", 0)
    goal_id = data.get("goal_id")
    current_step_id = data.get("current_step_id")

    checkin = await create_today_checkin(goal_id)
    checkin_id = checkin.get("id") or checkin.get("checkin_id")

    if message.photo:
        photo = message.photo[-1]

        payload = {
            "goal_id": goal_id,
            "proof_type": "photo",
            "telegram_file_id": photo.file_id,
            "file_unique_id": photo.file_unique_id,
            "mime_type": "image/jpeg",
            "filename": "photo.jpg",
            "caption": message.caption or ""
        }

        report_text = message.caption or "Фото отправлено как proof"

    elif message.document:
        doc = message.document

        payload = {
            "goal_id": goal_id,
            "proof_type": "file",
            "telegram_file_id": doc.file_id,
            "file_unique_id": doc.file_unique_id,
            "mime_type": doc.mime_type,
            "filename": doc.file_name,
            "caption": message.caption or ""
        }

        report_text = message.caption or "Файл отправлен как proof"

    else:
        payload = {
            "goal_id": goal_id,
            "proof_type": "text",
            "text": message.text
        }

        report_text = message.text or ""

    await create_step_proof(
        checkin_id=checkin_id,
        step_id=current_step_id,
        payload=payload
    )

    await submit_checkin_report(checkin_id, report_text)

    await set_step_status(
        checkin_id=checkin_id,
        step_id=current_step_id,
        status="done"
    )

    await complete_checkin(checkin_id)

    if message.photo:
     response_text = "📸 Фото-доказательство сохранено"
    
    elif message.document:
     response_text = "📎 Файл сохранен"
    
    else:
     response_text = "📝 Комментарий сохранен"

    await message.answer(
    f"{response_text}\n\n"
    f"🔥 Отлично, засчитано\n"
    f"Двигаемся дальше 👇"
)

    await state.update_data(current_task_index=current_task_index + 1)
    await send_current_step(message, state)


@router.message(GoalFlow.waiting_fail_comment)
async def fail_comment_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    failed_count = data.get("failed_count", 0)
    await state.update_data(failed_count=failed_count + 1)

    current_task_index = data.get("current_task_index", 0)
    goal_id = data.get("goal_id")
    current_step_id = data.get("current_step_id")

    comment = message.text

    checkin = await create_today_checkin(goal_id)
    checkin_id = checkin.get("id") or checkin.get("checkin_id")

    await submit_checkin_report(checkin_id, comment)

    await set_step_status(
        checkin_id=checkin_id,
        step_id=current_step_id,
        status="failed"
    )

    await complete_checkin(checkin_id)

    await message.answer(
    "Ок, зафиксировали ❌\n\n"
    "Главное — не выпадать из процесса.\n"
    "Идем дальше 👇"
)

    await state.update_data(current_task_index=current_task_index + 1)
    await send_current_step(message, state)

@router.message(GoalFlow.waiting_daily_proof)
async def daily_proof_handler(message: Message, state: FSMContext):
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
        pending_daily_proof_type=proof_type
    )

    await message.answer(
        f"{proof_label}\n\nProof принят. Возвращаю тебя к плану на сегодня 👇"
    )

    await state.set_state(GoalFlow.executing_plan)
    await send_today_daily_plan(message, state)

@router.callback_query(GoalFlow.confirming_plan)
async def confirm_plan_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "accept_plan":
        user_data = await state.get_data()
        goal_id = user_data.get("goal_id")

        await accept_plan(goal_id)

        plan = await get_current_plan(goal_id)

        await state.update_data(
            plan=plan,
            current_task_index=0,
            done_count=0,
            failed_count=0
        )

        await callback.message.answer(
            "План принят ✅\n\nТеперь начинаем выполнение."
        )

        await state.set_state(GoalFlow.executing_plan)
        await send_today_daily_plan(callback.message, state)

    elif data == "reject_plan":
        await callback.message.answer("Ок, переделаю план...")
        user_data = await state.get_data()
        goal_id = user_data.get("goal_id")
        await generate_plan(goal_id)
        plan = await get_current_plan(goal_id)
        plan_text = plan.get("summary_text") or plan.get("summary") or "План готов"

        await callback.message.answer(
            f"Вот новый план:\n\n{plan_text}\n\nПринять его?",
            reply_markup=confirm_plan_keyboard()
        )

        await state.set_state(GoalFlow.confirming_plan)

    await callback.answer()
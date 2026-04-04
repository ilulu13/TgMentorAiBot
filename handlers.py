from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import GoalFlow
from keyboards import execution_keyboard, confirm_plan_keyboard, coach_style_keyboard
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
)

router = Router()

def render_profiling_question_text(result: dict) -> str:
    current_question_text = result.get("current_question_text", "Следующий вопрос")
    example_answer = result.get("example_answer")
    feedback_message = result.get("feedback_message")
    follow_up_question = result.get("follow_up_question")
    needs_follow_up = result.get("needs_follow_up", False)

    answered = result.get("questions_answered_count")
    total = result.get("questions_total_count")

    # ===== ПРОГРЕСС =====
    progress_text = ""
    if isinstance(answered, int) and isinstance(total, int) and total > 0:
        progress_text = f"📊 Вопрос {answered + 1}/{total}\n\n"

    # ===== FOLLOW-UP (если ответ слабый) =====
    if needs_follow_up:
        text = "⚠️ Нужно чуть точнее\n\n"

        if feedback_message:
            text += f"{feedback_message}\n\n"

        text += follow_up_question or current_question_text

        if example_answer:
            text += f"\n\n💡 Пример:\n{example_answer}"

        return text

    # ===== ОБЫЧНЫЙ ВОПРОС =====
    text = progress_text

    text += f"{current_question_text}\n"

    if feedback_message:
        text += f"\n{feedback_message}\n"

    # подсказка (если есть)
    text += "\n💡 Подсказка:\nОтветь конкретно, с цифрами или фактами\n"

    if example_answer:
        text += f"\n📌 Пример:\n{example_answer}"

    return text


import random


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

    if needs_follow_up:
        if question_type == "choice" and current_question_key == "coach_style":
            await message_obj.answer(
                text,
                reply_markup=coach_style_keyboard()
            )
            await state.set_state(GoalFlow.choosing_coach_style)
            return

        await message_obj.answer(text)
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

        await message_obj.answer(text)
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

        await message_obj.answer(text)
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

        await message_obj.answer(text)
        await state.set_state(GoalFlow.clarifying_goal)
        return

    await message_obj.answer(text)
    await state.set_state(GoalFlow.clarifying_goal)

    current_question_key = result.get("current_question_key")
    text = render_profiling_question_text(result)

    needs_follow_up = result.get("needs_follow_up", False)
    answer_accepted = result.get("answer_accepted", False)

    if needs_follow_up:
        await message_obj.answer(text)
        await state.set_state(GoalFlow.clarifying_goal)
        return

    if show_positive_feedback and answer_accepted:
        feedback = get_positive_feedback()
        await message_obj.answer(feedback)

    if current_question_key == "coach_style":
        await message_obj.answer(
            text,
            reply_markup=coach_style_keyboard()
        )
        await state.set_state(GoalFlow.choosing_coach_style)
        return

    await message_obj.answer(text)
    await state.set_state(GoalFlow.clarifying_goal)


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


@router.message(GoalFlow.collecting_profile)
async def collect_profile(message: Message, state: FSMContext):
    await message.answer(
        "Этот этап теперь обрабатывается через backend profiling."
    )



@router.callback_query(GoalFlow.executing_plan)
async def execution_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data

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

@router.callback_query(GoalFlow.confirming_plan)
async def confirm_plan_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "accept_plan":
        user_data = await state.get_data()
        goal_id = user_data.get("goal_id")

        await accept_plan(goal_id)

        plan = await get_current_plan(goal_id)
        steps = plan.get("content", {}).get("steps", [])
        await state.update_data(
        plan=plan,
        steps=steps,
        current_task_index=0,
        done_count=0,
        failed_count=0
)

        await callback.message.answer(
            "План принят ✅\n\nТеперь начинаем выполнение."
        )

        await state.set_state(GoalFlow.executing_plan)
        await send_current_step(callback.message, state)

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
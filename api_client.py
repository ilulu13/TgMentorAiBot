import httpx

from config import BACKEND_BASE_URL


class BackendAPIError(Exception):
    pass


async def _handle_response(response: httpx.Response):
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        text = e.response.text
        print(f"[API ERROR] {e.response.status_code} | URL: {e.response.url} | Body: {text}")
        raise BackendAPIError(
            f"Backend returned {e.response.status_code}: {text}"
        ) from e

    try:
        return response.json()
    except ValueError as e:
        print(f"[API ERROR] Invalid JSON | URL: {response.url} | Body: {response.text}")
        raise BackendAPIError(
            f"Backend returned invalid JSON: {response.text}"
        ) from e


# =========================
# USERS
# =========================

async def get_or_create_user(payload: dict):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/users/get-or-create",
            json=payload,
        )
        return await _handle_response(response)


# =========================
# GOALS
# =========================

async def create_goal(payload: dict):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/goals",
            json=payload,
        )
        return await _handle_response(response)


async def list_goals(user_id: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{BACKEND_BASE_URL}/goals/{user_id}",
        )
        return await _handle_response(response)


async def set_active_goal(payload: dict):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/chat-context/active-goal",
            json=payload,
        )
        return await _handle_response(response)


# =========================
# PROFILING
# =========================

async def start_profiling(goal_id: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/goals/{goal_id}/profiling/start",
        )
        return await _handle_response(response)


async def get_current_profiling_question(goal_id: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{BACKEND_BASE_URL}/goals/{goal_id}/profiling/current-question",
        )
        return await _handle_response(response)


async def submit_profiling_answer(goal_id: str, answer: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/goals/{goal_id}/profiling/answer",
            json={"answer": answer},
        )
        return await _handle_response(response)


async def get_profiling_state(goal_id: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{BACKEND_BASE_URL}/goals/{goal_id}/profiling/state",
        )
        return await _handle_response(response)


# =========================
# PLAN
# =========================

async def generate_plan(goal_id: str):
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/goals/{goal_id}/plan/generate",
            json={"regenerate": False},
        )
        return await _handle_response(response)


async def get_current_plan(goal_id: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{BACKEND_BASE_URL}/goals/{goal_id}/plan/current",
        )
        return await _handle_response(response)


async def accept_plan(goal_id: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/goals/{goal_id}/plan/accept",
        )
        return await _handle_response(response)


# =========================
# DAILY PLANS
# =========================

async def get_next_daily_plan(goal_id: str):
    """
    Возвращает следующий actionable daily plan.
    Ответ: { "date": ..., "daily_plan": DailyPlanResponse | null }
    Возвращает {"error": "timeout"} при таймауте.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{BACKEND_BASE_URL}/goals/{goal_id}/daily-plans/next",
            )
            return await _handle_response(response)
    except httpx.ReadTimeout:
        return {"error": "timeout"}


async def get_today_daily_plan(goal_id: str):
    """
    Возвращает daily plan на сегодня.
    Ответ: { "date": ..., "daily_plan": DailyPlanResponse | null }
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{BACKEND_BASE_URL}/goals/{goal_id}/daily-plans/today",
            )
            return await _handle_response(response)
    except httpx.ReadTimeout:
        return {"error": "timeout"}


async def get_daily_plan_by_day(goal_id: str, day_number: int):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{BACKEND_BASE_URL}/goals/{goal_id}/daily-plans/{day_number}",
        )
        return await _handle_response(response)


async def get_daily_plans(goal_id: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{BACKEND_BASE_URL}/goals/{goal_id}/daily-plans",
        )
        return await _handle_response(response)


# =========================
# DAILY TASKS
# =========================

async def set_daily_task_status(task_id: str, status: str):
    """
    Обновляет статус задачи.
    Возвращает обновлённый DailyPlanResponse (со всеми tasks внутри).
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/daily-tasks/{task_id}/status",
            json={"status": status},
        )
        return await _handle_response(response)


async def set_daily_plan_status(daily_plan_id: str, status: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/daily-plans/{daily_plan_id}/status",
            json={"status": status},
        )
        return await _handle_response(response)


# =========================
# PROOFS
# =========================

async def create_daily_task_proof(task_id: str, payload: dict):
    """
    Создаёт proof для задачи.
    payload: { proof_type, telegram_file_id?, text? }
    Возвращает ProofResponse: { proof_id, status, review_message, ... }
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/daily-tasks/{task_id}/proofs",
            json=payload,
        )
        return await _handle_response(response)


async def get_task_proofs(task_id: str):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{BACKEND_BASE_URL}/daily-tasks/{task_id}/proofs",
        )
        return await _handle_response(response)
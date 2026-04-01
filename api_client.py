import httpx
BASE_URL = "https://tgbot-production-c88d.up.railway.app"
from config import BACKEND_BASE_URL


class BackendAPIError(Exception):
    pass


async def _handle_response(response: httpx.Response):
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        text = e.response.text
        raise BackendAPIError(
            f"Backend returned {e.response.status_code}: {text}"
        ) from e

    try:
        return response.json()
    except ValueError as e:
        raise BackendAPIError(
            f"Backend returned invalid JSON: {response.text}"
        ) from e


async def get_or_create_user(payload: dict):
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{BACKEND_BASE_URL}/users/get-or-create",
            json=payload,
        )
        return await _handle_response(response)


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
    
async def generate_plan(goal_id: str):
    timeout = httpx.Timeout(60.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{BASE_URL}/goals/{goal_id}/plan/generate",
            json={"regenerate": False}
        )
        response.raise_for_status()
        return response.json()


async def get_current_plan(goal_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/goals/{goal_id}/plan/current")
        response.raise_for_status()
        return response.json()


async def accept_plan(goal_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/goals/{goal_id}/plan/accept")
        response.raise_for_status()
        return response.json()
    
    
async def start_checkin(goal_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/goals/{goal_id}/checkins/today")
        response.raise_for_status()
        return response.json()


async def send_checkin_text(goal_id: str, text: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/goals/{goal_id}/checkins/today/text",
            json={"text": text}
        )
        response.raise_for_status()
        return response.json()


async def mark_step(goal_id: str, step_id: str, status: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/goals/{goal_id}/checkins/today/step",
            json={
                "step_id": step_id,
                "status": status
            }
        )
        response.raise_for_status()
        return response.json()
    
async def create_today_checkin(goal_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/goals/{goal_id}/checkins/today"
        )
        response.raise_for_status()
        return response.json()


async def get_today_checkin(goal_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/goals/{goal_id}/checkins/today"
        )
        response.raise_for_status()
        return response.json()


async def submit_checkin_report(checkin_id: str, text: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/checkins/{checkin_id}/report",
            json={"report_text": text}
        )
        response.raise_for_status()
        return response.json()


async def set_step_status(checkin_id: str, step_id: str, status: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/checkins/{checkin_id}/steps/{step_id}/status",
            json={"status": status}
        )
        response.raise_for_status()
        return response.json()


async def complete_checkin(checkin_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/checkins/{checkin_id}/complete"
        )
        response.raise_for_status()
        return response.json()
    
async def create_step_proof(checkin_id: str, step_id: str, payload: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/checkins/{checkin_id}/steps/{step_id}/proofs",
            json=payload
        )
        response.raise_for_status()
        return response.json()
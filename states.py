from aiogram.fsm.state import State, StatesGroup


class GoalFlow(StatesGroup):
    waiting_goal = State()
    clarifying_goal = State()
    collecting_profile = State()
    choosing_coach_style = State()
    choosing_plan = State()
    confirming_plan = State()
    executing_plan = State()
    waiting_done_comment = State()
    waiting_fail_comment = State()
    waiting_daily_proof = State()
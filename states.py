from aiogram.fsm.state import State, StatesGroup


class GoalFlow(StatesGroup):
    waiting_goal = State()
    clarifying_goal = State()
    choosing_coach_style = State()
    confirming_plan = State()
    executing_plan = State()
    waiting_daily_proof = State()
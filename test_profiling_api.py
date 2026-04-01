import asyncio
from api_client import (
    start_profiling,
    get_current_profiling_question,
    submit_profiling_answer,
    get_profiling_state,
)

GOAL_ID = "6498af5a-41d2-4223-9f82-45e8caae0d98"


async def main():
    result_start = await start_profiling(GOAL_ID)
    print("start_profiling:", result_start)

    result_question = await get_current_profiling_question(GOAL_ID)
    print("current_question:", result_question)

    result_answer = await submit_profiling_answer(GOAL_ID, "Потому что хочу стать сильнее и увереннее")
    print("submit_answer:", result_answer)

    result_state = await get_profiling_state(GOAL_ID)
    print("profiling_state:", result_state)


asyncio.run(main())

import asyncio
from api_client import create_goal


async def main():
    result = await create_goal(
        {
            "user_id": "b5372247-ce5a-4004-bf3e-a9da7d32fe85",
            "title": "Хочу сильные руки",
            "description": "Хочу сильные руки",
            "category": "fitness",
            "target_date": None,
            "priority": 1,
        }
    )
    print(result)


asyncio.run(main())

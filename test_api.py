import asyncio
from api_client import get_or_create_user


async def main():
    result = await get_or_create_user(
        {
            "telegram_user_id": 123456789,
            "telegram_chat_id": 123456789,
            "username": "test_user",
            "first_name": "Test",
            "last_name": "User",
            "language_code": "ru",
        }
    )
    print(result)


asyncio.run(main())
import asyncpg
from config import DATABASE_URL

db_pool = None


async def create_db_pool():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, ssl="require")


async def close_db_pool():
    global db_pool
    if db_pool:
        await db_pool.close()


async def get_or_create_user(
    telegram_user_id: int,
    telegram_chat_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    language_code: str | None,
):
    global db_pool

    async with db_pool.acquire() as conn:
        existing_user = await conn.fetchrow(
            """
            SELECT id
            FROM users
            WHERE telegram_user_id = $1
            """,
            telegram_user_id,
        )

        if existing_user:
            await conn.execute(
                """
                UPDATE users
                SET telegram_chat_id = $1,
                    username = $2,
                    first_name = $3,
                    last_name = $4,
                    language_code = $5,
                    updated_at = NOW(),
                    last_seen_at = NOW()
                WHERE telegram_user_id = $6
                """,
                telegram_chat_id,
                username,
                first_name,
                last_name,
                language_code,
                telegram_user_id,
            )
            return existing_user["id"]

        new_user = await conn.fetchrow(
            """
            INSERT INTO users (
                telegram_user_id,
                telegram_chat_id,
                username,
                first_name,
                last_name,
                language_code,
                status,
                is_blocked,
                created_at,
                updated_at,
                last_seen_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, 'active', false, NOW(), NOW(), NOW())
            RETURNING id
            """,
            telegram_user_id,
            telegram_chat_id,
            username,
            first_name,
            last_name,
            language_code,
        )
        return new_user["id"]


async def create_goal(
    user_id: int,
    title: str,
    description: str | None = None,
):
    global db_pool

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO goals (
                user_id,
                title,
                description,
                status,
                priority,
                created_at,
                updated_at,
                activated_at
            )
            VALUES ($1, $2, $3, 'active', 2, NOW(), NOW(), NOW())
            RETURNING id
            """,
            user_id,
            title,
            description,
        )
        return row["id"]


async def create_plan(
    goal_id: int,
    source: str = "manual",
    summary_text: str | None = None,
):
    global db_pool

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO plans (
                goal_id,
                version,
                status,
                source,
                summary_text,
                created_at,
                updated_at,
                accepted_at
            )
            VALUES ($1, 1, 'accepted', $2, $3, NOW(), NOW(), NOW())
            RETURNING id
            """,
            goal_id,
            source,
            summary_text,
        )
        return row["id"]


async def create_plan_step(
    plan_id: int,
    step_order: int,
    title: str,
    description: str | None = None,
):
    global db_pool

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO plan_steps (
                plan_id,
                step_order,
                title,
                description,
                is_required,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, true, NOW(), NOW())
            """,
            plan_id,
            step_order,
            title,
            description,
        )


async def get_plan_steps(plan_id: int):
    global db_pool

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, step_order, title, description
            FROM plan_steps
            WHERE plan_id = $1
            ORDER BY step_order ASC
            """,
            plan_id,
        )
        return rows
from datetime import date

async def create_or_update_checkin(
    user_id: int,
    goal_id: int,
    plan_id: int,
    status: str,
    text_report: str | None = None,
):
    global db_pool

    today = date.today()

    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id
            FROM daily_checkins
            WHERE user_id = $1
              AND goal_id = $2
              AND plan_id = $3
              AND checkin_date = $4
            """,
            user_id,
            goal_id,
            plan_id,
            today,
        )

        if existing:
            await conn.execute(
                """
                UPDATE daily_checkins
                SET status = $1,
                    text_report = $2,
                    updated_at = NOW()
                WHERE id = $3
                """,
                status,
                text_report,
                existing["id"],
            )
            return existing["id"]

        new_row = await conn.fetchrow(
            """
            INSERT INTO daily_checkins (
                user_id,
                goal_id,
                plan_id,
                checkin_date,
                status,
                text_report,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            RETURNING id
            """,
            user_id,
            goal_id,
            plan_id,
            today,
            status,
            text_report,
        )

        return new_row["id"]
    
async def create_or_update_step_report(
    daily_checkin_id,
    plan_step_id,
    status: str,
    comment: str | None = None,
):
    global db_pool

    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id
            FROM step_reports
            WHERE daily_checkin_id = $1
              AND plan_step_id = $2
            """,
            daily_checkin_id,
            plan_step_id,
        )

        if existing:
            await conn.execute(
                """
                UPDATE step_reports
                SET status = $1,
                    comment = $2,
                    updated_at = NOW()
                WHERE id = $3
                """,
                status,
                comment,
                existing["id"],
            )
            return existing["id"]

        row = await conn.fetchrow(
            """
            INSERT INTO step_reports (
                daily_checkin_id,
                plan_step_id,
                status,
                comment,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            RETURNING id
            """,
            daily_checkin_id,
            plan_step_id,
            status,
            comment,
        )
        return row["id"]
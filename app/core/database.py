from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

import redis.asyncio as aioredis
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)

pg_pool: AsyncConnectionPool | None = None
redis_client: aioredis.Redis | None = None


async def init_db() -> None:
    """Initialize database pools and execute startup migrations."""
    global pg_pool, redis_client
    settings = get_settings()

    logger.info("Connecting to PostgreSQL pool...")
    pg_pool = AsyncConnectionPool(
        conninfo=settings.postgres_connection_string,
        min_size=1,
        max_size=10,
        open=False,
    )
    await pg_pool.open()

    async with pg_pool.connection() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                id SERIAL PRIMARY KEY,
                slug VARCHAR(64) UNIQUE NOT NULL,
                target_url TEXT NOT NULL,
                title VARCHAR(200) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_urls_slug ON urls(slug);
            """
        )
    logger.info("PostgreSQL table 'urls' verified.")

    logger.info("Connecting to Redis...")
    redis_client = aioredis.from_url(
        settings.redis_connection_string,
        encoding="utf-8",
        decode_responses=True,
    )
    await redis_client.ping()
    logger.info("Redis connection established.")


async def close_db() -> None:
    """Gracefully close all database connections."""
    global pg_pool, redis_client
    if redis_client:
        await redis_client.aclose()
        logger.info("Redis connection closed.")
    if pg_pool:
        await pg_pool.close()
        logger.info("PostgreSQL pool closed.")


def get_redis() -> aioredis.Redis:
    """Provide the active Redis client."""
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized.")
    return redis_client


@asynccontextmanager
async def get_pg_connection() -> AsyncIterator:
    """Yield a PostgreSQL connection configured with dict row factory."""
    if pg_pool is None:
        raise RuntimeError("PostgreSQL pool is not initialized.")
    async with pg_pool.connection() as conn:
        conn.row_factory = dict_row
        yield conn


async def check_health() -> dict[str, str]:
    """Check health of PostgreSQL and Redis."""
    status = {"postgres": "error", "redis": "error"}

    try:
        async with get_pg_connection() as conn:
            cursor = await conn.execute("SELECT 1")
            await cursor.fetchone()
        status["postgres"] = "ok"
    except Exception as exc:
        status["postgres"] = f"error: {exc}"

    try:
        r = get_redis()
        pong = await r.ping()
        if pong:
            status["redis"] = "ok"
    except Exception as exc:
        status["redis"] = f"error: {exc}"

    return status

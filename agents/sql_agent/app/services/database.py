"""PostgreSQL async connection pool (read-only via asyncpg).

Provides execute_query() with timeout and auto-LIMIT.
"""

from __future__ import annotations

import asyncpg
from loguru import logger

from app.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool (lazy init)."""
    global _pool
    if _pool is not None:
        return _pool

    dsn = (
        f"postgresql://{settings.pg_user}:{settings.pg_password}"
        f"@{settings.pg_host}:{settings.pg_port}/{settings.pg_database}"
    )
    logger.info(
        f"Connecting to PostgreSQL {settings.pg_host}:{settings.pg_port}"
        f"/{settings.pg_database} as {settings.pg_user}"
    )
    try:
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            ssl="disable",
            min_size=1,
            max_size=5,
        )
    except Exception as exc:
        logger.error(
            f"PostgreSQL connection failed — "
            f"host={settings.pg_host}:{settings.pg_port} "
            f"db={settings.pg_database} user={settings.pg_user} | {exc}"
        )
        raise
    logger.info("PostgreSQL pool created successfully.")
    return _pool


async def close_pool() -> None:
    """Close the connection pool (call on app shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed.")


def _ensure_limit(sql: str, max_rows: int) -> str:
    """Append LIMIT if not already present."""
    if "limit" not in sql.lower():
        sql = sql.rstrip().rstrip(";")
        sql = f"{sql}\nLIMIT {max_rows};"
    return sql


async def execute_query(sql: str) -> list[dict]:
    """Execute a SELECT query and return rows as list of dicts.

    Applies:
    - statement_timeout for safety
    - auto LIMIT max_rows
    Raises on any error (caller decides how to handle).
    """
    pool = await get_pool()
    sql = _ensure_limit(sql, settings.max_rows)

    logger.info(f"Executing SQL:\n{sql}")

    async with pool.acquire() as conn:
        # Set per-connection timeout
        await conn.execute(
            f"SET statement_timeout = '{settings.query_timeout}s'"
        )
        rows = await conn.fetch(sql)

    result = [dict(r) for r in rows]
    logger.info(f"Query returned {len(result)} row(s)")
    return result

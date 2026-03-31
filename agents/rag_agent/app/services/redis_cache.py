"""Redis cache wrapper for the RAG Agent — stub.

TODO: same pattern as orchestrator redis_cache.py, adapted for RAG responses.
"""

from __future__ import annotations

import hashlib
import json

from loguru import logger

from app.config import settings

_pool = None


async def get_redis():
    """Return a shared async Redis connection.

    TODO: import redis.asyncio; return redis.from_url(settings.redis_url)
    """
    logger.debug("redis_cache.get_redis stub called")
    return None


def _cache_key(query: str) -> str:
    raw = query.strip().lower()
    return f"rag:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


async def get_cached(query: str) -> dict | None:
    """TODO: implement Redis GET."""
    return None


async def set_cached(query: str, result: dict) -> None:
    """TODO: implement Redis SET with TTL."""
    pass

"""Simple Redis cache wrapper for query results."""

from __future__ import annotations

import hashlib
import json

import redis.asyncio as aioredis
from loguru import logger

from app.config import settings

_pool: aioredis.Redis | None = None
CACHE_TTL = 300  # 5 minutes


async def get_redis() -> aioredis.Redis:
    """Return a shared async Redis connection."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _pool


def _cache_key(query: str, chatbot_id: int) -> str:
    """Generate a deterministic cache key."""
    raw = f"{chatbot_id}:{query.strip().lower()}"
    return f"cache:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


async def get_cached(query: str, chatbot_id: int) -> dict | None:
    """Return cached result or None."""
    try:
        r = await get_redis()
        data = await r.get(_cache_key(query, chatbot_id))
        if data:
            logger.info("Cache HIT for query")
            return json.loads(data)
    except Exception as exc:
        logger.warning(f"Redis read error (non-fatal): {exc}")
    return None


async def set_cached(query: str, chatbot_id: int, result: dict) -> None:
    """Store result in cache."""
    try:
        r = await get_redis()
        await r.set(
            _cache_key(query, chatbot_id),
            json.dumps(result, ensure_ascii=False),
            ex=CACHE_TTL,
        )
        logger.debug("Cached result for query")
    except Exception as exc:
        logger.warning(f"Redis write error (non-fatal): {exc}")

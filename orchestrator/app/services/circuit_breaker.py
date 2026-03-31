"""Simple circuit breaker — stub for MVP.

Tracks consecutive failures per agent. Opens circuit after threshold.
"""

from __future__ import annotations

from loguru import logger

# In-memory failure counters (reset on restart — fine for MVP)
_failures: dict[str, int] = {}
_THRESHOLD = 3


def is_open(agent_type: str) -> bool:
    """Return True if the circuit is open (agent should be skipped)."""
    count = _failures.get(agent_type, 0)
    if count >= _THRESHOLD:
        logger.warning(f"Circuit OPEN for agent '{agent_type}' ({count} failures)")
        return True
    return False


def record_success(agent_type: str) -> None:
    """Reset failure counter on success."""
    _failures[agent_type] = 0


def record_failure(agent_type: str) -> None:
    """Increment failure counter."""
    _failures[agent_type] = _failures.get(agent_type, 0) + 1
    logger.debug(f"Failure #{_failures[agent_type]} for agent '{agent_type}'")

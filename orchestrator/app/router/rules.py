"""Level 1 — Rule-based routing using keyword/regex patterns."""

from __future__ import annotations

from app.router.intent_rules import INTENT_PATTERNS


def route_by_rules(
    query: str, agent_types: list[str]
) -> tuple[list[str], float]:
    """Score each agent by matching keyword patterns against the query.

    Returns the best-matching agent(s) and a confidence score.
    """
    scores: dict[str, float] = {}

    for agent_type in agent_types:
        patterns = INTENT_PATTERNS.get(agent_type, [])
        agent_score = 0.0
        for pattern, weight in patterns:
            if pattern.search(query):
                agent_score = max(agent_score, weight)
        scores[agent_type] = agent_score

    if not scores:
        return [], 0.0

    best_agent = max(scores, key=scores.get)  # type: ignore[arg-type]
    best_score = scores[best_agent]

    if best_score <= 0.0:
        return [], 0.0

    # Check for multi-intent (multiple agents above 0.5)
    selected = [a for a, s in scores.items() if s >= 0.5]
    if len(selected) > 1:
        return selected, min(s for a, s in scores.items() if a in selected)

    return [best_agent], best_score

"""Node 3 — Call selected agents in parallel via HTTP."""

from __future__ import annotations

import asyncio

import httpx
from loguru import logger

from app.config import settings
from app.state import OrchestratorState
from app.services.circuit_breaker import is_open, record_success, record_failure


async def _call_agent(agent_cfg: dict, query: str) -> dict:
    """HTTP POST to a single agent endpoint."""
    agent_type = agent_cfg["agent_type"]
    url = f"http://{agent_cfg['host']}:{agent_cfg['port']}{agent_cfg['path']}"
    logger.info(f"Calling agent '{agent_type}' at {url} (timeout={settings.agent_timeout}s)")

    try:
        async with httpx.AsyncClient(timeout=settings.agent_timeout) as client:
            resp = await client.post(url, json={"query": query})
            resp.raise_for_status()
            data = resp.json()
            record_success(agent_type)
            logger.info(
                f"Agent '{agent_type}' responded — "
                f"confidence={data.get('confidence', 0)}, "
                f"strategy={data.get('metadata', {}).get('strategy', '?')}"
            )
            return {
                "agent": agent_type,
                "answer": data.get("answer", ""),
                "confidence": data.get("confidence", 0.0),
                "sources": data.get("sources", []),
                "data": data.get("data", {}),
                "metadata": data.get("metadata", {}),
            }
    except httpx.TimeoutException:
        record_failure(agent_type)
        logger.error(
            f"Agent '{agent_type}' TIMEOUT after {settings.agent_timeout}s — "
            f"the agent may need more time for LLM generation"
        )
        error_msg = f"timeout ({settings.agent_timeout}s)"
    except httpx.ConnectError as exc:
        record_failure(agent_type)
        logger.error(f"Agent '{agent_type}' CONNECTION ERROR — is it running? {exc}")
        error_msg = f"connection_error: {exc}"
    except httpx.HTTPStatusError as exc:
        record_failure(agent_type)
        logger.error(f"Agent '{agent_type}' HTTP {exc.response.status_code}: {exc}")
        error_msg = f"http_{exc.response.status_code}"
    except Exception as exc:
        record_failure(agent_type)
        logger.error(f"Agent '{agent_type}' unexpected error: {type(exc).__name__}: {exc}")
        error_msg = str(exc)

    return {
        "agent": agent_type,
        "answer": "",
        "confidence": 0.0,
        "sources": [],
        "data": {},
        "metadata": {"error": error_msg},
    }


async def call_agents(state: OrchestratorState) -> dict:
    """Fan-out HTTP calls to all selected agents."""
    logger.info("Node: call_agents")

    agents_config = state.get("agents_config", [])
    selected = state.get("selected_agents", [])
    sub_queries = state.get("sub_queries", {})

    config_map = {a["agent_type"]: a for a in agents_config}
    tasks = []
    for agent_type in selected:
        cfg = config_map.get(agent_type)
        if cfg is None:
            continue
        if is_open(agent_type):
            logger.warning(f"Skipping '{agent_type}' — circuit open")
            continue
        query = sub_queries.get(agent_type, state["query"])
        tasks.append(_call_agent(cfg, query))

    responses = await asyncio.gather(*tasks) if tasks else []
    agents_used = [r["agent"] for r in responses if r["answer"]]
    logger.info(f"Received {len(responses)} response(s), used: {agents_used}")

    return {
        "agent_responses": list(responses),
        "agents_used": agents_used,
        "tried_agents": list(state.get("tried_agents", [])) + selected,
    }

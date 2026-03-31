"""Node 1 — Load agent configuration from agents_config.json."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from app.state import OrchestratorState

CONFIG_PATH = Path(__file__).resolve().parents[2] / "agents_config.json"


def load_config(state: OrchestratorState) -> dict:
    """Read agents_config.json and inject into state."""
    logger.info("Node: load_config")
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            agents_config = json.load(f)
        logger.info(f"Loaded {len(agents_config)} agent(s) from config")
    except FileNotFoundError:
        logger.error(f"Config not found: {CONFIG_PATH}")
        agents_config = []
    return {"agents_config": agents_config}

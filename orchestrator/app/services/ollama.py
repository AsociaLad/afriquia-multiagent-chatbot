"""Minimal Ollama HTTP client — stub for MVP, real calls later."""

from __future__ import annotations

import httpx
from loguru import logger

from app.config import settings


async def generate(prompt: str, model: str | None = None) -> str:
    """Send a prompt to Ollama and return the generated text.

    MVP: actually calls Ollama if available, gracefully fails otherwise.
    """
    model = model or settings.ollama_model
    url = f"{settings.ollama_base_url}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
    except Exception as exc:
        logger.warning(f"Ollama call failed (non-fatal): {exc}")
        return ""

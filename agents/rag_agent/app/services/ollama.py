"""Ollama HTTP client for the RAG Agent.

Sends a prompt to Ollama /api/generate and returns the generated text.
temperature=0.1 for factual, low-creativity RAG responses.
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.config import settings

TEMPERATURE = 0.1
TIMEOUT     = 120.0  # seconds — LLM generation can be slow on CPU


async def generate(prompt: str, model: str | None = None) -> str:
    """Send a prompt to Ollama and return the generated text.

    Returns "" on any failure (non-fatal — caller decides how to handle it).
    """
    model = model or settings.ollama_model
    url   = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model":   model,
        "prompt":  prompt,
        "stream":  False,
        "options": {"temperature": TEMPERATURE},
    }

    logger.info(f"Ollama: calling model='{model}' prompt_len={len(prompt)} chars")

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            answer = resp.json().get("response", "").strip()
            logger.info(f"Ollama: response received ({len(answer)} chars)")
            return answer
    except httpx.TimeoutException:
        logger.warning("Ollama: request timed out (non-fatal)")
        return ""
    except Exception as exc:
        logger.warning(f"Ollama: call failed (non-fatal): {exc}")
        return ""

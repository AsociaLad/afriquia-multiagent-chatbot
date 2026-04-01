"""Formateur hybride pour les réponses SQL.

Stratégie :
- 0-3 lignes  → _format_simple (templates Python, pas de LLM)
- 4+ lignes   → _format_with_llm (Ollama, résumé concis FR)
                 └─ fallback _format_simple si LLM échoue
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.config import settings

# Max rows envoyées au LLM pour le formatage (limite le prompt)
_MAX_ROWS_FOR_LLM = 10

# ---------------------------------------------------------------------------
# Simple formatter (templates Python)
# ---------------------------------------------------------------------------


def _format_simple(question: str, rows: list[dict]) -> str:
    """Format 0-3 rows with Python templates. No LLM call."""
    if not rows:
        return "Aucun résultat trouvé pour cette requête."

    # 1 row, 1 column → direct value
    if len(rows) == 1 and len(rows[0]) == 1:
        col, val = next(iter(rows[0].items()))
        return f"{col} : {val}"

    # 1 row, multiple columns → phrase
    if len(rows) == 1:
        parts = [f"{k} : {v}" for k, v in rows[0].items()]
        return ", ".join(parts) + "."

    # 2-3 rows → bulleted list
    lines: list[str] = []
    for row in rows:
        parts = [f"{k}: {v}" for k, v in row.items()]
        lines.append("- " + ", ".join(parts))

    return f"{len(rows)} résultat(s) :\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM formatter (Ollama)
# ---------------------------------------------------------------------------

_FORMAT_SYSTEM_PROMPT = """Tu es un assistant qui reformule des résultats SQL en réponse naturelle en français.

Règles :
1. Réponds de manière concise et naturelle, en 5-6 lignes maximum.
2. Ne montre JAMAIS le SQL ni le JSON.
3. Utilise des listes à puces si besoin.
4. Réponds directement à la question posée.
5. Si les données sont nombreuses, résume les points clés.
"""


async def _format_with_llm(question: str, rows: list[dict]) -> str | None:
    """Format rows using Ollama for a natural French summary.

    Returns the formatted string, or None on any failure.
    """
    # Limit rows sent to LLM
    truncated = rows[:_MAX_ROWS_FOR_LLM]
    suffix = ""
    if len(rows) > _MAX_ROWS_FOR_LLM:
        suffix = f"\n(... et {len(rows) - _MAX_ROWS_FOR_LLM} autres résultats)"

    # Build a readable text table for the LLM
    data_text = "\n".join(
        ", ".join(f"{k}: {v}" for k, v in row.items())
        for row in truncated
    )
    data_text += suffix

    prompt = (
        f"Question de l'utilisateur : {question}\n\n"
        f"Résultats ({len(rows)} lignes) :\n{data_text}\n\n"
        f"Reformule ces résultats en réponse naturelle en français."
    )

    url = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "system": _FORMAT_SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 512,
        },
    }

    logger.info(f"[formatter] Calling Ollama for LLM formatting ({len(rows)} rows)")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("[formatter] Ollama timeout (15s) — will use simple format")
        return None
    except httpx.HTTPError as exc:
        logger.warning(f"[formatter] Ollama HTTP error: {exc} — will use simple format")
        return None
    except Exception as exc:
        logger.warning(f"[formatter] Unexpected error: {exc} — will use simple format")
        return None

    response_text = data.get("response", "").strip()

    # qwen3:8b thinking mode: check thinking field if response is empty
    if not response_text:
        thinking_text = data.get("thinking", "").strip()
        if thinking_text:
            # Use last paragraph of thinking as the answer
            paragraphs = [p.strip() for p in thinking_text.split("\n\n") if p.strip()]
            if paragraphs:
                response_text = paragraphs[-1]
                logger.info("[formatter] Used thinking field fallback")

    if not response_text:
        logger.warning("[formatter] Ollama returned empty — will use simple format")
        return None

    logger.info(f"[formatter] LLM formatted response ({len(response_text)} chars)")
    return response_text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def format_answer(question: str, rows: list[dict], sql: str) -> str:
    """Format SQL results into a natural French answer.

    - 0-3 rows: simple Python templates (no LLM)
    - 4+ rows: LLM formatting with automatic fallback to simple
    """
    n = len(rows)

    if n <= 3:
        answer = _format_simple(question, rows)
        logger.info(f"[formatter] Simple format ({n} rows)")
        return answer

    # 4+ rows: try LLM, fallback to simple
    llm_answer = await _format_with_llm(question, rows)
    if llm_answer is not None:
        logger.info(f"[formatter] LLM format used ({n} rows)")
        return llm_answer

    # Fallback
    answer = _format_simple(question, rows)
    logger.warning(f"[formatter] LLM failed, fell back to simple ({n} rows)")
    return answer

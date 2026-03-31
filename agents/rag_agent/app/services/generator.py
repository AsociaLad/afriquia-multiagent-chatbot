"""Generator — builds a RAG prompt, calls Ollama, returns structured answer."""

from __future__ import annotations

from loguru import logger

from app.services import ollama

# Exact fallback when no relevant chunks are available
NO_CONTEXT_ANSWER = (
    "Cette information n'est pas disponible dans notre documentation."
)

SYSTEM_PROMPT = (
    "Tu es un assistant Afriquia. "
    "Réponds uniquement en utilisant les extraits de documentation fournis ci-dessous. "
    "Si la réponse ne figure pas dans ces extraits, dis-le clairement. "
    "Ne fabrique pas d'information. "
    "Réponds en français, de manière concise et précise."
)


def _build_prompt(query: str, chunks: list[dict]) -> str:
    """Format the RAG prompt: system instructions + context chunks + question."""
    context_parts: list[str] = []
    for i, ch in enumerate(chunks):
        source = ch.get("source", "source inconnue")
        text   = ch.get("text", "")
        context_parts.append(f"[Extrait {i+1} — {source}]\n{text}")

    context_block = "\n\n".join(context_parts)

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"=== Documentation pertinente ===\n"
        f"{context_block}\n\n"
        f"=== Question ===\n"
        f"{query}\n\n"
        f"=== Réponse ==="
    )
    return prompt


def _estimate_confidence(chunks: list[dict], answer: str) -> float:
    """Simple MVP confidence heuristic.

    Based on the best chunk score and whether Ollama returned an answer.
    Not a real probability — just a comparable signal for the orchestrator.
    """
    if not answer or not chunks:
        return 0.0

    best_score = max(ch.get("score", 0.0) for ch in chunks)

    # Penalise if Ollama returned a very short answer (likely a refusal)
    length_ok = len(answer) > 40

    if best_score >= 0.70 and length_ok:
        return 0.88
    if best_score >= 0.50 and length_ok:
        return 0.72
    if best_score >= 0.35 and length_ok:
        return 0.55
    return 0.30


class Generator:
    """Generates a natural-language answer from retrieved document chunks."""

    async def generate(self, query: str, chunks: list[dict]) -> dict:
        """Return {answer, sources, confidence}.

        If no chunks provided → return the standard no-context answer.
        """
        logger.info(f"Generator: received {len(chunks)} chunk(s) for query='{query[:60]}…'"
                    if len(query) > 60 else
                    f"Generator: received {len(chunks)} chunk(s) for query='{query}'")

        # --- No context: return fixed fallback ---
        if not chunks:
            logger.info("Generator: no chunks — returning fallback answer")
            return {
                "answer":     NO_CONTEXT_ANSWER,
                "sources":    [],
                "confidence": 0.0,
            }

        # --- Build prompt ---
        prompt = _build_prompt(query, chunks)
        logger.debug(
            f"Generator: prompt built "
            f"({len(chunks)} chunk(s), {len(prompt)} chars total)"
        )

        # --- Call Ollama ---
        raw_answer = await ollama.generate(prompt)

        # --- Handle empty Ollama response ---
        if not raw_answer:
            logger.warning("Generator: Ollama returned empty response — using fallback")
            return {
                "answer":     NO_CONTEXT_ANSWER,
                "sources":    [],
                "confidence": 0.0,
            }

        logger.info(f"Generator: answer generated ({len(raw_answer)} chars)")

        # --- Build sources list (unique, sorted) ---
        sources = sorted({ch["source"] for ch in chunks if ch.get("source")})

        # --- Estimate confidence ---
        confidence = _estimate_confidence(chunks, raw_answer)

        return {
            "answer":     raw_answer,
            "sources":    sources,
            "confidence": confidence,
        }

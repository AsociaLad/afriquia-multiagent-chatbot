"""Manual test script for the NL-to-SQL pipeline (end-to-end).

Usage (unit — Ollama required, PostgreSQL NOT required):
    cd agents/sql_agent
    python -m scripts.test_generator

Usage (HTTP — SQL Agent must be running on port 8006):
    cd agents/sql_agent
    python -m scripts.test_generator --http
"""

import asyncio
import sys

from app.services.sql_generator import generate_sql
from app.services.sql_cleaner import clean_sql
from app.services.sql_validator import validate_sql

TEST_QUESTIONS = [
    # Covered by keyword mappings (should work via NL-to-SQL too)
    "Quel est le prix du gazoil ?",
    "Combien de commandes par statut ?",
    "Quelles sont les réclamations ouvertes ?",
    # NOT covered by keyword mappings (NL-to-SQL only)
    "Quels clients habitent à Casablanca ?",
    "Quel client a le plus dépensé ?",
    "Combien de livraisons sont en cours ?",
    "Liste des produits de type gaz avec leur prix",
    "Quelles commandes ont été passées en mars 2025 ?",
]


async def run_unit_tests():
    """Test generate → clean → validate (no DB execution)."""
    print("=" * 70)
    print("Mode UNIT : generate → clean → validate (Ollama requis)")
    print("=" * 70)

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\n{'─' * 60}")
        print(f"[{i}/{len(TEST_QUESTIONS)}] {question}")
        print(f"{'─' * 60}")

        # Step 1: Generate
        try:
            raw = await generate_sql(question)
        except RuntimeError as exc:
            print(f"  ERREUR generation: {exc}")
            continue

        print(f"  RAW : {raw[:200]}")

        # Step 2: Clean
        cleaned = clean_sql(raw)
        print(f"  CLEAN: {cleaned}")

        if not cleaned:
            print("  ERREUR: Aucun SELECT extrait.")
            continue

        # Step 3: Validate
        is_valid, reason = validate_sql(cleaned)
        status = "VALIDE" if is_valid else f"REJETÉ ({reason})"
        print(f"  STATUS: {status}")


def run_http_tests():
    """Test via HTTP against running SQL Agent (port 8006)."""
    import httpx

    print("=" * 70)
    print("Mode HTTP : appels POST /query sur localhost:8006")
    print("=" * 70)

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\n{'─' * 60}")
        print(f"[{i}/{len(TEST_QUESTIONS)}] {question}")
        print(f"{'─' * 60}")

        try:
            resp = httpx.post(
                "http://localhost:8006/query",
                json={"query": question},
                timeout=90.0,
            )
            data = resp.json()
        except Exception as exc:
            print(f"  ERREUR HTTP: {exc}")
            continue

        strategy = data.get("metadata", {}).get("strategy", "?")
        confidence = data.get("confidence", 0)
        rows = data.get("data", {}).get("rows_returned", "?")
        sql = data.get("data", {}).get("sql", "")
        answer = data.get("answer", "")[:150]

        print(f"  STRATEGY : {strategy}")
        print(f"  CONFIDENCE: {confidence}")
        print(f"  ROWS      : {rows}")
        if sql:
            print(f"  SQL       : {sql[:120]}")
        print(f"  ANSWER    : {answer}")


if __name__ == "__main__":
    if "--http" in sys.argv:
        run_http_tests()
    else:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_unit_tests())

    print(f"\n{'=' * 70}")
    print("Terminé.")

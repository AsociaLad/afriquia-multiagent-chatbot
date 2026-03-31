"""Script de test manuel du retriever — à lancer depuis agents/rag_agent/.

Usage:
    cd agents/rag_agent
    python scripts/test_retriever.py

Prérequis : Qdrant tourne sur localhost:6333, ingestion effectuée.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure app/ is importable from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger
from app.services.retriever import Retriever


QUERIES = [
    "Quelle est la norme EN590 ?",
    "Comment commander une bouteille de gaz ?",
    "Règles de sécurité pour le stockage du carburant",
    "Prix du gazoil Afriquia",
]


async def main() -> None:
    retriever = Retriever(top_k=4, score_threshold=0.35)

    for query in QUERIES:
        print()
        print(f"{'='*60}")
        print(f"QUERY : {query}")
        print(f"{'='*60}")

        chunks = await retriever.retrieve(query)

        if not chunks:
            print("  → Aucun chunk retenu (score < threshold ou erreur)")
            continue

        for i, ch in enumerate(chunks):
            print(f"\n  Chunk {i+1} — score={ch['score']:.4f}")
            print(f"  Source     : {ch['source']}")
            print(f"  Doc type   : {ch['doc_type']}")
            print(f"  Title      : {ch['title']}")
            print(f"  Chunk idx  : {ch['chunk_index']}")
            preview = ch["text"][:200].replace("\n", " ")
            print(f"  Texte      : {preview}…")

    print()
    print("Test terminé.")


if __name__ == "__main__":
    asyncio.run(main())

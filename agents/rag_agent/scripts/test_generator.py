"""Script de test manuel du pipeline retrieve → generate.

Usage:
    cd agents/rag_agent
    python scripts/test_generator.py

Prérequis :
  - Qdrant tourne sur localhost:6333, collection afriquia_docs ingérée
  - Ollama tourne sur localhost:11434 avec le modèle qwen3:8b chargé
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.retriever import Retriever
from app.services.generator import Generator

QUERIES = [
    "Quelle est la norme EN590 ?",
    "Comment commander une bouteille de gaz ?",
]


async def main() -> None:
    retriever = Retriever(top_k=4, score_threshold=0.35)
    generator = Generator()

    for query in QUERIES:
        print()
        print("=" * 65)
        print(f"QUERY : {query}")
        print("=" * 65)

        # 1. Retrieve
        chunks = await retriever.retrieve(query)
        print(f"Chunks retenus : {len(chunks)}")
        for ch in chunks:
            print(f"  • [{ch['score']:.3f}] {ch['source']} / chunk {ch['chunk_index']}")

        # 2. Generate
        result = await generator.generate(query, chunks)
        print()
        print(f"Confidence : {result['confidence']}")
        print(f"Sources    : {result['sources']}")
        print(f"Réponse    :\n{result['answer']}")

    print()
    print("Test terminé.")


if __name__ == "__main__":
    asyncio.run(main())

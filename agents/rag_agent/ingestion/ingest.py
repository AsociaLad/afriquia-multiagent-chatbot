"""Ingestion pipeline — loads TXT documents, chunks, embeds, upserts into Qdrant.

Usage:
    cd agents/rag_agent
    python -m ingestion.ingest
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from ingestion.chunker import chunk
from ingestion.preprocessor import clean

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DOCUMENTS_PATH = Path(__file__).resolve().parents[3] / "data" / "documents"
COLLECTION_NAME = "afriquia_docs"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE = 384  # output dim of MiniLM-L12-v2

# ---------------------------------------------------------------------------
# Doc-type inference from filename
# ---------------------------------------------------------------------------

_DOC_TYPE_MAP = {
    "fiche":      "fiche_produit",
    "norme":      "norme",
    "procedure":  "procedure",
    "faq":        "faq",
    "securite":   "securite",
}


def _infer_doc_type(filename: str) -> str:
    name = filename.lower()
    for key, dtype in _DOC_TYPE_MAP.items():
        if key in name:
            return dtype
    return "document"


def _infer_title(filename: str) -> str:
    return Path(filename).stem.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------

def _ensure_collection(client: QdrantClient) -> None:
    """Create the Qdrant collection if it does not exist."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        logger.info(f"Collection '{COLLECTION_NAME}' already exists — skipping creation")
        return
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    logger.info(f"Collection '{COLLECTION_NAME}' created (cosine, {VECTOR_SIZE}d)")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_ingestion() -> None:
    logger.info("=== Afriquia RAG Ingestion ===")
    logger.info(f"Documents path : {DOCUMENTS_PATH}")
    logger.info(f"Qdrant         : {QDRANT_HOST}:{QDRANT_PORT}")
    logger.info(f"Embed model    : {EMBED_MODEL}")

    # --- Load model ---
    logger.info("Loading embedding model…")
    model = SentenceTransformer(EMBED_MODEL)
    logger.info("Embedding model loaded.")

    # --- Connect to Qdrant ---
    logger.info("Connecting to Qdrant…")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    _ensure_collection(client)

    # --- Read TXT files ---
    txt_files = sorted(DOCUMENTS_PATH.glob("*.txt"))
    if not txt_files:
        logger.error(f"No .txt files found in {DOCUMENTS_PATH}")
        sys.exit(1)
    logger.info(f"Found {len(txt_files)} document(s): {[f.name for f in txt_files]}")

    total_chunks = 0
    points: list[PointStruct] = []

    for filepath in txt_files:
        logger.info(f"── Processing: {filepath.name}")

        # 1. Read
        raw_text = filepath.read_text(encoding="utf-8")
        logger.debug(f"   Read {len(raw_text)} chars")

        # 2. Preprocess
        cleaned = clean(raw_text)
        logger.debug(f"   After clean: {len(cleaned)} chars")

        # 3. Chunk
        chunks = chunk(cleaned, source=filepath.name)
        logger.info(f"   Chunked → {len(chunks)} chunk(s)")

        # 4. Embed + build points
        doc_type = _infer_doc_type(filepath.name)
        title    = _infer_title(filepath.name)

        for ch in chunks:
            vector = model.encode(ch["text"], convert_to_numpy=True).tolist()
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "text":        ch["text"],
                        "source":      ch["source"],
                        "chunk_index": ch["chunk_index"],
                        "doc_type":    doc_type,
                        "title":       title,
                    },
                )
            )
            total_chunks += 1

        logger.info(f"   Embedded {len(chunks)} chunk(s) for '{filepath.name}'")

    # 5. Upsert all points in one batch
    logger.info(f"Upserting {total_chunks} chunks into '{COLLECTION_NAME}'…")
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    logger.info("Upsert complete.")

    # --- Summary ---
    logger.info("")
    logger.info("=== Ingestion Summary ===")
    logger.info(f"  Documents read  : {len(txt_files)}")
    logger.info(f"  Total chunks    : {total_chunks}")
    logger.info(f"  Collection      : {COLLECTION_NAME}")
    logger.info("=========================")


if __name__ == "__main__":
    run_ingestion()

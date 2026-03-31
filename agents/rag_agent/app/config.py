"""RAG Agent configuration via Pydantic BaseSettings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8020

    # --- Qdrant vector store ---
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "afriquia_docs"

    # --- Embeddings ---
    embed_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # --- Ollama (generation) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # --- Redis cache ---
    redis_url: str = "redis://localhost:6379"
    cache_ttl: int = 300  # seconds

    # --- Retrieval ---
    top_k: int = 3                  # number of chunks to retrieve
    min_score: float = 0.40         # minimum similarity score to keep a chunk

    # --- Documents ---
    documents_path: str = "../../data/documents"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

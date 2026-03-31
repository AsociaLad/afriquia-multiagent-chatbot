"""Configuration via Pydantic BaseSettings. All thresholds documented."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Infrastructure URLs ---
    redis_url: str = "redis://localhost:6379"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # --- Routing thresholds ---
    # Level 1: keyword/regex rules confidence
    rules_threshold: float = 0.70
    # Level 2: embedding similarity threshold
    # MVP calibration: 0.40 (MiniLM + short descriptions → low cosine).
    # TODO: revalider ce seuil après enrichissement des descriptions ou changement de modèle.
    embed_threshold: float = 0.40
    # Level 3: multi-intent detection threshold
    multi_intent_threshold: float = 0.60
    # Minimum confidence to accept a routing decision
    routing_confidence_min: float = 0.40

    # --- Fusion ---
    # Minimum confidence for final fused answer
    fusion_confidence_min: float = 0.35

    # --- Retry ---
    max_retries: int = 1

    # --- Agent call timeout (seconds) ---
    agent_timeout: float = 10.0

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

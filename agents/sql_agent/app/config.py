"""SQL Agent configuration via Pydantic BaseSettings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8015

    # --- PostgreSQL (read-only user) ---
    pg_host: str = "localhost"
    pg_port: int = 5433
    pg_database: str = "chatbot_db"
    pg_user: str = "sql_agent_reader"
    pg_password: str = "reader_afriquia_2025"

    # --- Query safety ---
    query_timeout: int = 5          # seconds
    max_rows: int = 50              # LIMIT auto-injected

    # --- Ollama (prepared, not yet used) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent chatbot platform for Afriquia/AlloGaz (Moroccan fuel distribution). A FastAPI+LangGraph orchestrator routes natural-language queries (French) to specialized agents: SQL (structured data), RAG (documentation), Location (geolocation, currently mocked).

## Architecture

```
Orchestrator (port 8000)  →  SQL Agent (port 8006)  →  PostgreSQL (port 5433)
         ↓                →  RAG Agent (port 8005)  →  Qdrant (port 6333) + Ollama
         ↓                →  Mock Agent (port 8010)     (Location placeholder)
    LangGraph pipeline
    6 nodes, 2 conditional edges
    HybridRouter: L1 rules → L2 embeddings → L3 LLM stub
```

- **Orchestrator** (`orchestrator/`): LangGraph StateGraph pipeline. Router in `app/router/` (3-level cascade). Agent configs in `agents_config.json`. State is a TypedDict with 17 fields flowing through nodes.
- **SQL Agent** (`agents/sql_agent/`): NL-to-SQL via Ollama (generate→clean→validate→execute) with keyword-mapping fallback. Uses asyncpg to PostgreSQL.
- **RAG Agent** (`agents/rag_agent/`): Retriever (Qdrant vector search) → Generator (Ollama qwen3:8b). Ingestion pipeline in `ingestion/`.
- **Mock Agent** (`agents/mock_agent/`): Serves `/location/query` with static responses.

## Commands

### Infrastructure
```bash
docker compose up -d                    # PostgreSQL(5433), Redis(6379), Ollama(11434), Qdrant(6333)
docker exec afriquia-ollama ollama pull qwen3:8b
docker exec -i afriquia-postgres psql -U afriquia -d chatbot_db < data/demo_db.sql
cd agents/rag_agent && python -m ingestion.ingest   # Index 42 chunks into Qdrant
```

### Run Services (4 terminals)
```bash
cd agents/sql_agent  && uvicorn app.main:app --port 8006 --reload
cd agents/rag_agent  && uvicorn app.main:app --port 8005 --reload
cd agents/mock_agent && uvicorn app.main:app --port 8010 --reload
cd orchestrator      && uvicorn app.main:app --port 8000 --reload
```

### Tests
```bash
cd orchestrator      && python -m pytest tests/ -v    # 11+ tests
cd agents/sql_agent  && python -m pytest tests/ -v    # 48 tests
cd agents/rag_agent  && python -m pytest tests/ -v    # 10 tests
# Single test:
cd agents/sql_agent  && python -m pytest tests/test_sql_cleaner.py::test_clean_think_block -v
```

### Manual Testing
```bash
# SQL Agent standalone
cd agents/sql_agent && python -m scripts.test_generator          # Unit: Ollama only
cd agents/sql_agent && python -m scripts.test_generator --http   # HTTP: full agent
# Redis cache flush
docker exec afriquia-redis redis-cli FLUSHDB
```

## Key Patterns

- **Async everywhere**: pytest uses `asyncio_mode = "auto"` in `pyproject.toml`. Fixtures use `@pytest_asyncio.fixture`.
- **Monkeypatching imports**: `main.py` uses `from app.services.sql_generator import generate_sql` (direct import). To mock in tests, patch `app.main.generate_sql`, NOT `app.services.sql_generator.generate_sql`.
- **Module-level imports for DB**: `from app.services import database` then `database.execute_query()` — this allows monkeypatching via the module.
- **Config**: Each service uses Pydantic `BaseSettings` loading from `.env`.
- **Logging**: All code uses `loguru.logger`.
- **Response contract**: All agents return `{answer, confidence, agent, sources, data, metadata}`.

## Important Gotchas

- **PostgreSQL port is 5433** (not 5432) — avoids conflict with local Windows PostgreSQL installation.
- **qwen3:8b thinking mode**: This model uses internal `<think>` reasoning that consumes `num_predict` tokens. The `response` field may be empty if `num_predict` is too low — check the `thinking` field as fallback. Currently set to 1024.
- **L1 routing threshold is 0.70**: Rules must score >= 0.70 to take effect. Multi-intent (multiple agents >= 0.50) returns `min()` of scores — can fall below threshold.
- **City names in queries**: "Casablanca" alone used to trigger Location routing. Now city names only trigger Location when combined with "station"/"proche". For data queries ("clients à Casablanca"), SQL rules take precedence.
- **Agent timeout is 30s**: LLM-backed agents (NL-to-SQL, RAG generation) need 10-15s. Configured in `orchestrator/app/config.py`.
- **LLM fallback (L3)**: Currently a stub returning `([], 0.0)`. Router defaults to `["rag"], 0.30`.
- **Query Decomposer**: Stub — all agents receive the full query (no multi-intent splitting).
- **Fusion**: MVP — picks highest-confidence response (no LLM synthesis).

## Debugging Tips

- **Routing issues**: Check `orchestrator/app/router/intent_rules.py` for L1 patterns. Use test_router.py to verify. L2 embeddings depend on agent descriptions in `agents_config.json`.
- **SQL Agent returns empty**: Check Ollama logs (`docker logs afriquia-ollama`). Likely `num_predict` too low or model not loaded. Verify with `curl http://localhost:11434/api/tags`.
- **Agent unreachable from orchestrator**: Check port in `agents_config.json` matches the agent's uvicorn port. Look for `CONNECTION ERROR` in orchestrator logs.
- **SQL validation rejects valid query**: Check `sql_validator.py` ALLOWED_TABLES list and forbidden keywords. Rule 4b requires at least one business table in FROM clause.
- **Redis stale cache**: Flush with `docker exec afriquia-redis redis-cli FLUSHDB`. Cache TTL is 5 minutes.

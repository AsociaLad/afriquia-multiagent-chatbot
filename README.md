# Afriquia Multi-Agent Chatbot

PFE Afriquia / AlloGaz - Plateforme chatbot multi-agents.

## Architecture

- **Orchestrateur** : FastAPI + LangGraph avec routing hybride (rules, embeddings, LLM fallback)
- **Agents** : SQL Agent, RAG Agent, Location Agent (mock pour MVP)
- **Infrastructure** : PostgreSQL, Redis, Ollama

## Lancement rapide

```bash
# 1. Infrastructure
docker compose up -d

# 2. Mock agent (port 8010)
cd agents/mock_agent
pip install -r requirements.txt
uvicorn app.main:app --port 8010 --reload

# 3. Orchestrateur (port 8000)
cd orchestrator
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

## Tests

```bash
cd orchestrator
pytest tests/ -v
```

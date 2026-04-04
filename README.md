# Afriquia / AlloGaz — Plateforme Chatbot Multi-Agents

Plateforme de chatbot multi-agents pour Afriquia/AlloGaz (distribution de carburants et gaz au Maroc). Un orchestrateur central (FastAPI + LangGraph) recoit les questions en langage naturel (francais) et les route vers des agents specialises : **SQL** (donnees structurees), **RAG** (documentation technique), **Location** (geolocalisation, actuellement en mock).

Le coeur du systeme est un **pipeline adaptatif a 6 noeuds** qui s'ajuste selon la qualite des reponses : routing intelligent a 3 niveaux, appels paralleles, retry automatique, et clarification si necessaire.

Ce projet est un **MVP fonctionnel** developpe dans le cadre d'un PFE (Projet de Fin d'Etudes), concu des le depart pour evoluer vers un produit reel en production.

---

## Probleme metier et objectif

Afriquia/AlloGaz est un acteur majeur de la distribution de carburants et gaz au Maroc. Ses clients et equipes internes ont besoin d'acceder rapidement a des informations variees :

- **Donnees operationnelles** : prix des carburants, etat des commandes, reclamations, clients
- **Documentation technique** : normes (EN590), fiches produits, procedures, FAQ
- **Geolocalisation** : stations-service proches, itineraires

L'approche multi-agents est pertinente ici car chaque type de question necessite un traitement fondamentalement different (requete SQL vs recherche vectorielle vs appel API). L'orchestrateur central permet de router intelligemment sans que l'utilisateur ait besoin de savoir quel agent interroger.

---

## Etat actuel du projet

### Implemente et fonctionnel

- **Orchestrateur** : pipeline LangGraph complet (6 noeuds, 2 conditional edges), router hybride L1+L2, cache Redis, circuit breaker, appels paralleles async
- **SQL Agent** : pipeline NL-to-SQL complet (generation Ollama, nettoyage, validation, execution, retry intelligent, formatage hybride) + 6 mappings keyword en fallback
- **RAG Agent** : pipeline retrieval-generation complet (Qdrant + Ollama), 42 chunks indexes depuis 6 documents
- **Infrastructure** : Docker Compose (PostgreSQL, Redis, Ollama, Qdrant) operationnel
- **Tests** : 67+ tests automatises (orchestrateur, SQL Agent, RAG Agent)
- **Evaluation** : batterie de 20 questions SQL avec metriques

### Partiellement implemente

- **Router L3 (LLM fallback)** : stub — retourne `([], 0.0)`, le router se rabat sur le RAG par defaut
- **Query Decomposer** : stub — chaque agent recoit la question complete (pas de decomposition multi-intent)
- **Fusion multi-agents** : selection du meilleur score uniquement (pas de synthese LLM)

### Prevu / prochaines etapes

- **Location Agent reel** : actuellement mock (reponses statiques). Prevu : API de geocodage, donnees stations reelles
- **Frontend React** : pas d'interface utilisateur. Interaction via curl / API
- **Auth Gateway (Keycloak)** : pas d'authentification
- **Back-office Django** : pas d'administration
- **Support multilingue arabe** : non teste (le modele d'embeddings le supporte)

### Tableau recapitulatif

| Composant | Etat | Detail |
|-----------|------|--------|
| **Orchestrateur** | Fonctionnel | Pipeline LangGraph 6 noeuds, router L1+L2, cache Redis, circuit breaker |
| **SQL Agent** | Fonctionnel | NL-to-SQL complet + retry + formatage hybride + 6 keyword fallbacks |
| **RAG Agent** | Fonctionnel | Retrieval Qdrant (42 chunks) + generation Ollama qwen3:8b |
| **Location Agent** | Mock | Reponses statiques uniquement (Casablanca, Rabat) |
| **Frontend React** | Non commence | Pas d'interface — interaction via curl / API |
| **Back-office Django** | Non commence | Pas d'administration |
| **Auth Gateway (Keycloak)** | Non commence | Pas d'authentification — endpoints ouverts |

---

## Architecture

```
                       Utilisateur (curl / API)
                              |
                    ┌─────────┴─────────┐
                    │   Orchestrateur    │
                    │ FastAPI + LangGraph│
                    │    port 8000       │
                    └────┬────┬────┬────┘
                         │    │    │
              ┌──────────┘    │    └──────────┐
              │               │               │
        ┌─────┴─────┐  ┌─────┴─────┐  ┌──────┴──────┐
        │ SQL Agent  │  │ RAG Agent │  │  Location   │
        │ port 8006  │  │ port 8005 │  │  port 8010  │
        │ (NL-to-SQL)│  │(retrieval)│  │   (mock)    │
        └─────┬──────┘  └──┬────┬──┘  └─────────────┘
              │             │    │
         PostgreSQL      Qdrant  Ollama
         port 5433      port 6333  port 11434
                                 (qwen3:8b)
              │
            Redis
          port 6379
          (cache)
```

### Pipeline LangGraph (6 noeuds)

```
load_config
     │
 route_query ──[confiance < 0.40]──> clarification ──> FIN
     │
call_agents   (appels HTTP paralleles aux agents selectionnes)
     │
fuse_responses ──[confiance < 0.35 + agents restants]──> retry_router ──> route_query
     │
    FIN
```

Le pipeline est **adaptatif** : le chemin d'execution depend de la confiance mesuree a chaque etape.

---

## Agents et responsabilites

### Orchestrateur (port 8000)

**Role** : Recevoir les requetes, router vers le bon agent, fusionner les reponses.

**Endpoint** : `POST /query` — recoit `{"query": "..."}`, retourne la reponse complete.

**Router hybride a 3 niveaux** :

| Niveau | Methode | Latence | Seuil | Etat |
|--------|---------|---------|-------|------|
| L1 | Regles deterministes (regex/keywords) | < 1ms | >= 0.70 | Fonctionnel (20+ patterns) |
| L2 | Embeddings semantiques (MiniLM) | ~10ms | >= 0.40 | Fonctionnel |
| L3 | LLM fallback (Ollama) | ~1-2s | — | Stub (retourne vide) |

**Fonctionnalites** : cache Redis (TTL 5 min), circuit breaker (3 echecs → pause 60s), retry (max 1), clarification.

**Exemples de questions** :
- "Quel est le prix du gazoil ?" → route vers SQL Agent
- "Quelles sont les normes EN590 ?" → route vers RAG Agent
- "Station proche de Casablanca" → route vers Location Agent

---

### SQL Agent (port 8006)

**Role** : Repondre aux questions sur les donnees structurees (prix, commandes, clients, reclamations).

**Endpoint** : `POST /query`

**Pipeline NL-to-SQL** (strategie principale) :

```
Question → generate_sql (Ollama) → clean_sql → validate_sql → execute_query
                                                                    │
                                                          ┌─────────┴─────────┐
                                                         OK              Erreur SQL
                                                          │            corrigeable ?
                                                    format_answer     retry (1 max)
                                                          │               │
                                                       Reponse     clean → validate
                                                                   → execute → format
```

**Fallback** : 6 mappings keyword pre-ecrits (prix gazoil, prix essence, tous les prix, commandes en livraison, repartition commandes, reclamations ouvertes).

**Base de donnees** : 5 tables de demonstration — `produits` (6 lignes), `clients` (8), `commandes` (18), `livraisons` (10), `reclamations` (5).

**Securite** : utilisateur read-only, validation stricte (SELECT uniquement, tables autorisees, pas de sous-requetes), `statement_timeout`, auto-LIMIT 50.

**Exemples de questions** :
- "Quel est le prix du gazoil ?" → SELECT sur produits
- "Quels clients habitent a Casablanca ?" → SELECT avec WHERE
- "Combien de commandes par statut ?" → GROUP BY avec COUNT
- "Quel client a le plus depense ?" → JOIN + SUM + ORDER BY + LIMIT

---

### RAG Agent (port 8005)

**Role** : Repondre aux questions sur la documentation technique Afriquia.

**Endpoint** : `POST /query`

**Pipeline** : Question → embeddings MiniLM → recherche Qdrant (top-3, seuil 0.40) → generation Ollama qwen3:8b.

**Documents indexes** (42 chunks depuis 6 fichiers) :
- Fiche Gazoil 50 ppm, Fiche Essence Super
- Norme EN590 (diesel)
- Procedure de commande gaz
- Regles de securite et stockage
- FAQ Afriquia

**Exemples de questions** :
- "Quelles sont les normes EN590 pour le diesel ?"
- "Comment commander du gaz ?"
- "Quelles sont les regles de securite pour le stockage ?"

---

### Location Agent (port 8010 — mock)

**Role** : Localiser les stations-service proches.

**Etat actuel** : mock agent avec reponses statiques (Casablanca, Rabat).

**Endpoint** : `POST /location/query`

**Prevu** : API de geocodage reelle, donnees stations depuis `data/stations.json`.

---

## Stack technique

| Composant | Technologie | Role |
|-----------|-------------|------|
| Orchestration | FastAPI + LangGraph 0.2 | Pipeline adaptatif multi-agents |
| Agents | FastAPI 0.115 | Microservices HTTP independants |
| LLM | Ollama + qwen3:8b (local) | NL-to-SQL, generation RAG, formatage |
| Embeddings | sentence-transformers MiniLM-L12-v2 | Routing semantique + RAG retrieval (384 dims, multilingual) |
| Base vectorielle | Qdrant 1.11 | Stockage et recherche de documents |
| Base relationnelle | PostgreSQL 16 + asyncpg | Donnees structurees (5 tables) |
| Cache | Redis 7 | Cache des reponses (SHA256, TTL 5 min) |
| Configuration | Pydantic Settings + .env | Parametrage par service |
| Logs | Loguru | Logging structure dans tous les services |
| Tests | pytest + pytest-asyncio | 67+ tests unitaires et d'integration |
| Infrastructure | Docker Compose | 4 services containerises |

---

## Structure du projet

```
afriquia-multiagent-chatbot/
├── docker-compose.yml                # PostgreSQL 5433, Redis 6379, Ollama 11434, Qdrant 6333
├── .env / .env.example               # Variables d'environnement
├── CLAUDE.md                         # Guide pour Claude Code (commandes, patterns, gotchas)
│
├── orchestrator/                     # Orchestrateur (port 8000)
│   ├── app/
│   │   ├── main.py                   # POST /query, GET /health
│   │   ├── config.py                 # Seuils routing, timeout agents (30s)
│   │   ├── graph.py                  # Pipeline LangGraph (6 noeuds)
│   │   ├── state.py                  # OrchestratorState (17 champs)
│   │   ├── router/                   # HybridRouter (L1 regles, L2 embeddings, L3 stub)
│   │   ├── nodes/                    # load_config, router, parallel_calls, fusion, retry, clarification
│   │   └── services/                 # Redis cache, circuit breaker, decomposer
│   ├── agents_config.json            # Configuration des 3 agents (type, host, port, path)
│   └── tests/                        # 4 fichiers de tests
│
├── agents/
│   ├── sql_agent/                    # Agent SQL (port 8006)
│   │   ├── app/
│   │   │   ├── main.py               # Pipeline : NL-to-SQL → keyword fallback → unsupported
│   │   │   └── services/             # sql_generator, sql_cleaner, sql_validator, formatter, database
│   │   ├── scripts/
│   │   │   ├── eval_sql.py           # Batterie de 20 questions (5 categories)
│   │   │   └── test_generator.py     # Test manuel du generateur
│   │   └── tests/                    # 4 fichiers, 67+ tests
│   │
│   ├── rag_agent/                    # Agent RAG (port 8005)
│   │   ├── app/
│   │   │   └── services/             # retriever, generator, embedder, qdrant_client
│   │   ├── ingestion/                # ingest.py, chunker.py, preprocessor.py
│   │   └── tests/
│   │
│   └── mock_agent/                   # Agent Location mock (port 8010)
│       └── app/main.py               # Reponses statiques
│
├── data/
│   ├── demo_db.sql                   # Schema + donnees demo (5 tables, ~47 lignes)
│   ├── documents/                    # 6 fichiers texte pour le RAG
│   └── stations.json                 # Placeholder vide (prevu Location v2)
│
└── docs/
    └── guide.md                      # Guide de presentation PFE
```

---

## Guide de demarrage rapide

### Prerequis

- **Python 3.10+**
- **Docker Desktop** (avec Docker Compose)
- **Git**
- **~5 Go d'espace disque** (modele qwen3:8b + embeddings)
- **GPU optionnel** — Ollama fonctionne en CPU (plus lent, ~15-20s par requete LLM au lieu de ~5s)

### Etape 1 — Infrastructure Docker

```bash
cd afriquia-multiagent-chatbot
docker compose up -d
```

Cela demarre 4 services :

| Service | Port | Verification |
|---------|------|-------------|
| PostgreSQL | 5433 | `docker exec afriquia-postgres pg_isready -U afriquia` |
| Redis | 6379 | `docker exec afriquia-redis redis-cli ping` → `PONG` |
| Ollama | 11434 | `curl http://localhost:11434/api/tags` |
| Qdrant | 6333 | `curl http://localhost:6333/collections` |

> **Attention** : PostgreSQL est sur le port **5433** (pas 5432) pour eviter les conflits avec une installation locale.

### Etape 2 — Charger le modele LLM

```bash
docker exec afriquia-ollama ollama pull qwen3:8b
```

> Premiere execution : ~5 Go a telecharger. Les lancements suivants sont instantanes.

### Etape 3 — Initialiser la base PostgreSQL

```bash
docker exec -i afriquia-postgres psql -U afriquia -d chatbot_db < data/demo_db.sql
```

Cela cree 5 tables (produits, clients, commandes, livraisons, reclamations), insere les donnees de demonstration, et cree l'utilisateur read-only `sql_agent_reader`.

Verifier :
```bash
docker exec afriquia-postgres psql -U afriquia -d chatbot_db -c "SELECT COUNT(*) FROM produits;"
# count = 6
```

### Etape 4 — Indexer les documents RAG

```bash
cd agents/rag_agent
pip install -r requirements.txt
python -m ingestion.ingest
```

> Premiere execution : telecharge le modele d'embeddings (~120 Mo). Indexe 42 chunks dans Qdrant.

### Etape 5 — Lancer les 4 services (4 terminaux)

```bash
# Terminal 1 — SQL Agent
cd agents/sql_agent && pip install -r requirements.txt
uvicorn app.main:app --port 8006 --reload

# Terminal 2 — RAG Agent
cd agents/rag_agent
uvicorn app.main:app --port 8005 --reload

# Terminal 3 — Mock Agent (Location)
cd agents/mock_agent && pip install -r requirements.txt
uvicorn app.main:app --port 8010 --reload

# Terminal 4 — Orchestrateur
cd orchestrator && pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

### Etape 6 — Verifier que tout repond

```bash
curl http://localhost:8006/health   # SQL Agent    → {"status": "ok"}
curl http://localhost:8005/health   # RAG Agent    → {"status": "ok"}
curl http://localhost:8010/health   # Mock Agent   → {"status": "ok"}
curl http://localhost:8000/health   # Orchestrateur → {"status": "ok"}
```

### Windows / PowerShell — Demarrage rapide depuis VS Code

Ouvrir 4 terminaux dans VS Code (`Ctrl+Shift+``) et lancer :

```powershell
# Terminal 1 — SQL Agent
cd agents\sql_agent; pip install -r requirements.txt; uvicorn app.main:app --port 8006 --reload

# Terminal 2 — RAG Agent
cd agents\rag_agent; pip install -r requirements.txt; uvicorn app.main:app --port 8005 --reload

# Terminal 3 — Mock Agent
cd agents\mock_agent; pip install -r requirements.txt; uvicorn app.main:app --port 8010 --reload

# Terminal 4 — Orchestrateur
cd orchestrator; pip install -r requirements.txt; uvicorn app.main:app --port 8000 --reload
```

Verification rapide en PowerShell :

```powershell
Invoke-RestMethod http://localhost:8006/health
Invoke-RestMethod http://localhost:8005/health
Invoke-RestMethod http://localhost:8010/health
Invoke-RestMethod http://localhost:8000/health
```

Test d'une requete :

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/query `
  -ContentType "application/json" `
  -Body '{"query": "Quel est le prix du gazoil ?"}' | ConvertTo-Json -Depth 5
```

> **Astuce VS Code** : utiliser le bouton "Split Terminal" pour voir les 4 services cote a cote.

---

## Variables d'environnement

Le fichier `.env` (racine du projet) contient :

```env
POSTGRES_PASSWORD=afriquia_dev
POSTGRES_DB=chatbot_db
POSTGRES_USER=afriquia
REDIS_URL=redis://localhost:6379
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
```

Chaque service charge sa configuration via Pydantic `BaseSettings` avec `env_file=".env"`. Les valeurs par defaut sont suffisantes pour le developpement local.

Le SQL Agent utilise en plus un utilisateur read-only (`sql_agent_reader` / `reader_afriquia_2025`) cree par `demo_db.sql`.

---

## Exemples de requetes

Toutes les requetes passent par l'orchestrateur (port 8000) qui route automatiquement.

### SQL — Prix du gazoil

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quel est le prix du gazoil ?"}' | python -m json.tool
```

Reponse attendue : `"agents_used": ["sql"]`, prix depuis PostgreSQL.

### SQL — Question complexe

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quel client a le plus depense en commandes non annulees ?"}' | python -m json.tool
```

Reponse attendue : `"agents_used": ["sql"]`, resultat avec JOIN + aggregation.

### RAG — Documentation technique

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quelles sont les normes EN590 pour le diesel ?"}' | python -m json.tool
```

Reponse attendue : `"agents_used": ["rag"]`, reponse generee depuis les documents.

### Location — Station proche (mock)

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Station Afriquia proche de Casablanca"}' | python -m json.tool
```

Reponse attendue : `"agents_used": ["location"]`, reponse statique du mock.

### Cas limite — Hors perimetre

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quel est le code Wi-Fi de la station ?"}' | python -m json.tool
```

Reponse attendue : message indiquant que la question est hors perimetre.

### Agent SQL en direct (sans orchestrateur)

```bash
curl -s -X POST http://localhost:8006/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quels clients habitent a Casablanca ?"}' | python -m json.tool
```

---

## Tests

### Tests unitaires et d'integration

```bash
# Orchestrateur (11+ tests)
cd orchestrator && python -m pytest tests/ -v

# SQL Agent (67+ tests : agent, cleaner, validator, formatter)
cd agents/sql_agent && python -m pytest tests/ -v

# RAG Agent (10+ tests)
cd agents/rag_agent && python -m pytest tests/ -v
```

### Evaluation SQL (batterie de 20 questions)

Le script `eval_sql.py` lance 20 questions reparties en 5 categories contre le SQL Agent en HTTP :

```bash
# Le SQL Agent doit tourner sur le port 8006
cd agents/sql_agent
python -m scripts.eval_sql
```

**Categories** :
- **A** — Lecture simple (SELECT + WHERE, 1 table)
- **B** — Aggregation (COUNT, SUM, AVG, GROUP BY)
- **C** — Jointure (JOIN entre 2 tables)
- **D** — Complexe (aggregation + jointure + filtre)
- **E** — Cas limites (hors perimetre, 0 resultat)

Le script affiche un tableau par categorie avec strategy, confidence, rows, SQL genere et reponse. Le resume final donne les taux de nl_to_sql vs fallback vs unsupported.

### Resultats d'evaluation actuels

Derniere execution de `eval_sql.py` sur les 20 questions :

| Metrique | Valeur |
|----------|--------|
| Questions totales | 20 |
| NL-to-SQL reussies | 18/20 |
| Taux NL-to-SQL | **95%** |
| Fallback keyword | 0 |
| Unsupported (normal) | 1 (question hors perimetre, comportement attendu) |
| Timeout | 1 (C3 — jointure complexe, passe en test isole mais timeout en evaluation sequentielle) |

> **Note** : le cas C3 (jointure complexe) reussit systematiquement en test isole (`test_generator --http`). Le timeout survient uniquement lors de l'evaluation sequentielle des 20 questions, quand le modele est deja charge en memoire et traite les requetes en serie. Ce n'est pas un bug fonctionnel mais une contrainte de performance du LLM local.

---

## Seuils et parametres cles

| Parametre | Valeur | Fichier | Role |
|-----------|--------|---------|------|
| `rules_threshold` | 0.70 | orchestrator/app/config.py | Score L1 minimum pour router |
| `embed_threshold` | 0.40 | orchestrator/app/config.py | Score L2 minimum |
| `routing_confidence_min` | 0.40 | orchestrator/app/config.py | En dessous : clarification |
| `fusion_confidence_min` | 0.35 | orchestrator/app/config.py | En dessous : retry |
| `agent_timeout` | 30s | orchestrator/app/config.py | Timeout HTTP par agent |
| `max_retries` | 1 | orchestrator/app/config.py | Retry orchestrateur |
| `num_predict` | 2048 | agents/sql_agent/.../sql_generator.py | Budget tokens Ollama (NL-to-SQL) |
| `query_timeout` | 5s | agents/sql_agent/app/config.py | Timeout PostgreSQL |
| `max_rows` | 50 | agents/sql_agent/app/config.py | LIMIT auto |
| `cache_ttl` | 300s | orchestrator + rag_agent | TTL Redis |

---

## Limites actuelles

- **Latence LLM** : qwen3:8b en local prend 10-20s par requete en CPU. Un GPU reduit a ~3-5s. Le pipeline NL-to-SQL complet (generation + execution + formatage) peut atteindre 30s.
- **Thinking mode** : qwen3:8b utilise un raisonnement interne (`<think>`) qui consomme des tokens. Si la requete est complexe, le `response` peut etre vide — le pipeline gere ce cas mais la requete est alors perdue.
- **Location Agent** : entierement mock. Pas de donnees reelles ni d'API de geocodage.
- **Router L3** : stub. Les requetes ambigues qui passent L1 et L2 sont routees vers RAG par defaut.
- **Fusion** : selection du meilleur score. Pas de synthese intelligente quand plusieurs agents repondent.
- **Pas de frontend** : toute interaction se fait via curl ou outil HTTP.
- **Pas d'authentification** : les endpoints sont ouverts.
- **Donnees de demonstration** : 47 lignes dans PostgreSQL, 42 chunks dans Qdrant. Non representatif d'un volume production.
- **Monolingue** : teste en francais uniquement (le modele d'embeddings supporte l'arabe).

### Limite connue — Performance LLM local

Le modele qwen3:8b tourne en local via Ollama. En CPU (pas de GPU), chaque appel LLM prend **10-20 secondes**. Le pipeline NL-to-SQL complet (generation + nettoyage + validation + execution + formatage) peut atteindre **25-30 secondes** pour une requete complexe.

Les requetes avec jointures multiples (categorie C et D de l'evaluation) sont les plus couteuses. En particulier, **C3** (jointure + aggregation) passe systematiquement en test isole mais peut depasser le timeout de 30 secondes lors d'une evaluation sequentielle, car le modele est sollicite en continu sans pause entre les questions.

Avec un **GPU** (meme modeste), la latence tombe a **3-5 secondes** par appel LLM, et le timeout n'est plus un probleme.

---

## Roadmap

### Court terme — Stabilisation

- [ ] Optimiser la latence du pipeline NL-to-SQL (prompt plus court, modele plus leger)
- [ ] Implementer le Location Agent reel (API geocodage + donnees stations)
- [ ] Activer le L3 LLM fallback dans le router
- [ ] Implementer la fusion LLM pour les reponses multi-agents

### Moyen terme — Enrichissement

- [ ] Query Decomposer : decomposition LLM des questions multi-intent
- [ ] Frontend React avec interface de chat
- [ ] Auth Gateway (FastAPI + Keycloak) pour l'authentification JWT
- [ ] Back-office Django pour l'administration

### Long terme — Production

- [ ] Deploiement containerise complet (Docker Compose production ou Kubernetes)
- [ ] Monitoring et observabilite (metriques, alertes, tracing)
- [ ] Support multilingue arabe
- [ ] Tests de charge et optimisation des performances

---

## Reprendre le projet

Pour un developpeur qui decouvre le codebase :

**Lire en premier** :
1. Ce README
2. `CLAUDE.md` — contient les commandes, patterns de code, gotchas et astuces de debugging
3. `orchestrator/app/graph.py` — le pipeline LangGraph (point d'entree logique)
4. `orchestrator/app/router/intent_rules.py` — les regles de routing L1
5. `agents/sql_agent/app/main.py` — le pipeline SQL complet

**Points d'entree HTTP** :
- Orchestrateur : `orchestrator/app/main.py` → `POST /query`
- SQL Agent : `agents/sql_agent/app/main.py` → `POST /query`
- RAG Agent : `agents/rag_agent/app/main.py` → `POST /query`

**Configuration des agents** : `orchestrator/agents_config.json` (type, host, port, path, description).

**Tests** : chaque service a ses tests dans `tests/`. Lancer `python -m pytest tests/ -v` depuis le dossier du service.

---

## Contexte

Projet de Fin d'Etudes (PFE) — Conception et developpement d'une plateforme de chatbot multi-agents pour Afriquia/AlloGaz. L'objectif academique est de demontrer la faisabilite d'une architecture ou plusieurs agents specialises collaborent pour repondre a des questions en langage naturel, avec un pipeline adaptatif qui s'auto-ajuste selon la qualite des reponses.

---

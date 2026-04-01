# Afriquia / AlloGaz -- Plateforme Chatbot Multi-Agents

> Plateforme intelligente de chatbot multi-agents pour Afriquia/AlloGaz.
> Ce projet est concu comme un MVP fonctionnel destine a evoluer vers un produit reel en production.

---

## Contexte

### Contexte

Ce projet constitue le coeur technique d'un portant sur la conception et le developpement d'une plateforme de chatbot multi-agents. L'objectif academique est de demontrer la faisabilite d'une architecture ou plusieurs agents specialises collaborent pour repondre a des questions en langage naturel, avec un pipeline adaptatif qui s'auto-ajuste selon la qualite des reponses.

### Contexte produit

Afriquia/AlloGaz est un acteur majeur de la distribution de carburants et gaz au Maroc. La plateforme vise a permettre aux clients et equipes internes d'interroger les donnees, documents et services Afriquia en langage naturel (francais), via un chatbot intelligent capable de :

- consulter les **prix des carburants** et l'etat des **commandes** (donnees structurees)
- repondre a des questions sur la **documentation technique** (normes, procedures, FAQ)
- localiser les **stations-service** les plus proches (geolocalisation)

---

## Objectifs du projet

1. **Concevoir une architecture multi-agents** modulaire ou chaque agent est independant et specialise
2. **Implementer un pipeline adaptatif** (LangGraph) avec routing intelligent, retry et clarification
3. **Developper un router hybride a 3 niveaux** minimisant le recours au LLM (regles > embeddings > LLM)
4. **Realiser des agents fonctionnels** pour le SQL (donnees) et le RAG (documentation)
5. **Valider l'approche MVP** avec des donnees de demonstration realistes

---

## Architecture generale

```
                         Utilisateur
                             |
                     [ Orchestrateur ]
                     FastAPI + LangGraph
                      port 8000
                             |
           +-----------------+-----------------+
           |                 |                 |
     [ SQL Agent ]    [ RAG Agent ]    [ Location Agent ]
      port 8006        port 8005        port 8010 (mock)
           |                 |
      PostgreSQL          Qdrant
      (donnees)        (documents)
           |                 |
           +--------+--------+
                    |
                 Ollama
              (qwen3:8b)
```

### Pipeline LangGraph (6 noeuds)

```
load_config
     |
   router ----[confiance < 0.40]----> clarification --> FIN
     |
parallel_calls
     |
   fusion ----[confiance < 0.35 + agents restants]----> retry_router --> router
     |
    FIN
```

Le pipeline est **adaptatif** : le chemin d'execution depend de la qualite mesuree a chaque etape. Si le routage echoue, le systeme demande une clarification. Si la fusion donne une reponse de mauvaise qualite, il reessaie avec d'autres agents.

---

## Description des agents

### Orchestrateur (port 8000)

Coeur du systeme. Recoit les requetes utilisateur et orchestre le pipeline complet :

- **Router hybride a 3 niveaux** :
  - Niveau 1 -- Regles deterministes (< 1ms) : patterns regex/keywords par agent
  - Niveau 2 -- Embeddings semantiques (~10ms) : modele multilingual MiniLM, similarite cosinus
  - Niveau 3 -- LLM fallback : **stub actuel** (prevu pour v2)
- **Appels paralleles** aux agents selectionnes via HTTP (asyncio.gather)
- **Fusion** des reponses (strategie actuelle : meilleure confiance ; prevu v2 : synthese LLM)
- **Retry** automatique si la confiance est trop basse (max 1 retry)
- **Clarification** si aucun agent n'est identifie avec assez de confiance
- **Cache Redis** des reponses (SHA256, TTL 5 min)
- **Circuit breaker** par agent (3 echecs -> pause 60s)

### RAG Agent (port 8005)

Agent fonctionnel complet specialise dans la documentation technique Afriquia :

- **Retriever** : recherche vectorielle dans Qdrant (top-k=4, seuil=0.35)
- **Generator** : generation de reponse via Ollama qwen3:8b (temperature=0.1)
- **Anti-hallucination** : prompt systeme strict, reponse "information non disponible" si hors contexte
- **42 chunks indexes** a partir de 6 documents de demonstration (fiches carburant, normes, FAQ, procedures, securite)
- **Embeddings** : paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions, CPU, multilingual)

### SQL Agent (port 8006)

Agent fonctionnel MVP specialise dans les donnees structurees :

- **Strategie actuelle (MVP)** : 6 mappings keyword -> SQL pre-ecrit
  - Prix gazoil, prix essence, tous les prix
  - Commandes par statut, commandes avec livraisons
  - Reclamations ouvertes
- **Base PostgreSQL** : 5 tables de demonstration (produits, clients, commandes, livraisons, reclamations)
- **Securite** : utilisateur read-only `sql_agent_reader`, `statement_timeout`, auto-LIMIT
- **Prevu v2** : generation NL-to-SQL via Ollama (sql_generator.py, sql_validator.py)

### Location Agent (port 8010 -- mock)

Agent **non encore implemente**. Actuellement servi par le mock agent :

- Retourne des reponses statiques realistes (stations Casablanca, Rabat)
- Prevu v2 : appels API de geocodage, donnees stations reelles depuis `data/stations.json`

---

## Stack technique

| Composant | Technologie | Role |
|-----------|-------------|------|
| Orchestrateur | FastAPI + LangGraph | Pipeline adaptatif multi-agents |
| Agents | FastAPI | Microservices specialises |
| LLM | Ollama + qwen3:8b | Generation de reponses (RAG, fusion) |
| Embeddings | sentence-transformers MiniLM-L12-v2 | Routing semantique + RAG retrieval |
| Base vectorielle | Qdrant | Stockage et recherche de documents |
| Base relationnelle | PostgreSQL 16 | Donnees structurees (produits, commandes) |
| Cache | Redis 7 | Cache des reponses et configurations |
| Configuration | Pydantic Settings + .env | Parametrage centralise |
| Logs | Loguru | Logging structure |
| Tests | pytest + pytest-asyncio | Tests unitaires et d'integration |
| Infrastructure | Docker Compose | PostgreSQL, Redis, Ollama, Qdrant |

---

## Etat actuel du projet

### Fonctionnalites disponibles

- [x] Pipeline LangGraph complet a 6 noeuds avec conditional edges
- [x] Router hybride L1 (regles) + L2 (embeddings) fonctionnels et calibres
- [x] RAG Agent complet : ingestion, retrieval, generation avec anti-hallucination
- [x] SQL Agent MVP : 6 requetes pre-ecrites sur donnees de demonstration
- [x] Cache Redis des reponses avec invalidation
- [x] Circuit breaker par agent
- [x] Appels paralleles aux agents (asyncio.gather)
- [x] Retry automatique si confiance insuffisante
- [x] Clarification si routage echoue
- [x] Mock agent pour les tests d'integration
- [x] Suite de tests (orchestrateur + RAG + SQL)
- [x] Infrastructure Docker Compose (PostgreSQL, Redis, Ollama, Qdrant)

### Limitations actuelles / ce qui est encore MVP

- [ ] **L3 LLM fallback** : stub (retourne [], 0.0) -- le router se rabat sur le RAG par defaut
- [ ] **Query Decomposer** : stub (passthrough) -- chaque agent recoit la question complete
- [ ] **Fusion multi-agents** : selection du meilleur score -- pas encore de synthese LLM
- [ ] **SQL Agent** : 6 mappings keyword fixes -- pas encore de NL-to-SQL generatif
- [ ] **Location Agent** : entierement mocke -- pas de donnees ni d'API de geolocalisation reelles
- [ ] **data/stations.json** : fichier vide (placeholder)
- [ ] **Pas d'authentification** : pas de Keycloak/Auth Gateway (prevu dans l'architecture cible)
- [ ] **Pas de frontend** : pas d'interface React (prevu dans l'architecture cible)
- [ ] **Pas de back-office Django** : pas d'admin dashboard (prevu dans l'architecture cible)
- [ ] **Monolingue francais** : le support arabe n'est pas encore teste

---

## Structure du projet

```
afriquia-multiagent-chatbot/
|
|-- docker-compose.yml              # Infrastructure (PostgreSQL, Redis, Ollama, Qdrant)
|-- .env / .env.example             # Variables d'environnement
|
|-- orchestrator/                   # Orchestrateur principal
|   |-- app/
|   |   |-- main.py                 # FastAPI : POST /query, GET /health
|   |   |-- config.py               # Seuils et parametres (Pydantic Settings)
|   |   |-- graph.py                # Pipeline LangGraph (6 noeuds)
|   |   |-- state.py                # OrchestratorState (TypedDict, 17 champs)
|   |   |-- router/
|   |   |   |-- __init__.py         # HybridRouter (cascade L1 > L2 > L3)
|   |   |   |-- rules.py           # L1 : regles keyword/regex
|   |   |   |-- intent_rules.py    # Patterns par agent
|   |   |   |-- embeddings.py      # L2 : similarite cosinus
|   |   |   |-- llm_fallback.py    # L3 : stub (prevu v2)
|   |   |-- nodes/                  # Noeuds LangGraph
|   |   |-- services/               # Redis cache, circuit breaker, decomposer
|   |   |-- models/                 # Schemas Pydantic
|   |-- agents_config.json          # Configuration des agents (type, host, port, path)
|   |-- tests/
|   |-- requirements.txt
|
|-- agents/
|   |-- rag_agent/                  # Agent RAG fonctionnel
|   |   |-- app/                    # FastAPI : POST /query
|   |   |   |-- services/           # retriever, generator, embedder, ollama, qdrant
|   |   |-- ingestion/              # Pipeline d'ingestion (chunker, preprocessor, ingest)
|   |   |-- scripts/                # Scripts de test manuels
|   |   |-- tests/
|   |
|   |-- sql_agent/                  # Agent SQL (MVP keyword-match)
|   |   |-- app/                    # FastAPI : POST /query
|   |   |   |-- services/           # database.py (asyncpg pool)
|   |   |-- tests/
|   |
|   |-- mock_agent/                 # Agent mock (3 endpoints pour tests)
|       |-- app/main.py             # /sql/query, /rag/query, /location/query
|
|-- data/
|   |-- demo_db.sql                 # Schema + donnees de demonstration PostgreSQL
|   |-- documents/                  # 6 documents techniques (fiches, normes, FAQ)
|   |-- stations.json               # Placeholder (vide)
|
|-- docs/
    |-- guide.md                    # Guide de presentation pour l'encadrant
```

---

## Guide de demarrage local

### Prerequis

- **Python 3.10+**
- **Docker Desktop** (avec Docker Compose)
- **Git**
- **~4 Go d'espace disque** (modeles Ollama + embeddings)
- **GPU optionnel** (Ollama fonctionne aussi en CPU, plus lent)

### Etape 1 -- Infrastructure Docker

```bash
cd afriquia-multiagent-chatbot
docker compose up -d
```

Cela demarre :
- **PostgreSQL** sur le port `5433` (attention : pas 5432, pour eviter un conflit avec un PostgreSQL local)
- **Redis** sur le port `6379`
- **Ollama** sur le port `11434`
- **Qdrant** sur le port `6333`

Verifier :
```bash
docker compose ps
```

### Etape 2 -- Charger le modele Ollama

```bash
docker exec afriquia-ollama ollama pull qwen3:8b
```

> Premiere execution : ~5 Go a telecharger. Les lancements suivants sont instantanes.

### Etape 3 -- Initialiser la base PostgreSQL

```bash
docker exec -i afriquia-postgres psql -U afriquia -d chatbot_db < data/demo_db.sql
```

Cela cree les tables (produits, clients, commandes, livraisons, reclamations), insere les donnees de demonstration, et cree l'utilisateur read-only `sql_agent_reader`.

### Etape 4 -- Indexer les documents RAG

```bash
cd agents/rag_agent
pip install -r requirements.txt
python -m ingestion.ingest
```

> Premiere execution : telecharge le modele d'embeddings (~120 Mo). Indexe 42 chunks dans Qdrant.

### Etape 5 -- Lancer les services (4 terminaux)

**Terminal 1 -- SQL Agent (port 8006)**
```bash
cd agents/sql_agent
pip install -r requirements.txt
uvicorn app.main:app --port 8006 --reload
```

**Terminal 2 -- RAG Agent (port 8005)**
```bash
cd agents/rag_agent
uvicorn app.main:app --port 8005 --reload
```

**Terminal 3 -- Mock Agent / Location (port 8010)**
```bash
cd agents/mock_agent
pip install -r requirements.txt
uvicorn app.main:app --port 8010 --reload
```

**Terminal 4 -- Orchestrateur (port 8000)**
```bash
cd orchestrator
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

### Etape 6 -- Verifier

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

## Exemples de requetes

Toutes les requetes passent par l'orchestrateur (port 8000) qui route automatiquement vers le bon agent.

### Requete SQL -- Prix du gazoil

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quel est le prix du gazoil ?"}' | python -m json.tool
```

Reponse attendue : `"agents_used": ["sql"]`, prix reel depuis PostgreSQL (12.45 MAD/L).

### Requete SQL -- Reclamations ouvertes

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quelles sont les reclamations ouvertes ?"}' | python -m json.tool
```

Reponse attendue : `"agents_used": ["sql"]`, liste des reclamations avec noms de clients.

### Requete RAG -- Documentation technique

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Quelles sont les normes EN590 pour le diesel ?"}' | python -m json.tool
```

Reponse attendue : `"agents_used": ["rag"]`, reponse generee a partir des documents indexes.

### Requete Location -- Station proche

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Station Afriquia proche de Casablanca"}' | python -m json.tool
```

Reponse attendue : `"agents_used": ["location"]`, reponse du mock agent.

---

## Tests

```bash
# Tests orchestrateur (unitaires + integration)
cd orchestrator
pytest tests/ -v

# Tests RAG Agent
cd agents/rag_agent
pytest tests/ -v

# Tests SQL Agent
cd agents/sql_agent
pytest tests/ -v
```

---

## Seuils et parametres cles

| Parametre | Valeur | Role |
|-----------|--------|------|
| `rules_threshold` | 0.70 | Score minimum pour valider le routage L1 (regles) |
| `embed_threshold` | 0.40 | Score minimum pour valider le routage L2 (embeddings) |
| `routing_confidence_min` | 0.40 | En dessous : demander clarification |
| `fusion_confidence_min` | 0.35 | En dessous : retry avec d'autres agents |
| `max_retries` | 1 | Maximum 1 retry pour eviter les boucles |

---

## Roadmap / Prochaines etapes

### Court terme (MVP+)

- [ ] Implementer le **NL-to-SQL generatif** dans le SQL Agent (Ollama + schema BDD dans le prompt)
- [ ] Implementer le **Location Agent reel** (API de geocodage, donnees stations)
- [ ] Activer le **L3 LLM fallback** dans le router (Ollama pour les cas ambigus)
- [ ] Implementer la **fusion LLM** pour les reponses multi-agents

### Moyen terme (v2)

- [ ] **Query Decomposer** : decomposition LLM des questions multi-intent
- [ ] **Auth Gateway** (FastAPI + Keycloak) pour l'authentification JWT
- [ ] **Back-office Django** pour l'administration des chatbots et agents
- [ ] **Frontend React** avec interface de chat
- [ ] Support **multilingue arabe** (le modele d'embeddings le supporte deja)

### Long terme (production)

- [ ] Cache multi-niveaux avec TTL adaptatifs par type de donnee
- [ ] Monitoring et observabilite (metriques, alertes)
- [ ] Deploiement containerise complet (Docker Compose production ou Kubernetes)
- [ ] Tests de charge et optimisation des performances

---

## Note importante

Ce projet est un **MVP fonctionnel** qui demontre l'architecture et les mecanismes cles du systeme multi-agents. Il n'est pas un produit fini. Les donnees utilisees sont des donnees de demonstration, et plusieurs composants sont encore en version simplifiee (stubs) dans l'attente d'une implementation complete. L'architecture est concue des le depart pour permettre cette evolution progressive sans refactoring majeur.

---

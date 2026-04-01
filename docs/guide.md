# Guide de presentation -- Plateforme Afriquia/AlloGaz

> Derniere mise a jour : mars 2026.

---

## 1. Presentation du projet

Ce projet porte sur la conception et le developpement d'une **plateforme de chatbot multi-agents** pour Afriquia/AlloGaz, un acteur majeur de la distribution de carburants et de gaz au Maroc.

L'idee centrale est simple : au lieu d'un seul chatbot monolithique qui essaie de tout faire, on decompose le probleme en **agents specialises** (donnees, documentation, geolocalisation) coordonnes par un **orchestrateur intelligent** qui decide quel agent appeler, verifie la qualite de la reponse, et peut reessayer ou demander une clarification si necessaire.

Le projet est concu comme un **MVP evolutif** : les fondations architecturales sont posees, les mecanismes cles fonctionnent, et le systeme est pret a accueillir des implementations plus avancees sans restructuration majeure.

---

## 2. Problematique metier

Afriquia/AlloGaz gere un ecosysteme complexe de donnees et de services :

- **Donnees operationnelles** : prix des carburants, commandes, livraisons, reclamations clients
- **Documentation technique** : normes de qualite (EN590), fiches produits, procedures, FAQ
- **Reseau physique** : stations-service reparties sur tout le Maroc

Aujourd'hui, acceder a ces informations necessite de naviguer entre plusieurs systemes, de connaitre les bases de donnees, ou de chercher manuellement dans la documentation. Un client qui veut savoir le prix du gazoil et la station la plus proche doit faire deux demarches distinctes.

**La plateforme resout ce probleme** en offrant un point d'entree unique en langage naturel : l'utilisateur pose sa question, et le systeme identifie automatiquement de quoi il s'agit, consulte les bonnes sources, et retourne une reponse unifiee.

---

## 3. Vision fonctionnelle

L'architecture cible complete (decrite dans le document de specification) comprend :

| Composant | Role | Etat actuel |
|-----------|------|-------------|
| Frontend React | Interface de chat utilisateur | Non commence |
| Auth Gateway (Keycloak) | Authentification SSO / JWT | Non commence |
| Admin Dashboard (Django) | Back-office d'administration | Non commence |
| **Orchestrateur (LangGraph)** | **Pipeline adaptatif multi-agents** | **Fonctionnel** |
| **RAG Agent** | **Documentation technique** | **Fonctionnel** |
| **SQL Agent** | **Donnees structurees** | **MVP fonctionnel** |
| Location Agent | Geolocalisation des stations | Mock (simule) |
| PostgreSQL | Base de donnees relationnelle | Fonctionnel |
| Redis | Cache des reponses | Fonctionnel |
| Qdrant | Base de donnees vectorielle | Fonctionnel |
| Ollama (qwen3:8b) | LLM local | Fonctionnel |

**Le perimetre du Projet se concentre sur le coeur du systeme** : l'orchestrateur et les agents. Les composants peripheriques (frontend, authentification, administration) sont prevus dans l'architecture cible mais ne font pas partie du livrable MVP actuel.

---

## 4. Etat d'avancement reel

### Ce qui est implemente et fonctionnel

**Orchestrateur (contribution principale)**
- Pipeline LangGraph complet a 6 noeuds avec transitions conditionnelles
- Router hybride a 3 niveaux : regles deterministes (< 1ms) puis embeddings semantiques (~10ms) puis fallback
- Appels paralleles aux agents via HTTP
- Mecanisme de retry automatique si la qualite de reponse est insuffisante
- Mecanisme de clarification si la question est trop ambigue
- Cache Redis avec cle SHA256 pour eviter les recalculs
- Circuit breaker par agent (protection contre les pannes en cascade)

**RAG Agent (agent complet)**
- Pipeline retrieval-augmented generation fonctionnel de bout en bout
- 6 documents techniques realistes indexes (fiches carburant, normes EN590, FAQ, procedures, securite)
- 42 chunks vectoriels dans Qdrant
- Generation de reponse via Ollama avec prompt anti-hallucination
- Reponse de repli explicite quand l'information n'est pas dans les documents

**SQL Agent (MVP fonctionnel)**
- 6 requetes SQL pre-ecrites couvrant les cas d'usage principaux :
  prix des carburants, repartition des commandes, reclamations ouvertes
- Base PostgreSQL avec 5 tables et donnees de demonstration realistes (6 produits, 8 clients, 18 commandes, 10 livraisons, 5 reclamations)
- Connexion securisee en lecture seule avec timeout et limite de lignes

**Infrastructure**
- Docker Compose operationnel (PostgreSQL, Redis, Ollama, Qdrant)
- Suite de tests automatises pour chaque composant
- Configuration centralisee via variables d'environnement

### Ce qui est encore simplifie (stubs)

| Composant | Etat actuel | Comportement |
|-----------|-------------|--------------|
| Router L3 (LLM fallback) | Stub | Retourne un resultat vide ; le router se rabat sur l'agent RAG par defaut |
| Query Decomposer | Stub | Chaque agent recoit la question complete (pas de decomposition multi-intent) |
| Fusion multi-agents | MVP | Selection de la meilleure reponse par score de confiance (pas de synthese LLM) |
| SQL NL-to-SQL | MVP | 6 mappings keyword->SQL fixes (pas de generation SQL dynamique) |
| Location Agent | Mock | Reponses statiques pre-ecrites |

**Ces stubs ne sont pas des oublis** : ils sont le resultat d'une strategie de developpement MVP deliberee. Chacun a une interface definie et un contrat clair, ce qui permet de les remplacer par une implementation reelle sans modifier le reste du systeme.

---

## 5. Ce qui est demonstrable aujourd'hui

Le systeme peut etre lance localement et demontre les scenarios suivants en temps reel :

1. **Requete SQL** : "Quel est le prix du gazoil ?" --> le router identifie "prix" + "gazoil", appelle le SQL Agent, qui execute une vraie requete PostgreSQL et retourne "Gazoil 50 ppm a 12.45 MAD/L"

2. **Requete RAG** : "Quelles sont les normes EN590 ?" --> le router identifie "norme" + "EN590", appelle le RAG Agent, qui cherche dans Qdrant, extrait les chunks pertinents, et genere une reponse a partir de la documentation technique via Ollama

3. **Requete Location** : "Station proche de Casablanca" --> le router identifie "station" + "Casablanca", appelle le mock Location Agent qui retourne une reponse simulee

4. **Requete ambigue** : "Bonjour, comment ca va ?" --> aucun agent n'est identifie avec assez de confiance, le systeme demande une clarification

5. **Cache** : relancer la meme requete --> reponse instantanee depuis le cache Redis

6. **Resilience** : arreter un agent --> le circuit breaker evite les appels inutiles, le systeme retourne une reponse degradee plutot que de planter

---

## 6. Scenario de demonstration conseille

Pour une demonstration devant un jury ou un encadrant, voici l'ordre suggere :

### Preparation (5 min avant)

Lancer les 4 services (SQL Agent, RAG Agent, mock Agent, Orchestrateur) + verifier que Docker tourne.

### Demonstration (15 min)

**1. Montrer le health check (30s)**
```
curl http://localhost:8000/health --> {"status": "ok"}
```
Cela prouve que l'orchestrateur est operationnel et que le pipeline LangGraph est compile.

**2. Requete SQL simple (2 min)**
```
"Quel est le prix du gazoil ?"
```
Montrer dans la reponse : `agents_used: ["sql"]`, le prix reel, la confiance elevee. Expliquer que le router a identifie les mots-cles "prix" et "gazoil" en < 1ms (L1).

**3. Requete RAG (3 min)**
```
"Quelles sont les normes EN590 pour le diesel ?"
```
Montrer : `agents_used: ["rag"]`, la reponse generee, les sources. Expliquer le pipeline retrieval (Qdrant) -> generation (Ollama).

**4. Requete Location (1 min)**
```
"Station Afriquia proche de Casablanca"
```
Montrer le routage correct. Preciser honnêtement que c'est un mock pour l'instant.

**5. Requete ambigue (2 min)**
```
"Bonjour, comment ca va ?"
```
Montrer la clarification. Expliquer le mecanisme : aucun agent > seuil 0.40 -> clarification.

**6. Effet du cache (1 min)**
Relancer la requete "prix du gazoil". Montrer `from_cache: true` et la latence reduite.

**7. Montrer les logs (2 min)**
Dans le terminal de l'orchestrateur, montrer les logs qui tracent le parcours :
- Quel niveau du router a matche (L1, L2)
- Quel agent a ete appele
- Le temps de reponse

**8. Montrer l'architecture dans le code (3 min)**
Ouvrir `graph.py` et montrer le StateGraph : c'est la structure executable du pipeline, pas un schema PowerPoint.

---

## 7. Fonctionnement multi-agents explique simplement

Quand un utilisateur pose une question, voici ce qui se passe :

```
Question : "Quel est le prix du gazoil ?"
            |
            v
   [1] Le systeme charge la configuration
       (quels agents sont disponibles ?)
            |
            v
   [2] Le router analyse la question
       Niveau 1 : "prix" + "gazoil" correspondent aux regles SQL
       --> Score 0.80, agent selectionne : SQL
            |
            v
   [3] L'orchestrateur appelle le SQL Agent via HTTP
       Le SQL Agent execute la requete dans PostgreSQL
       et retourne : "Gazoil 50 ppm a 12.45 MAD/L" (confiance 0.88)
            |
            v
   [4] La fusion verifie la qualite
       Confiance 0.88 > seuil 0.35 --> reponse acceptee
            |
            v
   [5] Le cache stocke la reponse pour les prochaines fois
            |
            v
   Reponse retournee a l'utilisateur
```

Le systeme est **adaptatif** : si l'etape 2 ne trouve pas d'agent (score trop bas), il demande une clarification. Si l'etape 4 donne une mauvaise confiance, il reessaie avec un autre agent. Ce n'est pas un pipeline fixe mais un graphe de decisions.

---

## 8. Choix techniques et justifications

### Pourquoi LangGraph pour l'orchestrateur ?

LangGraph permet de definir un **graphe d'execution avec des transitions conditionnelles**. Contrairement a un simple enchainement sequentiel, le pipeline peut prendre des chemins differents selon la qualite des resultats intermediaires (clarification, retry). C'est exactement le comportement adaptatif recherche.

### Pourquoi un router hybride a 3 niveaux ?

Le LLM est puissant mais lent (~400ms) et couteux en ressources. En placant des regles deterministes (< 1ms) et des embeddings (~10ms) en amont, on traite la majorite des requetes sans appeler le LLM. Le LLM n'intervient qu'en dernier recours pour les cas ambigus. C'est un compromis performance/intelligence.

### Pourquoi FastAPI pour tous les services ?

Chaque agent est un microservice HTTP independant. FastAPI offre : asyncio natif (appels paralleles), validation automatique (Pydantic), documentation OpenAPI generee, et un ecosysteme Python riche pour le NLP/ML.

### Pourquoi Ollama + qwen3:8b ?

Ollama permet d'executer un LLM **localement**, sans dependance a une API cloud (pas de couts, pas de latence reseau, pas de probleme de confidentialite des donnees). Le modele qwen3:8b est multilingual (francais/arabe), tourne sur GPU grand public, et offre un bon rapport qualite/taille.

### Pourquoi sentence-transformers MiniLM-L12-v2 ?

Modele d'embeddings **multilingual** (50+ langues dont le francais et l'arabe), **leger** (120 Mo, 384 dimensions), et performant sur CPU. Utilise a deux endroits : le router L2 (similarite entre question et descriptions d'agents) et le RAG Agent (recherche de documents).

### Pourquoi Qdrant pour le RAG ?

Base de donnees vectorielle optimisee pour la recherche par similarite cosinus. API HTTP simple, performante, et deployable en Docker sans configuration complexe.

### Pourquoi une approche MVP progressive ?

Plutot que d'essayer d'implementer tout le systeme d'un coup, on construit d'abord un squelette fonctionnel avec des stubs, puis on remplace chaque stub par une implementation reelle une fois que l'integration est validee. Cette approche reduit les risques et permet de demontrer la valeur du systeme a chaque etape.

---

## 9. Ce qui reste a faire

### Pour une version plus avancee

| Tache | Complexite | Impact |
|-------|-----------|--------|
| NL-to-SQL generatif (Ollama + schema BDD) | Moyenne | Le SQL Agent pourra repondre a n'importe quelle question sur les donnees |
| Location Agent reel (API geocodage) | Moyenne | Geolocalisation fonctionnelle des stations |
| L3 LLM fallback du router | Faible | Meilleur routage des questions ambigues |
| Fusion LLM multi-agents | Faible | Synthese plus naturelle quand plusieurs agents repondent |
| Query Decomposer LLM | Moyenne | Gestion des questions multi-intent ("prix ET station proche") |

### Pour une mise en production

- Auth Gateway avec Keycloak (authentification SSO)
- Back-office Django pour l'administration
- Frontend React avec interface de chat
- Support multilingue arabe teste
- Monitoring, observabilite, tests de charge
- Deploiement containerise complet

---

## 10. Conclusion

Ce projet demontre la **faisabilite et la valeur d'une architecture multi-agents** pour le domaine metier d'Afriquia/AlloGaz. Le MVP actuel prouve que :

1. **Le routage intelligent fonctionne** : les questions sont correctement dirigees vers le bon agent specialise, sans appel systematique au LLM
2. **Les agents specialises repondent avec des donnees reelles** : le RAG Agent genere des reponses a partir de documents indexes, le SQL Agent execute des requetes sur une base PostgreSQL
3. **Le pipeline est adaptatif** : le systeme sait demander une clarification, reessayer, ou se degrader proprement en cas de panne
4. **L'architecture est extensible** : chaque stub peut etre remplace par une implementation reelle sans modifier le reste du systeme

Le projet n'est pas un prototype jetable. Il est concu des le depart avec une architecture de production (microservices, cache, circuit breaker, configuration externalisee) qui permettra une evolution vers un produit.

---

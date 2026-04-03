"""NL-to-SQL generator via Ollama (qwen3:8b).

Converts a natural-language question into a PostgreSQL SELECT query
using a system prompt with schema description and few-shot examples.
"""

from __future__ import annotations

import re

import httpx
from loguru import logger

from app.config import settings

# ---------------------------------------------------------------------------
# Database schema (compact, injected into the system prompt)
# ---------------------------------------------------------------------------

DB_SCHEMA = """
-- Table: produits (6 lignes)
-- Produits Afriquia : carburants et gaz
CREATE TABLE produits (
    id              SERIAL PRIMARY KEY,
    nom             VARCHAR(100) NOT NULL,       -- ex: 'Gazoil 50 ppm', 'Essence SP95', 'Butane 12 kg'
    categorie       VARCHAR(50)  NOT NULL,       -- 'carburant' | 'gaz'
    prix_unitaire   DECIMAL(10,2) NOT NULL,      -- prix en MAD
    unite           VARCHAR(20)  NOT NULL,       -- 'L' (litre) | 'bouteille'
    date_maj        DATE NOT NULL                -- dernière mise à jour du prix
);

-- Table: clients (8 lignes)
-- Clients particuliers et entreprises
CREATE TABLE clients (
    id              SERIAL PRIMARY KEY,
    nom             VARCHAR(100) NOT NULL,
    ville           VARCHAR(50)  NOT NULL,       -- ex: 'Casablanca', 'Rabat', 'Tanger'
    type_client     VARCHAR(20)  NOT NULL,       -- 'particulier' | 'entreprise'
    telephone       VARCHAR(20)
);

-- Table: commandes (18 lignes)
-- Commandes de produits par les clients
CREATE TABLE commandes (
    id              SERIAL PRIMARY KEY,
    client_id       INT NOT NULL REFERENCES clients(id),
    produit_id      INT NOT NULL REFERENCES produits(id),
    quantite        DECIMAL(10,2) NOT NULL,
    montant_total   DECIMAL(12,2) NOT NULL,      -- en MAD
    statut          VARCHAR(30) NOT NULL,         -- 'en_attente' | 'confirmee' | 'en_livraison' | 'livree' | 'annulee'
    date_commande   TIMESTAMP NOT NULL,
    date_livraison  TIMESTAMP                     -- NULL si pas encore livrée
);

-- Table: livraisons (10 lignes)
-- Suivi des livraisons associées aux commandes
CREATE TABLE livraisons (
    id              SERIAL PRIMARY KEY,
    commande_id     INT NOT NULL REFERENCES commandes(id),
    livreur         VARCHAR(100) NOT NULL,        -- nom du livreur
    statut          VARCHAR(30) NOT NULL,          -- 'en_cours' | 'livree' | 'echouee'
    date_depart     TIMESTAMP NOT NULL,
    date_arrivee    TIMESTAMP                      -- NULL si en cours
);

-- Table: reclamations (5 lignes)
-- Réclamations des clients sur leurs commandes
CREATE TABLE reclamations (
    id              SERIAL PRIMARY KEY,
    client_id       INT NOT NULL REFERENCES clients(id),
    commande_id     INT NOT NULL REFERENCES commandes(id),
    sujet           VARCHAR(200) NOT NULL,         -- description du problème
    statut          VARCHAR(30) NOT NULL,           -- 'ouverte' | 'en_cours' | 'resolue'
    date_creation   TIMESTAMP NOT NULL
);
""".strip()

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""Tu es un assistant SQL expert pour la base de données Afriquia/AlloGaz.

Ta mission : convertir une question en langage naturel en une requête PostgreSQL SELECT valide.

### Schéma de la base de données :

{DB_SCHEMA}

### Règles strictes :
1. Génère UNIQUEMENT une requête SELECT. Jamais de INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
2. Utilise UNIQUEMENT les tables et colonnes décrites ci-dessus.
3. Utilise ILIKE pour les recherches textuelles (insensible aux accents/casse).
4. Utilise des alias clairs pour les JOIN (ex: cl pour clients, c pour commandes).
5. Retourne UNIQUEMENT la requête SQL, sans explication, sans commentaire, sans markdown.
6. Si la question n'a aucun rapport avec les données disponibles, retourne UNIQUEMENT le texte : HORS_PERIMETRE
7. Limite les résultats à 50 lignes maximum avec LIMIT.

### Exemples :

Question : Quel est le prix du gazoil ?
SELECT nom, prix_unitaire, unite, date_maj FROM produits WHERE nom ILIKE '%gazoil%';

Question : Combien de commandes par statut ?
SELECT statut, COUNT(*) AS nombre FROM commandes GROUP BY statut ORDER BY nombre DESC;

Question : Quelles sont les réclamations ouvertes ?
SELECT r.id, cl.nom AS client, r.sujet, r.statut, r.date_creation FROM reclamations r JOIN clients cl ON cl.id = r.client_id WHERE r.statut IN ('ouverte', 'en_cours') ORDER BY r.date_creation DESC;

Question : Quel client a le plus dépensé ?
SELECT cl.nom, cl.ville, SUM(c.montant_total) AS total_depense FROM commandes c JOIN clients cl ON cl.id = c.client_id WHERE c.statut != 'annulee' GROUP BY cl.nom, cl.ville ORDER BY total_depense DESC LIMIT 1;

Question : Quelles commandes sont en livraison ?
SELECT c.id, cl.nom AS client, p.nom AS produit, c.quantite, c.montant_total, c.date_commande FROM commandes c JOIN clients cl ON cl.id = c.client_id JOIN produits p ON p.id = c.produit_id WHERE c.statut = 'en_livraison' ORDER BY c.date_commande DESC;

Question : Quelles commandes ont le statut livree ?
SELECT c.id, cl.nom AS client, p.nom AS produit, c.quantite, c.montant_total, c.date_commande FROM commandes c JOIN clients cl ON cl.id = c.client_id JOIN produits p ON p.id = c.produit_id WHERE c.statut = 'livree' ORDER BY c.date_commande DESC;

Question : Quel est le prix moyen des carburants ?
SELECT AVG(prix_unitaire) AS prix_moyen FROM produits WHERE categorie = 'carburant';

Question : Quelles livraisons sont en cours, avec le nom du livreur ?
SELECT l.id, l.livreur, l.statut, l.date_depart, c.id AS commande_id FROM livraisons l JOIN commandes c ON c.id = l.commande_id WHERE l.statut = 'en_cours' ORDER BY l.date_depart DESC;

Question : Quels clients habitent à Casablanca ?
SELECT nom, ville, type_client, telephone FROM clients WHERE ville ILIKE '%Casablanca%';

Question : Combien de clients par ville ?
SELECT ville, COUNT(*) AS nombre FROM clients GROUP BY ville ORDER BY nombre DESC;

Question : Quels produits de type gaz sont disponibles ?
SELECT nom, prix_unitaire, unite FROM produits WHERE categorie = 'gaz' ORDER BY nom;

Question : Quelle est la météo demain ?
HORS_PERIMETRE
"""

# ---------------------------------------------------------------------------
# Generator function
# ---------------------------------------------------------------------------


async def generate_sql(question: str) -> str:
    """Convert a natural-language question to a PostgreSQL SELECT query.

    Calls Ollama with qwen3:8b and the NL-to-SQL system prompt.
    Returns the raw LLM output (caller should clean + validate).

    Note: qwen3:8b uses an internal "thinking" mode that consumes tokens
    from the num_predict budget. We set num_predict=2048 to leave room
    for both thinking and the final SQL response. If the response field
    is empty but the thinking field contains usable SQL, we fall back to
    extracting from thinking.

    Raises:
        RuntimeError: if Ollama is unreachable or returns an error.
    """
    url = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": question,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 2048,
        },
    }

    logger.info(f"[sql_generator] Sending to Ollama: {question!r}")

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.error("[sql_generator] Ollama timeout (90s)")
        raise RuntimeError("Ollama timeout — le modèle met trop de temps à répondre.")
    except httpx.HTTPError as exc:
        logger.error(f"[sql_generator] Ollama HTTP error: {exc}")
        raise RuntimeError(f"Ollama error: {exc}")

    response_text = data.get("response", "").strip()
    thinking_text = data.get("thinking", "").strip()
    done_reason = data.get("done_reason", "unknown")

    logger.info(
        f"[sql_generator] Ollama reply — "
        f"response: {len(response_text)} chars, "
        f"thinking: {len(thinking_text)} chars, "
        f"done_reason: {done_reason}"
    )

    # Primary: use the response field
    if response_text:
        logger.info(f"[sql_generator] Using response field:\n{response_text}")
        return response_text

    # Fallback: if response is empty, try to extract SQL from thinking
    if thinking_text:
        logger.warning(
            "[sql_generator] Response field empty — "
            "attempting fallback extraction from thinking field"
        )
        logger.debug(f"[sql_generator] Thinking content:\n{thinking_text[:500]}")

        # Look for SQL in the thinking text (the model sometimes writes
        # the final query inside its reasoning).
        # Strict regex: require SELECT ... FROM ... ; to avoid capturing
        # random text that happens to contain "select" and a semicolon.
        select_match = re.search(
            r"(SELECT\s+\S+.+?\bFROM\b.+?;)",
            thinking_text,
            re.DOTALL | re.IGNORECASE,
        )
        if select_match:
            extracted = select_match.group(1).strip()
            # Extra guard: reject if it contains too many natural-language words
            # (a real SQL query won't have sentences with spaces between words
            # outside of string literals)
            if len(extracted) > 500:
                logger.warning(
                    f"[sql_generator] Extracted SQL too long "
                    f"({len(extracted)} chars) — likely garbage, ignoring"
                )
            else:
                logger.info(
                    f"[sql_generator] Extracted SQL from thinking (fallback): "
                    f"{extracted[:200]}"
                )
                return extracted

        logger.warning("[sql_generator] No valid SELECT..FROM found in thinking field")

    raise RuntimeError(
        f"Ollama returned empty response (done_reason={done_reason}). "
        f"Thinking had {len(thinking_text)} chars but no extractable SQL."
    )


# ---------------------------------------------------------------------------
# Retry prompt
# ---------------------------------------------------------------------------

_RETRY_SYSTEM_PROMPT = f"""Tu es un assistant SQL expert pour la base de données Afriquia/AlloGaz.

Ta mission : corriger une requête SQL qui a échoué lors de l'exécution PostgreSQL.

### Schéma de la base de données :

{DB_SCHEMA}

### Règles strictes :
1. Génère UNIQUEMENT une requête SELECT corrigée.
2. Utilise UNIQUEMENT les tables et colonnes décrites ci-dessus.
3. Corrige l'erreur indiquée tout en répondant à la question initiale.
4. Retourne UNIQUEMENT la requête SQL corrigée, sans explication.
"""


async def retry_generate_sql(
    question: str, previous_sql: str, pg_error: str
) -> str:
    """Re-generate SQL after a PostgreSQL execution error.

    Sends the original question, the failed SQL, and the error message
    to Ollama so it can produce a corrected query.

    Raises:
        RuntimeError: if Ollama is unreachable or returns an error.
    """
    # Truncate error message to keep prompt clean
    short_error = pg_error[:300].strip()

    prompt = (
        f"Question de l'utilisateur : {question}\n\n"
        f"Requête SQL précédente (échouée) :\n{previous_sql}\n\n"
        f"Erreur PostgreSQL :\n{short_error}\n\n"
        f"Génère une requête SQL SELECT corrigée."
    )

    url = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "system": _RETRY_SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 2048,
        },
    }

    logger.info(f"[sql_generator] Retry — sending correction request to Ollama")
    logger.debug(f"[sql_generator] Retry — error was: {short_error}")

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.error("[sql_generator] Retry — Ollama timeout (90s)")
        raise RuntimeError("Ollama timeout on retry.")
    except httpx.HTTPError as exc:
        logger.error(f"[sql_generator] Retry — Ollama HTTP error: {exc}")
        raise RuntimeError(f"Ollama error on retry: {exc}")

    response_text = data.get("response", "").strip()
    thinking_text = data.get("thinking", "").strip()

    if response_text:
        logger.info(f"[sql_generator] Retry — got response ({len(response_text)} chars)")
        return response_text

    # Fallback: extract from thinking (strict regex: SELECT...FROM...;)
    if thinking_text:
        select_match = re.search(
            r"(SELECT\s+\S+.+?\bFROM\b.+?;)",
            thinking_text, re.DOTALL | re.IGNORECASE,
        )
        if select_match:
            extracted = select_match.group(1).strip()
            if len(extracted) <= 500:
                logger.info(f"[sql_generator] Retry — extracted SQL from thinking")
                return extracted

    raise RuntimeError("Retry returned empty response.")

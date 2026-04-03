"""SQL Agent — FastAPI application.

Endpoint : POST /query
Pipeline : NL-to-SQL (Ollama) → fallback keyword mapping → unsupported.
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.models.schemas import SQLRequest, SQLResponse
from app.services import database
from app.services.sql_generator import generate_sql, retry_generate_sql
from app.services.sql_cleaner import clean_sql
from app.services.sql_validator import validate_sql
from app.services.formatter import format_answer


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------

# PostgreSQL error patterns that indicate a correctable SQL problem
_RETRYABLE_PATTERNS = [
    "syntax error",
    "column",
    "does not exist",
    "relation",
    "ambiguous",
    "invalid input syntax",
    "operator does not exist",
    "missing FROM-clause",
    "must appear in the GROUP BY",
]


def _is_retryable_error(error: Exception) -> bool:
    """Check if a DB execution error is a SQL mistake worth retrying.

    Returns True for syntax/column/table errors.
    Returns False for network/timeout/connection errors.
    """
    msg = str(error).lower()
    return any(pattern in msg for pattern in _RETRYABLE_PATTERNS)


# ---------------------------------------------------------------------------
# MVP: pattern matching → SQL query mapping (fallback)
# ---------------------------------------------------------------------------

_MVP_QUERIES: list[dict] = [
    {
        "keywords": ["prix", "gazoil"],
        "sql": "SELECT nom, prix_unitaire, unite, date_maj FROM produits WHERE nom ILIKE '%gazoil%';",
        "formatter": lambda rows: (
            f"Le {rows[0]['nom']} est à {rows[0]['prix_unitaire']} MAD/{rows[0]['unite']} "
            f"(mis à jour le {rows[0]['date_maj']})."
            if rows else "Aucun produit gazoil trouvé."
        ),
    },
    {
        "keywords": ["prix", "essence"],
        "sql": "SELECT nom, prix_unitaire, unite, date_maj FROM produits WHERE nom ILIKE '%essence%' OR nom ILIKE '%SP95%';",
        "formatter": lambda rows: (
            f"L'{rows[0]['nom']} est à {rows[0]['prix_unitaire']} MAD/{rows[0]['unite']} "
            f"(mis à jour le {rows[0]['date_maj']})."
            if rows else "Aucun produit essence trouvé."
        ),
    },
    {
        "keywords": ["prix"],
        "sql": "SELECT nom, prix_unitaire, unite FROM produits ORDER BY nom;",
        "formatter": lambda rows: (
            "Voici les prix actuels :\n"
            + "\n".join(f"- {r['nom']} : {r['prix_unitaire']} MAD/{r['unite']}" for r in rows)
            if rows else "Aucun produit trouvé."
        ),
    },
    {
        "keywords": ["commande", "livraison"],
        "sql": (
            "SELECT c.id, cl.nom AS client, p.nom AS produit, c.quantite, c.statut "
            "FROM commandes c "
            "JOIN clients cl ON cl.id = c.client_id "
            "JOIN produits p ON p.id = c.produit_id "
            "WHERE c.statut = 'en_livraison' "
            "ORDER BY c.date_commande DESC;"
        ),
        "formatter": lambda rows: (
            f"{len(rows)} commande(s) en livraison :\n"
            + "\n".join(
                f"- Commande #{r['id']} : {r['client']} — {r['quantite']} {r['produit']}"
                for r in rows
            )
            if rows else "Aucune commande en livraison."
        ),
    },
    {
        "keywords": ["combien", "commande"],
        "sql": "SELECT statut, COUNT(*) AS nb FROM commandes GROUP BY statut ORDER BY nb DESC;",
        "formatter": lambda rows: (
            "Répartition des commandes :\n"
            + "\n".join(f"- {r['statut']} : {r['nb']}" for r in rows)
            if rows else "Aucune commande trouvée."
        ),
    },
    {
        "keywords": ["clamation"],
        "sql": (
            "SELECT r.id, cl.nom AS client, r.sujet, r.statut "
            "FROM reclamations r "
            "JOIN clients cl ON cl.id = r.client_id "
            "WHERE r.statut IN ('ouverte','en_cours') "
            "ORDER BY r.date_creation DESC;"
        ),
        "formatter": lambda rows: (
            f"{len(rows)} réclamation(s) ouverte(s)/en cours :\n"
            + "\n".join(
                f"- #{r['id']} ({r['statut']}) {r['client']} : {r['sujet']}"
                for r in rows
            )
            if rows else "Aucune réclamation ouverte."
        ),
    },
]


def _match_query(user_query: str) -> dict | None:
    """Find the first MVP mapping whose keywords all appear in the query."""
    q = user_query.lower()
    for mapping in _MVP_QUERIES:
        if all(kw in q for kw in mapping["keywords"]):
            return mapping
    return None


# ---------------------------------------------------------------------------
# NL-to-SQL pipeline
# ---------------------------------------------------------------------------


async def _try_nl_to_sql(question: str) -> SQLResponse | None:
    """Attempt NL-to-SQL: generate → clean → validate → execute → format.

    Returns a SQLResponse on success, None on any failure (caller falls back).
    """
    # --- Step 1: Generate ---
    try:
        raw = await generate_sql(question)
        logger.info(f"[nl_to_sql] Generated raw SQL ({len(raw)} chars)")
    except Exception as exc:
        logger.warning(f"[nl_to_sql] Generation failed: {exc}")
        return None

    # --- Step 2: Clean ---
    sql = clean_sql(raw)
    if not sql:
        logger.warning("[nl_to_sql] Cleaning returned empty — no SELECT found")
        return None
    logger.info(f"[nl_to_sql] Cleaned SQL: {sql}")

    # --- Step 3: Validate ---
    is_valid, reason = validate_sql(sql)
    if not is_valid:
        logger.warning(f"[nl_to_sql] Validation failed: {reason}")
        return None
    logger.info("[nl_to_sql] Validation passed")

    # --- Step 4: Execute ---
    retry_used = False
    retry_success = False

    try:
        rows = await database.execute_query(sql)
        logger.info(f"[nl_to_sql] Query returned {len(rows)} row(s)")
    except Exception as exc:
        logger.warning(f"[nl_to_sql] First execution failed: {exc}")

        # Only retry on correctable SQL errors (not network/timeout)
        if not _is_retryable_error(exc):
            logger.error("[nl_to_sql] Error is not retryable — giving up")
            return None

        # --- Step 4b: Retry (1 attempt max) ---
        retry_used = True
        logger.info("[nl_to_sql] Retry started — asking LLM to correct SQL")

        try:
            retry_raw = await retry_generate_sql(question, sql, str(exc))
        except Exception as retry_exc:
            logger.warning(f"[nl_to_sql] Retry generation failed: {retry_exc}")
            return None

        retry_sql = clean_sql(retry_raw)
        if not retry_sql:
            logger.warning("[nl_to_sql] Retry cleaning returned empty")
            return None

        # Avoid retrying with the exact same SQL
        if retry_sql == sql:
            logger.warning("[nl_to_sql] Retry SQL identical to original — skipping")
            return None

        is_valid, reason = validate_sql(retry_sql)
        if not is_valid:
            logger.warning(f"[nl_to_sql] Retry validation failed: {reason}")
            return None

        try:
            rows = await database.execute_query(retry_sql)
            sql = retry_sql  # use corrected SQL from here on
            retry_success = True
            logger.info(
                f"[nl_to_sql] Retry succeeded — {len(rows)} row(s)"
            )
        except Exception as retry_exec_exc:
            logger.error(f"[nl_to_sql] Retry execution also failed: {retry_exec_exc}")
            return None

    # --- Step 5: Format ---
    answer = await format_answer(question, rows, sql)
    tables = _extract_tables(sql)

    # Confidence: slightly lower if retry was needed
    if rows:
        confidence = 0.72 if retry_used else 0.82
    else:
        confidence = 0.35 if retry_used else 0.40

    metadata = {"strategy": "nl_to_sql", "retry_used": retry_used}
    if retry_used:
        metadata["retry_success"] = retry_success

    return SQLResponse(
        answer=answer,
        confidence=confidence,
        sources=[f"table:{t}" for t in tables],
        data={"rows_returned": len(rows), "sql": sql},
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_tables(sql: str) -> list[str]:
    """Quick extraction of table names from FROM/JOIN clauses."""
    tables = re.findall(r'(?:FROM|JOIN)\s+(\w+)', sql, re.IGNORECASE)
    return sorted(set(tables))


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: warm the pool (non-fatal). Shutdown: close it."""
    try:
        await database.get_pool()
    except Exception as exc:
        logger.warning(
            f"Could not connect to PostgreSQL at startup: {exc}. "
            "Will retry on first query."
        )
    yield
    await database.close_pool()


app = FastAPI(title="Afriquia SQL Agent", version="0.2.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=SQLResponse)
async def query(req: SQLRequest) -> SQLResponse:
    logger.info(f"SQL Agent | query='{req.query}'")

    # --- Strategy 1: NL-to-SQL via Ollama ---
    nl_result = await _try_nl_to_sql(req.query)
    if nl_result is not None:
        logger.info("[query] Answered via NL-to-SQL")
        return nl_result

    # --- Strategy 2: Fallback keyword mapping ---
    mapping = _match_query(req.query)
    if mapping is not None:
        logger.info("[query] Falling back to keyword mapping")
        sql = mapping["sql"]
        try:
            rows = await database.execute_query(sql)
        except Exception as exc:
            logger.error(f"SQL execution error: {exc}")
            return SQLResponse(
                answer="Erreur lors de l'exécution de la requête.",
                confidence=0.0,
                metadata={"strategy": "mvp_keyword_match", "error": str(exc)},
            )

        try:
            answer = mapping["formatter"](rows)
        except Exception as exc:
            logger.error(f"Formatter error: {exc}")
            answer = f"Résultat brut : {rows}"

        return SQLResponse(
            answer=answer,
            confidence=0.88 if rows else 0.50,
            sources=[f"table:{t}" for t in _extract_tables(sql)],
            data={"rows_returned": len(rows), "sql": sql},
            metadata={"strategy": "mvp_keyword_match"},
        )

    # --- Strategy 3: Unsupported ---
    logger.info("[query] No strategy matched — unsupported")
    return SQLResponse(
        answer="Je n'ai pas pu répondre à cette question. "
               "Essayez une question sur les prix, commandes, clients ou réclamations.",
        confidence=0.0,
        metadata={"strategy": "unsupported"},
    )

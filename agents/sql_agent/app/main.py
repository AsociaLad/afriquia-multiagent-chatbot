"""SQL Agent — FastAPI application.

Endpoint : POST /query
MVP provisoire : quelques requêtes hardcoded sur des mots-clés.
Prochaine étape : NL-to-SQL via Ollama.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.models.schemas import SQLRequest, SQLResponse
from app.services import database


# ---------------------------------------------------------------------------
# MVP: pattern matching → SQL query mapping
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
        "keywords": ["commande"],
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

NOT_IMPLEMENTED_MSG = (
    "La génération NL-to-SQL n'est pas encore implémentée. "
    "Essayez une question sur les prix, commandes ou réclamations."
)


def _match_query(user_query: str) -> dict | None:
    """Find the first MVP mapping whose keywords all appear in the query."""
    q = user_query.lower()
    for mapping in _MVP_QUERIES:
        if all(kw in q for kw in mapping["keywords"]):
            return mapping
    return None


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


app = FastAPI(title="Afriquia SQL Agent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=SQLResponse)
async def query(req: SQLRequest) -> SQLResponse:
    logger.info(f"SQL Agent | query='{req.query}'")

    mapping = _match_query(req.query)

    # --- No mapping found: NL-to-SQL not yet implemented ---
    if mapping is None:
        logger.info("No keyword match — NL-to-SQL not yet implemented")
        return SQLResponse(
            answer=NOT_IMPLEMENTED_MSG,
            confidence=0.0,
            metadata={"status": "not_implemented"},
        )

    # --- Execute the mapped SQL ---
    sql = mapping["sql"]
    try:
        rows = await database.execute_query(sql)
    except Exception as exc:
        logger.error(f"SQL execution error: {exc}")
        return SQLResponse(
            answer="Erreur lors de l'exécution de la requête.",
            confidence=0.0,
            metadata={"error": "sql_execution_failed", "detail": str(exc)},
        )

    # --- Format the answer ---
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


def _extract_tables(sql: str) -> list[str]:
    """Quick extraction of table names from FROM/JOIN clauses."""
    import re
    tables = re.findall(r'(?:FROM|JOIN)\s+(\w+)', sql, re.IGNORECASE)
    return sorted(set(tables))

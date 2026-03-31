"""Mock agent — single FastAPI serving SQL, RAG, and Location endpoints.

Returns hard-coded realistic responses for MVP testing.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Afriquia Mock Agent", version="0.1.0")


class AgentRequest(BaseModel):
    query: str


class AgentReply(BaseModel):
    answer: str
    confidence: float
    sources: list[str] = []
    data: dict = {}
    metadata: dict = {}


# ---------------------------------------------------------------------------
# SQL Agent
# ---------------------------------------------------------------------------

@app.post("/sql/query", response_model=AgentReply)
async def sql_query(req: AgentRequest) -> AgentReply:
    q = req.query.lower()

    if "prix" in q and ("gasoil" in q or "gazoil" in q or "diesel" in q):
        return AgentReply(
            answer="Le gazoil AKWA est à 12.45 MAD/L (prix station, mise à jour aujourd'hui).",
            confidence=0.92,
            sources=["table:prix_carburants"],
        )
    if "commande" in q:
        return AgentReply(
            answer="Votre commande #1234 est en cours de livraison. Arrivée estimée : demain 10h.",
            confidence=0.88,
            sources=["table:commandes"],
        )
    if "facture" in q:
        return AgentReply(
            answer="Facture #F-2024-0567 : 15 000 MAD, statut payée.",
            confidence=0.85,
            sources=["table:factures"],
        )

    return AgentReply(
        answer="Donnée non trouvée dans la base.",
        confidence=0.30,
    )


# ---------------------------------------------------------------------------
# RAG Agent
# ---------------------------------------------------------------------------

@app.post("/rag/query", response_model=AgentReply)
async def rag_query(req: AgentRequest) -> AgentReply:
    q = req.query.lower()

    if "norme" in q or "en590" in q or "en 590" in q:
        return AgentReply(
            answer=(
                "La norme EN 590 définit les spécifications du carburant diesel "
                "en Europe. Elle fixe les limites de teneur en soufre (max 10 ppm), "
                "le point éclair (min 55°C) et l'indice de cétane (min 51)."
            ),
            confidence=0.88,
            sources=["doc:fiche_technique_diesel.pdf"],
        )
    if "faq" in q or "procédure" in q:
        return AgentReply(
            answer=(
                "Pour commander du carburant en gros, appelez le 0801 000 000 ou "
                "utilisez l'application AlloGaz. Minimum de commande : 1000 litres."
            ),
            confidence=0.85,
            sources=["doc:faq_allogaz.pdf"],
        )
    if "sécurité" in q:
        return AgentReply(
            answer=(
                "Les règles de sécurité en station incluent : interdiction de fumer, "
                "arrêt du moteur pendant le remplissage, pas de téléphone portable."
            ),
            confidence=0.82,
            sources=["doc:guide_securite.pdf"],
        )

    return AgentReply(
        answer="Document non trouvé dans la base documentaire.",
        confidence=0.25,
    )


# ---------------------------------------------------------------------------
# Location Agent
# ---------------------------------------------------------------------------

def _is_location_query(q: str) -> bool:
    """True if the query is about finding a fuel station (any phrasing)."""
    location_hints = ("station", "ravitailler", "carburant", "proche", "adresse", "itinéraire")
    return any(hint in q for hint in location_hints)


@app.post("/location/query", response_model=AgentReply)
async def location_query(req: AgentRequest) -> AgentReply:
    q = req.query.lower()

    if _is_location_query(q) and "casablanca" in q:
        return AgentReply(
            answer="Station Afriquia Bd Zerktouni, Casablanca — 1.2 km de votre position.",
            confidence=0.90,
            sources=["geo:stations_casablanca"],
            data={"lat": 33.5731, "lng": -7.5898, "distance_km": 1.2},
        )
    if _is_location_query(q) and "rabat" in q:
        return AgentReply(
            answer="Station Afriquia Av Mohammed V, Rabat — 0.8 km de votre position.",
            confidence=0.90,
            sources=["geo:stations_rabat"],
            data={"lat": 34.0209, "lng": -6.8416, "distance_km": 0.8},
        )
    if _is_location_query(q):
        return AgentReply(
            answer="Veuillez préciser la ville pour localiser la station la plus proche.",
            confidence=0.50,
        )

    return AgentReply(
        answer="Localisation non déterminée. Précisez votre demande.",
        confidence=0.20,
    )

"""Keyword and regex patterns for rule-based intent detection."""

import re

# Each entry: agent_type → list of (pattern, weight)
INTENT_PATTERNS: dict[str, list[tuple[re.Pattern, float]]] = {
    "sql": [
        (re.compile(r"\bprix\b", re.I), 0.8),
        (re.compile(r"\bcommande[s]?\b", re.I), 0.8),
        (re.compile(r"\blivraison[s]?\b", re.I), 0.7),
        (re.compile(r"\bfacture[s]?\b", re.I), 0.8),
        (re.compile(r"\bstock[s]?\b", re.I), 0.7),
        (re.compile(r"\bgasoil|gazoil|diesel|essence\b", re.I), 0.6),
        (re.compile(r"\br[ée]clamation[s]?\b", re.I), 0.8),
        (re.compile(r"\bclient[s]?\b", re.I), 0.6),
        (re.compile(r"\bcombien\b", re.I), 0.5),
        (re.compile(r"\bcoût\b", re.I), 0.6),
    ],
    "rag": [
        (re.compile(r"\bnorme[s]?\b", re.I), 0.8),
        (re.compile(r"\bEN\s?590\b", re.I), 0.9),
        (re.compile(r"\bFAQ\b", re.I), 0.8),
        (re.compile(r"\bprocédure[s]?\b", re.I), 0.8),
        (re.compile(r"\bdocument(ation)?\b", re.I), 0.7),
        (re.compile(r"\bfiche[s]?\b", re.I), 0.6),
        (re.compile(r"\bsécurité\b", re.I), 0.6),
        (re.compile(r"\bspéc(ification)?[s]?\b", re.I), 0.7),
    ],
    "location": [
        (re.compile(r"\bstation[s]?\b", re.I), 0.8),
        (re.compile(r"\bproche[s]?\b", re.I), 0.7),
        (re.compile(r"\badresse[s]?\b", re.I), 0.7),
        (re.compile(r"\bitinéraire[s]?\b", re.I), 0.8),
        (re.compile(r"\blocalisation\b", re.I), 0.8),
        (re.compile(r"\bkilomètre|km\b", re.I), 0.6),
        (re.compile(r"\bcasablanca|rabat|tanger|marrakech|fès|agadir\b", re.I), 0.5),
    ],
}

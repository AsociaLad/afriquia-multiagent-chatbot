"""Validate SQL queries for safety before execution.

MVP validation rules:
1. Must be a SELECT statement (no INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE)
2. Only allowed tables: produits, clients, commandes, livraisons, reclamations
3. No subqueries (no nested SELECT)
4. Reasonable length limit
"""

from __future__ import annotations

import re

from loguru import logger

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ALLOWED_TABLES = frozenset({
    "produits",
    "clients",
    "commandes",
    "livraisons",
    "reclamations",
})

MAX_SQL_LENGTH = 1000  # characters

# Dangerous keywords that must NOT appear
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"EXECUTE|EXEC|COPY|VACUUM|EXPLAIN|CALL)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate a SQL query for safe execution.

    Args:
        sql: The cleaned SQL string to validate.

    Returns:
        (is_valid, reason) — True + "ok" if valid,
        False + human-readable reason if rejected.
    """
    if not sql or not sql.strip():
        return False, "Requête vide."

    sql_stripped = sql.strip()

    # --- Rule 1: Must start with SELECT ---
    if not sql_stripped.upper().startswith("SELECT"):
        logger.warning(f"[sql_validator] Not a SELECT: {sql_stripped[:50]!r}")
        return False, "Seules les requêtes SELECT sont autorisées."

    # --- Rule 2: No forbidden keywords ---
    forbidden_match = FORBIDDEN_KEYWORDS.search(sql_stripped)
    if forbidden_match:
        keyword = forbidden_match.group(1).upper()
        logger.warning(f"[sql_validator] Forbidden keyword: {keyword}")
        return False, f"Mot-clé interdit détecté : {keyword}."

    # --- Rule 3: No subqueries (nested SELECT) ---
    # Count SELECT occurrences — more than 1 means subquery
    select_count = len(re.findall(r"\bSELECT\b", sql_stripped, re.IGNORECASE))
    if select_count > 1:
        logger.warning(f"[sql_validator] Subquery detected ({select_count} SELECTs)")
        return False, "Les sous-requêtes ne sont pas autorisées."

    # --- Rule 4: Only allowed tables ---
    # Extract table names from FROM and JOIN clauses
    # Pattern matches: FROM <table>, JOIN <table>
    table_pattern = re.compile(
        r"(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        re.IGNORECASE,
    )
    tables_found = table_pattern.findall(sql_stripped)

    for table in tables_found:
        table_lower = table.lower()
        if table_lower not in ALLOWED_TABLES:
            logger.warning(f"[sql_validator] Disallowed table: {table}")
            return False, f"Table non autorisée : {table}. Tables permises : {', '.join(sorted(ALLOWED_TABLES))}."

    # --- Rule 4b: Must reference at least one business table ---
    if not tables_found:
        logger.warning("[sql_validator] No business table referenced (SELECT without FROM)")
        return False, "La requête doit référencer au moins une table métier."

    # --- Rule 5: Length limit ---
    if len(sql_stripped) > MAX_SQL_LENGTH:
        logger.warning(f"[sql_validator] Too long: {len(sql_stripped)} chars")
        return False, f"Requête trop longue ({len(sql_stripped)} caractères, max {MAX_SQL_LENGTH})."

    # --- Rule 6: No comments (safety) ---
    if "--" in sql_stripped or "/*" in sql_stripped:
        logger.warning("[sql_validator] SQL comments detected")
        return False, "Les commentaires SQL ne sont pas autorisés."

    logger.info(f"[sql_validator] Valid query ({len(sql_stripped)} chars, tables: {tables_found})")
    return True, "ok"

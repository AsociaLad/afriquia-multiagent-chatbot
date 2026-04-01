"""Tests for sql_cleaner.py — extract clean SQL from raw LLM output."""

from app.services.sql_cleaner import clean_sql


# --- Markdown code fences ---

def test_clean_simple_fence():
    raw = "```sql\nSELECT * FROM produits;\n```"
    assert clean_sql(raw) == "SELECT * FROM produits;"


def test_clean_fence_no_language():
    raw = "```\nSELECT nom FROM clients;\n```"
    assert clean_sql(raw) == "SELECT nom FROM clients;"


def test_clean_fence_with_surrounding_text():
    raw = "Voici la requête :\n```sql\nSELECT prix_unitaire FROM produits WHERE nom ILIKE '%gazoil%';\n```\nCette requête retourne le prix."
    result = clean_sql(raw)
    assert result.startswith("SELECT")
    assert "produits" in result
    assert "gazoil" in result


# --- Inline backticks ---

def test_clean_inline_backticks():
    raw = "`SELECT nom FROM produits;`"
    assert clean_sql(raw) == "SELECT nom FROM produits;"


# --- Think blocks (qwen3) ---

def test_clean_think_block():
    raw = "<think>\nLet me think about this query...\nI need to find prices.\n</think>\nSELECT prix_unitaire FROM produits;"
    result = clean_sql(raw)
    assert result == "SELECT prix_unitaire FROM produits;"


# --- Text before/after SELECT ---

def test_clean_text_before_select():
    raw = "Bien sûr, voici la requête SQL :\nSELECT nom, prix_unitaire FROM produits;"
    result = clean_sql(raw)
    assert result.startswith("SELECT")
    assert "produits" in result


def test_clean_text_after_semicolon():
    raw = "SELECT statut, COUNT(*) FROM commandes GROUP BY statut;\n\nCette requête regroupe les commandes."
    result = clean_sql(raw)
    assert result.endswith(";")
    assert "regroupe" not in result


# --- Missing semicolon ---

def test_clean_adds_semicolon():
    raw = "SELECT nom FROM produits"
    assert clean_sql(raw) == "SELECT nom FROM produits;"


# --- Whitespace normalization ---

def test_clean_normalizes_whitespace():
    raw = "SELECT  nom,\n  prix_unitaire\nFROM   produits\nWHERE  categorie = 'carburant';"
    result = clean_sql(raw)
    assert "\n" not in result
    assert "  " not in result


# --- Edge cases ---

def test_clean_empty_input():
    assert clean_sql("") == ""


def test_clean_no_select():
    assert clean_sql("Je ne peux pas répondre à cette question.") == ""


def test_clean_pure_sql():
    """Already clean SQL should pass through."""
    raw = "SELECT r.id, cl.nom FROM reclamations r JOIN clients cl ON cl.id = r.client_id;"
    result = clean_sql(raw)
    assert result.startswith("SELECT")
    assert "reclamations" in result
    assert result.endswith(";")

"""Tests for sql_validator.py — safety validation of SQL queries."""

from app.services.sql_validator import validate_sql, ALLOWED_TABLES


# --- Valid queries ---

def test_valid_simple_select():
    ok, reason = validate_sql("SELECT nom, prix_unitaire FROM produits;")
    assert ok is True
    assert reason == "ok"


def test_valid_with_join():
    sql = (
        "SELECT r.id, cl.nom FROM reclamations r "
        "JOIN clients cl ON cl.id = r.client_id;"
    )
    ok, reason = validate_sql(sql)
    assert ok is True


def test_valid_with_where_and_group_by():
    sql = "SELECT statut, COUNT(*) AS nb FROM commandes GROUP BY statut ORDER BY nb DESC;"
    ok, reason = validate_sql(sql)
    assert ok is True


def test_valid_multi_join():
    sql = (
        "SELECT c.id, cl.nom, p.nom FROM commandes c "
        "JOIN clients cl ON cl.id = c.client_id "
        "JOIN produits p ON p.id = c.produit_id;"
    )
    ok, reason = validate_sql(sql)
    assert ok is True


def test_valid_all_allowed_tables():
    """Each allowed table should pass individually."""
    for table in ALLOWED_TABLES:
        ok, reason = validate_sql(f"SELECT * FROM {table};")
        assert ok is True, f"Table {table} should be allowed"


# --- SELECT only ---

def test_reject_empty():
    ok, reason = validate_sql("")
    assert ok is False
    assert "vide" in reason.lower()


def test_reject_insert():
    ok, reason = validate_sql("INSERT INTO produits (nom) VALUES ('test');")
    assert ok is False
    assert "SELECT" in reason


def test_reject_update():
    ok, reason = validate_sql("UPDATE produits SET prix_unitaire = 0;")
    assert ok is False


def test_reject_delete():
    ok, reason = validate_sql("DELETE FROM produits;")
    assert ok is False


def test_reject_drop():
    ok, reason = validate_sql("DROP TABLE produits;")
    assert ok is False


def test_reject_alter():
    ok, reason = validate_sql("ALTER TABLE produits ADD COLUMN test TEXT;")
    assert ok is False


def test_reject_truncate():
    ok, reason = validate_sql("TRUNCATE produits;")
    assert ok is False


# --- Disallowed tables ---

def test_reject_unknown_table():
    ok, reason = validate_sql("SELECT * FROM pg_catalog.pg_roles;")
    assert ok is False
    assert "non autorisée" in reason.lower() or "non autoris" in reason.lower()


def test_reject_system_table():
    ok, reason = validate_sql("SELECT * FROM information_schema.tables;")
    assert ok is False


def test_reject_unknown_in_join():
    sql = "SELECT * FROM commandes c JOIN users u ON u.id = c.client_id;"
    ok, reason = validate_sql(sql)
    assert ok is False
    assert "users" in reason


# --- Subqueries ---

def test_reject_subquery():
    sql = "SELECT * FROM produits WHERE id IN (SELECT produit_id FROM commandes);"
    ok, reason = validate_sql(sql)
    assert ok is False
    assert "sous-requête" in reason.lower() or "sous-requ" in reason.lower()


# --- Length limit ---

def test_reject_too_long():
    sql = "SELECT " + ", ".join([f"col{i}" for i in range(200)]) + " FROM produits;"
    ok, reason = validate_sql(sql)
    assert ok is False
    assert "longue" in reason.lower() or "long" in reason.lower()


# --- Comments ---

def test_reject_line_comment():
    sql = "SELECT * FROM produits; -- safe comment"
    ok, reason = validate_sql(sql)
    assert ok is False
    assert "commentaire" in reason.lower()


def test_reject_block_comment():
    sql = "SELECT * /* hack */ FROM produits;"
    ok, reason = validate_sql(sql)
    assert ok is False


# --- No business table (SELECT without FROM) ---

def test_reject_select_literal():
    """SELECT 'hors périmètre' AS erreur; has no table → rejected."""
    sql = "SELECT 'Question hors périmètre' AS erreur;"
    ok, reason = validate_sql(sql)
    assert ok is False
    assert "table" in reason.lower()


def test_reject_select_constant():
    """SELECT 1; has no table → rejected."""
    sql = "SELECT 1;"
    ok, reason = validate_sql(sql)
    assert ok is False
    assert "table" in reason.lower()


def test_reject_select_expression():
    """SELECT NOW(); has no table → rejected."""
    sql = "SELECT NOW();"
    ok, reason = validate_sql(sql)
    assert ok is False

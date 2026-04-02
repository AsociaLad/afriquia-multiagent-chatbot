"""Tests for the hybrid SQL formatter."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.formatter import _format_simple, _format_with_llm, format_answer


# ---------------------------------------------------------------------------
# _format_simple — unit tests (no LLM)
# ---------------------------------------------------------------------------


def test_simple_zero_rows():
    result = _format_simple("Clients à Tombouctou ?", [])
    assert "Aucun résultat" in result


def test_simple_one_row_one_col():
    result = _format_simple("Combien de clients ?", [{"count": 42}])
    assert "42" in result


def test_simple_one_row_multi_cols():
    result = _format_simple(
        "Prix du gazoil ?",
        [{"nom": "Gazoil 50 ppm", "prix_unitaire": 12.45, "unite": "L"}],
    )
    assert "Gazoil 50 ppm" in result
    assert "12.45" in result


def test_simple_two_rows():
    rows = [
        {"nom": "Alice", "ville": "Casablanca"},
        {"nom": "Bob", "ville": "Rabat"},
    ]
    result = _format_simple("Quels clients ?", rows)
    assert "2 résultat(s)" in result
    assert "Alice" in result
    assert "Bob" in result


def test_simple_three_rows():
    rows = [{"v": "a"}, {"v": "b"}, {"v": "c"}]
    result = _format_simple("Test ?", rows)
    assert "3 résultat(s)" in result


# ---------------------------------------------------------------------------
# format_answer — dispatch logic
# ---------------------------------------------------------------------------


async def test_format_answer_zero_rows_uses_simple():
    """0 rows → always simple, no LLM call."""
    result = await format_answer("Clients ?", [], "SELECT * FROM clients;")
    assert "Aucun résultat" in result


async def test_format_answer_two_rows_uses_simple():
    """2 rows → simple format, no LLM call."""
    rows = [{"nom": "A"}, {"nom": "B"}]
    result = await format_answer("Clients ?", rows, "SELECT nom FROM clients;")
    assert "2 résultat(s)" in result
    assert "A" in result


async def test_format_answer_four_rows_calls_llm():
    """4+ rows → LLM format attempted."""
    rows = [{"nom": f"Client_{i}", "ville": "Casa"} for i in range(5)]

    mock_response = {
        "response": "Voici les 5 clients trouvés à Casablanca : Client_0, Client_1, Client_2, Client_3 et Client_4.",
        "thinking": "",
    }

    with patch("app.services.formatter.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await format_answer("Clients ?", rows, "SELECT * FROM clients;")
        assert "Client_0" in result
        # Verify LLM was called (not simple format)
        mock_client.post.assert_called_once()


async def test_format_answer_llm_fails_falls_back():
    """LLM error → automatic fallback to simple format."""
    rows = [{"nom": f"Client_{i}"} for i in range(5)]

    with patch("app.services.formatter.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Ollama down")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await format_answer("Clients ?", rows, "SELECT * FROM clients;")
        # Should fallback to simple
        assert "5 résultat(s)" in result
        assert "Client_0" in result


async def test_format_answer_llm_empty_response_falls_back():
    """LLM returns empty response → fallback to simple."""
    rows = [{"nom": f"X_{i}"} for i in range(4)]

    mock_response = {"response": "", "thinking": ""}

    with patch("app.services.formatter.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await format_answer("Test ?", rows, "SELECT * FROM clients;")
        assert "4 résultat(s)" in result


# ---------------------------------------------------------------------------
# _format_with_llm — thinking field is NEVER used
# ---------------------------------------------------------------------------


async def test_llm_ignores_thinking_field():
    """Empty response + thinking with content → returns None (not thinking)."""
    rows = [{"nom": f"C_{i}"} for i in range(5)]

    mock_response = {
        "response": "",
        "thinking": "Let me format this.\n\nVoici les 5 clients trouvés dans la base.",
    }

    with patch("app.services.formatter.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await _format_with_llm("Clients ?", rows)
        # Must return None — thinking field must NOT be used
        assert result is None


async def test_format_answer_thinking_only_falls_back_to_simple():
    """Ollama response empty + thinking has reasoning → fallback to simple."""
    rows = [{"statut": "livree", "nb": 7}, {"statut": "en_livraison", "nb": 4},
            {"statut": "en_attente", "nb": 3}, {"statut": "annulee", "nb": 2}]

    mock_response = {
        "response": "",
        "thinking": "Check for any typos and ensure the numbers match the results. That should cover",
    }

    with patch("app.services.formatter.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await format_answer(
            "Combien de commandes par statut ?", rows,
            "SELECT statut, COUNT(*) AS nb FROM commandes GROUP BY statut;",
        )
        # Must use simple format — NOT the thinking garbage
        assert "4 résultat(s)" in result
        assert "livree" in result
        assert "Check" not in result
        assert "typos" not in result


# ---------------------------------------------------------------------------
# Edge case: exactly 3 rows → simple (boundary)
# ---------------------------------------------------------------------------


async def test_format_answer_exactly_three_uses_simple():
    """3 rows is the boundary — should use simple, not LLM."""
    rows = [{"nom": "A"}, {"nom": "B"}, {"nom": "C"}]
    result = await format_answer("Test ?", rows, "SELECT * FROM clients;")
    assert "3 résultat(s)" in result

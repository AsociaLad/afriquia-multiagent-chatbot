"""Tests for Redis cache helpers (unit-level, mocked)."""

from app.services.redis_cache import _cache_key


def test_cache_key_deterministic():
    k1 = _cache_key("prix gasoil", 1)
    k2 = _cache_key("prix gasoil", 1)
    assert k1 == k2


def test_cache_key_varies_by_chatbot():
    k1 = _cache_key("prix gasoil", 1)
    k2 = _cache_key("prix gasoil", 2)
    assert k1 != k2


def test_cache_key_case_insensitive():
    k1 = _cache_key("Prix Gasoil", 1)
    k2 = _cache_key("prix gasoil", 1)
    assert k1 == k2

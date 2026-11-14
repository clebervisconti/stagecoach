"""Production must not boot with a stand-in Apple key set."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.apple_oidc import refuse_static_jwks_in_production


def test_production_refuses_a_static_jwks_document(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("APPLE_JWKS_JSON", '{"keys":[]}')
    with pytest.raises(RuntimeError, match="APPLE_JWKS_JSON"):
        refuse_static_jwks_in_production()


def test_static_jwks_is_allowed_outside_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("APPLE_JWKS_JSON", '{"keys":[]}')
    refuse_static_jwks_in_production()

"""Production must not boot with a stand-in Apple key set."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.apple_oidc import refuse_static_jwks_in_production

REPO = Path(__file__).resolve().parents[3]
PROD_COMPOSE = REPO / "docker-compose.prod.yml"
PROD_OTEL = "deployment.environment=production,service.namespace=cybersphere,stagecoach.component=api"


def _clear_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("OTEL_RESOURCE_ATTRIBUTES", raising=False)


def test_production_refuses_a_static_jwks_document(monkeypatch: pytest.MonkeyPatch):
    _clear_environment(monkeypatch)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("APPLE_JWKS_JSON", '{"keys":[]}')
    with pytest.raises(RuntimeError, match="APPLE_JWKS_JSON"):
        refuse_static_jwks_in_production()


def test_static_jwks_is_allowed_when_env_is_test(monkeypatch: pytest.MonkeyPatch):
    _clear_environment(monkeypatch)
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("APPLE_JWKS_JSON", '{"keys":[]}')
    refuse_static_jwks_in_production()
    monkeypatch.delenv("ENV")
    monkeypatch.setenv("ENVIRONMENT", "test")
    refuse_static_jwks_in_production()


def test_prod_compose_otel_refuses_static_jwks_when_env_is_unset(monkeypatch: pytest.MonkeyPatch):
    _clear_environment(monkeypatch)
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", PROD_OTEL)
    monkeypatch.setenv("APPLE_JWKS_JSON", '{"keys":[]}')
    with pytest.raises(RuntimeError, match="APPLE_JWKS_JSON"):
        refuse_static_jwks_in_production()


def test_unset_environment_refuses_static_jwks(monkeypatch: pytest.MonkeyPatch):
    _clear_environment(monkeypatch)
    monkeypatch.setenv("APPLE_JWKS_JSON", '{"keys":[]}')
    with pytest.raises(RuntimeError, match="APPLE_JWKS_JSON"):
        refuse_static_jwks_in_production()


def test_prod_compose_sets_env_production_for_the_api():
    document = yaml.safe_load(PROD_COMPOSE.read_text(encoding="utf-8"))
    environment = document["services"]["api"]["environment"]
    assert environment["ENV"] == "production"


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not on PATH")
def test_prod_compose_config_sets_env_production_for_the_api():
    env = os.environ.copy()
    env.setdefault("POSTGRES_PASSWORD", "ci-placeholder")
    env.setdefault("AUTH_SECRET", "ci-placeholder")
    result = subprocess.run(
        ["docker", "compose", "-f", str(PROD_COMPOSE), "config", "--format", "json"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(result.stderr or result.stdout)
    config = json.loads(result.stdout)
    api_env = config["services"]["api"]["environment"]
    assert api_env["ENV"] == "production"

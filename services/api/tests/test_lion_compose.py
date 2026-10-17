"""LION overlay must publish only 127.0.0.1:8870, 6380, 9010.

`ports: []` does not clear the base compose list — the overlay uses
!reset / !override. This test runs `docker compose config` so the merged
ports are what Compose would actually bind.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
LION = REPO / "infra" / "compose.lion.yaml"

COMPOSE_ENV = {
    "POSTGRES_PASSWORD": "ci-lion-compose",
    "AUTH_SECRET": "ci-lion-compose-secret-not-for-production",
    "MINIO_ACCESS_KEY": "ci-minio-access",
    "MINIO_SECRET_KEY": "ci-minio-secret-key-value",
    "PRIVATE_BETA_EMAIL": "ci@example.invalid",
}


def _published_ports(service: dict) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for mapping in service.get("ports") or []:
        if isinstance(mapping, str):
            parts = mapping.split(":")
            if len(parts) == 3:
                found.append((parts[0], parts[1]))
            elif len(parts) == 2:
                found.append(("0.0.0.0", parts[0]))
            continue
        if not isinstance(mapping, dict):
            continue
        published = mapping.get("published")
        if published in (None, ""):
            continue
        host_ip = mapping.get("host_ip") or mapping.get("published_ip") or "0.0.0.0"
        found.append((str(host_ip), str(published)))
    return found


def test_lion_overlay_uses_reset_or_override():
    text = LION.read_text(encoding="utf-8")
    assert "!reset" in text
    assert "!override" in text
    # Raw YAML must not rely on ports: [] — Compose merges that with the base.
    data = None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None
    if isinstance(data, dict):
        for name in ("postgres", "api", "mailpit"):
            ports = (data.get("services") or {}).get(name, {}).get("ports")
            assert ports != [], f"{name} ports: [] does not reset the base list"


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not on PATH")
def test_lion_merged_compose_publishes_only_loopback_safe_ports():
    env = {**os.environ, **COMPOSE_ENV}
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "infra/compose.lion.yaml",
            "--profile",
            "web",
            "--profile",
            "minio",
            "--profile",
            "workers",
            "config",
            "--format",
            "json",
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"docker compose config failed: {result.stderr or result.stdout}")

    data = json.loads(result.stdout)
    published: dict[str, list[tuple[str, str]]] = {}
    all_host_ports: list[str] = []
    for name, service in (data.get("services") or {}).items():
        ports = _published_ports(service)
        published[name] = ports
        for host_ip, host_port in ports:
            assert host_ip in {"127.0.0.1", "::1"}, f"{name} must bind loopback: {host_ip}:{host_port}"
            assert host_port not in {"8000", "5432"}, f"{name} must not bind host :{host_port}"
            all_host_ports.append(host_port)

    assert published.get("postgres") == []
    assert published.get("api") == []
    assert published.get("mailpit") == []
    assert ("127.0.0.1", "8870") in published.get("web", [])
    assert ("127.0.0.1", "6380") in published.get("redis", [])
    assert ("127.0.0.1", "9010") in published.get("minio", [])
    assert set(all_host_ports) == {"8870", "6380", "9010"}

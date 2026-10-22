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
MAKEFILE = REPO / "Makefile"

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


DEFAULT_PUBLIC_URL = "http://127.0.0.1:8870"
BASE_COMPOSE = REPO / "docker-compose.yml"


def _service_env(service: dict) -> dict[str, str]:
    raw = service.get("environment") or {}
    if isinstance(raw, dict):
        return {str(k): "" if v is None else str(v) for k, v in raw.items()}
    out: dict[str, str] = {}
    for item in raw:
        if isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            out[key] = value
    return out


def _compose_config(extra_env: dict[str, str] | None = None) -> dict:
    env = {**os.environ, **COMPOSE_ENV}
    env.pop("STAGECOACH_PUBLIC_URL", None)
    if extra_env:
        env.update(extra_env)
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
    return json.loads(result.stdout)


def test_lion_overlay_uses_reset_or_override():
    text = LION.read_text(encoding="utf-8")
    assert "!reset" in text
    assert "!override" in text
    assert "${STAGECOACH_PUBLIC_URL:-http://127.0.0.1:8870}" in text
    assert "NEXTAUTH_URL: http://127.0.0.1:8870" not in text
    assert "command: npm run dev" not in text
    assert 'command: ["node", "server.js"]' in text
    # Raw YAML must not rely on ports: [] — Compose merges that with the base.
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None
    if isinstance(data, dict):
        for name in ("postgres", "api", "mailpit"):
            ports = (data.get("services") or {}).get(name, {}).get("ports")
            assert ports != [], f"{name} ports: [] does not reset the base list"


def test_base_compose_passes_public_url_to_api():
    text = BASE_COMPOSE.read_text(encoding="utf-8")
    assert "STAGECOACH_PUBLIC_URL: ${STAGECOACH_PUBLIC_URL:-http://127.0.0.1:8870}" in text


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not on PATH")
def test_lion_merged_compose_publishes_only_loopback_safe_ports():
    data = _compose_config()
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
    api_env = _service_env(data["services"]["api"])
    web_env = _service_env(data["services"]["web"])
    assert api_env.get("STAGECOACH_PUBLIC_URL") == DEFAULT_PUBLIC_URL
    assert web_env.get("STAGECOACH_PUBLIC_URL") == DEFAULT_PUBLIC_URL
    assert web_env.get("NEXTAUTH_URL") == DEFAULT_PUBLIC_URL
    web = data["services"]["web"]
    command = web.get("command")
    command_s = " ".join(command) if isinstance(command, list) else str(command or "")
    assert "npm run dev" not in command_s
    assert "server.js" in command_s or "next" in command_s


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not on PATH")
def test_lion_public_url_reads_from_env():
    public = "https://stagecoach.example.test"
    data = _compose_config({"STAGECOACH_PUBLIC_URL": public})
    api_env = _service_env(data["services"]["api"])
    web_env = _service_env(data["services"]["web"])
    assert api_env.get("STAGECOACH_PUBLIC_URL") == public
    assert web_env.get("NEXTAUTH_URL") == public


def test_makefile_lion_targets_pass_project_env_and_override():
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "COMPOSE_PROJECT_NAME ?=" in text
    assert "ENV_FILE ?=" in text
    assert "LION_OVERRIDE ?=" in text
    assert "LION_SERVICES ?=" in text
    assert "-p $(COMPOSE_PROJECT_NAME)" in text
    assert "--env-file $(ENV_FILE)" in text or "ENV_FILE_FLAG" in text
    assert "up -d $(LION_SERVICES)" in text
    assert "LION_SERVICES ?= postgres redis minio api worker web mailpit" in text
    assert "worker-beat" not in text.split("LION_SERVICES ?=")[1].split("\n", 1)[0]


def test_makefile_lion_up_dry_run_command():
    result = subprocess.run(
        [
            "make",
            "-n",
            "lion-up",
            "COMPOSE_PROJECT_NAME=lab-lion",
            "ENV_FILE=/tmp/stagecoach-ci.env",
            "LION_OVERRIDE=infra/compose.lion.yaml",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    command = result.stdout
    compose_line = [line for line in command.splitlines() if "docker compose" in line][-1]
    assert "-p lab-lion" in compose_line
    assert "worker-beat" not in compose_line
    assert " up -d " in compose_line
    assert "worker" in compose_line
    assert "--profile" in compose_line


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not on PATH")
def test_lion_overlay_drops_worker_beat_from_workers_profile():
    data = _compose_config()
    services = data.get("services") or {}
    assert "worker" in services
    assert "worker-beat" not in services

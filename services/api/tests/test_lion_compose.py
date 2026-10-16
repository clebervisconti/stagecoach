"""LION compose overlay must not steal host :8000 or :5432."""

from pathlib import Path

import yaml

LION = Path(__file__).resolve().parents[3] / "infra" / "compose.lion.yaml"


def test_lion_compose_publishes_only_loopback_safe_ports():
    data = yaml.safe_load(LION.read_text(encoding="utf-8"))
    published: list[str] = []
    for name, service in (data.get("services") or {}).items():
        for mapping in service.get("ports") or []:
            assert isinstance(mapping, str), f"{name} port must be a host:container string"
            assert mapping.startswith("127.0.0.1:"), f"{name} must bind loopback only: {mapping}"
            host_port = mapping.split(":")[1]
            assert host_port not in {"8000", "5432"}, f"{name} must not bind host :{host_port}"
            published.append(host_port)
    assert "8870" in published
    assert "6380" in published
    assert "9010" in published
    assert data["services"]["postgres"].get("ports") == []
    assert data["services"]["api"].get("ports") == []

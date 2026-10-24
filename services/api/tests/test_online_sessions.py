"""SessionCreate online fields stay behind ONLINE_MODES_ENABLED (O0)."""

import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.routers.sessions import SessionCreate, gate_online_session_fields

ALLOWED = SimpleNamespace(online_modes=True)
DENIED = SimpleNamespace(online_modes=False)


def _stage(**overrides):
    body = {
        "title": "Keynote",
        "context_type": "keynote",
        "language": "en",
        "camera_setup": "stage",
    }
    body.update(overrides)
    return SessionCreate(**body)


def test_stage_create_unchanged_when_flag_off(monkeypatch):
    monkeypatch.delenv("ONLINE_MODES_ENABLED", raising=False)
    data = _stage()
    gate_online_session_fields(data)
    assert data.delivery_mode == "stage"
    assert data.source_kind == "upload"
    assert data.camera_setup == "stage"


def test_unknown_camera_setup_accepted_for_stage():
    data = _stage(camera_setup="unknown")
    assert data.camera_setup == "unknown"


def test_online_mode_is_404_when_flag_off(monkeypatch):
    monkeypatch.delenv("ONLINE_MODES_ENABLED", raising=False)
    data = _stage(delivery_mode="webinar", camera_setup="unknown", rights_attested=True)
    with pytest.raises(HTTPException) as exc:
        gate_online_session_fields(data)
    assert exc.value.status_code == 404


def test_webinar_accepted_when_flag_on(monkeypatch):
    monkeypatch.setenv("ONLINE_MODES_ENABLED", "true")
    monkeypatch.setenv("ONLINE_MODES_ALLOWED_EMAILS", "owner@example.invalid")
    data = _stage(delivery_mode="webinar", camera_setup=None, rights_attested=True)
    gate_online_session_fields(data, ALLOWED)
    assert data.camera_setup == "unknown"


def test_webinar_requires_rights(monkeypatch):
    monkeypatch.setenv("ONLINE_MODES_ENABLED", "true")
    data = _stage(delivery_mode="webinar", camera_setup="unknown")
    with pytest.raises(HTTPException) as exc:
        gate_online_session_fields(data, ALLOWED)
    assert exc.value.status_code == 400


def test_online_mode_denied_for_other_accounts(monkeypatch):
    monkeypatch.setenv("ONLINE_MODES_ENABLED", "true")
    monkeypatch.setenv("ONLINE_MODES_ALLOWED_EMAILS", "owner@example.invalid")
    data = _stage(delivery_mode="webinar", camera_setup="unknown", rights_attested=True)
    with pytest.raises(HTTPException) as exc:
        gate_online_session_fields(data, DENIED)
    assert exc.value.status_code == 404


def test_email_string_does_not_enable_online_modes(monkeypatch):
    monkeypatch.setenv("ONLINE_MODES_ENABLED", "true")
    monkeypatch.setenv("ONLINE_MODES_ALLOWED_EMAILS", "owner@example.invalid")
    data = _stage(delivery_mode="webinar", camera_setup="unknown", rights_attested=True)
    with pytest.raises(HTTPException) as exc:
        gate_online_session_fields(data, "owner@example.invalid")
    assert exc.value.status_code == 404


def test_url_source_is_404_when_url_flag_off(monkeypatch):
    monkeypatch.setenv("ONLINE_MODES_ENABLED", "true")
    monkeypatch.delenv("URL_INGEST_ENABLED", raising=False)
    data = _stage(
        delivery_mode="recorded_video",
        camera_setup="unknown",
        source_kind="url",
        source_url="https://example.invalid/talk",
        rights_attested=True,
        target_length_min=12,
    )
    with pytest.raises(HTTPException) as exc:
        gate_online_session_fields(data, ALLOWED)
    assert exc.value.status_code == 404


def test_target_length_rejected_for_stage():
    with pytest.raises(ValidationError):
        _stage(target_length_min=10)


def test_analysis_window_must_be_at_least_60s():
    with pytest.raises(ValidationError):
        _stage(analysis_window={"start_s": 0, "end_s": 30})

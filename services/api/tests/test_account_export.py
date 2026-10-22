"""Zip export: JSON members, 24 h HMAC media links, no live S3."""

import io
import json
import os
import zipfile
from datetime import UTC, datetime

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.account_export import (
    EXPORT_TTL_S,
    ZIP_FILES,
    media_link,
    pack_zip,
    sign_export_link,
    verify_export_link,
)
from app.auth import jwt as jwt_mod


def test_export_ttl_is_24_hours():
    assert EXPORT_TTL_S == 24 * 60 * 60


def test_export_signature_roundtrip_and_reject_tamper(monkeypatch):
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", "e" * 32)
    exp = 1_800_000_000
    sig = sign_export_link("sess-1", "asset-1", exp)
    assert verify_export_link("sess-1", "asset-1", exp, sig) is True
    assert verify_export_link("sess-2", "asset-1", exp, sig) is False
    assert verify_export_link("sess-1", "asset-2", exp, sig) is False
    assert verify_export_link("sess-1", "asset-1", exp + 1, sig) is False
    assert verify_export_link("sess-1", "asset-1", exp, "ab" * 16) is False


def test_media_link_is_24h_and_verifies(monkeypatch):
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", "e" * 32)
    exp = 1_800_100_000
    link = media_link(
        session_id="sess-1",
        asset_id="asset-9",
        kind="original",
        storage_uri="users/u/sessions/sess-1/original.bin",
        expires_at=exp,
        api_base="https://stagecoach.example",
    )
    assert link["expires_in_s"] == EXPORT_TTL_S
    assert link["expires_at"].endswith("Z")
    assert "purpose=export" in link["url"]
    assert "asset=asset-9" in link["url"]
    assert f"exp={exp}" in link["url"]
    sig = link["url"].split("sig=")[1].split("&")[0]
    assert verify_export_link("sess-1", "asset-9", exp, sig) is True


def test_pack_zip_contains_spec_json_members(monkeypatch):
    monkeypatch.setattr(jwt_mod, "AUTH_SECRET", "e" * 32)
    exp = int(datetime(2026, 10, 16, 12, 0, tzinfo=UTC).timestamp()) + EXPORT_TTL_S
    files = {
        "manifest.json": {"schema": "stagecoach.export.v1", "files": list(ZIP_FILES)},
        "user.json": {"id": "user-1", "email": "speaker@example.invalid"},
        "sessions.json": [{"id": "sess-1", "title": "Keynote"}],
        "scores.json": {"category_scores": [], "overall_scores": []},
        "evidence.json": [],
        "transcripts.json": [{"language": "en", "words_uri": "derived/words.json"}],
        "plans.json": {"talk_plans": [{"id": "plan-1"}], "goals": []},
        "consents.json": [{"purpose": "video_analysis", "granted": True}],
        "layouts.json": [],
        "media_links.json": [
            media_link(
                session_id="sess-1",
                asset_id="asset-1",
                kind="playback",
                storage_uri="users/u/sessions/sess-1/playback.mp4",
                expires_at=exp,
                api_base="https://stagecoach.example",
            )
        ],
    }
    blob = pack_zip(files)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        assert set(archive.namelist()) == set(ZIP_FILES)
        consents = json.loads(archive.read("consents.json"))
        assert consents[0]["purpose"] == "video_analysis"
        links = json.loads(archive.read("media_links.json"))
        assert links[0]["expires_in_s"] == 86400
        sessions = json.loads(archive.read("sessions.json"))
        assert sessions[0]["title"] == "Keynote"

"""PDF export path containment (issue #49)."""

import json
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.routers import exports as exports_mod
from fastapi import HTTPException
import pytest


def test_export_dir_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(exports_mod, "MEDIA_ROOT", tmp_path.resolve())
    with pytest.raises(HTTPException) as exc:
        exports_mod._export_dir("../outside")
    assert exc.value.status_code == 404


def test_owned_meta_hides_other_users(tmp_path, monkeypatch):
    monkeypatch.setattr(exports_mod, "MEDIA_ROOT", tmp_path.resolve())
    dest = tmp_path / "exports" / "e1"
    dest.mkdir(parents=True)
    (dest / "meta.json").write_text(json.dumps({"user_id": "aaa", "status": "ready"}))

    class User:
        id = "bbb"

    with pytest.raises(HTTPException) as exc:
        exports_mod._owned_meta("e1", User())
    assert exc.value.status_code == 404

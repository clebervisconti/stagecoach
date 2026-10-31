"""Revision chain for screen flow. Postgres is not required."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.models.screen_flow import ScreenFlow, ScreenSegment


def _load_revision():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261031_1200_014_screen_flow.py"
    spec = importlib.util.spec_from_file_location("migration_014_screen_flow", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_revision_014_follows_media_bytes():
    migration = _load_revision()
    assert migration.revision == "014_screen_flow"
    assert migration.down_revision == "013_media_bytes"


def test_screen_flow_rows_cascade_on_delete():
    for model in (ScreenFlow, ScreenSegment):
        session_fk = next(iter(model.__table__.c.session_id.foreign_keys))
        job_fk = next(iter(model.__table__.c.job_id.foreign_keys))
        assert session_fk.ondelete == "CASCADE"
        assert job_fk.ondelete == "CASCADE"
    assert ScreenFlow.__table__.c.job_id.unique is True

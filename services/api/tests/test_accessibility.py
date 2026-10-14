"""Accessibility profile normalization (issue #40)."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import pytest
from fastapi import HTTPException

from app.routers.users import normalize_accessibility


def test_wheelchair_implies_seated():
    out = normalize_accessibility({"wheelchair": True})
    assert out["wheelchair"] is True
    assert out["seated"] is True
    assert out["one_handed"] is False


def test_unknown_key_is_rejected():
    with pytest.raises(HTTPException) as exc:
        normalize_accessibility({"inferred_disability": True})
    assert exc.value.status_code == 422

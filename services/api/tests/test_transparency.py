"""Public References and scoring-config endpoints (issue #51)."""

import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.research import load_sources, parse_sources
from app.scoring_public import load_scoring_config
from app.routers.transparency import research_sources, scoring_config


SAMPLE = """
### Evaluation (S1–S2)
- **[S1]** Toastmasters International. https://example.com/s1
- **[S20]** Mehrabian 7-38-55 misuse. https://example.com/s20
"""


def test_parse_sources_keeps_keys_and_anchors():
    rows = parse_sources(SAMPLE)
    assert [row["key"] for row in rows] == ["S1", "S20"]
    assert rows[0]["anchor"] == "S1"
    assert rows[1]["section"].startswith("Evaluation")
    assert rows[1]["urls"] == ["https://example.com/s20"]


def test_load_sources_from_repo():
    payload = load_sources()
    keys = {row["key"] for row in payload["sources"]}
    assert payload["count"] >= 56
    assert "S1" in keys
    assert "S20" in keys
    assert "S56" in keys


def test_research_sources_endpoint():
    body = research_sources()
    assert body["count"] == len(body["sources"])
    s20 = next(row for row in body["sources"] if row["key"] == "S20")
    assert s20["anchor"] == "S20"
    assert "Mehrabian" in s20["text"]


def test_scoring_config_is_readonly_v1():
    body = scoring_config("1.0.0")
    assert body["readonly"] is True
    assert body["version"] == "1.0.0"
    assert "categories" in body["config"]
    assert "weights" in body["config"]


def test_unknown_scoring_version_404():
    from fastapi import HTTPException

    try:
        scoring_config("9.9.9")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected 404")


def test_load_scoring_rejects_path_escape():
    with pytest.raises(FileNotFoundError):
        load_scoring_config("../secrets")

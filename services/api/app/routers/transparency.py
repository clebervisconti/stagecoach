"""Public research and scoring-config endpoints (issue #51)."""

from fastapi import APIRouter, HTTPException

from app.research import load_sources
from app.scoring_public import DEFAULT_VERSION, load_scoring_config

router = APIRouter()


@router.get("/research/sources")
def research_sources() -> dict:
    try:
        return load_sources()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="sources.md is not available") from exc


@router.get("/config/scoring/{version}")
def scoring_config(version: str) -> dict:
    try:
        return load_scoring_config(version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scoring config {version}") from exc


@router.get("/config/scoring")
def scoring_config_default() -> dict:
    return scoring_config(DEFAULT_VERSION)

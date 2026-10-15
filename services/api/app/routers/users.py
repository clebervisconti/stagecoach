"""User endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.consents.policy import CONSENT_PURPOSES, POLICY_ID, load_policy, localize_purpose, policy_version
from app.consents.store import current_from_rows, records_for_user
from app.database import get_db
from app.models.consent import Consent
from app.models.user import User, uuid7
from app.llm_providers import normalize_llm_settings, provider_catalog
from app.retention import DEFAULT_RETENTION_POLICY, RETENTION_POLICIES, normalize_retention_policy

router = APIRouter(prefix="/me", tags=["users"])

ACCESSIBILITY_KEYS = (
    "seated",
    "wheelchair",
    "limited_mobility",
    "one_handed",
    "speech_difference",
    "prefers_no_video_metrics",
    "low_vision",
)


def normalize_accessibility(raw: Optional[dict]) -> dict:
    """Keep known boolean flags only. Wheelchair implies seated (SPEC §10.6)."""
    src = raw or {}
    unknown = [key for key in src if key not in ACCESSIBILITY_KEYS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown accessibility_profile keys: {unknown}",
        )
    out = {key: bool(src.get(key)) for key in ACCESSIBILITY_KEYS}
    if out["wheelchair"]:
        out["seated"] = True
    return out


def parse_llm_settings(value: Optional[dict]) -> dict:
    try:
        return normalize_llm_settings(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def parse_retention_policy(value: Optional[str]) -> str:
    try:
        return normalize_retention_policy(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"retention_policy must be one of {list(RETENTION_POLICIES)}",
        ) from exc


class UserProfile(BaseModel):
    """User profile response."""
    id: str
    email: str
    name: Optional[str] = None
    locale: str = "en"
    timezone: str = "UTC"
    accessibility_profile: Optional[dict] = None
    retention_policy: str = DEFAULT_RETENTION_POLICY
    llm_settings: Optional[dict] = None


class UserProfileUpdate(BaseModel):
    """User profile update request."""
    name: Optional[str] = Field(None, max_length=255)
    locale: Optional[str] = Field(None, pattern="^(en|pt-BR)$")
    timezone: Optional[str] = Field(None, max_length=50)
    accessibility_profile: Optional[dict] = None
    retention_policy: Optional[str] = None
    llm_settings: Optional[dict] = None


class ConsentChange(BaseModel):
    purpose: str = Field(..., min_length=1, max_length=50)
    granted: bool


def _locale(requested: Optional[str], user: User) -> str:
    if requested in {"en", "pt-BR"}:
        return requested
    if user.locale in {"en", "pt-BR"}:
        return user.locale
    return "en"


def _country(request: Request) -> Optional[str]:
    raw = (request.headers.get("cf-ipcountry") or "").strip().upper()
    if len(raw) == 2 and raw.isalpha() and raw != "XX":
        return raw
    return None


def build_consent_payload(user: User, db: Session, locale: str) -> dict:
    policy = load_policy()
    version = policy_version(policy)
    current = current_from_rows(records_for_user(db, user.id))
    items = []
    for purpose in CONSENT_PURPOSES:
        copy = localize_purpose(purpose, locale, policy)
        row = current.get(purpose)
        items.append(
            {
                "purpose": purpose,
                "granted": bool(row.granted) if row else False,
                "granted_at": row.granted_at.isoformat() if row and row.granted_at else None,
                "revoked_at": row.revoked_at.isoformat() if row and row.revoked_at else None,
                "version": row.version if row else None,
                **copy,
            }
        )
    return {
        "policy_id": POLICY_ID,
        "policy_version": version,
        "locale": locale,
        "consents": items,
    }


@router.get("", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        locale=current_user.locale,
        timezone=current_user.timezone,
        accessibility_profile=current_user.accessibility_profile,
        retention_policy=parse_retention_policy(getattr(current_user, "retention_policy", None)),
        llm_settings=parse_llm_settings(getattr(current_user, "llm_settings", None)),
    )


@router.get("/ai-providers")
async def get_ai_providers(current_user: User = Depends(get_current_user)):
    """Catalog of selectable providers. Reports key presence, never key values."""
    return {
        **provider_catalog(),
        "llm_settings": parse_llm_settings(getattr(current_user, "llm_settings", None)),
    }


@router.patch("", response_model=UserProfile)
async def update_me(
    update: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile."""
    if update.name is not None:
        current_user.name = update.name
    if update.locale is not None:
        current_user.locale = update.locale
    if update.timezone is not None:
        current_user.timezone = update.timezone
    if update.accessibility_profile is not None:
        current_user.accessibility_profile = normalize_accessibility(update.accessibility_profile)
    if update.retention_policy is not None:
        current_user.retention_policy = parse_retention_policy(update.retention_policy)
    if update.llm_settings is not None:
        current_user.llm_settings = parse_llm_settings(update.llm_settings)

    db.commit()
    db.refresh(current_user)

    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        locale=current_user.locale,
        timezone=current_user.timezone,
        accessibility_profile=current_user.accessibility_profile,
        retention_policy=parse_retention_policy(getattr(current_user, "retention_policy", None)),
        llm_settings=parse_llm_settings(getattr(current_user, "llm_settings", None)),
    )


@router.get("/consents")
async def get_consents(
    locale: Optional[str] = Query(None, pattern="^(en|pt-BR)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Current consent state per purpose (append-only latest wins)."""
    return build_consent_payload(current_user, db, _locale(locale, current_user))


@router.post("/consents", status_code=status.HTTP_201_CREATED)
async def post_consent(
    change: ConsentChange,
    request: Request,
    locale: Optional[str] = Query(None, pattern="^(en|pt-BR)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grant or revoke a purpose. Appends a new consents row; never edits old rows."""
    if change.purpose not in CONSENT_PURPOSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown consent purpose: {change.purpose}",
        )
    now = datetime.utcnow()
    version = policy_version()
    row = Consent(
        id=uuid7(),
        user_id=current_user.id,
        purpose=change.purpose,
        granted=change.granted,
        version=version,
        granted_at=now,
        revoked_at=None if change.granted else now,
        ip_country=_country(request),
    )
    db.add(row)
    db.commit()
    return build_consent_payload(current_user, db, _locale(locale, current_user))

"""User endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.account_deletion import (
    cancel_account_deletion,
    deletion_status,
    pending_account_deletion,
    request_account_deletion,
)
from app.account_export import collect_export, export_filename, pack_zip
from app.auth import get_current_user
from app.consents.policy import CONSENT_PURPOSES, POLICY_ID, load_policy, localize_purpose, policy_version
from app.consents.store import current_from_rows, records_for_user
from app.database import get_db
from app.models.consent import Consent
from app.models.user import User, uuid7
from app.llm_providers import normalize_llm_settings, provider_catalog
from app.retention import DEFAULT_RETENTION_POLICY, RETENTION_POLICIES, normalize_retention_policy
from app.online_flags import user_online_modes_enabled

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


REVIEW_LAYOUTS = ("always", "when_unsure", "never")


def parse_review_layout(value: Optional[str]) -> str:
    if value is None or value == "":
        return "when_unsure"
    if value not in REVIEW_LAYOUTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"review_layout must be one of {list(REVIEW_LAYOUTS)}",
        )
    return value


def confirmed_online_layouts(db: Session, user_id: object) -> int:
    """Confirmed non-stage layouts. MemoryDB has no join, so tests stay at 0."""
    try:
        from app.models.session import Session as TalkSession
        from app.models.session_layout import SessionLayout

        query = db.query(SessionLayout)
    except Exception:
        return 0
    if not hasattr(query, "join"):
        return 0
    try:
        counted = (
            query.join(TalkSession, SessionLayout.session_id == TalkSession.id)
            .filter(TalkSession.user_id == user_id, TalkSession.delivery_mode != "stage")
            .filter(SessionLayout.status.in_(("confirmed", "auto_confirmed")))
            .count()
        )
        return int(counted or 0)
    except Exception:
        return 0


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
    online_modes_enabled: bool = False
    review_layout: str = "when_unsure"
    confirmed_online_layouts: int = 0
    role: str = "member"
    must_change_password: bool = False


class UserProfileUpdate(BaseModel):
    """User profile update request."""
    name: Optional[str] = Field(None, max_length=255)
    locale: Optional[str] = Field(None, pattern="^(en|pt-BR)$")
    timezone: Optional[str] = Field(None, max_length=50)
    accessibility_profile: Optional[dict] = None
    retention_policy: Optional[str] = None
    llm_settings: Optional[dict] = None
    review_layout: Optional[str] = None


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


def _profile(user: User, db: Optional[Session] = None) -> UserProfile:
    return UserProfile(
        id=str(user.id),
        email=user.email,
        name=user.name,
        locale=user.locale,
        timezone=user.timezone,
        accessibility_profile=user.accessibility_profile,
        retention_policy=parse_retention_policy(getattr(user, "retention_policy", None)),
        llm_settings=parse_llm_settings(getattr(user, "llm_settings", None)),
        online_modes_enabled=user_online_modes_enabled(user),
        review_layout=parse_review_layout(getattr(user, "layout_review_pref", None)),
        confirmed_online_layouts=confirmed_online_layouts(db, user.id) if db is not None else 0,
        role=user.role or "member",
        must_change_password=bool(user.must_change_password),
    )


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
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user profile."""
    return _profile(current_user, db)


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
    if update.review_layout is not None:
        current_user.layout_review_pref = parse_review_layout(update.review_layout)

    db.commit()
    db.refresh(current_user)

    return _profile(current_user, db)


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


@router.post("/export")
async def export_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Zip of JSON (sessions, scores, evidence, transcripts, plans, consents) + 24 h media links."""
    payload = collect_export(
        db,
        current_user,
        request_base=str(request.base_url).rstrip("/"),
    )
    blob = pack_zip(payload)
    filename = export_filename(current_user.id)
    return Response(
        content=blob,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/deletion")
async def get_deletion(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return deletion_status(pending_account_deletion(db, current_user.id))


@router.delete("/deletion", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_deletion(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if cancel_account_deletion(db, current_user) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending deletion")
    return None


@router.delete("", status_code=status.HTTP_202_ACCEPTED)
async def delete_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start the 7-day grace period. The account stays usable until finalize."""
    row = request_account_deletion(
        db,
        current_user,
        ip=request.client.host if request.client else None,
    )
    return deletion_status(row)

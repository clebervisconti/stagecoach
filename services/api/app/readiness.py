"""Owner checklist for a self-serve launch. Values of secrets are never returned."""

from __future__ import annotations

import os
from typing import Any

from app.apple_oidc import apple_configured
from app.emailing import resend_configured


def _set(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def self_serve_readiness() -> dict[str, Any]:
    """Which launch gates are configured. This does not turn them on."""
    asr = (os.getenv("ASR_MODEL") or "").strip()
    kms = _set("KMS_KEY_ID")
    local_key = _set("STAGECOACH_KEK") or _set("STAGECOACH_ARTIFACT_KEY")
    return {
        "self_serve_open": os.getenv("SELF_SERVE_OPEN", "0") == "1",
        "online_modes_enabled": os.getenv("ONLINE_MODES_ENABLED", "0") == "1",
        "gates": {
            "resend": resend_configured(),
            "apple": apple_configured(),
            "asr_model": asr or "unset",
            "kms": kms,
            "local_envelope_key": local_key and not kms,
            "privacy_reviewed": os.getenv("PRIVACY_REVIEWED", "0") == "1",
        },
        "notes": {
            "resend": "Verification mail stays on the console stand-in until RESEND_API_KEY and DNS are set.",
            "apple": "Sign in with Apple stays hidden until the four Apple secrets exist.",
            "asr_model": "Production compose still defaults ASR_MODEL to tiny until the owner points it at TIGER.",
            "privacy_reviewed": "Set PRIVACY_REVIEWED=1 only after counsel reviews docs/PRIVACY.md.",
            "access": "Cloudflare Access remains the production login until SELF_SERVE_OPEN=1.",
        },
    }

"""Stable N/A reason codes (O1, ADR-070). Shared with fusion via packages/schemas."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_schemas_path() -> None:
    """Find packages/schemas without assuming a repo-relative depth.

    In Docker the API lives at /app/app/..., so parents[3] raises IndexError.
    Prefer the compose mount at /packages/schemas.
    """
    here = Path(__file__).resolve().parent
    candidates = [Path("/packages/schemas")]
    for parent in [here, *here.parents]:
        candidates.append(parent / "packages" / "schemas")
        candidates.append(parent / "schemas")
    for path in candidates:
        try:
            if (path / "na_codes.py").is_file():
                resolved = str(path)
                if resolved not in sys.path:
                    sys.path.insert(0, resolved)
                return
        except OSError:
            continue


_ensure_schemas_path()

from na_codes import NA_CODES, S5_TO_NA_CODE, infer_na_code  # noqa: E402

__all__ = ["NA_CODES", "S5_TO_NA_CODE", "infer_na_code"]

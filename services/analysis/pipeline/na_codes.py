"""Re-export the shared N/A code enum used by fusion and the API."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCHEMAS = _ROOT / "packages" / "schemas"
if str(_SCHEMAS) not in sys.path:
    sys.path.insert(0, str(_SCHEMAS))

from na_codes import NA_CODES, S5_TO_NA_CODE, infer_na_code  # noqa: E402

__all__ = ["NA_CODES", "S5_TO_NA_CODE", "infer_na_code"]

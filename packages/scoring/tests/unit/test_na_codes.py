import sys
from pathlib import Path

_SCHEMAS = Path(__file__).resolve().parents[3] / "schemas"
sys.path.insert(0, str(_SCHEMAS))

from na_codes import NA_CODES, infer_na_code  # noqa: E402


def test_enum_covers_s5_keys():
    for key in (
        "not_in_phase",
        "consent_video_off",
        "vision_unavailable",
        "camera_not_visible",
        "audio_only_chosen",
        "qa_not_detected",
    ):
        assert key in NA_CODES


def test_infer_from_free_text():
    assert infer_na_code("This session did not include a Q&A segment.") == "qa_declared_none"
    consent = "Video analysis consent is off; pose and face landmarks were not processed."
    assert infer_na_code(consent) == "consent_video_off"
    assert infer_na_code(None) is None

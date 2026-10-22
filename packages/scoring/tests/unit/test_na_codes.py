from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "schemas"))

from na_codes import NA_CODES, infer_na_code


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
    assert infer_na_code(None) is None

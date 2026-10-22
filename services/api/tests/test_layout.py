"""Layout accept payload and review helpers."""

from app.models.session_layout import SessionLayout
from app.routers.layout import LayoutAcceptBody
from app.routers.sessions import _step_problem, _video_analysis_granted
from app.na_codes import infer_na_code


def test_accept_body_defaults_to_full_analysis():
    body = LayoutAcceptBody()
    assert body.audio_only is False
    assert LayoutAcceptBody(audio_only=True).audio_only is True


def test_na_code_maps_s5_keys():
    assert infer_na_code("not_in_phase") == "not_in_phase"
    assert infer_na_code("Video analysis is off. Turn it on in Settings to measure this.") == "consent_video_off"
    assert infer_na_code("Video analysis consent is off; pose and face landmarks were not processed.") == "consent_video_off"
    assert infer_na_code("You chose to analyse audio only.") == "audio_only_chosen"
    assert infer_na_code("Coming soon.") == "not_in_phase"


class _Step:
    def __init__(self, metrics=None, error=None, status="skipped"):
        self.metrics = metrics
        self.error = error
        self.status = status


def test_step_problem_maps_consent_reason_and_not_a_bare_skip():
    assert _step_problem(_Step(metrics={"reason": "consent_denied:video_analysis"})) == "consent_video_off"
    assert _step_problem(_Step(metrics={"na_code": "consent_video_off"})) == "consent_video_off"
    assert _step_problem(_Step(metrics={"reason": "mediapipe_unavailable"})) == "vision_unavailable"
    assert _step_problem(_Step(metrics={"reason": "no_video_stream"})) is None
    assert _step_problem(_Step(metrics=None)) is None


def test_video_analysis_granted_uses_consent_signal():
    snapshot = {"purposes": {"video_analysis": {"granted": True}}}
    assert _video_analysis_granted(snapshot, [{"problem": "vision_unavailable"}]) is True
    assert _video_analysis_granted(snapshot, [{"problem": "consent_video_off"}]) is False
    assert _video_analysis_granted({"purposes": {"video_analysis": {"granted": False}}}, []) is False


def test_session_layouts_cascade_when_session_is_deleted():
    session_fk = next(iter(SessionLayout.__table__.c.session_id.foreign_keys))
    job_fk = next(iter(SessionLayout.__table__.c.job_id.foreign_keys))
    assert session_fk.ondelete == "CASCADE"
    assert job_fk.ondelete == "CASCADE"

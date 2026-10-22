"""Layout accept payload and review helpers."""

from app.models.session_layout import SessionLayout
from app.routers.layout import LayoutAcceptBody
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


def test_session_layouts_cascade_when_session_is_deleted():
    session_fk = next(iter(SessionLayout.__table__.c.session_id.foreign_keys))
    job_fk = next(iter(SessionLayout.__table__.c.job_id.foreign_keys))
    assert session_fk.ondelete == "CASCADE"
    assert job_fk.ondelete == "CASCADE"

"""Terminal status follows Appendix C C4: partial when coverage is low or a stage failed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.job_outcome import job_status_after_success


def test_successful_job_status_is_succeeded():
    assert job_status_after_success() == "succeeded"


def test_low_coverage_or_failed_stage_is_partial():
    assert job_status_after_success({"overall": {"partial": True, "coverage": 0.9}}) == "partial"
    assert job_status_after_success({"overall": {"partial": False, "coverage": 0.22}}) == "partial"
    assert job_status_after_success({"overall": {"partial": False, "coverage": 0.8}}) == "succeeded"
    assert job_status_after_success({"overall": {"coverage": 0.9}}, stage_failed=True) == "partial"

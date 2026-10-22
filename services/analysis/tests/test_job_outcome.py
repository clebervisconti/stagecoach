"""Successful jobs end ready, not partial (Appendix C C4)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.job_outcome import job_status_after_success


def test_successful_job_status_is_succeeded():
    assert job_status_after_success() == "succeeded"

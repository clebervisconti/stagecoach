"""Terminal job/session status after a finished pipeline (Appendix C, C4)."""

from typing import Any, Optional

PARTIAL_COVERAGE = 0.6


def job_status_after_success(
    report: Optional[dict[str, Any]] = None,
    *,
    stage_failed: bool = False,
) -> str:
    """Return the analysis_jobs.status for a pipeline that did not crash.

    SPEC C4: the job is succeeded when coverage is high and no stage failed.
    Otherwise it is partial, and the session mapper writes `partial` instead
    of `ready`. A call with no report stays succeeded.
    """
    if stage_failed:
        return "partial"
    if not isinstance(report, dict):
        return "succeeded"
    overall = report.get("overall") or {}
    if overall.get("partial"):
        return "partial"
    coverage = overall.get("coverage")
    try:
        if coverage is not None and float(coverage) < PARTIAL_COVERAGE:
            return "partial"
    except (TypeError, ValueError):
        pass
    return "succeeded"

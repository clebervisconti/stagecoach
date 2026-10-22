"""Terminal job/session status after a finished pipeline (Appendix C, C4)."""


def job_status_after_success() -> str:
    """Return the analysis_jobs.status for a pipeline that did not fail.

    Successful jobs end `succeeded`. The session mapper writes `ready`.
    `overall.partial` on the report is a coverage flag, not the job outcome.
    """
    return "succeeded"

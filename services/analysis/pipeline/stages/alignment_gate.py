"""Optional WhisperX alignment for the live analysis job.

The live job keeps going when the alignment package or its models are absent.
"""

from pathlib import Path
from typing import Any


def run_live_alignment(
    *,
    audio_path: Path,
    transcript_path: Path,
    output_dir: Path,
    session_id: str,
    language: str,
) -> dict[str, Any]:
    try:
        from pipeline.stages.alignment import align_transcript
    except Exception as exc:
        return {
            "status": "skipped",
            "metrics": {"reason": "alignment_unavailable"},
            "error": {"type": type(exc).__name__, "message": str(exc)[:200]},
        }

    try:
        result = align_transcript(
            audio_path=audio_path,
            transcript_path=transcript_path,
            output_dir=output_dir,
            session_id=session_id,
            language=language,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "metrics": {"reason": "alignment_failed"},
            "error": {"type": type(exc).__name__, "message": str(exc)[:200]},
        }

    payload = result.to_dict()
    return {
        "status": "succeeded",
        "artifacts": {"alignment": str(output_dir / f"{session_id}_alignment.json")},
        "metrics": {
            "mean_alignment_score": payload.get("mean_alignment_score"),
            "aligned_words": len(payload.get("aligned_words") or []),
            "gap_fills_count": payload.get("gap_fills_count"),
        },
    }

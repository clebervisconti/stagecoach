"""Build the private-beta audio/text report view model.

This intentionally emits a partial report. It scores only observable signals
available from ASR and audio features; unavailable content/video categories are
marked N/A instead of being inferred.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import yaml

STAGE_VERSION = "1.0.0"
WORD_RE = re.compile(r"[\wÀ-ÿ'-]+", re.UNICODE)


def _clamp(value: float) -> int:
    return int(round(max(0.0, min(100.0, value))))


def _band_score(value: float, low: float, ideal_low: float, ideal_high: float, high: float) -> int:
    if ideal_low <= value <= ideal_high:
        return 95
    if value < ideal_low:
        if value <= low:
            return 25
        return _clamp(25 + (value - low) / (ideal_low - low) * 70)
    if value >= high:
        return 25
    return _clamp(95 - (value - ideal_high) / (high - ideal_high) * 70)


def _filler_score(rate: float) -> int:
    if rate <= 5:
        return 95
    if rate >= 12:
        return 25
    return _clamp(95 - (rate - 5) / 7 * 70)


def _pvq_score(value: float | None) -> int | None:
    if value is None:
        return None
    if 0.14 <= value <= 0.30:
        return 95
    if value < 0.14:
        return _clamp(15 + max(0.0, value - 0.06) / 0.08 * 80)
    return _clamp(95 - min(1.0, (value - 0.30) / 0.10) * 15)


def _load_lexicon(language: str, packages_dir: Path) -> dict[str, Any]:
    name = "pt-BR.yaml" if language.startswith("pt") else "en.yaml"
    return yaml.safe_load((packages_dir / "lexicons" / name).read_text())


def _flatten_words(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for segment in transcript.get("segments", []):
        for word in segment.get("words", []):
            token = str(word.get("word", "")).strip()
            if token:
                words.append(
                    {
                        "word": token,
                        "start": float(word.get("start", segment.get("start", 0))),
                        "end": float(word.get("end", segment.get("end", 0))),
                        "probability": float(word.get("probability", 0)),
                    }
                )
    return words


def _filler_hits(words: list[dict[str, Any]], fillers: list[str]) -> list[dict[str, Any]]:
    normalized = {item.casefold() for item in fillers}
    return [word for word in words if word["word"].strip(".,!?;:").casefold() in normalized]


def _series(prosody_path: Path) -> list[dict[str, float | None]]:
    table = pq.read_table(prosody_path, columns=["time_s", "f0_st", "intensity_db"])
    times = table["time_s"].to_numpy()
    f0_st = table["f0_st"].to_numpy()
    intensity = table["intensity_db"].to_numpy()
    if len(times) == 0:
        return []
    points: list[dict[str, float | None]] = []
    for second in range(int(math.ceil(float(times[-1])) + 1)):
        mask = (times >= second) & (times < second + 1)
        pitch = f0_st[mask]
        loudness = intensity[mask]
        points.append(
            {
                "t": float(second),
                "pitch_st": (
                    round(float(np.nanmedian(pitch)), 3)
                    if pitch.size and np.any(np.isfinite(pitch))
                    else None
                ),
                "intensity_db": (
                    round(float(np.nanmedian(loudness)), 3)
                    if loudness.size and np.any(np.isfinite(loudness))
                    else None
                ),
            }
        )
    return points


def build_mvp_report(
    *,
    session_id: str,
    context_type: str,
    language: str,
    slot_min: int | None,
    ingest: dict[str, Any],
    transcript_path: Path,
    audio_metrics_path: Path,
    prosody_path: Path,
    packages_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Create and persist an honest partial report for the private beta."""
    transcript = json.loads(transcript_path.read_text())
    audio = json.loads(audio_metrics_path.read_text())
    words = _flatten_words(transcript)
    speech_start = min((word["start"] for word in words), default=0.0)
    speech_end = max((word["end"] for word in words), default=float(transcript.get("duration", 0)))
    speech_span_s = max(1.0, speech_end - speech_start)
    lexical_words = sum(len(WORD_RE.findall(word["word"])) for word in words)
    wpm = lexical_words / speech_span_s * 60.0

    lexicon = _load_lexicon(language, packages_dir)
    fillers = _filler_hits(words, list(lexicon.get("filler_sounds", [])))
    filler_rate = len(fillers) / speech_span_s * 60.0
    duration_s = float(ingest["media_info"]["duration"])
    time_ratio = duration_s / (slot_min * 60) if slot_min else None
    pvq = audio.get("pvq_median")
    asr_confidence = float(transcript.get("mean_word_probability", 0))
    audio_cap = float(audio.get("confidence", {}).get("inclusion_cap", 1))
    confidence = round(min(asr_confidence, audio_cap), 3)

    metrics: list[dict[str, Any]] = [
        {
            "id": "pp_wpm",
            "label": "Words per minute",
            "value": round(wpm, 1),
            "unit": "wpm",
            "score": _band_score(wpm, 90, 130, 165, 210),
            "confidence": round(asr_confidence, 3),
            "basis": "heuristic",
            "source": "S13",
        },
        {
            "id": "fl_filler_sounds_per_min",
            "label": "Filler sounds",
            "value": round(filler_rate, 2),
            "unit": "/min",
            "score": _filler_score(filler_rate),
            "confidence": round(asr_confidence, 3),
            "basis": "research",
            "source": "S12",
        },
        {
            "id": "vv_pvq_median",
            "label": "Pitch variation",
            "value": pvq,
            "unit": "PVQ",
            "score": _pvq_score(pvq),
            "confidence": confidence,
            "basis": "research",
            "source": "S24",
        },
        {
            "id": "pp_boundary_pauses",
            "label": "Boundary pauses",
            "value": int(audio.get("pause_counts", {}).get("boundary", 0)),
            "unit": "count",
            "score": None,
            "confidence": confidence,
            "basis": "heuristic",
            "source": "heuristic",
        },
    ]
    if time_ratio is not None:
        metrics.append(
            {
                "id": "tm_pct_of_slot",
                "label": "Slot used",
                "value": round(time_ratio * 100, 1),
                "unit": "%",
                "score": _band_score(time_ratio, 0.5, 0.8, 1.0, 1.3),
                "confidence": 1.0,
                "basis": "heuristic",
                "source": "heuristic",
            }
        )

    scored = [metric for metric in metrics if metric["score"] is not None]
    overall = (
        round(sum(metric["score"] * metric["confidence"] for metric in scored) /
              sum(metric["confidence"] for metric in scored))
        if scored and sum(metric["confidence"] for metric in scored) > 0
        else None
    )

    evidence = [
        {
            "id": f"filler-{index + 1}",
            "metric_id": "fl_filler_sounds_per_min",
            "t_start": hit["start"],
            "t_end": hit["end"],
            "kind": "observation",
            "text": f'Filler sound: “{hit["word"]}”',
            "confidence": hit["probability"],
        }
        for index, hit in enumerate(fillers[:50])
    ]

    ranked = sorted(scored, key=lambda metric: metric["score"])
    opportunities = [
        {
            "metric_id": metric["id"],
            "title": {
                "pp_wpm": "Rehearse with pace checkpoints",
                "fl_filler_sounds_per_min": "Replace filler sounds with a pause",
                "vv_pvq_median": "Mark the words that deserve emphasis",
                "tm_pct_of_slot": "Rehearse against the target slot",
            }.get(metric["id"], "Practice this signal"),
            "score": metric["score"],
            "evidence_ids": [
                item["id"] for item in evidence if item["metric_id"] == metric["id"]
            ][:3],
        }
        for metric in ranked[:3]
    ]
    strengths = [
        {
            "metric_id": metric["id"],
            "title": {
                "pp_wpm": "Pace stayed in the target band",
                "fl_filler_sounds_per_min": "Few clear filler sounds",
                "vv_pvq_median": "Pitch showed useful variation",
                "tm_pct_of_slot": "Timing matched the target slot",
            }.get(metric["id"], "Strong measured signal"),
            "score": metric["score"],
        }
        for metric in sorted(scored, key=lambda metric: metric["score"], reverse=True)[:2]
        if metric["score"] >= 70
    ]

    warnings = []
    if audio.get("noise_flag"):
        warnings.append("Background noise reduced measurement confidence.")
    if audio.get("music_flag"):
        warnings.append("Background music makes vocal-variety scoring unavailable.")
    if asr_confidence < 0.6:
        warnings.append("Transcription confidence is low; verify the transcript.")

    report = {
        "version": STAGE_VERSION,
        "session_id": session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "partial": True,
        "coverage": round(len(scored) / 17, 3),
        "overall": overall,
        "confidence": confidence,
        "summary": (
            f"This partial audio/text report measured {lexical_words} words over "
            f"{speech_span_s / 60:.1f} minutes. Video, slides, and content judgments "
            "are not included in this private-beta report."
        ),
        "context_type": context_type,
        "language": language,
        "duration_s": duration_s,
        "quality": {
            "asr_mean_word_probability": round(asr_confidence, 3),
            "snr_db": audio.get("snr_db"),
            "warnings": warnings,
        },
        "metrics": metrics,
        "strengths": strengths,
        "opportunities": opportunities,
        "evidence": evidence,
        "transcript": transcript.get("segments", []),
        "series": _series(prosody_path),
        "unavailable_categories": [
            "core_message",
            "structure",
            "storytelling",
            "audience_adaptation",
            "opening_close",
            "clarity",
            "impact",
            "visual_aids",
            "gestures_body",
            "eye_contact",
            "facial_affect",
            "qa",
        ],
        "sources": ["S12", "S13", "S24", "S25", "heuristic"],
    }
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report

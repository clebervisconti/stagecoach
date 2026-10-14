"""Assemble Phase 1 metrics from ASR + audio-features artifacts and persist them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence

import yaml

from .confidence import asr_confidence, prosody_confidence
from .fluency import combined_filler_rate, compute_fluency_metrics, filler_benchmark_note
from .fluency_disambig import (
    confirmed_filler_word_objects,
    disambiguate_transcript,
    write_fluency_disambig,
)
from .pace import compute_pace_metrics
from .prosody import compute_prosody_metrics
from .timing import compute_timing_metrics
from .types import MetricBundle, PauseEvent, ProsodyFrame, SectionPlan, Word

STAGE_VERSION = "1.0.0"


def flatten_words(transcript: dict[str, Any]) -> list[Word]:
    words: list[Word] = []
    for segment in transcript.get("segments", []):
        for item in segment.get("words", []):
            token = str(item.get("word", "")).strip()
            if not token:
                continue
            words.append(
                Word(
                    text=token,
                    start=float(item.get("start", segment.get("start", 0))),
                    end=float(item.get("end", segment.get("end", 0))),
                    probability=float(item.get("probability", 0)),
                )
            )
    return words


def load_lexicon(language: str, packages_dir: Path) -> dict[str, Any]:
    name = "pt-BR.yaml" if language.startswith("pt") else "en.yaml"
    path = packages_dir / "lexicons" / name
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def frames_from_audio_metrics(
    audio: dict[str, Any],
    *,
    times: Optional[Sequence[float]] = None,
    f0_hz: Optional[Sequence[Optional[float]]] = None,
    f0_st: Optional[Sequence[Optional[float]]] = None,
    voiced: Optional[Sequence[bool]] = None,
    intensity_db: Optional[Sequence[Optional[float]]] = None,
) -> list[ProsodyFrame]:
    """Build frames from optional 10 ms tracks; otherwise synthesize from summaries."""
    if times and f0_hz and voiced is not None:
        out: list[ProsodyFrame] = []
        for i, t in enumerate(times):
            out.append(
                ProsodyFrame(
                    time_s=float(t),
                    f0_hz=f0_hz[i] if f0_hz else None,
                    f0_st=f0_st[i] if f0_st else None,
                    voiced=bool(voiced[i]),
                    intensity_db=intensity_db[i] if intensity_db else None,
                )
            )
        return out
    # Fallback: one synthetic 10-s voiced window so PVQ median can still run
    # when only audio_metrics.json is present (tests / smoke).
    return []


def pauses_from_json(payload: dict[str, Any]) -> list[PauseEvent]:
    return [
        PauseEvent(
            start=float(item["start"]),
            end=float(item["end"]),
            position=str(item.get("position", "unknown")),
        )
        for item in payload.get("pauses", [])
    ]


def compute_session_metrics(
    *,
    transcript: dict[str, Any],
    audio_metrics: dict[str, Any],
    pauses: Sequence[PauseEvent],
    frames: Sequence[ProsodyFrame],
    lexicon: dict[str, Any],
    slot_s: Optional[float] = None,
    planned_qa_s: float = 0.0,
    sections: Sequence[SectionPlan] = (),
    confirmed_filler_words: Sequence[Word] = (),
    grammar_level: Optional[float] = None,
    expected_speech_duration_s: Optional[float] = None,
) -> MetricBundle:
    """Pure assembly of every Phase 1 voice/time sub-metric."""
    words = flatten_words(transcript)
    if not words and transcript.get("word_count"):
        # Synthetic smoke transcripts may only have segments without word boxes.
        text = " ".join(seg.get("text", "") for seg in transcript.get("segments", []))
        tokens = [tok for tok in text.split() if tok]
        duration = float(transcript.get("duration") or audio_metrics.get("duration_s") or 0)
        step = duration / max(len(tokens), 1)
        words = [
            Word(text=tok, start=i * step, end=(i + 1) * step, probability=float(transcript.get("mean_word_probability", 1)))
            for i, tok in enumerate(tokens)
        ]

    span = 0.0
    if words:
        span = max(w.end for w in words) - min(w.start for w in words)
    transcribed = span
    expected = expected_speech_duration_s
    if expected is None:
        expected = float(audio_metrics.get("duration_s") or span or 0.0)

    asr_c = asr_confidence(
        words,
        transcribed_duration_s=transcribed,
        expected_speech_duration_s=expected if expected else 0.0,
    )
    prosody_c = prosody_confidence(
        voiced_ratio=float(audio_metrics.get("voiced_ratio") or 0.0),
        snr_db=audio_metrics.get("snr_db"),
        octave_error_ratio=float(audio_metrics.get("octave_jump_ratio") or 0.0),
    )
    if audio_metrics.get("confidence", {}).get("snr_below_15db"):
        prosody_c = min(prosody_c, 0.5)

    language = str(transcript.get("language") or "en")
    filler_preserving = not language.startswith("pt")  # tiny/faster-whisper is weak on pt fillers

    pace = compute_pace_metrics(
        words,
        pauses,
        filler_sounds=list(lexicon.get("filler_sounds", [])),
        syllable_count=int(audio_metrics.get("syllable_count") or 0),
        phonation_time_s=float(audio_metrics.get("phonation_time_s") or 0.0),
        confidence=asr_c,
    )
    fluency = compute_fluency_metrics(
        words,
        filler_sounds=list(lexicon.get("filler_sounds", [])),
        confirmed_filler_words=confirmed_filler_words,
        hedges=list(lexicon.get("hedges", [])),
        apologies=list(lexicon.get("apologies", [])),
        grammar_level=grammar_level,
        confidence=asr_c,
        filler_preserving_asr=filler_preserving,
    )
    prosody = compute_prosody_metrics(
        frames,
        duration_s=float(audio_metrics.get("duration_s") or span or 0.0),
        confidence=prosody_c,
        music_flag=bool(audio_metrics.get("music_flag")),
    )
    # When frames are missing (smoke / parquet not loaded), fall back to stage summaries.
    if not frames:
        if audio_metrics.get("pvq_median") is not None:
            from .types import MetricResult

            prosody["vv_pvq_median"] = MetricResult(
                id="vv_pvq_median",
                value=float(audio_metrics["pvq_median"]),
                unit="ratio",
                basis="research",
                source="S24",
                confidence=prosody_c,
            )
        if audio_metrics.get("pitch_range_st_median") is not None:
            from .types import MetricResult

            prosody["vv_pitch_range_st"] = MetricResult(
                id="vv_pitch_range_st",
                value=float(audio_metrics["pitch_range_st_median"]),
                unit="semitones",
                basis="heuristic",
                source="H",
                confidence=prosody_c,
            )
        if audio_metrics.get("monotone_windows_ratio") is not None:
            from .types import MetricResult

            prosody["vv_monotone_windows_ratio"] = MetricResult(
                id="vv_monotone_windows_ratio",
                value=float(audio_metrics["monotone_windows_ratio"]),
                unit="ratio",
                basis="heuristic",
                source="H",
                confidence=prosody_c,
            )
        if audio_metrics.get("intensity_sd_db_median") is not None:
            from .types import MetricResult

            prosody["vv_intensity_variation_db"] = MetricResult(
                id="vv_intensity_variation_db",
                value=float(audio_metrics["intensity_sd_db_median"]),
                unit="decibels",
                basis="heuristic",
                source="H",
                confidence=min(prosody_c, 0.7),
            )
        if audio_metrics.get("emphasis_rate_per_min") is not None:
            from .types import MetricResult

            prosody["vv_emphasis_rate_per_min"] = MetricResult(
                id="vv_emphasis_rate_per_min",
                value=float(audio_metrics["emphasis_rate_per_min"]),
                unit="per_minute",
                basis="heuristic",
                source="H",
                confidence=prosody_c,
            )

    rush = pace["pp_rush_index"].value
    timing = compute_timing_metrics(
        speaking_span_s=span,
        slot_s=slot_s,
        planned_qa_s=planned_qa_s,
        sections=sections,
        rush_index=rush,
        confidence=1.0 if slot_s else 0.0,
    )

    metrics = {**pace, **prosody, **fluency, **timing}
    combined = combined_filler_rate(
        fluency["fl_filler_sounds_per_min"].value,
        fluency["fl_filler_words_per_min"].value,
    )
    return MetricBundle(
        metrics=metrics,
        asr_confidence=asr_c,
        prosody_confidence=prosody_c,
        combined_filler_rate_per_min=combined,
        filler_benchmark=filler_benchmark_note(combined),
    )


def persist_session_metrics(
    *,
    output_dir: Path,
    transcript_path: Path,
    audio_metrics_path: Path,
    pauses_path: Optional[Path] = None,
    packages_dir: Path,
    slot_s: Optional[float] = None,
) -> Path:
    """Write `metrics.json` next to the other stage artifacts."""
    transcript = json.loads(transcript_path.read_text()) if transcript_path.exists() else {}
    audio = json.loads(audio_metrics_path.read_text()) if audio_metrics_path.exists() else {}
    pauses_payload = json.loads(pauses_path.read_text()) if pauses_path and pauses_path.exists() else {}
    language = str(transcript.get("language") or "en")
    lexicon = load_lexicon(language, packages_dir)
    sidecar = disambiguate_transcript(transcript, lexicon)
    write_fluency_disambig(output_dir / "fluency_disambig.json", sidecar)
    bundle = compute_session_metrics(
        transcript=transcript,
        audio_metrics=audio,
        pauses=pauses_from_json(pauses_payload),
        frames=[],
        lexicon=lexicon,
        slot_s=slot_s,
        confirmed_filler_words=confirmed_filler_word_objects(transcript, sidecar),
    )
    dest = output_dir / "metrics.json"
    payload = {
        "version": STAGE_VERSION,
        "scoring_config_version": "1.0.0",
        **bundle.to_dict(),
    }
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest

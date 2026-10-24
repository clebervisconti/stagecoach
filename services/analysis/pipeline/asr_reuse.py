"""Reuse ASR when a later job analyses the same audio window (F6)."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

ASR_STAGE_VERSION = "1.0.0"


def window_key(window: Optional[dict[str, Any]]) -> str:
    if not window:
        return "full"
    return f"{float(window['start_s']):.3f}-{float(window['end_s']):.3f}"


def windows_unchanged(left: Optional[dict[str, Any]], right: Optional[dict[str, Any]], tolerance: float = 0.05) -> bool:
    if not left and not right:
        return True
    if not left or not right:
        return False
    return abs(float(left["start_s"]) - float(right["start_s"])) <= tolerance and abs(
        float(left["end_s"]) - float(right["end_s"])
    ) <= tolerance


def asr_input_sha(
    language: str,
    window: Optional[dict[str, Any]],
    *,
    stage_version: str = ASR_STAGE_VERSION,
) -> str:
    payload = {"language": language or "auto", "window": window_key(window), "stage_version": stage_version}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def ffmpeg_cut_command(src: Path, dest: Path, start_s: float, end_s: float) -> list[str]:
    """Argv only. Start and end are numbers, never interpolated into a filter graph."""
    return [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{float(start_s):.3f}",
        "-to",
        f"{float(end_s):.3f}",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(dest),
    ]


def cut_wav(src: Path, dest: Path, start_s: float, end_s: float, runner: Optional[Callable] = None) -> Path:
    import subprocess

    dest.parent.mkdir(parents=True, exist_ok=True)
    command = ffmpeg_cut_command(src, dest, start_s, end_s)
    run = runner or subprocess.run
    run(command, check=True, capture_output=True, timeout=180)
    return dest


def _shift_value(value: Any, offset_s: float) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value) + offset_s, 3)
    return value


def shift_transcript_times(document: dict[str, Any], offset_s: float) -> dict[str, Any]:
    """Move word and segment times from window-local time back to source time."""
    shifted = json.loads(json.dumps(document))
    if offset_s == 0:
        return shifted
    for segment in shifted.get("segments") or []:
        for key in ("start", "end", "t_start", "t_end"):
            if key in segment and isinstance(segment[key], (int, float)):
                segment[key] = _shift_value(segment[key], offset_s)
        for word in segment.get("words") or []:
            for key in ("start", "end", "t_start", "t_end"):
                if key in word and isinstance(word[key], (int, float)):
                    word[key] = _shift_value(word[key], offset_s)
    for word in shifted.get("words") or []:
        for key in ("start", "end", "t_start", "t_end"):
            if key in word and isinstance(word[key], (int, float)):
                word[key] = _shift_value(word[key], offset_s)
    if isinstance(shifted.get("duration"), (int, float)):
        shifted["duration"] = _shift_value(shifted["duration"], offset_s)
    shifted["window_offset_s"] = offset_s
    return shifted


def _stored_window(job_dir: Path) -> Optional[dict[str, Any]]:
    marker = job_dir / "asr_input.json"
    if marker.is_file():
        data = json.loads(marker.read_text())
        window = data.get("window")
        return window if isinstance(window, dict) else None
    layout = job_dir / "layout.json"
    if layout.is_file():
        window = json.loads(layout.read_text()).get("analysis_window")
        return window if isinstance(window, dict) else None
    return None


def find_reusable_transcript(
    session_dir: Path,
    job_dir: Path,
    sha: str,
    window: Optional[dict[str, Any]],
) -> Optional[Path]:
    if not session_dir.is_dir():
        return None
    current = job_dir.resolve()
    for child in sorted(session_dir.iterdir()):
        if not child.is_dir() or child.resolve() == current:
            continue
        transcript = child / "transcript.json"
        if not transcript.is_file():
            continue
        marker = child / "asr_input.json"
        if marker.is_file():
            data = json.loads(marker.read_text())
            if data.get("sha") == sha:
                return transcript
            continue
        if windows_unchanged(_stored_window(child), window):
            return transcript
    return None


def _stats(document: dict[str, Any]) -> tuple[str, int, float]:
    language = str(document.get("language") or "en")
    words = document.get("words") or []
    if not words:
        for segment in document.get("segments") or []:
            words.extend(segment.get("words") or [])
    count = int(document.get("word_count") or len(words) or 0)
    if words:
        probs = [float(word.get("probability") or word.get("p") or 0) for word in words]
        mean = sum(probs) / len(probs)
    else:
        mean = float(document.get("mean_word_probability") or 0)
    return language, count, mean


def write_asr_marker(job_dir: Path, *, sha: str, language: str, window: Optional[dict[str, Any]]) -> None:
    (job_dir / "asr_input.json").write_text(
        json.dumps(
            {
                "sha": sha,
                "language": language,
                "window": window,
                "stage_version": ASR_STAGE_VERSION,
            },
            indent=2,
        )
        + "\n"
    )


@dataclass
class AsrResolution:
    reused: bool
    language: str
    word_count: int
    mean_word_probability: float
    transcript_path: Path
    input_sha: str
    window_offset_s: float


def resolve_asr(
    *,
    session_dir: Path,
    job_dir: Path,
    language: str,
    asr_language: Optional[str],
    window: Optional[dict[str, Any]],
    audio_path: Path,
    session_id: str,
    allow_reuse: bool,
    transcribe: Optional[Callable[..., Any]] = None,
    cut_audio: Optional[Callable[..., Path]] = None,
) -> AsrResolution:
    """Transcribe, or copy a previous transcript when the window and language match."""
    sha = asr_input_sha(language, window)
    job_dir.mkdir(parents=True, exist_ok=True)
    reusable = find_reusable_transcript(session_dir, job_dir, sha, window) if allow_reuse else None
    if reusable is not None:
        target = job_dir / "transcript.json"
        if reusable.resolve() != target.resolve():
            shutil.copyfile(reusable, target)
        document = json.loads(target.read_text())
        lang, count, mean = _stats(document)
        write_asr_marker(job_dir, sha=sha, language=language, window=window)
        return AsrResolution(
            reused=True,
            language=lang,
            word_count=count,
            mean_word_probability=mean,
            transcript_path=target,
            input_sha=sha,
            window_offset_s=float(window["start_s"]) if window else 0.0,
        )

    source = audio_path
    offset = 0.0
    if window:
        offset = float(window["start_s"])
        window_audio = job_dir / "audio_window.wav"
        cutter = cut_audio or cut_wav
        source = cutter(audio_path, window_audio, float(window["start_s"]), float(window["end_s"]))

    if transcribe is None:
        from pipeline.stages.asr import transcribe_audio

        transcribe = transcribe_audio
    transcribe(
        audio_path=source,
        output_dir=job_dir,
        session_id=session_id,
        language=asr_language,
    )
    target = job_dir / "transcript.json"
    if offset:
        document = shift_transcript_times(json.loads(target.read_text()), offset)
        target.write_text(json.dumps(document, indent=2) + "\n")
    document = json.loads(target.read_text())
    lang, count, mean = _stats(document)
    write_asr_marker(job_dir, sha=sha, language=language, window=window)
    return AsrResolution(
        reused=False,
        language=lang,
        word_count=count,
        mean_word_probability=mean,
        transcript_path=target,
        input_sha=sha,
        window_offset_s=offset,
    )

#!/usr/bin/env python3
"""Measure ingest → ASR → audio-features → fusion → report wall time.

Public repo: no personal recordings. Default source is a 16 kHz mono sine (CC0).
Pass --speech to use espeak-ng synthetic speech when the binary is installed.

Usage:
  python scripts/bench_phase1_cpu.py --seconds 600 --language en --out /tmp/bench-en.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "scoring"))
sys.path.insert(0, str(ROOT / "services" / "analysis"))


def cpu_info() -> dict:
    model = None
    cpus = os.cpu_count()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text().splitlines():
            if line.lower().startswith("model name"):
                model = line.split(":", 1)[1].strip()
                break
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "model_name": model,
        "cpu_count": cpus,
    }


def write_sine_wav(path: Path, seconds: float, sample_rate: int = 16000) -> None:
    import math
    import struct

    n = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n):
            value = int(8000 * math.sin(2 * math.pi * 220 * (i / sample_rate)))
            frames.extend(struct.pack("<h", value))
        handle.writeframes(frames)


def write_espeak_wav(path: Path, seconds: float, language: str) -> str | None:
    binary = shutil.which("espeak-ng") or shutil.which("espeak")
    if not binary:
        return None
    voice = "pt-br" if language.lower().startswith("pt") else "en"
    if language.lower().startswith("pt"):
        paragraph = (
            "Olá, então vamos começar. Isto é um tipo de reunião. Legal né. "
            "O plano é claro e o tipo de evidência importa. Então seguimos."
        )
    else:
        paragraph = (
            "Hello everyone. So we will begin. This looks like a plan. "
            "I was like, wait, and then we continue the talk with measured evidence."
        )
    repeats = max(1, int(seconds / 8))
    text = " ".join([paragraph] * repeats)
    cmd = [
        binary,
        "-v",
        voice,
        "-s",
        "140",
        "-w",
        str(path),
        text,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return binary


def timed(name: str, records: list[dict], fn):
    started = time.perf_counter()
    try:
        result = fn()
        elapsed = time.perf_counter() - started
        records.append({"stage": name, "seconds": round(elapsed, 3), "ok": True, "error": None})
        return result
    except Exception as exc:  # noqa: BLE001 — bench must record the failure
        elapsed = time.perf_counter() - started
        records.append({"stage": name, "seconds": round(elapsed, 3), "ok": False, "error": f"{type(exc).__name__}: {exc}"})
        raise


def run_bench(seconds: float, language: str, speech: bool, model_name: str) -> dict:
    from pipeline.stages.asr import transcribe_audio
    from pipeline.stages.audio_features import extract_audio_features
    from pipeline.stages.fusion_scoring import run_fusion_scoring
    from pipeline.stages.ingest import ingest
    from pipeline.stages.report import run_report_stage
    from metrics.compute import persist_session_metrics

    records: list[dict] = []
    source = "sine_cc0"
    transcript = None
    analysis: dict | None = None
    audio = None
    with tempfile.TemporaryDirectory(prefix="stagecoach-bench-") as tmp:
        tmp_path = Path(tmp)
        wav = tmp_path / "input.wav"
        if speech:
            used = write_espeak_wav(wav, seconds, language)
            if used:
                source = f"espeak:{used}"
            else:
                write_sine_wav(wav, seconds)
                source = "sine_cc0_espeak_missing"
        else:
            write_sine_wav(wav, seconds)
        duration = None
        with wave.open(str(wav), "rb") as handle:
            duration = handle.getnframes() / float(handle.getframerate())
        out = tmp_path / "out"
        out.mkdir()
        session_id = "bench-phase1-36"
        try:
            ingest_out = timed("ingest", records, lambda: ingest(wav, out, session_id))
            audio16k = Path(ingest_out.artifacts["audio16k"])
            os.environ.setdefault("CI", "true")
            transcript = timed(
                "asr",
                records,
                lambda: transcribe_audio(
                    audio16k,
                    out,
                    session_id,
                    language="pt" if language.lower().startswith("pt") else "en",
                    model_name=model_name,
                ),
            )
            audio = timed(
                "audio_features",
                records,
                lambda: extract_audio_features(
                    audio_path=audio16k,
                    output_dir=out,
                    session_id=session_id,
                    transcript_path=out / "transcript.json",
                ),
            )
            timed(
                "metrics",
                records,
                lambda: persist_session_metrics(
                    output_dir=out,
                    transcript_path=out / "transcript.json",
                    audio_metrics_path=Path(audio.artifacts["audio_metrics"]),
                    pauses_path=out / "pauses.json",
                    packages_dir=ROOT / "packages",
                    slot_s=seconds,
                ),
            )
            analysis = timed(
                "fusion_scoring",
                records,
                lambda: run_fusion_scoring(
                    session_id=session_id,
                    output_dir=out,
                    context_type="keynote",
                    language="pt-BR" if language.lower().startswith("pt") else "en",
                    slot_min=max(1, int(seconds / 60)),
                    qa_in_slot=False,
                    camera_setup="audio_only",
                    transcript_path=out / "transcript.json",
                    audio_metrics_path=Path(audio.artifacts["audio_metrics"]),
                    metrics_path=out / "metrics.json",
                    packages_dir=ROOT / "packages",
                ),
            )
            timed(
                "report",
                records,
                lambda: run_report_stage(output_dir=out, analysis=analysis, packages_dir=ROOT / "packages"),
            )
        except Exception as exc:  # noqa: BLE001 — keep stage timings even if a later stage fails
            failed = f"{type(exc).__name__}: {exc}"
        else:
            failed = None
        disambig = {}
        sidecar = out / "fluency_disambig.json"
        if sidecar.is_file():
            disambig = json.loads(sidecar.read_text())
        tokens = sorted(
            {item.get("token") for item in disambig.get("disambiguations") or [] if item.get("token")}
        )
        overall = (analysis or {}).get("overall") or {}
        wall = sum(item["seconds"] for item in records if item["ok"])
        result = {
            "ok": failed is None and all(item["ok"] for item in records),
            "error": failed,
            "target_seconds": seconds,
            "measured_audio_seconds": duration,
            "language": language,
            "source": source,
            "asr_model": model_name,
            "cpu": cpu_info(),
            "stages": records,
            "wall_seconds": round(wall, 3),
            "within_15_min": wall <= 900,
            "overall_score": overall.get("score"),
            "disambiguation_tokens": tokens,
            "transcript_words": getattr(transcript, "word_count", None),
        }
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1 CPU wall-time bench")
    parser.add_argument("--seconds", type=float, default=600.0)
    parser.add_argument("--language", default="en", choices=["en", "pt-BR", "pt"])
    parser.add_argument("--speech", action="store_true", help="Use espeak-ng if installed")
    parser.add_argument("--model", default="tiny", help="faster-whisper model (dev CPU profile uses tiny)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        payload = run_bench(args.seconds, args.language, args.speech, args.model)
    except Exception as exc:  # noqa: BLE001
        payload = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "cpu": cpu_info(),
            "target_seconds": args.seconds,
            "language": args.language,
            "asr_model": args.model,
        }
    payload["script_wall_seconds"] = round(time.perf_counter() - started, 3)
    text = json.dumps(payload, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

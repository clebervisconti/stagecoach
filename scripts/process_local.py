#!/usr/bin/env python3
"""Run a local fixture through fusion scoring, or compare golden outputs.

Usage:
  python scripts/process_local.py --golden
  python scripts/process_local.py --write-expected
  python scripts/process_local.py path/to/fixture-dir
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "scoring"))
sys.path.insert(0, str(ROOT / "services" / "analysis"))

from tests.golden.build import fixtures, run_fusion_for, write_all
from tests.golden.compare import compare_results
from tests.golden.audio import read_wav_meta


def _load_expected(fixture_id: str) -> dict:
    path = ROOT / "services" / "analysis" / "tests" / "golden" / "fixtures" / fixture_id / "expected" / "analysis_result.json"
    if not path.is_file():
        raise SystemExit(f"missing golden expected file: {path}")
    return json.loads(path.read_text())


def run_golden() -> int:
    write_all(with_expected=False)
    failed = 0
    for spec in fixtures():
        wav = ROOT / "services" / "analysis" / "tests" / "golden" / "fixtures" / spec["id"] / "audio.wav"
        if not wav.is_file():
            print(f"FAIL {spec['id']}: audio.wav missing")
            failed += 1
            continue
        meta = read_wav_meta(wav)
        if meta["sample_rate"] != 16000 or meta["channels"] != 1:
            print(f"FAIL {spec['id']}: audio.wav is not 16 kHz mono")
            failed += 1
            continue
        actual = run_fusion_for(spec)
        expected = _load_expected(spec["id"])
        errors = compare_results(actual, expected)
        if spec["kind"] == "noisy":
            overall = actual.get("overall") or {}
            if overall.get("score") is not None:
                errors.append(f"noisy overall.score should be excluded, got {overall.get('score')}")
            if float(overall.get("confidence") or 0) >= 0.5:
                errors.append(
                    f"noisy overall.confidence should be Low (< 0.5), got {overall.get('confidence')}"
                )
            snr = (actual.get("quality") or {}).get("snr_db")
            if snr is None or float(snr) > 10.0001:
                errors.append(f"noisy snr_db should be 10, got {snr}")
        if errors:
            print(f"FAIL {spec['id']}")
            for err in errors:
                print(f"  {err}")
            failed += 1
        else:
            overall = actual.get("overall") or {}
            print(
                f"PASS {spec['id']} language={spec['language']} kind={spec['kind']} "
                f"overall={overall.get('score')} confidence={overall.get('confidence')}"
            )
    if failed:
        print(f"{failed} golden fixture(s) failed")
        return 1
    print("all golden fixtures passed (±2 scores, ±5% metrics)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage Coach local fixture runner")
    parser.add_argument("--golden", action="store_true", help="Compare committed golden fixtures")
    parser.add_argument("--write-expected", action="store_true", help="Regenerate fixture files and expected JSON")
    parser.add_argument("path", nargs="?", help="Optional fixture directory (unused with --golden)")
    args = parser.parse_args()
    if args.write_expected:
        written = write_all(with_expected=True)
        for path in written:
            print(f"wrote {path}")
        return 0
    if args.golden or args.path is None:
        return run_golden()
    print(f"single-path mode is not implemented; use --golden ({args.path})")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

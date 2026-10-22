#!/usr/bin/env python3
"""Skeleton bench for online-session stages against spec §13 (E0-6).

Prints per-stage budgets. Optional `--run` times fixture generation and a
local ingest of `composite_pip_tr`. Layout, crops, and later stages stay
placeholders until O1+ implement them.

Usage:
  python scripts/bench_online_cpu.py
  python scripts/bench_online_cpu.py --run --out /tmp/bench-online.json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "analysis"))

# Spec §13 budgets, 60-min 1080p composite on LION (linux/arm64).
BUDGETS_S = {
    "ingest": 240,
    "layout": 90,
    "region_crops": 240,
    "vision_camera_crop": None,
    "screen_flow": 180,
    "camera_presence": 20,
    "production_quality": 60,
    "online_flow_v1": 90,
}


def cpu_info() -> dict:
    model = None
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text().splitlines():
            if line.lower().startswith("model name"):
                model = line.split(":", 1)[1].strip()
                break
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": __import__("os").cpu_count(),
        "model_name": model,
    }


def _time_generate(tmp: Path) -> float:
    from tests.online.generate_online_fixtures import generate_one

    started = time.perf_counter()
    generate_one("composite_pip_tr", tmp)
    return time.perf_counter() - started


def _time_ingest(source: Path, dest: Path) -> float:
    from pipeline.stages.ingest import ingest

    dest.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    ingest(source, dest, "bench-online")
    return time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Time fixture generate + ingest")
    parser.add_argument("--out", type=Path, help="Write JSON timings")
    args = parser.parse_args()

    result = {
        "host": cpu_info(),
        "budgets_s": BUDGETS_S,
        "measured_s": {},
        "notes": (
            "O0 skeleton. layout/region_crops/screen_flow/camera_presence/"
            "production_quality/online_flow_v1 are not timed until those stages exist."
        ),
    }
    print("Stage                 budget_s  measured_s")
    print("------------------------------------------")
    if args.run:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gen_s = _time_generate(tmp_path)
            source = tmp_path / "composite_pip_tr" / "source.mp4"
            ingest_s = _time_ingest(source, tmp_path / "ingest")
            result["measured_s"]["fixture_generate"] = round(gen_s, 3)
            result["measured_s"]["ingest"] = round(ingest_s, 3)
    for name, budget in BUDGETS_S.items():
        measured = result["measured_s"].get(name)
        budget_txt = f"{budget:>8}" if budget is not None else "   n/a  "
        measured_txt = f"{measured:10.3f}" if measured is not None else "       n/a"
        print(f"{name:<20} {budget_txt} {measured_txt}")
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

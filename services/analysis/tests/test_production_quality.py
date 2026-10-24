"""Integrated loudness comes from the ebur128 summary, not the -70 progress floor."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.stages.production_quality import parse_ebur128


def test_summary_loudness_is_kept_and_the_silence_floor_is_not():
    log = """
[Parsed_ebur128_0 @ 0x1] t: 0.1    M: -70.0 S: -70.0     I: -70.0 LUFS
[Parsed_ebur128_0 @ 0x1] t: 35.0   M: -19.0 S: -18.8     I: -18.7 LUFS
[Parsed_ebur128_0 @ 0x1] Summary:
  Integrated loudness:
    I:         -18.6 LUFS
    Threshold: -28.6 LUFS
  True peak:
    Peak:       -1.2 dBFS
"""
    lufs, peak = parse_ebur128(log)
    assert lufs == pytest.approx(-18.6)
    assert peak == pytest.approx(-1.2)

    silent, silent_peak = parse_ebur128(
        "Summary:\n  Integrated loudness:\n    I:         -70.0 LUFS\n  True peak:\n    Peak: -70.0 dBFS\n"
    )
    assert silent is None
    assert silent_peak == pytest.approx(-70.0)

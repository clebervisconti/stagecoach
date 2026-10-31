"""E3-1: 1 Hz activity classes on synthetic frames."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.screen.activity import activity_from_grays, read_activity_parquet, write_activity_parquet
from tests.online.screen_frames import (
    content_frames,
    motion_frames,
    pointer_frames,
    scroll_frames,
    static_frames,
    typing_frames,
)

MANIFEST = Path(__file__).parent / "fixtures" / "screen_flow_manifest.json"


def _labeled(frames, label: str):
    rows = activity_from_grays(frames)
    return [(row, label) for row in rows]


def test_class_accuracy_meets_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    labeled = []
    labeled.extend(_labeled(static_frames(8), "static"))
    labeled.extend(_labeled(pointer_frames(8), "pointer"))
    labeled.extend(_labeled(scroll_frames(10), "scroll"))
    labeled.extend(_labeled(typing_frames(8), "typing"))
    labeled.extend(_labeled(motion_frames(8), "motion"))
    content = activity_from_grays(content_frames())
    labeled.append((content[0], "content_change"))
    for row in content[1:]:
        labeled.append((row, "static"))

    mismatches = [
        (row["t"], row["cls"], expected, row["changed_ratio"], row["bbox_area"], row["v_shift"], row["v_response"])
        for row, expected in labeled
        if row["cls"] != expected
    ]
    accuracy = 1.0 - (len(mismatches) / len(labeled))
    assert accuracy >= manifest["class_accuracy_min"], mismatches


def test_activity_parquet_columns(tmp_path: Path):
    rows = activity_from_grays(static_frames(4))
    path = tmp_path / "screen_activity.parquet"
    write_activity_parquet(path, rows)
    restored = read_activity_parquet(path)
    assert list(restored[0]) == ["t", "changed_ratio", "bbox_area", "cls"]
    assert restored[0]["cls"] == "static"

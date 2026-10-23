"""Corrected boxes drive the crop. The longest span wins when the layout changes."""

from pipeline.layout.crop import dominant_region, regions_for


def test_dominant_region_uses_the_saved_longer_box():
    layout = {
        "segments": [
            {
                "t_start": 0,
                "t_end": 20,
                "regions": [{"id": "a", "role": "camera", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
            },
            {
                "t_start": 20,
                "t_end": 100,
                "regions": [{"id": "b", "role": "camera", "x": 0.7, "y": 0.0, "w": 0.25, "h": 0.3}],
            },
        ]
    }
    chosen = dominant_region(layout, "camera")
    assert chosen is not None
    assert chosen["id"] == "b"
    assert chosen["x"] == 0.7
    assert len(regions_for(layout, "camera")) == 2
    assert regions_for(layout, "screen") == []

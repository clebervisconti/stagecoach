"""Screen activity, transitions, segment types, and flow metrics (spec §9.5–§9.7)."""

from pipeline.screen.activity import activity_from_grays, activity_from_video
from pipeline.screen.classify import classify_segments
from pipeline.screen.flow import build_screen_flow
from pipeline.screen.transitions import accept_transitions

__all__ = [
    "accept_transitions",
    "activity_from_grays",
    "activity_from_video",
    "build_screen_flow",
    "classify_segments",
]

# ADR-069: Session state machine for online modes

**Date:** 2026-10-22  
**Status:** Accepted  
**Phase:** O0 (decision only; implementation is O1)

## Decision

Online uploads add `preparing` and `layout_review`. SSE may emit `waiting`. Analysis can `skip_ingest` after layout. Stage uploads still enqueue `run_mvp_analysis` directly.

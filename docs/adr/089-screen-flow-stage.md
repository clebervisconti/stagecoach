# ADR-089: Screen-flow measurement for online modes

**Date:** 2026-10-31
**Status:** Accepted
**Phase:** O3

## Context

ADR-064 says screen-flow numbers describe delivery and never whether a slide is true. OD-1 through OD-10 are approved as the spec records them (22 Oct 2026). OD-5 allows the factual-correctness guard. That guard's prompt edit is E3-8 and is not part of this stage.

E3-1 through E3-4 need a backend measurement: 1 Hz activity, debounced transitions, segment types, alignment, dead air, and silent demo. E3-5 scoring, the Screen & Flow tab, `online_flow_v1`, and the prompt version bump wait on design. `screen_flow` and `online_engagement` stay N/A in fusion until E3-5. YouTube and Vimeo link analysis stays off (OD-2). `ONLINE_MODES_ENABLED` stays off until O4.

## Decision

- Run a `screen_flow` job step after slides and before `content_llm`, only when `delivery_mode` is webinar, online talk, or recorded video. Stage mode does not gain a step and does not run the stage. Audio-only and a missing screen file skip the step. A failure is recorded and scoring continues.
- Activity is 1 Hz on a 640 px gray frame blurred with σ = 1. A coherent vertical shift (phase correlation, at least 8 px and response at least 0.12) is scroll even when most pixels change, so a full-frame scroll is not a slide cut. An unrelated cut rarely has that response, so it stays `content_change`. A thin band is typing only when it persists at least 3 seconds.
- Transitions are the union of SSIM below 0.85 (Gaussian-window SSIM on 320 px gray, OpenCV and numpy, no new dependency) and PySceneDetect `ContentDetector(27)`. Candidates closer than 2 seconds keep the lowest SSIM. A cut is dropped when the change box is under 0.25 of the frame, or when at least half of the ±2 s window is scroll or typing, or when the next two seconds are not stable (SSIM at least 0.95). Match tolerance for the acceptance test is 1.0 second because the grid is 1 Hz.
- Segment priority: VIDEO when motion is at least 60% and a run with change ratio at least 0.15 lasts at least 5 seconds; else DEMO when scroll or typing is at least 25% or three content changes fall inside 30 seconds; else SLIDE when static plus pointer is at least 80% and the frame has text or a deck page. A pointer on a text slide stays SLIDE. The cut second is left out of the mix. Online `slides.json` scenes are replaced from these segments so the existing Slides tab and visual-aids file keep their shape. The stored glance is reused. This stage does not call a language model.
- Dead air is VAD non-speech of at least 4 seconds (webinar and online talk) or 2.5 seconds (recorded video) while the screen is static, IDLE, or `no_video`. Silent demo stays at 8 seconds of pointer, scroll, typing, or content change inside a DEMO with no speech (§9.6). A 6 second scroll gap counts as neither. Scenario 7's three dead-air events are 6 second static silences on a 600 second window (3.0 per 10 minutes). The scroll silence in that fixture is 8 seconds so the ratio is above zero.
- Narration alignment uses content words of at least 5 characters, stopwords removed, matched on a 5-character prefix. The lead is the first time two screen terms are spoken at or after the segment start. A segment counts as aligned when two terms are spoken between 2 seconds before the start and the end. Words with probability under 0.4 whose midpoint sits in a VAD non-speech span of at least 2 seconds are dropped before that match. Dead air uses VAD, so those words cannot fill a silence. If VAD is missing, dead air and silent demo are not applicable (`vad_missing`) and nothing is dropped.
- The artifact is `screen_flow.json` (Appendix B.2) plus `screen_activity.parquet` (`t`, `changed_ratio`, `bbox_area`, `cls`). `content_judgment` is always false. Migration `014_screen_flow` stores the document and segments for export and deletion, cascading with the session and the job. The file is the source of truth. A database error does not fail the job. `GET /api/v1/sessions/{id}/screens` reads the file. A missing file is `404 {"reason":"not_measured"}`. Keyframe URLs are signed the same way as layout previews and must stay inside the job directory. Reads stay on the user rate-limit bucket.
- OCR of keyframes stops at 150 frames. The pass stops at about 170 seconds and sets `quality.truncated`. PySceneDetect runs only when time remains; otherwise `transition_engine` is `ssim`.
- `check_for_content_judgment` can see the banned phrases, including `wrong` unless the next word is slide, screen, or order. It is not wired to prompts, drops, or a fallback. That wiring is E3-7.

## Alternatives considered

- Treat every large pixel change as a cut. A scroll of a page would become a slide change.
- Count a 6 second scroll silence as a silent demo because scenario 7's prose mentions 6 seconds. §9.6 says 8 seconds. The fixture follows §9.6.
- Score `screen_flow` in this change. The curves exist and the tab does not. Fusion stays N/A until E3-5.
- Add a paid vision API for slide cuts. OpenCV, numpy, and PySceneDetect are already in the worker.

## Consequences

- Online jobs gain a `screen_flow` step and rewrite `slides.json` from the measured segments. Stage jobs are unchanged.
- `alembic upgrade head` must apply `014_screen_flow` before the API writes those tables. This change does not deploy.
- Issues #169–#172 are the backend stories. #173–#176 (scoring, the tab, `online_flow_v1`, prompt 1.0.1) are not implemented.
- The owner still needs a GitHub label `phase:O3`. The token used here cannot create labels.

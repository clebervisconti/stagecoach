# ADR-090: Screen-flow scoring, tab, and coaching

**Date:** 2026-10-31
**Status:** Accepted
**Phase:** O3

## Context

ADR-089 measured screen activity, transitions, segment type, alignment, and dead air, and left `screen_flow` and `online_engagement` unscored. Issues #173–#176 and the deferred E2-7 settings row are the rest of O3 plus the layout-review preference (OD-3). Jonny's design package maps the same stories: E3-5 categories, E3-6 the Screen & flow tab, E3-7 `online_flow_v1`, E3-8 the factual-correctness guard with no screen of its own, E2-7 Analysis preferences. GitHub issues are the definition of done. The package is the look and the interaction detail.

`ONLINE_MODES_ENABLED` stays off until O4. On-camera presence stays "Coming soon."

## Decision

- Score `screen_flow` and `online_engagement` from scoring-config 1.1.0 when the delivery mode is webinar, online talk, or recorded video. Stage weights, category scores, and opportunity ranking stay on the published stage context weights (`effective_weights` with `mode="stage"`). Opportunities for online modes use that mode's weights, so a scored screen-flow category can rank.
- `min_evidence` is unchanged: screen flow needs `screen_visible_s` ≥ 120 and at least two segments; online engagement needs `speech_seconds` ≥ 120. A missing screen file with enough speech synthesizes engagement metrics in memory and does not write `screen_flow.json`, so `GET /screens` stays 404. Video consent off still scores screen flow. Choosing audio-only N/As screen flow and can still score engagement from speech.
- The Screen & flow tab is shown for webinar, online talk, and recorded video. Jonny's acceptance note 7 names webinar and online talk only. Recorded video is included so a mode that can score the category has a surface. Stage sessions keep the existing tabs, including Slides. Online modes hide Slides; those scenes already follow the measured segments (ADR-089).
- `GET /sessions/{id}/screens` keeps signed keyframe URLs and, when `online_flow.json` exists, attaches coaching. A 404 is the empty or processing state. A failed fetch is the error state, and the category cards still render.
- `online_flow_v1` is one sample, does not fail the job, and uses the user's existing language-model setting (local Qwen by default). The payload is text: at most 40 screens, at most 600 transcript words each, and no image, frame, keyframe, thumbnail, or base64 fields. A reply that judges content is dropped, `content_judgment` is logged as a count, and the stored file never contains the sentence. One re-ask, then the templated drills. Latency is stored on the artifact and the job step even when the call fails. This environment did not call TIGER, so there is no live timing.
- Every file in `services/analysis/prompts/` is version 1.0.1, including the new `online_flow_v1`. The SPEC §11.3 sample header says `online_flow_v1` 1.0.0. Issue #176 says every prompt file is 1.0.1, so the new file is 1.0.1 too. The live client does not send the markdown bodies. The guard sentence is in each file and is appended to the system prompt. Legacy prompt bodies are not dumped into the request. Stage golden fixtures stay on the language-model-off path and were not retuned.
- `PATCH /api/v1/me` accepts `review_layout` (`always`, `when_unsure`, `never`) and stores it on the existing `users.layout_review_pref` column. `GET /me` also returns `confirmed_online_layouts`. The settings panel is hidden unless `/me` reports `online_modes_enabled`. The default is When unsure. `needs_layout_review` already implements OD-3 and the extra §9.2.6 gates.
- Jonny's open questions, resolved by the mocks: radio cards in their own Analysis preferences panel; "Never" is a note, not a second dialog; fallback coaching says it came from templates; the long-session zoom opens on 15 minutes; zero-count filter chips stay visible and disabled.

## Alternatives considered

- Hide the tab for recorded video, matching acceptance note 7 literally. A scored category would then have no screen of its own.
- Send the full prompt markdown on every content call so the guard lives only in the file. That would change stage scores beyond the approved OD-5 sentence.
- Rename `layout_review_pref` to `review_layout`. The column already shipped in migration 011.
- Add a component-test runner. The web app tests pure view models with `node:test` and components with Playwright.

## Consequences

- Online fusion can score screen flow and engagement. Stage golden fixtures still pass. `on_camera_presence` is still N/A.
- Account export includes `online_flow.json`.
- `alembic upgrade head` is unchanged from ADR-089. This change does not deploy and does not turn the flag on.
- A live TIGER latency for `online_flow_v1` is still unmeasured.

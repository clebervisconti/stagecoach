# Stage Coach Backlog

## Done in tree (0.4.0)

- Upload, ASR, audio features, fusion scoring, evidence-linked report, session delete.
- Consented vision, slides, timeline, Body and Slides tabs, PDF export, retention sweeper.
- Content analysis on `tasks.run_mvp_analysis`. A down model leaves categories 1–7 N/A.
- Talk-prep writes a real plan (message, SCR for exec briefings, 90% time budget, cut order, rehearsal dates).
- Report Objectives tab: plan objectives, planned vs actual, rehearsal progress, baseline badge.
- Trends, goals, password and Apple sign-in code, Resend adapter, account export and 7-day deletion.

## Next

### SC-UX-001 — Analysis status the user can see

**Priority:** P0

- [x] Show the full pipeline while a job runs, including the current step, elapsed time, and a plain-language note when a step fails.
- [x] Persist a running job step when a stage starts, and return that step's message and error on the session.
- [x] Show upload percent and a human status on the session list.
- [x] Install an arm64 MediaPipe wheel, or skip vision before it throws, so pose tracking does not fail on LION.
- [ ] Move speech recognition onto TIGER. The live default is already `small`; `ASR_MODEL` is unset on LION.

### SC-UX-002 — Report and navigation

**Priority:** P1

- [x] Give the report one reading order: score, what to practice, evidence.
- [x] Put Sessions, Talk Prep, and Trends first. The session list shows the score and the next action.
- [x] Surface the content-coach "model unavailable" reason on the report, in the step log, not only in the worker log.

### SC-REL-001 — Production close-out

**Priority:** P0  
**Owner:** product owner. Do not flip these without an explicit decision.

- [ ] Run `tests/uat/mvp-flow.md` against the live host.
- [ ] Run speech recognition on TIGER. The in-tree default model is already `small`.
- [ ] Set Resend secrets and DNS (`docs/email.md`) before verification mail leaves the machine.
- [ ] Set the four Apple secrets before Sign in with Apple is offered.
- [ ] Counsel reviews `docs/PRIVACY.md` before a launch beyond the private beta.
- [ ] Choose KMS or keep the local envelope key.

### SC-P1-005 — Licensed validation

Golden tests use synthetic timestamps. Licensed human speech and inter-rater agreement are still open (`docs/VALIDATION.md`).

### SC-P4-001 — Practice loop

In-browser recording and the live coach overlay. Start only after a real upload produces content scores and a real plan, which the 0.4.0 job now does when the local model is up.

## Online and recorded sessions

Spec: `docs/online-sessions/SPEC.md`. Flag `ONLINE_MODES_ENABLED` defaults to false. Stage mode stays identical. The spec does not judge whether the subject matter is correct. Other participants' faces are never landmarked.

Owner decisions OD-1 through OD-10 were approved on 22 Oct 2026, each exactly as the spec recommends. ADRs 061–069 record those choices. Phase O0 is unblocked. Later phases stay behind `ONLINE_MODES_ENABLED=false` until their own work lands.

### Owner decisions (OD-1–OD-10)

**Owner:** Cleber. **Approved 22 Oct 2026** as the spec recommends.

| ID | Decision | Approved option | Blocks |
|---|---|---|---|
| OD-1 | Mode taxonomy | **(a)** stage, webinar, online talk, recorded video | O0 (closed) |
| OD-2 | Analyse YouTube/Vimeo links | **(b)** later, off by default, own content only | O6 |
| OD-3 | When to show layout review | **(b)** first 3 online sessions, then only when confidence is below 0.80 | O1 |
| OD-4 | Layout boxes without `video_analysis` consent | **(a)** yes, with consent text v1.1 | O1 |
| OD-5 | "Never judge factual correctness" on existing prompts | **(a)** yes, prompt versions 1.0.1 | O3 |
| OD-6 | Webinar upload limits | **(b)** 2 GB / 120 min, resumable in O2 | O1 |
| OD-7 | Other speakers in the transcript | **(a)** keep, labelled, plus **(b)** a setting to remove after analysis | O2 |
| OD-8 | MediaPipe 0.10.31 → 1.x on LION | **(a)** upgrade and re-baseline vision goldens | O0 (closed) |
| OD-9 | Four new categories and mode weights | **(a)** approve as heuristic and calibrate after 30 sessions | O0 (closed) |
| OD-10 | Who gets online modes first | **(a)** owner account only, until the security gate | O4 |

### SC-ONL-O0 — Foundations

**Blocked by:** OD-1, OD-8, OD-9.

- [x] E0-1 MediaPipe 1.x on linux/arm64, ADR-067, vision golden re-baseline. The live container already imports 1.1.1.
- [x] E0-2 YuNet in the model registry, plus a fake face detector for tests.
- [x] E0-3 Migration `011_online_sessions`, including deletion and export of layouts.
- [x] E0-4 Scoring config 1.1.0, effective weights, engine `mode`, stage parity test, context-curve fallback.
- [x] E0-5 Synthetic fixtures: composite picture-in-picture, screen only, camera only.
- [x] E0-6 `scripts/bench_online_cpu.py`.

### SC-ONL-O1 — Upload, layout review, report

**Blocked by:** O0, plus OD-3, OD-4, OD-6.

- [x] E1-1 Mode wizard. Stage uploads keep today's form.
- [x] E1-2 `tasks.prepare_session` and states `preparing` / `layout_review`.
- [x] E1-3 Single-layout detection.
- [x] E1-4 Layout API.
- [x] E1-5 Read-only layout review.
- [x] E1-6 Region crops. Vision on the camera crop. Slides on the screen crop.
- [x] E1-7 Production quality.
- [x] E1-8 Mode fusion, mode badge, core delivery score, N/A reasons.

### SC-ONL-O2 — Correct, trim, gallery

**Blocked by:** O1 and OD-7.

- [x] E2-1 Region editor (roles, pointer, keyboard, 390 sheet).
- [x] E2-2 Multi-segment layouts. Runs shorter than three samples fold into a neighbour.
- [x] E2-3 Gallery marks the highest-score face as camera and the rest as other participants. Mouth×VAD active-speaker correlation waits until layout runs after aligned speech.
- [x] E2-4 Analysis-window trim, minimum 60 seconds.
- [x] E2-5 Re-analyse without a second ASR pass when the window is unchanged.
- [x] E2-6 Report entry back into the editor.
- [x] E2-7 Review-preference settings row (OD-3). Shown when online modes are on for that user.

### SC-ONL-O3 — Screen and flow

**Blocked by:** O2 and OD-5.

- [x] E3-1 Screen activity at 1 Hz. #169
- [x] E3-2 Transitions (SSIM and PySceneDetect). #170
- [x] E3-3 Segment types. Online `slides.json` scenes follow them. #171
- [x] E3-4 Alignment, dead air, silent demo, ASR guard. #172
- [x] E3-5 Score `screen_flow` and `online_engagement`. #173
- [x] E3-6 Screen & Flow tab. #174
- [x] E3-7 `online_flow_v1`. #175
- [x] E3-8 OD-5 prompt guard 1.0.1. #176

### SC-ONL-O4 — On camera, trends, release candidate

**Blocked by:** O3 and OD-10.

- [ ] E4-1 through E4-7: camera presence, On Camera tab, mode pace bands, trends filter, optional diarization, calibration on five owner webinars, security gate. Flag stays off for everyone else.

### SC-ONL-O5 — Two-track upload

- [ ] E5-1 Two drop zones.
- [ ] E5-2 Audio sync and review slider.

### SC-ONL-O6 — Link ingest

**Blocked by:** OD-2. Do not build unless OD-2 is approved.

- [ ] E6-1 Sandboxed fetch worker.
- [ ] E6-2 URL endpoint, attestation, SSRF tests.
- [ ] E6-3 Link tab, hidden while the flag is off.

### SC-ONL-E7 — Docs that land with the phases

- [x] ADR-061 through ADR-069, indexed from `docs/DECISIONS.md`.
- [ ] Privacy note and consent text v1.1 (OD-4).
- [ ] Research sources S57–S78 and the in-app research page.

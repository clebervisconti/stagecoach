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

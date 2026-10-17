# Stage Coach Backlog

## Done in tree (0.4.0)

- Upload, ASR, audio features, fusion scoring, evidence-linked report, session delete.
- Consented vision, slides, timeline, Body and Slides tabs, PDF export, retention sweeper.
- Content analysis on `tasks.run_mvp_analysis`. A down model leaves categories 1–7 N/A.
- Talk-prep writes a real plan (message, SCR for exec briefings, 90% time budget, cut order, rehearsal dates).
- Report Objectives tab: plan objectives, planned vs actual, rehearsal progress, baseline badge.
- Trends, goals, password and Apple sign-in code, Resend adapter, account export and 7-day deletion.

## Next

### SC-REL-001 — Production close-out

**Priority:** P0  
**Owner:** product owner. Do not flip these without an explicit decision.

- [ ] Run `tests/uat/mvp-flow.md` against the live host.
- [ ] Move ASR off `ASR_MODEL=tiny` on LION toward TIGER.
- [ ] Set Resend secrets and DNS (`docs/email.md`) before verification mail leaves the machine.
- [ ] Set the four Apple secrets before Sign in with Apple is offered.
- [ ] Counsel reviews `docs/PRIVACY.md` before a launch beyond the private beta.
- [ ] Choose KMS or keep the local envelope key.

### SC-P1-005 — Licensed validation

Golden tests use synthetic timestamps. Licensed human speech and inter-rater agreement are still open (`docs/VALIDATION.md`).

### SC-P4-001 — Practice loop

In-browser recording and the live coach overlay. Start only after a real upload produces content scores and a real plan, which the 0.4.0 job now does when the local model is up.

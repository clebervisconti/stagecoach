# Phase 3 — Talk-prep coach + objectives + trends

Runnable with `docker compose up` / `make dev` (SPEC §3.1). Per-issue notes:

| Issue | Demo |
|---|---|
| #55 talk plans + plan API | [55.md](phase-3/55.md) |
| #56 plan form + clarify | [56.md](phase-3/56.md) |
| #57 core message + audience | [57.md](phase-3/57.md) |
| #58 structure + outline | [58.md](phase-3/58.md) |
| #59 time budget / cut list / rehearsal | [59.md](phase-3/59.md) |
| #62 objective check engine | [62.md](phase-3/62.md) |
| #66 personal baseline | [66.md](phase-3/66.md) |
| #69 privacy engineering draft | [69.md](phase-3/69.md) |
| #70 this exit checklist | [70.md](phase-3/70.md) |

## Phase 3 AC on current `main`

- Exec-briefing plan: ≤ 15-word core message, SCR option, 90% time-budget arithmetic, ordered cut list, dated rehearsal plan — covered by `services/analysis/tests/test_phase3_exit.py`.
- Linked rehearsal objective statuses and trends “not comparable” — engines exist (#62, and #64 when merged); report panel / goals radar wait on #63 UI and #65.
- `npm audit` and `pip-audit` run in CI. Trivy is not wired (owner).
- Cross-user plan access is 404 (`require_owned`).

Skipped: #67 D10 email, #68 D9 OAuth, paid Sentry/KMS.

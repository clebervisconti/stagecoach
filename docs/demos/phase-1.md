# Phase 1 CI observations

Recorded 2026-10-14 from `gh run view` / downloaded job logs. Only output that was actually read is quoted.

## PR #93 — WhisperX alignment (#21)

- URL: https://github.com/clebervisconti/stagecoach/pull/93
- Head SHA: `0020e4799d031880946c30237ab4021cdc3f8123`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38492919936
- `gh pr view 93 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`

Jobs (all success): Lint and Type Check, Web Type Check and Build, Worker Tests, Check Generated Code, API Unit Tests, Test Suite, Secret Scan, Validate Scoring Config, Production Dependency Audit, Docker Compose Smoke Test.

Worker Tests excerpt (`5_Worker Tests.txt`):

```
================== 95 passed, 7 skipped, 1 warning in 23.59s ===================
```

Smoke excerpt (`2_Docker Compose Smoke Test.txt`):

```
Health check: {'status': 'healthy', 'worker': 'celery'}
✅ Ingest passed: /tmp/tmpyt9k25_6/output/audio16k.wav
✅ ASR passed: /tmp/tmpyt9k25_6/output/smoke-test_transcript.json
✅ Ingest + ASR pipeline test passed
✅ Phase 0 + Phase 1 smoke test complete
```

## PR #94 — Diarization (#22)

- URL: https://github.com/clebervisconti/stagecoach/pull/94
- Head SHA: `5def268e4a1f63da74962431649b2fd4c9b7f370`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38493300136
- `gh pr view 94 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`

Jobs (all success): Test Suite, Worker Tests, Production Dependency Audit, Secret Scan, API Unit Tests, Lint and Type Check, Web Type Check and Build, Check Generated Code, Validate Scoring Config, Docker Compose Smoke Test.

## PR #98 — Audio features (#24), already on main

- URL: https://github.com/clebervisconti/stagecoach/pull/98
- Head SHA at merge: `40a1471a6047012076373c2addf3b8cd02fd0250`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38105073908
- Jobs observed via `gh run view`: Secret Scan, Worker Tests, Check Generated Code, Validate Scoring Config, Test Suite, Lint and Type Check, Docker Compose Smoke Test — all success.

## PR #97 — CI smoke-test stability (#96), already on main

- URL: https://github.com/clebervisconti/stagecoach/pull/97
- Head SHA at merge: `f632d941b6b6d419ccc0ce58fa42d5ae6243d02e`
- Issue #96 CLOSED COMPLETED 2026-10-11
- Acceptance still present on current main / this branch: `pull_request` + `push` to `main` only, concurrency cancel, image pre-pull with retries, healthcheck `start_period`, dump `docker compose ps` and service logs on failure.
- Five consecutive smoke successes on that SHA (workflow_dispatch):
  - https://github.com/clebervisconti/stagecoach/actions/runs/38029103959
  - https://github.com/clebervisconti/stagecoach/actions/runs/38029348299
  - https://github.com/clebervisconti/stagecoach/actions/runs/38029613621
  - https://github.com/clebervisconti/stagecoach/actions/runs/38029898375
  - https://github.com/clebervisconti/stagecoach/actions/runs/38030159853
- PR-event CI: https://github.com/clebervisconti/stagecoach/actions/runs/38009482454
- Jobs observed via `gh run view` on both the last dispatch and the PR-event run: Check Generated Code, Validate Scoring Config, Lint and Type Check, Test Suite, Secret Scan, Worker Tests, Docker Compose Smoke Test — all success.

## PR #104 — Metric functions (#25), after merging origin/main

- URL: https://github.com/clebervisconti/stagecoach/pull/104
- Merge-main head SHA: `e0525a337532cbd8f4cb10b6bfe13a7d5887cc92`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38494974201
- `gh pr view 104 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`
- Conflicts were only `docs/DECISIONS.md`. Both sides kept; metrics ADR renumbered to ADR-016.

Jobs (all success): Test Suite, API Unit Tests, Worker Tests, Check Generated Code, Lint and Type Check, Production Dependency Audit, Secret Scan, Validate Scoring Config, Docker Compose Smoke Test, Web Type Check and Build.

Worker Tests excerpt (`gh run view 38494974201 --log`):

```
tests/test_metrics.py::test_units_match_scoring_yaml PASSED
tests/test_metrics.py::test_pp_wpm_known_rate PASSED
tests/test_metrics.py::test_filler_sounds_five_per_minute_benchmark PASSED
tests/test_metrics.py::test_filler_sounds_twelve_per_minute_benchmark PASSED
tests/test_metrics.py::test_prosody_confidence_snr_anchors PASSED
================== 120 passed, 8 skipped, 1 warning in 24.32s ==================
```

Smoke excerpt (synthetic fixture produced audio features and persisted metrics):

```
✅ Ingest passed: /tmp/tmpwgocyvuf/output/audio16k.wav
✅ ASR passed: /tmp/tmpwgocyvuf/output/smoke-test_transcript.json
audio_features keys: ['session_id', 'stage_version', 'artifacts', 'metrics']
✅ audio_features + metrics persisted: /tmp/tmpwgocyvuf/output/metrics.json
✅ Ingest + ASR + audio_features + metrics pipeline test passed
```

Earlier impl SHA before the main merge (still green, superseded): `676e27b069b0641f836bd02b3608c1d0a05b6734` / run 38493376302.

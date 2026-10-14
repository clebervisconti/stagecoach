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

## PR #104 — Metric functions (#25)

- URL: https://github.com/clebervisconti/stagecoach/pull/104
- Head SHA: `676e27b069b0641f836bd02b3608c1d0a05b6734`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38493376302
- `gh pr view 104 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`

Jobs (all success): Production Dependency Audit, Worker Tests, Test Suite, Web Type Check and Build, Validate Scoring Config, API Unit Tests, Check Generated Code, Secret Scan, Docker Compose Smoke Test, Lint and Type Check.

Worker Tests excerpt:

```
tests/test_metrics.py::test_units_match_scoring_yaml PASSED
tests/test_metrics.py::test_pp_wpm_known_rate PASSED
tests/test_metrics.py::test_filler_sounds_five_per_minute_benchmark PASSED
tests/test_metrics.py::test_filler_sounds_twelve_per_minute_benchmark PASSED
tests/test_metrics.py::test_prosody_confidence_snr_anchors PASSED
================== 119 passed, 5 skipped, 1 warning in 25.23s ==================
```

Smoke excerpt (synthetic fixture produced audio features and persisted metrics):

```
✅ Ingest passed: /tmp/tmphmz_j1fe/output/audio16k.wav
✅ ASR passed: /tmp/tmphmz_j1fe/output/transcript.json
audio_features keys: ['session_id', 'stage_version', 'artifacts', 'metrics']
✅ audio_features + metrics persisted: /tmp/tmphmz_j1fe/output/metrics.json
✅ Ingest + ASR + audio_features + metrics pipeline test passed
```

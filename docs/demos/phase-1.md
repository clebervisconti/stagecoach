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

## PR #105 — Fusion scoring + report (#30)

- URL: https://github.com/clebervisconti/stagecoach/pull/105
- Head SHA: `bc5f5d69703dca7ab9dd6584a5ad1c5feb824ab5`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38497537834
- `gh pr view 105 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`
- First smoke on `d78315a705923b8bcd1fe7bf8e49629525683fd3` (run 38496992520) failed: worker path `/app/pipeline/stages/fusion_scoring.py` made `Path.parents[4]` raise `IndexError: 4`. Fixed by walking ancestors and preferring `/packages`.

Jobs on `bc5f5d69703dca7ab9dd6584a5ad1c5feb824ab5` (all success): Worker Tests, Check Generated Code, API Unit Tests, Web Type Check and Build, Test Suite, Validate Scoring Config, Production Dependency Audit, Secret Scan, Lint and Type Check, Docker Compose Smoke Test.

Worker Tests excerpt (`gh run view 38497537834 --log`):

```
tests/test_fusion_scoring.py::test_packages_lookup_does_not_assume_repo_depth PASSED
tests/test_fusion_scoring.py::test_missing_content_marks_text_categories_unavailable PASSED
tests/test_fusion_scoring.py::test_content_and_metrics_score_audio_text_categories PASSED
tests/test_fusion_scoring.py::test_report_phrases_only_fact_numbers_and_attaches_drills PASSED
tests/test_fusion_scoring.py::test_never_invents_video_or_missing_llm_metrics PASSED
================== 125 passed, 8 skipped, 1 warning in 15.33s ==================
```

Smoke excerpt (synthetic 3s sine produced `report.json`; most categories N/A, no invented scores):

```
✅ Ingest passed: /tmp/tmpp76m705h/output/audio16k.wav
✅ ASR passed: /tmp/tmpp76m705h/output/smoke-test_transcript.json
✅ audio_features + metrics persisted: /tmp/tmpp76m705h/output/metrics.json
✅ fusion_scoring + report produced: /tmp/tmpp76m705h/output/report.json
✅ Ingest + ASR + audio_features + metrics + fusion + report pipeline test passed
✅ Phase 0 + Phase 1 smoke test complete
```

## PR #106 — Report API (#31), stacked on #105

- URL: https://github.com/clebervisconti/stagecoach/pull/106
- Head SHA: `276d4e7aacdd29f2b37ad5de49b7f70a5045cf60`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38497892855
- `gh pr view 106 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`
- Base: `cursor/p1-fusion-scoring-30-c0e2`. First smoke on pre-rebase `03e8794` (run 38497300240) failed with the same `IndexError: 4`; rebased onto the #105 fix.

Jobs on `276d4e7aacdd29f2b37ad5de49b7f70a5045cf60` (all success): API Unit Tests, Worker Tests, Web Type Check and Build, Validate Scoring Config, Lint and Type Check, Test Suite, Check Generated Code, Production Dependency Audit, Docker Compose Smoke Test, Secret Scan.

API Unit Tests excerpt (`gh run view 38497892855 --log`):

```
tests/test_auth_and_sessions.py::test_playback_signature_roundtrip_and_reject_tamper PASSED
tests/test_auth_and_sessions.py::test_highlights_come_only_from_existing_evidence PASSED
tests/test_auth_and_sessions.py::test_video_series_placeholder_is_one_second PASSED
tests/test_auth_and_sessions.py::test_token_bucket_denies_after_burst PASSED
========================= 8 passed, 1 warning in 0.46s =========================
```

Smoke excerpt (`GET /report` returned the fixture `report.json`):

```
✅ Ingest passed: /data/stagecoach/smoke-fixture/audio16k.wav
✅ ASR passed: /data/stagecoach/smoke-fixture/smoke-test_transcript.json
✅ audio_features + metrics persisted: /data/stagecoach/smoke-fixture/metrics.json
✅ fusion_scoring + report produced: /data/stagecoach/smoke-fixture/report.json
summary: This is a partial audio/text report. 0 categories have scores and 17 are unavailable because their inputs were missing. No category was given an invented score.
   ✅ GET /report returned the synthetic fixture report.json
✅ Phase 0 + Phase 1 smoke test complete
```

## PR #107 — Report v1 UI (#32)

- URL: https://github.com/clebervisconti/stagecoach/pull/107
- Impl SHA: `0d2920ed5ecf2a2ad53ea8876031af8f83efc4b7`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38499678585
- `gh pr view 107 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`

Jobs on `0d2920ed5ecf2a2ad53ea8876031af8f83efc4b7` (all success): Web Type Check and Build, Validate Scoring Config, Worker Tests, Test Suite, Production Dependency Audit, API Unit Tests, Lint and Type Check, Secret Scan, Check Generated Code, Docker Compose Smoke Test.

Web tests excerpt (`gh run view 38499678585 --log`):

```
ok 1 - en and pt-BR UI strings do not use emotion-inference terms
ok 2 - overall headline is 71 ± 4 with partial coverage
ok 3 - unavailable pillars are gaps, never scored as zero
ok 4 - missing key metrics are labelled unavailable, not zero
ok 5 - N/A category scores stay null
# tests 5
# pass 5
# fail 0
```

Smoke excerpt (fixture report has no invented pillar zeros):

```
unavailable pillars: ['message', 'story_impact', 'visuals', 'voice', 'body', 'presence_time'] scored: []
   ✅ GET /report returned the synthetic fixture report.json
✅ Phase 0 + Phase 1 smoke test complete
```

## PR #108 — Player, transcript, Voice tab (#33), stacked on #107

- URL: https://github.com/clebervisconti/stagecoach/pull/108
- Impl SHA: `22d089693e2eb4c4235b06b63ce4babe13deb21d`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38501030248
- Base: `cursor/p1-report-v1-ui-32-1b22`

Jobs on `22d089693e2eb4c4235b06b63ce4babe13deb21d` (all success): Worker Tests, API Unit Tests, Docker Compose Smoke Test, Production Dependency Audit, Validate Scoring Config, Check Generated Code, Web Type Check and Build, Secret Scan, Lint and Type Check, Test Suite.

Web tests excerpt (`gh run view 38501030248 --log`):

```
ok 2 - evidence chips seek to t_start minus 2 seconds
ok 3 - keyboard map covers space, arrows, and J/L markers
ok 10 - transcript highlights fillers, pauses, and API core-message spans
ok 12 - exports txt, srt, and vtt from existing segments
ok 13 - pace windows use null when a window has no speech
ok 14 - unavailable series are not treated as zeros
# tests 15
# pass 15
```

## PR #109 — Delete session hard delete + audit (#34)

- URL: https://github.com/clebervisconti/stagecoach/pull/109
- Impl SHA: `1258bac3e98babcb3799df4bde4e53d4ee70ca76`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38502355460
- `gh pr view 109 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`
- Branched from `main` (`a7929b7`); independent of #32 / #33

Jobs on `1258bac3e98babcb3799df4bde4e53d4ee70ca76` (all success): Check Generated Code, Secret Scan, Lint and Type Check, Production Dependency Audit, Docker Compose Smoke Test, Web Type Check and Build, Worker Tests, API Unit Tests, Test Suite, Validate Scoring Config.

API Unit Tests excerpt (`gh run view 38502355460 --log`):

```
tests/test_deletion.py::test_delete_local_prefix_removes_session_files_only PASSED
tests/test_deletion.py::test_dict_object_store_deletes_only_matching_prefix PASSED
tests/test_deletion.py::test_audit_details_are_counts_only PASSED
=================== 26 passed, 2 skipped, 1 warning in 0.64s ===================
```

Smoke excerpt (session prefix files and CASCADE rows gone; audit counts only; fixture kept):

```
planted 3 files under /data/stagecoach/0206900d-14a0-40c0-bb74-afdca5c53a27 and result rows for job 44b21d01-d380-4db6-a718-3e15d517ef38
   DELETE HTTP Status: 204
   GET after delete HTTP Status: 404
audit object_count=3 db_rows={'insights': 1, 'sessions': 1, 'job_steps': 1, 'transcripts': 1, 'media_assets': 1, 'analysis_jobs': 1, 'metric_values': 1, 'evidence_items': 1, 'overall_scores': 1, 'category_scores': 1} verification={'db_left': {'insights': 0, 'sessions': 0, 'job_steps': 0, 'transcripts': 0, 'media_assets': 0, 'analysis_jobs': 0, 'metric_values': 0, 'evidence_items': 0, 'overall_scores': 0, 'category_scores': 0}, 'db_rows': {'insights': 1, 'sessions': 1, 'job_steps': 1, 'transcripts': 1, 'media_assets': 1, 'analysis_jobs': 1, 'metric_values': 1, 'evidence_items': 1, 'overall_scores': 1, 'category_scores': 1}, 'db_remaining': 0, 'object_count': 3, 'search_index': 'not_deployed', 'local_remaining': 0, 'object_store_remaining': 0}
   ✅ DELETE removed session files and DB rows; audit has counts only
✅ Phase 0 + Phase 1 smoke test complete
```

## PR #110 — Golden fixtures and metric validation start (#35)

- URL: https://github.com/clebervisconti/stagecoach/pull/110
- Impl SHA: `fb45c95cec8de905f3942e31ae0d892f5440d676`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38592701585
- Branched from `main` (`478e91a`)
- After merging origin/main (`7bb7164`, includes #109): merge SHA `fe329530d9a10eb2bfaae033ae4f23510cf74d43`
- Merge CI: https://github.com/clebervisconti/stagecoach/actions/runs/38594492808
- `gh pr view 110 --json mergeable,mergeStateStatus` → `MERGEABLE` / `CLEAN`

Jobs on merge SHA `fe329530d9a10eb2bfaae033ae4f23510cf74d43` (all success): Production Dependency Audit, Secret Scan, Lint and Type Check, Check Generated Code, Test Suite, Validate Scoring Config, Web Type Check and Build, Worker Tests, Docker Compose Smoke Test, API Unit Tests.

Jobs on impl SHA `fb45c95cec8de905f3942e31ae0d892f5440d676` (all success): Web Type Check and Build, Validate Scoring Config, API Unit Tests, Lint and Type Check, Docker Compose Smoke Test, Test Suite, Production Dependency Audit, Check Generated Code, Worker Tests, Secret Scan.

Worker Tests excerpt (`gh run view 38592701585 --log`):

```
tests/golden/test_golden.py::test_golden_comparison_tolerances[en_clean] PASSED
tests/golden/test_golden.py::test_golden_comparison_tolerances[ptbr_clean] PASSED
tests/golden/test_golden.py::test_golden_comparison_tolerances[noisy_low_snr] PASSED
tests/golden/test_golden.py::test_noisy_fixture_is_low_confidence_and_excluded_from_overall PASSED
tests/golden/test_validation_start.py::test_en_and_ptbr_corpora_are_at_least_twenty_minutes PASSED
PASS en_clean language=en kind=clean overall=92 confidence=0.8499999999999999
PASS ptbr_clean language=pt-BR kind=clean overall=91 confidence=0.8499999999999999
PASS noisy_low_snr language=en kind=noisy overall=None confidence=0.0
all golden fixtures passed (±2 scores, ±5% metrics)
```

## PR #111 — Phase 1 exit e2e + CPU bench (#36)

- URL: https://github.com/clebervisconti/stagecoach/pull/111
- Impl SHA: `7609c679144b2e9ae6e085488317f5274c906653`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38598347916
- Branched from `main` (`7bb7164`)
- Local Playwright (this agent, Chromium): both specs passed in 9.8s (`upload → progress → report → delete` and pt-BR né/tipo/então rows)

Jobs on `7609c679144b2e9ae6e085488317f5274c906653` (all success): Production Dependency Audit, Validate Scoring Config, Test Suite, Docker Compose Smoke Test, Web Type Check and Build, Check Generated Code, Secret Scan, API Unit Tests, Worker Tests, Lint and Type Check, Playwright E2E.

Playwright E2E excerpt (`gh run view 38598347916 --log`):

```
✓  1 [chromium] › e2e/upload-report-delete.spec.ts:20:5 › upload → progress → report → delete (en) (3.4s)
✓  2 [chromium] › e2e/upload-report-delete.spec.ts:36:5 › pt-BR upload shows né/tipo/então disambiguation then delete (3.3s)
2 passed (9.0s)
```

Worker Tests excerpt: `127 passed, 8 skipped, 1 warning in 26.06s`. Web unit tests include `ok 12 - pt-BR né/tipo/então disambiguation rows stay on the payload`.

### CPU bench (observed on this agent VM, 2026-10-14)

Command: `python3 scripts/bench_phase1_cpu.py --seconds 600 --speech --model tiny`

Host: `Intel(R) Xeon(R) Processor`, 4 CPUs, Linux 6.12.94+ x86_64. ASR: faster-whisper `tiny` int8 CPU (same model CI uses). Audio is **espeak-ng synthetic speech**, not a licensed human talk (D13). The 3-second CI smoke sine is not this benchmark.

A 600 s CC0 sine was also run: measured duration 600.0 s, **0 transcript words**, ingest 6.399 s + ASR 2.180 s + audio_features 3.653 s + fusion 0.104 s = **12.338 s** to analysis. That is not a talk; Whisper VAD produced an empty transcript.

**en (espeak-ng, requested 600 s):**

- measured audio: **773.534 s** (12.9 min; espeak ran long)
- wall ingest→report: **29.604 s** (script 30.153 s) — **within 15 min**
- stages: ingest 8.740 s, asr 16.601 s, audio_features 4.082 s, metrics 0.021 s, fusion 0.108 s, report 0.052 s
- transcript_words: 1980; overall_score: 73; disambiguation tokens: `like`, `so`

**pt-BR (espeak-ng, requested 600 s):**

- measured audio: **865.414 s** (14.4 min)
- wall ingest→report: **36.115 s** (script 36.694 s) — **within 15 min**
- stages: ingest 9.852 s, asr 21.595 s, audio_features 4.485 s, metrics 0.022 s, fusion 0.109 s, report 0.052 s
- transcript_words: 1874; overall_score: 73
- disambiguation tokens observed: **né, tipo, então, é** (heuristic_v1)

Not measured: a consented human 10-minute talk; faster-whisper `small`/`medium`; GPU; live LLM `fluency_disambig_v1` (no API key in this environment). Heuristic readings are labelled as such in the UI.


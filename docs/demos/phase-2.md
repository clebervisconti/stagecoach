# Phase 2 CI observations

Recorded from `gh run view` / downloaded job logs. Only output that was actually read is quoted.

## PR #112 — Consent UI + `/me/consents` (#37)

- URL: https://github.com/clebervisconti/stagecoach/pull/112
- Head SHA at green CI: `7aa2c577c34f52913c6e9dde96da266674c0afcd`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38602602267
- `gh run view 38602602267 --json conclusion,headSha` → `success` / `7aa2c577c34f52913c6e9dde96da266674c0afcd`

Jobs on that SHA (all success): Check Generated Code, Worker Tests, API Unit Tests, Validate Scoring Config, Test Suite, Production Dependency Audit, Web Type Check and Build, Playwright E2E, Lint and Type Check, Docker Compose Smoke Test, Secret Scan.

Earlier run https://github.com/clebervisconti/stagecoach/actions/runs/38602198127 on `a44ec43c7b41a6d5f28b4e6f4b8fa80c1dbe250c` failed: Docker Compose Smoke Test / Start services — `public.ecr.aws` returned `429 Too Many Requests` / `toomanyrequests: Data limit exceeded` resolving `python:3.11-slim`. Follow-up commit pointed API and worker Dockerfiles at `mirror.gcr.io/library/python` and pre-pulled those tags with retries.

Worker Tests excerpt:

```
tests/test_consent.py::test_defaults_skip_all_vision PASSED
tests/test_consent.py::test_video_consent_does_not_enable_expression_or_raw_landmarks PASSED
tests/test_consent.py::test_expression_and_tracking_require_video_consent PASSED
tests/test_consent.py::test_runner_is_not_called_without_video_consent PASSED
tests/test_consent.py::test_persist_snapshot_and_na_reasons PASSED
tests/test_fusion_scoring.py::test_consent_denied_sets_video_na_reasons PASSED
================== 139 passed, 8 skipped, 1 warning in 26.96s ==================
```

API Unit Tests excerpt:

```
tests/test_consents.py::test_policy_hash_is_sha256_and_stable PASSED
tests/test_consents.py::test_policy_text_does_not_infer_emotions PASSED
tests/test_consents.py::test_defaults_are_denied PASSED
tests/test_consents.py::test_latest_row_wins_and_revoke_is_recorded PASSED
tests/test_consents.py::test_localize_falls_back_to_english PASSED
=================== 31 passed, 2 skipped, 1 warning in 0.88s ===================
```

Smoke excerpt (issue #37 endpoints):

```
7a. GET/POST /api/v1/me/consents (issue #37):
policy_version 82d9145fd990 defaults off
granted video_analysis; expression still off
revoked video_analysis
   ✅ Consents default off, grant/revoke append-only, unknown purpose rejected
Phase 2 additions:
  - GET/POST /me/consents (defaults off, grant/revoke, unknown purpose 422)
```

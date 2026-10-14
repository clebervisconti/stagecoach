# Phase 2 CI observations

Recorded from `gh run view` / downloaded job logs. Only output that was actually read is quoted.

## PR #112 — Consent UI + `/me/consents` (#37)

- URL: https://github.com/clebervisconti/stagecoach/pull/112
- Head SHA at green CI: `7aa2c577c34f52913c6e9dde96da266674c0afcd`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38602602267
- `gh run view 38602602267 --json conclusion,headSha` → `success` / `7aa2c577c34f52913c6e9dde96da266674c0afcd`
- Docs commit SHA `085fc2c93b349d7b17061bd6280d54702bec113d` also green: https://github.com/clebervisconti/stagecoach/actions/runs/38603296124 (`gh run view` conclusion `success`, same 11 jobs)

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

## PR #113 — Vision stage MediaPipe pose/hands/face (#38)

- URL: https://github.com/clebervisconti/stagecoach/pull/113
- Head SHA at green CI: `da67ddd0834508377439a2605ee8b61589869493`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38606687456
- `gh run view 38606687456 --json conclusion,headSha` → `success` / `da67ddd0834508377439a2605ee8b61589869493`

Jobs on that SHA (all success): Test Suite, Web Type Check and Build, Secret Scan, API Unit Tests, Production Dependency Audit, Playwright E2E, Validate Scoring Config, Lint and Type Check, Docker Compose Smoke Test, Check Generated Code, Worker Tests.

Earlier run https://github.com/clebervisconti/stagecoach/actions/runs/38606259851 on `616466dd60c27c82dfeb9c7c4439fa5b40e3b391` failed: Docker Compose Smoke Test / Start services — pip conflict `mediapipe 0.10.14 depends on protobuf<5` vs `splunk-opentelemetry 2.13.1 depends on protobuf>=6`. Follow-up pin is `mediapipe==0.10.31`.

Worker Tests excerpt:

```
tests/test_vision.py::test_one_euro_damps_impulse PASSED
tests/test_vision.py::test_savgol_reduces_high_freq_jitter PASSED
tests/test_vision.py::test_iou_and_primary_person_is_larger_central PASSED
tests/test_vision.py::test_face_hands_sampling_is_10_of_15 PASSED
tests/test_vision.py::test_consent_skips_without_calling_stage PASSED
tests/test_vision.py::test_aggregates_encrypted_and_raw_discarded PASSED
tests/test_vision.py::test_keep_detailed_tracking_writes_raw_landmarks PASSED
tests/test_vision.py::test_expression_opt_in_adds_blendshape_columns PASSED
tests/test_vision.py::test_openface_not_a_dependency PASSED
tests/test_vision.py::test_licenses_are_apache_for_models PASSED
================== 152 passed, 8 skipped, 1 warning in 26.32s ==================
```

Smoke excerpt (issue #38 registry):

```
Running upgrade 004_audit_deletion -> 005_model_registry, model_registry for vision provenance
 public | model_registry    | table | stagecoach
5b. model_registry (issue #38):
 face_landmarker      | Apache-2.0
 hand_landmarker      | Apache-2.0
 pose_landmarker_full | Apache-2.0
Phase 2 additions:
  - model_registry table seeded with MediaPipe pose/hands/face (Apache-2.0)
```

## PR #114 — Vision events, quality JSON, camera-setup check (#39)

- URL: https://github.com/clebervisconti/stagecoach/pull/114
- Head SHA at green CI: `465e6c6d0af6890f65f1b3cc6061915272890770`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38609292593
- `gh run view 38609292593 --json conclusion,headSha` → `success` / `465e6c6d0af6890f65f1b3cc6061915272890770`

Jobs on that SHA (all success): Web Type Check and Build, Lint and Type Check, Validate Scoring Config, Production Dependency Audit, API Unit Tests, Docker Compose Smoke Test, Test Suite, Worker Tests, Playwright E2E, Check Generated Code, Secret Scan.

Worker Tests excerpt:

```
tests/test_vision_events.py::test_scripted_events_cover_required_types PASSED
tests/test_vision_events.py::test_smile_and_flat_face_require_expression_consent PASSED
tests/test_vision_events.py::test_flat_face_window_on_long_low_expressivity PASSED
tests/test_vision_events.py::test_setup_mismatch_relaxes_thresholds PASSED
tests/test_vision_events.py::test_mismatch_written_on_emptyish_person PASSED
tests/test_vision_events.py::test_detect_events_direct_stroke PASSED
tests/test_vision_events.py::test_detect_events_direct_pose_and_face_types PASSED
tests/test_vision_events.py::test_quality_json_has_no_emotion_labels PASSED
================== 160 passed, 8 skipped, 1 warning in 27.11s ==================
```

Smoke excerpt (issue #39 echo):

```
Phase 2 additions:
  - GET/POST /me/consents (defaults off, grant/revoke, unknown purpose 422)
  - model_registry table seeded with MediaPipe pose/hands/face (Apache-2.0)
  - vision_events.json / vision_quality.json when video_analysis is granted
```

## PR #115 — Category 14 facial expressiveness, opt-in (D8, #42)

- URL: https://github.com/clebervisconti/stagecoach/pull/115
- Head SHA at green CI: `d942eb0e138a529cf022308fa204be0995496eda`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38611949981
- `gh run view 38611949981 --json conclusion,headSha` → `success` / `d942eb0e138a529cf022308fa204be0995496eda`

Jobs on that SHA (all success): Lint and Type Check, Web Type Check and Build, Validate Scoring Config, Docker Compose Smoke Test, API Unit Tests, Check Generated Code, Playwright E2E, Secret Scan, Production Dependency Audit, Test Suite, Worker Tests.

Worker Tests excerpt:

```
tests/test_expressiveness.py::test_expression_metrics_written_only_with_consent PASSED
tests/test_expressiveness.py::test_facial_affect_scored_only_when_opted_in PASSED
tests/test_expressiveness.py::test_default_off_keeps_category_14_na PASSED
tests/test_expressiveness.py::test_incongruence_flag_is_observation_not_emotion PASSED
tests/test_expressiveness.py::test_no_ser_models_in_requirements PASSED
tests/test_expressiveness.py::test_source_and_ui_have_no_forbidden_emotion_labels PASSED
================== 166 passed, 8 skipped, 1 warning in 27.42s ==================
```

Smoke excerpt (issue #42 echo):

```
Phase 2 additions:
  - GET/POST /me/consents (defaults off, grant/revoke, unknown purpose 422)
  - model_registry table seeded with MediaPipe pose/hands/face (Apache-2.0)
  - vision_events.json / vision_quality.json when video_analysis is granted
  - category 14 (facial_affect) only when expression_analysis is granted; no emotion labels
```

## PR #118 — Slides stage: PySceneDetect, keyframes, deck, OCR (#43)

- URL: https://github.com/clebervisconti/stagecoach/pull/118
- Head SHA at green CI: `f9daff7092ecf1a8f1ac0a2db72642e91d66c5d3`
- CI: https://github.com/clebervisconti/stagecoach/actions/runs/38619748706
- `gh run view 38619748706 --json conclusion,headSha` → `success` / `f9daff7092ecf1a8f1ac0a2db72642e91d66c5d3`

Jobs on that SHA (all success): Lint and Type Check, Production Dependency Audit, Playwright E2E, Docker Compose Smoke Test, Check Generated Code, Validate Scoring Config, Web Type Check and Build, Secret Scan, API Unit Tests, Test Suite, Worker Tests.

Worker Tests excerpt:

```
tests/test_slides.py::test_merge_scenes_under_two_seconds PASSED
tests/test_slides.py::test_antivirus_accepts_pptx_rejects_macro_and_exe_magic PASSED
tests/test_slides.py::test_antivirus_scan_file PASSED
tests/test_slides.py::test_stage_region_full_frame_for_screen_recording PASSED
tests/test_slides.py::test_stage_region_finds_bright_quad PASSED
tests/test_slides.py::test_tfidf_and_reading_overlap PASSED
tests/test_slides.py::test_ahash_hamming PASSED
tests/test_slides.py::test_pptx_extract PASSED
tests/test_slides.py::test_run_slides_on_synthetic_scenes PASSED
tests/test_slides.py::test_audio_only_without_deck_is_skipped PASSED
tests/test_slides.py::test_no_pyscenedetect_in_forbidden_models PASSED
================== 177 passed, 8 skipped, 1 warning in 20.84s ==================
```

API Unit Tests excerpt:

```
tests/test_deck.py::test_pptx_ok_macro_rejected PASSED
tests/test_deck.py::test_pdf_javascript_rejected PASSED
tests/test_deck.py::test_wrong_extension_rejected PASSED
=================== 34 passed, 2 skipped, 1 warning in 0.92s ===================
```

Smoke excerpt (issue #43 echo):

```
Phase 2 additions:
  - GET/POST /me/consents (defaults off, grant/revoke, unknown purpose 422)
  - model_registry table seeded with MediaPipe pose/hands/face (Apache-2.0)
  - vision_events.json / vision_quality.json when video_analysis is granted
  - category 14 (facial_affect) only when expression_analysis is granted; no emotion labels
  - slides stage: PySceneDetect (BSD), keyframes, python-pptx/pdftotext, Tesseract OCR; deck antivirus in sandbox
```

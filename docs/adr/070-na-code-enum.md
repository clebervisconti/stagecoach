# ADR-070: Stable `na_code` enum beside `na_reason`

**Date:** 2026-10-22
**Status:** Accepted
**Phase:** O1

## Context

`na_reason` is free text. The O1 report needs stable UI copy for not-measured categories (Jonny Ive §S5). Mapping from prose is brittle.

## Decision

Add `na_code` as a closed enum next to `na_reason` in `analysis_result.v1.json`, fusion output, and the API. The UI keys off `na_code`; `na_reason` remains fallback text. Codes: `not_in_phase`, `consent_video_off`, `vision_unavailable`, `camera_not_visible`, `camera_too_small`, `audio_only_chosen`, `audio_only_media`, `no_screen`, `qa_not_detected`, `qa_declared_none`, `target_length_missing`, `insufficient_speech`, `hands_not_visible`, `stage_mode`, `no_slides`, `not_applicable`. Shared module: `packages/schemas/na_codes.py`.

## Alternatives considered

1. Keep free-text only and match substrings in the UI — rejected, copy would drift.
2. Replace `na_reason` — rejected, existing goldens and exports still use the sentence.

## Consequences

Fusion writes both fields. Stage goldens stay valid because `na_code` is additive. New jobs use schema 1.1.0.

# ADR-088: Report measurements say what was actually measured

**Date:** 2026-10-24
**Status:** Accepted
**Phase:** Online

## Context

The same 35:49 webinar report showed numbers and sentences that do not match the recording.

Integrated loudness was −70 LUFS. That is the libebur128 absolute-gate floor, printed on the progress line from the first frame. The talk had clear speech and a working transcript. Scoring that floor as a webinar loudness (the curve expects about −23 to −16) is a measurement bug. The analysis WAV is loudness-normalised to −16, so it is not a production measurement either.

The report UI printed metric ids (`pq integrated lufs`, `va glance llm`). Strengths and the speaking-rate evidence were stamped 00:00. Strength titles used snake case ("visual aids is a measured strength"). A score of 62 (level 4, "Strong") was listed as a strength while the same category was a top opportunity ("Practice visual aids").

Seven message and story categories said "Not measured for this recording." The stored reason was that the language model step did not finish (ADR-087). The UI preferred the generic `na_code` and hid `na_reason`.

Eye contact scored 37 ("Needs practice") with audience-facing time at 11%. The layout review said the camera was not the frame for most of the talk. SPEC §9.5 scores gaze toward the lens only while the camera fills the frame. Looking at a shared screen during a demo is expected. The OD table in SPEC §17 does not change that rule. SPEC §15 is the phased plan, not the gaze decision.

The headline read like a full score ("65 · Strong") when 8 of 21 categories were measured.

## Decision

- Parse integrated loudness from the ebur128 summary. A value at or below −70 LUFS is not a measurement and is not scored. If the default audio stream is that floor, try the other audio streams. Do not measure the loudness-normalised analysis WAV.
- The report shows a display name and a unit for each metric. −70 LUFS renders as unavailable on reports that were stored before this change.
- Session-wide evidence (speaking rate, filler rate, and the same class of metric) does not show a 00:00 seek chip. The insights list says "Whole session". A chip whose evidence belongs to another category is omitted.
- Strength and opportunity titles use category display names. A category in the top three opportunities is not also a strength. The UI builds those titles from the locale file, including reports already stored.
- When `na_reason` says the language model did not finish, the UI says that, including reports whose `na_code` is still `not_applicable`. New runs store `model_unavailable`. Online sessions link to the existing layout re-analyse. There is no separate content-only retry.
- For webinar, online talk, and recorded video, gaze is computed on frames whose time falls in a camera-full segment (or a camera region with no shared screen). Coverage under 20% of the session is N/A (`camera_coverage_low`). Coverage from 20% to 50% is scored with confidence capped at 0.55. Stage mode is unchanged. Camera time on `camera.mp4` is shifted by the crop origin in `camera_spans.json`.
- When the report is partial, or coverage is under 0.6, the headline uses "Partial score" instead of the level name "Strong".

## Alternatives considered

- Keep −70 and show it with a warning. A silence floor still moves the production score.
- Treat every 00:00 stamp as a real moment at the start. The speaking-rate evidence is a session aggregate, and several strengths were pointing at that same row.
- Score eye contact on the whole composite, then lower the number. SPEC §9.5 says those frames are not the lens.

## Consequences

- Loudness, gaze coverage, strengths, and the partial session status change on the next analysis. Labels, the partial headline, N/A reasons, and 00:00 chips change for reports already stored.
- OD-1 through OD-10 are unchanged. Gaze follows SPEC §9.5.

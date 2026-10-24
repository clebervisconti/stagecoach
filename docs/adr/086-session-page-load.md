# ADR-086: Session-page load, per-user rate limits, and prepare progress

**Date:** 2026-10-24
**Status:** Accepted
**Phase:** Online

## Context

A real-stack run on the LION host (one 819 MB, 35:49 webinar) showed four failures that look unrelated and are not.

The API rate limiter keyed the per-user bucket on the first 32 characters of the bearer token. An HS256 JWT header is those 32 characters, so Redis held a single `rl:user:*` key. One busy tab emptied the bucket for every signed-in user. The limits were 2 requests/s per user (burst 60) and 4/s per IP (burst 120).

The session page polled every 2.5 seconds. While status was `processing` it also requested the report, transcript, series, timeline, and the other artifacts. Those answers are 409 until the job has something to show. `/events` was already open. After layout accept, traffic went from about 24 to 288 requests per minute, and 58% of them were 429. A failed session GET left "Could not load this session." on screen after a later GET succeeded. 429 responses from the API already carried `Retry-After`; the browser-facing proxy dropped the header.

Prepare emitted one progress event at 5% ("Validating media") and then nothing until layout. On that recording the steps were a one-second probe, about 50 seconds of audio, about 113 seconds of analysis video, about 185 seconds of 1080p-to-720p playback, the poster, about 40 seconds of sprites, then layout. The preview was a broken image until the poster, roughly six minutes in. `media_assets.duration_s` stayed NULL, so the length read 0:00. The elapsed clock parsed a timezone-less UTC timestamp as local time and clamped a future start to 0:00.

The layout review headline used the first segment only. A single SCREEN region produced "We found your screen. Your camera isn't visible." The timeline underneath listed many segments, including camera. The detector was not the bug.

## Decision

Rate-limit keys:

- After the token verifies, the user bucket is `rl:user:{sub}`.
- If a bearer token does not verify, the bucket is `rl:user:token:{sha256 of the full token}`.
- A request with no bearer token is limited by IP only.
- The route still checks the session version and the user row. The limiter does not.
- `GET` and `HEAD` of `/api/v1/me`, `GET /api/v1/sessions/{id}`, and `GET /api/v1/sessions/{id}/events` do not spend the user bucket. The IP bucket still applies. Artifact reads and writes stay on the user bucket.
- Defaults are 8 requests/s per user with a burst of 120, and 16/s per IP with a burst of 240. `RATE_LIMIT_*` still overrides them.
- 429 keeps `Retry-After`. The web proxy forwards that header.

Session page:

- Progress comes from `/events`. A running stage updates the line on screen and does not fetch the session.
- The fallback is one session GET every 12 seconds. A refresh does not start while another is in flight.
- Artifacts are fetched when status is `ready` or `partial`, or when an event is `partial_ready`, `done`, or a stage `succeeded`.
- 409 on an artifact is not ready. It does not clear data already on screen and it is not the load error.
- 429 backs off for `Retry-After` (bounded to 1–120 seconds). That wait applies to a refresh that was queued during the limited request.
- The next successful session GET clears "Could not load this session."

Prepare:

- Ingest emits one progress event per sub-step, with a percentage inside the ingest band and a remaining-time estimate. The UI translates the step code.
- The poster is a single frame from the original, before the long encodes. The page shows the title as a placeholder until that file exists, and drops a broken image.
- The worker writes `media_assets.duration_s` when ffprobe returns a positive length, and only when the column is still NULL. The upload path writes the same value when the API image can run ffprobe.
- The page treats a timestamp with no zone as UTC.
- Playback stays CRF 23 and moves from preset `medium` to `veryfast`. The file can be a little larger. The three full encodes stay in series: one 819 MB source on one host is enough memory pressure. Sprites are one ffmpeg pass, with the old per-frame loop if that pass produces nothing.
- Each transcode timeout is `duration × factor + 180` seconds, at least 180 and at most 7200. Playback uses 0.6. A 36-minute file is past the old flat 1200 seconds. A 120-minute file is about 4500 seconds, under the cap.

Layout copy:

- When the timeline has more than one composition, the headline names the dominant layout by duration (tie broken by segment count) and says how many segments include the camera.
- A single composition keeps the previous sentence, including "We found your camera and your screen."
- The detector, the regions, and the segment list are unchanged.

## Alternatives considered

- Keep the prefix key and raise the limit — every user would still share one bucket.
- Exempt every GET — a tight loop of report reads would have no per-user bound.
- Poll faster, or keep fetching artifacts during `processing` — that is the storm this records.
- Run audio, analysis, and playback ffmpeg at the same time — three 1080p decodes of an 819 MB file on one host. `veryfast` and one sprite pass are the speedup that stays inside the same memory shape.
- Change the layout detector so the headline and the timeline agree — the timeline was already right.

## Consequences

- An open session page is one event stream, a session GET about every 12 seconds, and one burst of artifact reads when a step finishes. Two tabs can land a report together inside the new burst.
- No Alembic migration. `duration_s` is already on `media_assets`. Existing originals stay NULL until a new ingest. A ready session still shows its length from the report.
- No new required environment variable. A host that exported the old `RATE_LIMIT_USER_PER_SEC=2` (or the old bursts) keeps that override until the variable is removed.
- Deploy is a rebuild of the api, worker, and web images. Cloudflare and the tunnel are unchanged.
- Playback files encoded after this change can be larger at the same CRF. In-flight jobs keep the old worker until that image is replaced, so they will not emit sub-steps or fill duration.
- The elapsed-clock fix is in the web image and applies to timestamps already stored without a zone.

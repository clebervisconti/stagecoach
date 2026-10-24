# ADR-085: Chunked resumable uploads under the Cloudflare body cap

**Date:** 2026-10-24
**Status:** Accepted
**Phase:** Online sessions

## Context

A signed-in admin uploaded an 819 MB, 35:49, 1920×1080 webinar (MP4, pt-BR, video consent on) to `https://stagecoach.cybersphere.com.br`. The wizard reached about 43% at roughly 167 MB/s and then showed "File too large · This file is 819 MB. The limit is 2 GB." No analysis started. It failed the same way on every retry.

The browser posts the whole recording as one multipart body to `/api/stagecoach/sessions/{id}/upload`. The Next.js route streams that body to FastAPI. There is no application body-size limit on that route. Cloudflare's proxied request limit is 100 MB on Free and Pro, 200 MB on Business, and configurable up to 5 GB only on Enterprise ([Error 413](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-413/)). A non-Enterprise zone rejects the larger request with HTTP 413 before the tunnel delivers it. The browser's upload progress counts bytes it has handed to the socket, so the bar can sit well past the cap when the 413 comes back.

The wizard treated every HTTP 413 as "this file exceeds 2 GB" and ignored the response body. An 819 MB file was described as over a 2 GB limit.

A second, independent 413 lived in the deploy defaults. `docker-compose.prod.yml`, `deploy/stagecoach-run.sh`, and `.env.example` set `MAX_UPLOAD_BYTES=83886080` (80 MiB). If that value is what the API process has, FastAPI returns 413 after 80 MiB and the same sentence hides it. The product copy and `apps/web/lib/online.ts` already say 2 GiB. Ingest refuses only above 2 GiB.

ADR-003 chose tus plus S3. Production does not run tusd. Originals are files under `MEDIA_ROOT`, and the worker reads those paths. Adding object storage would not fix the Cloudflare hop by itself, and it is a larger change than this bug.

## Decision

The browser uploads a recording in 8 MiB chunks. Each request is far under 100 MB.

- `POST /api/v1/sessions/{id}/uploads` checks the owner, the online-mode flag, the type, the declared size against the 2 GiB product limit, and webinar rights. It does not accept the bytes.
- `PUT /api/v1/sessions/{id}/uploads/{upload_id}/chunks/{index}` writes one chunk. The same bytes may be sent again. Different bytes for an index conflict. A body over 32 MiB is `chunk_too_large`, not `file_too_large`.
- `GET` returns the indexes still missing, so a dropped connection resumes.
- `POST .../complete` concatenates the chunks, checks the size and sha256, stores the original, enqueues the existing analysis task, and deletes the parts.
- The BFF allows `PUT` and keeps the same-origin check. The browser does not call the API directly. Every route still requires the bearer token and the session owner. Viewers cannot write.
- The client shows "File too large" only when the file is over 2 GiB. A 413, a proxy HTML page, or a dropped connection is a proxy or network error with Try again.
- `MAX_UPLOAD_BYTES` below 2 GiB is ignored and logged. The compose default, the run script, and `.env.example` are 2147483648. `media_assets.bytes` becomes `bigint` (migration 013) because a signed integer cannot store 2147483648.
- The old single-request `POST /upload` remains for a client on a private network. The wizard and the session form do not use it.

Chunks stay on the media volume next to the assembled file (`upload-parts/{upload_id}/`). Deleting the session still removes that directory. While a complete is in progress the volume holds the parts and the original, so a 2 GiB upload needs about 4 GiB free until the parts are removed.

## Alternatives considered

- Raise the Cloudflare plan or the zone's Maximum Upload Size. Enterprise can go to 5 GB. That spends money to keep a single request the edge is documented to reject, and it does not add resume.
- DNS-only for the hostname. The body cap goes away and so does the proxy in front of the origin.
- Presigned multipart upload to R2 or S3. ADR-003's direction, and the right one if originals leave the media volume. The worker would have to fetch the object before analysis. Not required to get a 2 GiB file through the current tunnel.
- tusd in front of the volume. Another process and a protocol, for the same disk the API already writes.

## Consequences

- An 819 MB webinar is a few dozen 8 MiB requests. A failed chunk retries, and Try again continues the same upload.
- Operators redeploy the web and API images. The API entrypoint already runs `alembic upgrade head` (migration 013). Remove a host-level `MAX_UPLOAD_BYTES` below 2 GiB if one is set; the process ignores it either way. No Cloudflare plan change and no new secret.
- The single-request route can still be rejected by Cloudflare. Browsers no longer call it for recordings.
- ADR-003 remains the note for a future move to object storage. This decision is the upload path production runs.

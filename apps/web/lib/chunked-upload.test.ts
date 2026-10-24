import assert from "node:assert/strict";
import { test } from "node:test";
import {
  DEFAULT_CHUNK_BYTES,
  MAX_CHUNK_BYTES,
  safeFilename,
  uploadRecordingChunked,
  type UploadRequest,
  type UploadTransport,
} from "./chunked-upload.ts";

const UPLOAD_ID = "a".repeat(32);
const PROXY_CAP = 10;

function json(status: number, body: unknown) {
  return { status, text: JSON.stringify(body) };
}

test("the browser chunk is 8 MiB and under a 100 MB proxy cap", () => {
  assert.equal(DEFAULT_CHUNK_BYTES, 8 * 1024 * 1024);
  assert.ok(DEFAULT_CHUNK_BYTES < 100 * 1024 * 1024);
  assert.ok(DEFAULT_CHUNK_BYTES <= MAX_CHUNK_BYTES);
});

test("a file larger than the proxy cap is split, and a dropped chunk is retried", async () => {
  const file = new File([new Uint8Array(25)], "webinar.mp4", { type: "video/mp4" });
  const puts: Array<{ index: string; size: number }> = [];
  let failuresLeft = 1;
  let completed = 0;
  const transport: UploadTransport = async (request) => {
    const bodySize = request.body instanceof Blob ? request.body.size : 0;
    if (bodySize > PROXY_CAP) return json(413, { detail: "payload too large" });
    if (request.method === "POST" && request.url.endsWith("/uploads")) {
      const declared = JSON.parse(String(request.body)) as { size: number; filename: string; rights_attested: boolean };
      assert.equal(declared.size, 25);
      assert.equal(declared.filename, "webinar.mp4");
      assert.equal(declared.rights_attested, true);
      return json(201, {
        upload_id: UPLOAD_ID,
        chunk_bytes: 8,
        size: 25,
        missing: [0, 1, 2, 3],
        complete: false,
      });
    }
    if (request.method === "PUT") {
      const index = request.url.split("/").pop() ?? "";
      puts.push({ index, size: bodySize });
      if (failuresLeft > 0) {
        failuresLeft -= 1;
        return json(502, { detail: "edge reset" });
      }
      return json(200, { upload_id: UPLOAD_ID, missing: [], complete: false });
    }
    if (request.url.endsWith("/complete")) {
      completed += 1;
      return json(202, { status: "preparing" });
    }
    return json(500, { detail: `unexpected ${request.method} ${request.url}` });
  };

  const seen: number[] = [];
  const outcome = await uploadRecordingChunked({
    sessionId: "session-1",
    file,
    rightsAttested: true,
    transport,
    sleeper: async () => undefined,
    onProgress: (value) => seen.push(value.pct),
  });

  assert.equal(outcome.ok, true);
  if (outcome.ok) assert.equal(outcome.uploadId, UPLOAD_ID);
  assert.deepEqual(
    puts.map((put) => put.index),
    ["0", "0", "1", "2", "3"],
  );
  assert.deepEqual(
    puts.map((put) => put.size),
    [8, 8, 8, 8, 1],
  );
  assert.ok(puts.every((put) => put.size <= PROXY_CAP));
  assert.equal(completed, 1);
  assert.equal(seen.at(-1), 100);
});

test("resume sends only the chunks the server is missing", async () => {
  const file = new File([new Uint8Array(10)], "talk.mp4", { type: "video/mp4" });
  const requests: string[] = [];
  const transport: UploadTransport = async (request: UploadRequest) => {
    requests.push(`${request.method} ${request.url}`);
    if (request.method === "GET") {
      return json(200, { upload_id: UPLOAD_ID, chunk_bytes: 4, missing: [1], received: [0, 2], complete: false });
    }
    if (request.method === "PUT") {
      return json(200, { upload_id: UPLOAD_ID, missing: [], complete: true });
    }
    if (request.url.endsWith("/complete")) return json(202, { status: "preparing" });
    return json(500, {});
  };

  const outcome = await uploadRecordingChunked({
    sessionId: "session-1",
    file,
    uploadId: UPLOAD_ID,
    transport,
    sleeper: async () => undefined,
  });
  assert.equal(outcome.ok, true);
  assert.deepEqual(requests, [
    `GET /api/stagecoach/sessions/session-1/uploads/${UPLOAD_ID}`,
    `PUT /api/stagecoach/sessions/session-1/uploads/${UPLOAD_ID}/chunks/1`,
    `POST /api/stagecoach/sessions/session-1/uploads/${UPLOAD_ID}/complete`,
  ]);
});

test("a filename keeps its extension when the path is long", () => {
  assert.equal(safeFilename("folder/talk.mp4"), "talk.mp4");
  const long = `${"a".repeat(240)}.mp4`;
  const safe = safeFilename(long);
  assert.ok(safe.endsWith(".mp4"));
  assert.ok(safe.length <= 200);
});

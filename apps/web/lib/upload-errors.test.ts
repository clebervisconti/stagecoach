import assert from "node:assert/strict";
import { test } from "node:test";
import { PRODUCT_MAX_BYTES, uploadErrorCopy } from "./upload-errors.ts";

const WEBINAR = 819 * 1024 * 1024;

function copy(status: number, fileSize: number, code?: string | null, detail?: string) {
  const used: string[] = [];
  const result = uploadErrorCopy({
    fileSize,
    maxBytes: PRODUCT_MAX_BYTES,
    status,
    code,
    detail,
    tooLarge: () => {
      used.push("too_large");
      return "too large";
    },
    proxy: () => {
      used.push("proxy");
      return "proxy rejected";
    },
    network: () => {
      used.push("network");
      return "connection dropped";
    },
    other: (text) => {
      used.push("other");
      return text || "other";
    },
  });
  return { ...result, used };
}

test("an 819 MB recording with HTTP 413 is a proxy rejection, not file too large", () => {
  const result = copy(413, WEBINAR, null, "<html>413 Payload Too Large</html>");
  assert.deepEqual(result.used, ["proxy"]);
  assert.equal(result.kind, "proxy");
  assert.equal(result.retry, true);
  assert.equal(result.message, "proxy rejected");
});

test("a server file_too_large code still is not 'too large' when the file is under 2 GB", () => {
  const result = copy(413, WEBINAR, "file_too_large", "This file is larger than the upload limit.");
  assert.equal(result.kind, "proxy");
  assert.equal(result.retry, true);
});

test("a file over 2 GB is too large even when the proxy also returns 413", () => {
  const result = copy(413, PRODUCT_MAX_BYTES + 1, "file_too_large");
  assert.equal(result.kind, "too_large");
  assert.equal(result.retry, false);
});

test("a dropped connection can be retried and is not described as too large", () => {
  const dropped = copy(0, WEBINAR);
  assert.equal(dropped.kind, "network");
  assert.equal(dropped.retry, true);
  const unavailable = copy(502, WEBINAR);
  assert.equal(unavailable.kind, "network");
});

test("an unsupported type is shown as itself and is not retried", () => {
  const result = copy(415, WEBINAR, "unsupported_type", "Unsupported file type");
  assert.equal(result.kind, "other");
  assert.equal(result.retry, false);
  assert.equal(result.message, "Unsupported file type");
});

test("HTML from a proxy is not pasted into the error", () => {
  const result = copy(401, 100, null, "<html>login</html>");
  assert.equal(result.kind, "other");
  assert.equal(result.message, "other");
});

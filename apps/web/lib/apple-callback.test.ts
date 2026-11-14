import assert from "node:assert/strict";
import { test } from "node:test";
import { appleFailureKey, planAppleCallback } from "./apple-callback.ts";

const stored = JSON.stringify({
  verifier: "verifier-value",
  nonce: "nonce-value",
  state: "state-value",
  redirect: "https://app.example/auth/apple/callback",
  invite: "invite-value",
});

test("a cancelled Apple redirect does not call the API", () => {
  const plan = planAppleCallback("?error=user_cancelled_authorize&state=state-value", stored);
  assert.deepEqual(plan, { type: "error", key: "cancelled" });
});

test("a state mismatch asks the person to start again", () => {
  const plan = planAppleCallback("?code=abc&state=other", stored);
  assert.deepEqual(plan, { type: "error", key: "startAgain" });
});

test("a matching callback keeps the code, nonce, and invite", () => {
  const plan = planAppleCallback("?code=abc&state=state-value", stored);
  assert.equal(plan.type, "finish");
  if (plan.type !== "finish") return;
  assert.equal(plan.body.code, "abc");
  assert.equal(plan.body.nonce, "nonce-value");
  assert.equal(plan.body.verifier, "verifier-value");
  assert.equal(plan.body.invite, "invite-value");
  assert.equal(JSON.stringify(plan).includes("secret"), false);
});

test("Apple API details stay on the safe list", () => {
  assert.equal(appleFailureKey(403, "No account is linked to this Apple ID."), "noAccount");
  assert.equal(appleFailureKey(503, "Sign in with Apple is not configured"), "unavailable");
  assert.equal(appleFailureKey(401, "Invalid Apple ID token"), "failed");
});

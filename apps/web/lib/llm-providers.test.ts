import assert from "node:assert/strict";
import { test } from "node:test";
import {
  DEFAULT_LLM_PROVIDER,
  leavesMachine,
  normalizeLlmSettings,
  normalizeProviderId,
} from "./llm-providers.ts";

test("xAI is the default and does not show the leave-machine warning", () => {
  assert.equal(normalizeProviderId(null), DEFAULT_LLM_PROVIDER);
  assert.equal(leavesMachine("xai"), false);
});

test("other cloud providers warn that data leaves the machine", () => {
  assert.equal(leavesMachine("openai"), true);
  assert.equal(leavesMachine("anthropic"), true);
  assert.equal(leavesMachine("gemini"), true);
  assert.equal(leavesMachine("custom", "https://api.example.com/v1"), true);
});

test("local loopback stays on the machine", () => {
  assert.equal(leavesMachine("local", "http://127.0.0.1:1234/v1"), false);
  assert.equal(leavesMachine("custom", "http://localhost:1234/v1"), false);
});

test("settings reject key-shaped fields", () => {
  assert.throws(() => normalizeLlmSettings({ provider: "xai", api_key: "sk-test" }));
});

test("unknown provider falls back to xAI", () => {
  const settings = normalizeLlmSettings({ provider: "mystery" });
  assert.equal(settings.provider, "xai");
});

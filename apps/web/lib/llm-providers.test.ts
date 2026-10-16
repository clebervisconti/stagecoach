import assert from "node:assert/strict";
import { test } from "node:test";
import {
  DEFAULT_LLM_PROVIDER,
  DEFAULT_LOCAL_MODEL,
  leavesMachine,
  normalizeLlmSettings,
  normalizeProviderId,
} from "./llm-providers.ts";

test("local LM Studio / Qwen is the default and stays on-box", () => {
  assert.equal(DEFAULT_LLM_PROVIDER, "local");
  assert.equal(normalizeProviderId(null), "local");
  const settings = normalizeLlmSettings(null);
  assert.equal(settings.provider, "local");
  assert.equal(settings.model, DEFAULT_LOCAL_MODEL);
  assert.equal(settings.base_url, "http://127.0.0.1:1234/v1");
  assert.equal(settings.leaves_machine, false);
  assert.equal(leavesMachine("local", "http://127.0.0.1:1234/v1"), false);
});

test("xAI is selectable and warns that data leaves the machine", () => {
  const settings = normalizeLlmSettings({ provider: "xai" });
  assert.equal(settings.provider, "xai");
  assert.equal(leavesMachine("xai"), true);
  assert.equal(settings.leaves_machine, true);
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

test("unknown provider falls back to local", () => {
  const settings = normalizeLlmSettings({ provider: "mystery" });
  assert.equal(settings.provider, "local");
});

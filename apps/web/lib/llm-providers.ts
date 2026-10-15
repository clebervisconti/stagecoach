export const LLM_PROVIDERS = [
  "xai",
  "local",
  "anthropic",
  "openai",
  "gemini",
  "custom",
] as const;

export type LlmProviderId = (typeof LLM_PROVIDERS)[number];

export const DEFAULT_LLM_PROVIDER: LlmProviderId = "xai";

export const DEFAULT_LLM_BASE_URLS: Record<LlmProviderId, string> = {
  xai: "https://api.x.ai/v1",
  local: "http://127.0.0.1:1234/v1",
  anthropic: "https://api.anthropic.com",
  openai: "https://api.openai.com/v1",
  gemini: "https://generativelanguage.googleapis.com/v1beta/openai",
  custom: "",
};

export type LlmSettings = {
  provider: LlmProviderId;
  base_url: string;
  model: string;
  leaves_machine: boolean;
};

const LOOPBACK = new Set(["localhost", "127.0.0.1", "::1", "0.0.0.0"]);

export function normalizeProviderId(raw: unknown): LlmProviderId {
  if (typeof raw === "string" && (LLM_PROVIDERS as readonly string[]).includes(raw)) {
    return raw as LlmProviderId;
  }
  return DEFAULT_LLM_PROVIDER;
}

export function isLoopbackUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return LOOPBACK.has(host);
  } catch {
    return false;
  }
}

export function leavesMachine(provider: LlmProviderId, baseUrl = ""): boolean {
  if (provider === "xai") return false;
  if (provider === "local") return !isLoopbackUrl(baseUrl || DEFAULT_LLM_BASE_URLS.local);
  if (provider === "custom") return !isLoopbackUrl(baseUrl);
  return provider === "anthropic" || provider === "openai" || provider === "gemini";
}

export function normalizeLlmSettings(raw: unknown): LlmSettings {
  const src = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  for (const key of Object.keys(src)) {
    const lower = key.toLowerCase();
    if (lower.includes("key") || lower.includes("secret") || lower.includes("token")) {
      throw new Error("API keys must not be stored in settings");
    }
  }
  const provider = normalizeProviderId(src.provider);
  let base_url = typeof src.base_url === "string" ? src.base_url.trim() : "";
  if ((provider === "local" || provider === "custom") && !base_url) {
    base_url = DEFAULT_LLM_BASE_URLS[provider];
  }
  const model = typeof src.model === "string" ? src.model.trim() : "";
  return {
    provider,
    base_url,
    model,
    leaves_machine: leavesMachine(provider, base_url),
  };
}

export function emptyLlmSettings(): LlmSettings {
  return normalizeLlmSettings(null);
}

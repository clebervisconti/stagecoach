export type AppleCallbackKey = "cancelled" | "unavailable" | "startAgain" | "noAccount" | "invalidInvite" | "failed";

export type AppleStoredState = {
  verifier: string;
  nonce: string;
  state: string;
  redirect: string;
  invite?: string;
};

export type AppleCallbackPlan =
  | { type: "error"; key: AppleCallbackKey }
  | {
      type: "finish";
      body: {
        code?: string;
        id_token?: string;
        nonce: string;
        verifier: string;
        redirect_uri: string;
        invite?: string;
      };
    };

const NO_ACCOUNT = "No account is linked to this Apple ID.";
const INVALID_INVITE = "This invite is invalid or expired.";

export function readStoredAppleState(raw: string | null): AppleStoredState | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<AppleStoredState>;
    if (!parsed.verifier || !parsed.nonce || !parsed.state || !parsed.redirect) return null;
    return {
      verifier: parsed.verifier,
      nonce: parsed.nonce,
      state: parsed.state,
      redirect: parsed.redirect,
      invite: parsed.invite || undefined,
    };
  } catch {
    return null;
  }
}

export function planAppleCallback(search: string, storedRaw: string | null): AppleCallbackPlan {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const error = params.get("error");
  if (error === "user_cancelled_authorize") return { type: "error", key: "cancelled" };
  if (error) return { type: "error", key: "failed" };
  const stored = readStoredAppleState(storedRaw);
  if (!stored) return { type: "error", key: "startAgain" };
  const state = params.get("state");
  if (!state || state !== stored.state) return { type: "error", key: "startAgain" };
  const code = params.get("code") || undefined;
  const idToken = params.get("id_token") || undefined;
  if (!code && !idToken) return { type: "error", key: "failed" };
  return {
    type: "finish",
    body: {
      code,
      id_token: idToken,
      nonce: stored.nonce,
      verifier: stored.verifier,
      redirect_uri: stored.redirect,
      invite: stored.invite,
    },
  };
}

export function appleFailureKey(status: number, detail: string): AppleCallbackKey {
  if (detail === NO_ACCOUNT) return "noAccount";
  if (detail === INVALID_INVITE) return "invalidInvite";
  if (status === 503) return "unavailable";
  return "failed";
}

export const APPLE_CALLBACK_COPY = {
  en: {
    working: "Finishing Sign in with Apple…",
    cancelled: "Sign in with Apple was cancelled.",
    unavailable: "Sign in with Apple is unavailable.",
    startAgain: "Start Sign in with Apple again from the sign-in page.",
    noAccount: "No account is linked to this Apple ID. Ask an administrator for access.",
    invalidInvite: "This invite is invalid or expired.",
    failed: "Sign in with Apple could not be completed.",
    back: "Back to sign in",
  },
  "pt-BR": {
    working: "Concluindo a entrada com a Apple…",
    cancelled: "A entrada com a Apple foi cancelada.",
    unavailable: "A entrada com a Apple não está disponível.",
    startAgain: "Comece de novo a entrada com a Apple na página de acesso.",
    noAccount: "Nenhuma conta está ligada a este ID Apple. Peça acesso a um administrador.",
    invalidInvite: "Este convite é inválido ou expirou.",
    failed: "Não foi possível concluir a entrada com a Apple.",
    back: "Voltar para entrar",
  },
} as const;

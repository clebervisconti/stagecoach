import { auth } from "@/auth";
import { SignJWT } from "jose";

const issuer = "stagecoach-web";
const audience = "stagecoach-api";

type Account = {
  id: string;
  email: string;
  sessionVersion: number;
};

export async function currentAccount(): Promise<Account | null> {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) return null;
  return {
    id: session.user.id || email,
    email,
    sessionVersion: session.user.sessionVersion ?? 0,
  };
}

export async function currentEmail(): Promise<string | null> {
  const account = await currentAccount();
  return account?.email ?? null;
}

async function apiToken(account: Account): Promise<string> {
  const secret = process.env["AUTH_SECRET"];
  if (!secret || secret.length < 32) {
    throw new Error("AUTH_SECRET must contain at least 32 characters");
  }
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({ email: account.email, sv: account.sessionVersion })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuer(issuer)
    .setAudience(audience)
    .setSubject(account.id)
    .setIssuedAt(now)
    .setNotBefore(now - 5)
    .setExpirationTime(now + 60)
    .sign(new TextEncoder().encode(secret));
}

export async function stagecoachApi(
  path: string,
  init: RequestInit = {},
  options: { anonymous?: boolean } = {},
): Promise<Response> {
  const account = options.anonymous ? null : await currentAccount();
  if (!account && !options.anonymous) {
    return new Response(JSON.stringify({ detail: "Unauthorized" }), {
      status: 401,
      headers: { "content-type": "application/json" },
    });
  }
  const base = process.env["INTERNAL_API_URL"] || "http://127.0.0.1:8000";
  const token = account ? await apiToken(account) : null;
  const headers = new Headers(init.headers);
  if (token) headers.set("authorization", `Bearer ${token}`);
  return fetch(`${base}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

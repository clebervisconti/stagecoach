import { auth } from "@/auth";
import { SignJWT } from "jose";

const issuer = "stagecoach-web";
const audience = "stagecoach-api";

export async function currentEmail(): Promise<string | null> {
  if (process.env.PRIVATE_BETA_MODE === "true") {
    return process.env.PRIVATE_BETA_EMAIL || null;
  }
  const session = await auth();
  return session?.user?.email || null;
}

async function apiToken(email: string): Promise<string> {
  const secret = process.env.AUTH_SECRET;
  if (!secret || secret.length < 32) {
    throw new Error("AUTH_SECRET must contain at least 32 characters");
  }
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({ email })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuer(issuer)
    .setAudience(audience)
    .setSubject(email)
    .setIssuedAt(now)
    .setNotBefore(now - 5)
    .setExpirationTime(now + 60)
    .sign(new TextEncoder().encode(secret));
}

export async function stagecoachApi(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const email = await currentEmail();
  if (!email) {
    return new Response(JSON.stringify({ detail: "Unauthorized" }), {
      status: 401,
      headers: { "content-type": "application/json" },
    });
  }
  const base = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";
  const token = await apiToken(email);
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${token}`);
  return fetch(`${base}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

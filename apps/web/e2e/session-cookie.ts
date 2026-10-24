import { encode } from "next-auth/jwt";

export const E2E_AUTH_SECRET = process.env.AUTH_SECRET || "ci-build-placeholder-not-a-runtime-secret";

/** Playwright talks to http://localhost, so the cookie is never the __Secure- name. */
export const E2E_SESSION_COOKIE = "authjs.session-token";

export async function sessionCookie(input: {
  email: string;
  role: string;
  mustChangePassword: boolean;
  sessionVersion?: number;
  id?: string;
}) {
  const id = input.id || "11111111-1111-4111-8111-111111111101";
  const value = await encode({
    token: {
      sub: id,
      id,
      email: input.email,
      role: input.role,
      mustChangePassword: input.mustChangePassword,
      sessionVersion: input.sessionVersion ?? 1,
    },
    secret: E2E_AUTH_SECRET,
    salt: E2E_SESSION_COOKIE,
    maxAge: 60 * 60 * 12,
  });
  return {
    name: E2E_SESSION_COOKIE,
    value,
    domain: "localhost",
    path: "/",
    httpOnly: true,
    secure: false,
    sameSite: "Lax" as const,
    expires: Math.floor(Date.now() / 1000) + 60 * 60 * 12,
  };
}

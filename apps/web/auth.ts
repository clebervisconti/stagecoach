import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { authConfig } from "./auth.config";

const apiBase = () => process.env["INTERNAL_API_URL"] || "http://127.0.0.1:8000";

function secureCookie(): boolean {
  const url = process.env["AUTH_URL"] || process.env["NEXTAUTH_URL"] || "";
  return url.startsWith("https://");
}

type Identity = {
  id: string;
  email: string;
  role?: string;
  must_change_password?: boolean;
  session_version?: number;
};

function account(body: Identity) {
  return {
    id: body.id,
    email: body.email,
    role: body.role || "member",
    mustChangePassword: Boolean(body.must_change_password),
    sessionVersion: Number(body.session_version ?? 0),
  };
}

const secure = secureCookie();

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  session: { strategy: "jwt", maxAge: 60 * 60 * 12 },
  useSecureCookies: secure,
  cookies: {
    sessionToken: {
      name: secure ? "__Secure-authjs.session-token" : "authjs.session-token",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure,
      },
    },
  },
  providers: [
    Credentials({
      id: "credentials",
      name: "Email and password",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
        ticket: { label: "Ticket", type: "text" },
      },
      async authorize(credentials) {
        const ticket = String(credentials?.ticket || "");
        if (ticket) {
          const response = await fetch(`${apiBase()}/api/v1/auth/session-ticket`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ ticket }),
          });
          if (!response.ok) return null;
          return account((await response.json()) as Identity);
        }
        const email = String(credentials?.email || "").trim().toLowerCase();
        const password = String(credentials?.password || "");
        if (!email || !password) return null;
        const response = await fetch(`${apiBase()}/api/v1/auth/login`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!response.ok) return null;
        return account((await response.json()) as Identity);
      },
    }),
  ],
});

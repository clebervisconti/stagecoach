import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { authConfig } from "./auth.config";

const apiBase = () => process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
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
          const body = (await response.json()) as { id: string; email: string };
          return { id: body.id, email: body.email };
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
        const body = (await response.json()) as { id: string; email: string };
        return { id: body.id, email: body.email };
      },
    }),
  ],
});

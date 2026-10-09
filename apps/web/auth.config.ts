import type { NextAuthConfig } from "next-auth";
import Resend from "next-auth/providers/resend";

export const authConfig = {
  providers: [
    Resend({
      apiKey: process.env.RESEND_API_KEY || "fake-key-for-dev",
      from: process.env.EMAIL_FROM || "noreply@stagecoach.example.com",
    }),
  ],
  pages: {
    signIn: "/sign-in",
    verifyRequest: "/verify-request",
    error: "/auth/error",
  },
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user;
      const isOnApp = nextUrl.pathname.startsWith("/sessions") ||
        nextUrl.pathname.startsWith("/trends") ||
        nextUrl.pathname.startsWith("/settings") ||
        nextUrl.pathname.startsWith("/prep");
      
      if (isOnApp) {
        if (isLoggedIn) return true;
        return false; // Redirect unauthenticated users to login page
      } else if (isLoggedIn) {
        return Response.redirect(new URL("/sessions", nextUrl));
      }
      return true;
    },
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      if (token && session.user) {
        session.user.id = token.id as string;
      }
      return session;
    },
  },
} satisfies NextAuthConfig;

import type { NextAuthConfig } from "next-auth";
import Nodemailer from "next-auth/providers/nodemailer";

export const authConfig = {
  providers: [
    Nodemailer({
      server: process.env.EMAIL_SERVER || {
        host: "localhost",
        port: 1025,
        auth: null,
      },
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

import type { NextAuthConfig } from "next-auth";

export const authConfig = {
  // Cloudflare Access is the private-beta identity boundary. Application
  // providers stay disabled until a production identity design is approved.
  providers: [],
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

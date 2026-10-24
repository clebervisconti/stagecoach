import type { NextAuthConfig } from "next-auth";

export const authConfig = {
  // D9: email+password and Sign in with Apple live in auth.ts (Credentials +
  // Apple OIDC on the API). Magic-link and Google/Microsoft providers are retired.
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
        if (user.email) token.email = user.email;
        token.role = user.role ?? "member";
        token.mustChangePassword = Boolean(user.mustChangePassword);
        token.sessionVersion = Number(user.sessionVersion ?? 0);
      }
      return token;
    },
    async session({ session, token }) {
      if (token && session.user) {
        if (typeof token.id === "string") session.user.id = token.id;
        if (typeof token.email === "string") session.user.email = token.email;
        session.user.role = typeof token.role === "string" ? token.role : "member";
        session.user.mustChangePassword = Boolean(token.mustChangePassword);
        session.user.sessionVersion =
          typeof token.sessionVersion === "number" ? token.sessionVersion : 0;
      }
      return session;
    },
  },
} satisfies NextAuthConfig;

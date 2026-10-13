import { redirectToSessions } from "@/lib/redirect-to-sessions";

export default async function SignInPage() {
  // Cloudflare Access owns private-beta login.
  await redirectToSessions();
}

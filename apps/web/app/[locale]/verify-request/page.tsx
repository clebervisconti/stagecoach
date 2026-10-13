import { redirectToSessions } from "@/lib/redirect-to-sessions";

export default async function VerifyRequestPage() {
  await redirectToSessions();
}

import { redirect } from "next/navigation";

export default function SignInPage() {
  // Cloudflare Access owns private-beta login.
  redirect("/sessions");
}

import Link from "next/link";

export default function VerifyRequestPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="max-w-md space-y-3 text-center">
        <h1 className="text-2xl font-bold">Magic links are retired</h1>
        <p className="text-sm text-muted-foreground">
          Sign in with email and password, or Sign in with Apple. Verification and reset
          tokens arrive through the email stand-in until a production provider (D10) is chosen.
        </p>
        <Link href="/sign-in" className="text-sm underline">
          Back to sign in
        </Link>
      </div>
    </div>
  );
}

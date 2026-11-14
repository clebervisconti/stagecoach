import { Suspense } from "react";
import { AuthFrame } from "@/components/auth/auth-frame";
import { SignInForm } from "@/components/auth/sign-in-form";
import { titled } from "@/lib/titles";

export function generateMetadata() {
  return titled("Sign in", "Entrar");
}

export default function SignInPage() {
  return (
    <AuthFrame>
      <Suspense fallback={<p className="text-base">Loading</p>}>
        <SignInForm />
      </Suspense>
    </AuthFrame>
  );
}

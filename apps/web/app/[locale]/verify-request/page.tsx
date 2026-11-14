import { Suspense } from "react";
import { AuthFrame } from "@/components/auth/auth-frame";
import { VerifyForm } from "@/components/auth/verify-form";
import { titled } from "@/lib/titles";

export function generateMetadata() {
  return titled("Confirm your email", "Confirme seu e-mail");
}

export default function VerifyRequestPage() {
  return (
    <AuthFrame>
      <Suspense fallback={<p className="text-base">Loading</p>}>
        <VerifyForm />
      </Suspense>
    </AuthFrame>
  );
}

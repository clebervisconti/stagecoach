import { SignInForm } from "@/components/auth/sign-in-form";

export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full min-w-0 max-w-md">
        <SignInForm />
      </div>
    </div>
  );
}

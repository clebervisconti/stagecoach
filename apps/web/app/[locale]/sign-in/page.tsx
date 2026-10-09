"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { signIn } from "next-auth/react";

export default function SignInPage() {
  const t = useTranslations("auth");
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const result = await signIn("nodemailer", {
        email,
        redirect: false,
        callbackUrl: "/sessions",
      });

      if (result?.error) {
        setError(t("invalidEmail"));
      } else {
        // Redirect to verify-request page
        window.location.href = "/verify-request?email=" + encodeURIComponent(email);
      }
    } catch (err) {
      setError(t("invalidEmail"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/50 px-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold">Stage Coach</h1>
          <h2 className="mt-4 text-2xl font-semibold">{t("signInTitle")}</h2>
          <p className="mt-2 text-muted-foreground">{t("signInDescription")}</p>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-6">
          <div className="rounded-lg bg-card p-6 shadow">
            <label htmlFor="email" className="block text-sm font-medium">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-2 block w-full rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder={t("emailPlaceholder")}
            />
            
            {error && (
              <p className="mt-2 text-sm text-destructive">{error}</p>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="mt-4 w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {isLoading ? t("loading") : t("sendMagicLink")}
            </button>
          </div>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Phase 0 - Development
        </p>
      </div>
    </div>
  );
}

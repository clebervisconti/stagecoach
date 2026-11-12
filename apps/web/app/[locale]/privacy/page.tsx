import type { Metadata } from "next";
import { getLocale } from "next-intl/server";
import { privacyPolicy } from "@/lib/privacy-policy";

export const metadata: Metadata = {
  title: "Privacy - Stage Coach",
};

export default async function PrivacyPage() {
  const locale = await getLocale();
  const copy = privacyPolicy(locale);
  const signIn = locale === "pt-BR" ? "/pt-BR/sign-in" : "/sign-in";

  return (
    <main className="mx-auto min-h-screen max-w-2xl px-4 py-12" data-testid="privacy-policy">
      <h1 className="text-2xl">{copy.title}</h1>
      {copy.paragraphs.map((paragraph) => (
        <p key={paragraph} className="mt-4 text-sm leading-6" data-testid="privacy-paragraph">
          {paragraph}
        </p>
      ))}
      <p className="mt-8 text-sm">
        <a href={signIn} className="underline">
          {copy.back}
        </a>
      </p>
    </main>
  );
}

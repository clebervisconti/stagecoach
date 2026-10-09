import { useTranslations } from "next-intl";
import Link from "next/link";

export default function HomePage() {
  const t = useTranslations("marketing");

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <h1 className="text-2xl font-bold">Stage Coach</h1>
          <Link
            href="/sign-in"
            className="rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
          >
            {t("getStarted")}
          </Link>
        </div>
      </header>

      <main className="flex-1">
        <section className="container mx-auto px-4 py-24 text-center">
          <h2 className="mb-6 text-4xl font-bold tracking-tight sm:text-6xl">
            {t("tagline")}
          </h2>
          <p className="mx-auto mb-8 max-w-2xl text-lg text-muted-foreground">
            {t("description")}
          </p>
          <div className="flex justify-center gap-4">
            <Link
              href="/sign-in"
              className="rounded-md bg-primary px-6 py-3 text-lg font-medium text-primary-foreground hover:bg-primary/90"
            >
              {t("getStarted")}
            </Link>
            <Link
              href="/about"
              className="rounded-md border border-input bg-background px-6 py-3 text-lg font-medium hover:bg-accent hover:text-accent-foreground"
            >
              {t("learnMore")}
            </Link>
          </div>
        </section>

        <section className="border-t bg-muted/50 py-16">
          <div className="container mx-auto px-4">
            <h3 className="mb-8 text-center text-2xl font-bold">
              Research-Grounded Coaching
            </h3>
            <div className="grid gap-8 md:grid-cols-3">
              <div className="rounded-lg bg-card p-6 text-card-foreground shadow">
                <h4 className="mb-2 text-lg font-semibold">Evidence-Based</h4>
                <p className="text-muted-foreground">
                  Every metric traces to published research or labeled heuristics.
                </p>
              </div>
              <div className="rounded-lg bg-card p-6 text-card-foreground shadow">
                <h4 className="mb-2 text-lg font-semibold">Clickable Evidence</h4>
                <p className="text-muted-foreground">
                  Every finding links to timestamps in your recording.
                </p>
              </div>
              <div className="rounded-lg bg-card p-6 text-card-foreground shadow">
                <h4 className="mb-2 text-lg font-semibold">Context-Aware</h4>
                <p className="text-muted-foreground">
                  Keynotes, briefings, and pitches are scored differently.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>&copy; 2026 Stage Coach. Phase 0 - Foundations.</p>
        </div>
      </footer>
    </div>
  );
}

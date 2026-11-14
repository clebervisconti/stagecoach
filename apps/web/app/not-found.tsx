import Link from "next/link";
import { BrandLockup } from "@/components/brand/brand-lockup";
import "./globals.css";

const themeScript = `(function(){try{var saved=localStorage.getItem("cs-theme");var theme=saved==="light"||saved==="dark"?saved:(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");document.documentElement.dataset.theme=theme;}catch(e){document.documentElement.dataset.theme="dark";}})();`;

export default function RootNotFound() {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <title>Page not found · Stage Coach</title>
        <meta name="robots" content="noindex, nofollow" />
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <main id="main" className="min-h-screen px-6 py-8 md:px-16 md:py-12">
          <div className="max-w-md">
            <BrandLockup />
            <p className="mt-4 text-base leading-[26px] text-[color:var(--text-secondary)]">
              Upload or record a talk. Get research-backed feedback.
            </p>
            <h1 className="mt-10 text-3xl">Page not found</h1>
            <p className="mt-3 text-base leading-[26px] text-[color:var(--text-secondary)]">
              That address is not in Stage Coach.
            </p>
            <Link href="/sessions" className="cs-button cs-button-primary mt-8">
              Go to sessions
            </Link>
            <footer className="mt-16 border-t border-[color:var(--line)] pt-6">
              <Link href="/privacy" className="cs-text-link">
                Privacy
              </Link>
            </footer>
          </div>
        </main>
      </body>
    </html>
  );
}

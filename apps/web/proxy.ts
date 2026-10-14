import createMiddleware from "next-intl/middleware";
import { locales } from "./i18n";

export default createMiddleware({
  locales,
  defaultLocale: "en",
  localePrefix: "as-needed",
  // Cookie-based locale detection 307s /sessions onto itself under next-intl 4 + Next 16,
  // which breaks Playwright's health check and the first document load. Locale stays in the URL.
  localeDetection: false,
});

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};

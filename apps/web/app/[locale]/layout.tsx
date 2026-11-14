import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { Rum } from "@/components/rum";
import "../globals.css";

const themeScript = `(function(){try{var saved=localStorage.getItem("cs-theme");var theme=saved==="light"||saved==="dark"?saved:(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");document.documentElement.dataset.theme=theme;}catch(e){document.documentElement.dataset.theme="dark";}})();`;

export const metadata: Metadata = {
  metadataBase: new URL("https://stagecoach.cybersphere.com.br"),
  title: {
    default: "Stage Coach",
    template: "%s · Stage Coach",
  },
  description: "Upload or record a talk. Get research-backed feedback.",
  robots: { index: false, follow: false },
  icons: { icon: "/favicon.ico", apple: "/apple-icon.png" },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)" />
        <meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)" />
        <link rel="preload" href="/fonts/D-DIN-Bold.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
        <link rel="preload" href="/fonts/Geist-Variable.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
      </head>
      <body>
        <Rum />
        <NextIntlClientProvider messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}

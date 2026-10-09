import { auth } from "@/auth";
import { redirect } from "next/navigation";
import { useTranslations } from "next-intl";
import Link from "next/link";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();

  if (!session) {
    redirect("/sign-in");
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-8">
            <Link href="/sessions" className="text-xl font-bold">
              Stage Coach
            </Link>
            <nav className="flex gap-6">
              <Link
                href="/sessions"
                className="text-sm font-medium hover:text-primary"
              >
                Sessions
              </Link>
              <Link
                href="/prep"
                className="text-sm font-medium hover:text-primary"
              >
                Prep
              </Link>
              <Link
                href="/trends"
                className="text-sm font-medium hover:text-primary"
              >
                Trends
              </Link>
            </nav>
          </div>
          
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              {session.user?.email}
            </span>
            <Link
              href="/settings"
              className="text-sm font-medium hover:text-primary"
            >
              Settings
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>
    </div>
  );
}

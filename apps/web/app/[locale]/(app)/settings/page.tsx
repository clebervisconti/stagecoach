import { auth, signOut } from "@/auth";

export default async function SettingsPage() {
  const session = await auth();

  return (
    <div className="container mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-8 text-3xl font-bold">Settings</h1>

      <div className="space-y-6">
        <div className="rounded-lg border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">Account</h2>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Email</span>
              <span>{session?.user?.email}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Locale</span>
              <span>English</span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">Session</h2>
          <form
            action={async () => {
              "use server";
              await signOut();
            }}
          >
            <button
              type="submit"
              className="rounded-md border border-input bg-background px-4 py-2 font-medium hover:bg-accent hover:text-accent-foreground"
            >
              Sign Out
            </button>
          </form>
        </div>

        <p className="text-sm text-muted-foreground">
          Phase 0 - Profile editing and consent management coming in later phases
        </p>
      </div>
    </div>
  );
}

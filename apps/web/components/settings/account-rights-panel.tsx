"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

type DeletionState = {
  status: string;
  due_at?: string | null;
  requested_at?: string | null;
  grace_days?: number;
};

export function AccountRightsPanel() {
  const t = useTranslations("accountRights");
  const [deletion, setDeletion] = useState<DeletionState>({ status: "none" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/stagecoach/me/deletion", { cache: "no-store" });
    if (!response.ok) throw new Error(t("loadError"));
    const body = (await response.json()) as DeletionState;
    setDeletion(body);
  }, [t]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void load().catch((reason: Error) => setError(reason.message));
    }, 0);
    return () => window.clearTimeout(id);
  }, [load]);

  async function exportData() {
    setBusy("export");
    setError("");
    try {
      const response = await fetch("/api/stagecoach/me/export", { method: "POST" });
      if (!response.ok) throw new Error(t("exportError"));
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const header = response.headers.get("content-disposition") || "";
      const match = /filename="([^"]+)"/.exec(header);
      link.href = url;
      link.download = match?.[1] || "stagecoach-export.zip";
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("exportError"));
    } finally {
      setBusy("");
    }
  }

  async function requestDelete() {
    if (!window.confirm(t("deleteConfirm"))) return;
    setBusy("delete");
    setError("");
    try {
      const response = await fetch("/api/stagecoach/me", { method: "DELETE" });
      const body = (await response.json()) as DeletionState & { detail?: string };
      if (!response.ok) throw new Error(body.detail || t("deleteError"));
      setDeletion(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("deleteError"));
    } finally {
      setBusy("");
    }
  }

  async function cancelDelete() {
    setBusy("cancel");
    setError("");
    try {
      const response = await fetch("/api/stagecoach/me/deletion", { method: "DELETE" });
      if (!response.ok) throw new Error(t("cancelError"));
      setDeletion({ status: "none" });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("cancelError"));
    } finally {
      setBusy("");
    }
  }

  const pending = deletion.status === "pending";

  return (
    <section
      data-testid="account-rights-panel"
      className="rounded-lg border bg-card p-6"
      aria-labelledby="account-rights-heading"
    >
      <h2 id="account-rights-heading" className="text-lg font-semibold">
        {t("heading")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("intro")}</p>
      {error ? (
        <div role="alert" className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm">
          {error}
        </div>
      ) : null}
      {pending ? (
        <p data-testid="deletion-pending" className="mt-3 text-sm">
          {t("pending", { due: deletion.due_at || "" })}
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          data-testid="export-data"
          className="rounded-md border border-input bg-background px-4 py-2 font-medium hover:bg-accent hover:text-accent-foreground"
          disabled={busy === "export"}
          onClick={() => void exportData()}
        >
          {busy === "export" ? t("exporting") : t("export")}
        </button>
        {pending ? (
          <button
            type="button"
            data-testid="cancel-deletion"
            className="rounded-md border border-input bg-background px-4 py-2 font-medium hover:bg-accent hover:text-accent-foreground"
            disabled={busy === "cancel"}
            onClick={() => void cancelDelete()}
          >
            {t("cancel")}
          </button>
        ) : (
          <button
            type="button"
            data-testid="delete-account"
            className="rounded-md border border-destructive/40 bg-background px-4 py-2 font-medium text-destructive hover:bg-destructive/10"
            disabled={busy === "delete"}
            onClick={() => void requestDelete()}
          >
            {t("delete")}
          </button>
        )}
      </div>
    </section>
  );
}

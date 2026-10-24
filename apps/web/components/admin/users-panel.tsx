"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useLocale } from "next-intl";
import { ConfirmDialog } from "@/components/layout/confirm-dialog";

const COPY = {
  en: {
    heading: "Users",
    intro: "Admins manage accounts. Members coach their own talks. Viewers can read, not change.",
    search: "Search",
    searchLabel: "Search by email or name",
    loading: "Loading users…",
    empty: "No users match this search.",
    loadError: "Could not load users.",
    retry: "Try again",
    create: "Create user",
    email: "Email",
    name: "Name",
    role: "Role",
    temp: "Temporary password",
    tempHint: "Leave blank to generate one. It must be changed at first sign-in.",
    online: "Online modes",
    submit: "Create",
    saving: "Saving…",
    created: "User created. Temporary password (shown once):",
    resetDone: "Temporary password (shown once):",
    disable: "Disable",
    enable: "Enable",
    onlineOn: "Turn online modes on",
    onlineOff: "Turn online modes off",
    reset: "Force password reset",
    revoke: "Revoke sessions",
    delete: "Delete",
    confirmTitle: "Delete this user?",
    confirmBody: "Sessions end immediately. The email can be used again.",
    cancel: "Cancel",
    disabled: "Disabled",
    mustChange: "Must change password",
    apple: "Apple linked",
    verified: "Email verified",
    actionError: "Could not update that user.",
  },
  "pt-BR": {
    heading: "Usuários",
    intro: "Admins administram contas. Membros treinam as próprias palestras. Visitantes leem, sem alterar.",
    search: "Buscar",
    searchLabel: "Buscar por e-mail ou nome",
    loading: "Carregando usuários…",
    empty: "Nenhum usuário corresponde a esta busca.",
    loadError: "Não foi possível carregar os usuários.",
    retry: "Tentar de novo",
    create: "Criar usuário",
    email: "E-mail",
    name: "Nome",
    role: "Papel",
    temp: "Senha temporária",
    tempHint: "Deixe em branco para gerar. A troca é obrigatória no primeiro acesso.",
    online: "Modos online",
    submit: "Criar",
    saving: "Salvando…",
    created: "Usuário criado. Senha temporária (mostrada uma vez):",
    resetDone: "Senha temporária (mostrada uma vez):",
    disable: "Desativar",
    enable: "Ativar",
    onlineOn: "Ligar modos online",
    onlineOff: "Desligar modos online",
    reset: "Forçar nova senha",
    revoke: "Revogar sessões",
    delete: "Excluir",
    confirmTitle: "Excluir este usuário?",
    confirmBody: "As sessões terminam na hora. O e-mail pode ser usado de novo.",
    cancel: "Cancelar",
    disabled: "Desativado",
    mustChange: "Precisa trocar a senha",
    apple: "Apple vinculada",
    verified: "E-mail verificado",
    actionError: "Não foi possível atualizar esse usuário.",
  },
} as const;

type Role = "admin" | "member" | "viewer";

type UserRow = {
  id: string;
  email: string;
  name: string | null;
  role: Role;
  disabled: boolean;
  must_change_password: boolean;
  online_modes: boolean;
  email_verified: boolean;
  apple_linked: boolean;
};

type Phase = "loading" | "error" | "empty" | "success";

export function AdminUsersPanel() {
  const locale = useLocale();
  const t = COPY[locale === "pt-BR" ? "pt-BR" : "en"];
  const [phase, setPhase] = useState<Phase>("loading");
  const [users, setUsers] = useState<UserRow[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<UserRow | null>(null);

  const applyUsers = useCallback((next: UserRow[]) => {
    setUsers(next);
    setPhase(next.length ? "success" : "empty");
  }, []);

  const load = useCallback(
    async (q: string) => {
      setPhase("loading");
      setError("");
      try {
        const response = await fetch(`/api/stagecoach/admin/users?q=${encodeURIComponent(q)}`, {
          cache: "no-store",
        });
        if (!response.ok) throw new Error(t.loadError);
        const body = (await response.json()) as { users?: UserRow[] };
        applyUsers(body.users ?? []);
      } catch (reason) {
        setUsers([]);
        setPhase("error");
        setError(reason instanceof Error ? reason.message : t.loadError);
      }
    },
    [applyUsers, t.loadError],
  );

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/stagecoach/admin/users?q=", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(t.loadError);
        const body = (await response.json()) as { users?: UserRow[] };
        return body.users ?? [];
      })
      .then((next) => {
        applyUsers(next);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setUsers([]);
        setPhase("error");
        setError(reason instanceof Error ? reason.message : t.loadError);
      });
    return () => controller.abort();
  }, [applyUsers, t.loadError]);

  async function mutate(path: string, method: string, payload?: object) {
    setBusy(true);
    setNotice("");
    setError("");
    try {
      const response = await fetch(path, {
        method,
        headers: payload ? { "content-type": "application/json" } : undefined,
        body: payload ? JSON.stringify(payload) : undefined,
      });
      const body = (await response.json().catch(() => null)) as {
        detail?: string;
        temporary_password?: string;
      } | null;
      if (!response.ok) {
        setError(typeof body?.detail === "string" ? body.detail : t.actionError);
        return null;
      }
      return body;
    } catch {
      setError(t.actionError);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const temp = String(form.get("temp_password") || "");
    const body = await mutate("/api/stagecoach/admin/users", "POST", {
      email: String(form.get("email") || ""),
      name: String(form.get("name") || "") || null,
      role: String(form.get("role") || "member"),
      temp_password: temp || null,
      online_modes: form.get("online_modes") === "on",
    });
    if (!body) return;
    event.currentTarget.reset();
    if (body.temporary_password) setNotice(`${t.created} ${body.temporary_password}`);
    await load(query);
  }

  async function patch(user: UserRow, payload: object) {
    const body = await mutate(`/api/stagecoach/admin/users/${user.id}`, "PATCH", payload);
    if (body) await load(query);
  }

  async function resetPassword(user: UserRow) {
    const body = await mutate(`/api/stagecoach/admin/users/${user.id}/reset-password`, "POST", {});
    if (!body) return;
    if (body.temporary_password) setNotice(`${t.resetDone} ${body.temporary_password}`);
    await load(query);
  }

  async function revoke(user: UserRow) {
    const body = await mutate(`/api/stagecoach/admin/users/${user.id}/revoke-sessions`, "POST");
    if (body) await load(query);
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    const body = await mutate(`/api/stagecoach/admin/users/${target.id}`, "DELETE");
    if (body) await load(query);
  }

  return (
    <div
      className="mx-auto w-full max-w-3xl px-4 py-8"
      data-testid="admin-users"
      data-state={phase}
      aria-busy={phase === "loading"}
    >
      <h1 className="text-3xl">{t.heading}</h1>
      <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{t.intro}</p>

      {phase === "loading" ? (
        <p className="mt-8 text-sm" data-testid="admin-loading">
          {t.loading}
        </p>
      ) : null}

      {phase === "error" ? (
        <div className="mt-8 space-y-3" data-testid="admin-error" role="alert">
          <p className="text-sm text-destructive">{error || t.loadError}</p>
          <button type="button" data-testid="admin-retry" className="border px-3 py-2 text-sm" onClick={() => void load(query)}>
            {t.retry}
          </button>
        </div>
      ) : null}

      {phase === "empty" || phase === "success" ? (
        <div className="mt-8 space-y-6">
          <form
            className="flex flex-col gap-2 sm:flex-row"
            onSubmit={(event) => {
              event.preventDefault();
              void load(query);
            }}
          >
            <label className="min-w-0 flex-1 text-sm">
              {t.searchLabel}
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="mt-1 w-full px-3 py-2"
                data-testid="admin-search"
              />
            </label>
            <button type="submit" className="border px-3 py-2 text-sm sm:self-end">
              {t.search}
            </button>
          </form>

          <form onSubmit={(event) => void onCreate(event)} className="space-y-3 border bg-card p-4">
            <h2 className="text-lg">{t.create}</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="text-sm">
                {t.email}
                <input name="email" type="email" required className="mt-1 w-full px-3 py-2" data-testid="admin-create-email" />
              </label>
              <label className="text-sm">
                {t.name}
                <input name="name" className="mt-1 w-full px-3 py-2" data-testid="admin-create-name" />
              </label>
              <label className="text-sm">
                {t.role}
                <select name="role" defaultValue="member" className="mt-1 w-full px-3 py-2" data-testid="admin-create-role">
                  <option value="member">member</option>
                  <option value="admin">admin</option>
                  <option value="viewer">viewer</option>
                </select>
              </label>
              <label className="text-sm">
                {t.temp}
                <input
                  name="temp_password"
                  type="text"
                  autoComplete="off"
                  className="mt-1 w-full px-3 py-2"
                  data-testid="admin-create-temp"
                />
              </label>
            </div>
            <p className="text-sm text-muted-foreground">{t.tempHint}</p>
            <label className="flex items-center gap-2 text-sm">
              <input name="online_modes" type="checkbox" />
              {t.online}
            </label>
            <button type="submit" disabled={busy} className="bg-primary px-3 py-2 text-sm text-primary-foreground" data-testid="admin-create-submit">
              {busy ? t.saving : t.submit}
            </button>
          </form>

          {notice ? (
            <p className="break-all text-sm" data-testid="admin-notice">
              {notice}
            </p>
          ) : null}
          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          {phase === "empty" ? (
            <p className="text-sm" data-testid="admin-empty">
              {t.empty}
            </p>
          ) : (
            <ul className="space-y-3">
              {users.map((user) => (
                <li key={user.id} className="min-w-0 border bg-card p-4" data-testid="admin-user">
                  <p className="break-all text-sm font-medium">{user.email}</p>
                  {user.name ? <p className="text-sm text-muted-foreground">{user.name}</p> : null}
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>{user.role}</span>
                    {user.disabled ? <span>{t.disabled}</span> : null}
                    {user.must_change_password ? <span>{t.mustChange}</span> : null}
                    {user.apple_linked ? <span>{t.apple}</span> : null}
                    {user.email_verified ? <span>{t.verified}</span> : null}
                    {user.online_modes ? <span>{t.online}</span> : null}
                  </div>
                  <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <label className="text-sm">
                      {t.role}
                      <select
                        value={user.role}
                        aria-label={`${t.role} ${user.email}`}
                        className="mt-1 w-full px-3 py-2"
                        disabled={busy}
                        onChange={(event) => void patch(user, { role: event.target.value })}
                      >
                        <option value="member">member</option>
                        <option value="admin">admin</option>
                        <option value="viewer">viewer</option>
                      </select>
                    </label>
                    <div className="grid grid-cols-1 gap-2">
                      <button type="button" disabled={busy} className="border px-3 py-2 text-xs" onClick={() => void patch(user, { disabled: !user.disabled })}>
                        {user.disabled ? t.enable : t.disable}
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        className="border px-3 py-2 text-xs"
                        onClick={() => void patch(user, { online_modes: !user.online_modes })}
                      >
                        {user.online_modes ? t.onlineOff : t.onlineOn}
                      </button>
                      <button type="button" disabled={busy} className="border px-3 py-2 text-xs" onClick={() => void resetPassword(user)}>
                        {t.reset}
                      </button>
                      <button type="button" disabled={busy} className="border px-3 py-2 text-xs" onClick={() => void revoke(user)}>
                        {t.revoke}
                      </button>
                      <button type="button" disabled={busy} className="border px-3 py-2 text-xs" onClick={() => setPendingDelete(user)}>
                        {t.delete}
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      {pendingDelete ? (
        <ConfirmDialog
          title={t.confirmTitle}
          body={`${t.confirmBody} ${pendingDelete.email}`}
          onCancel={() => setPendingDelete(null)}
          actions={[
            { id: "delete-user", label: t.delete, tone: "danger", onClick: () => void confirmDelete() },
            { id: "cancel-delete", label: t.cancel, tone: "ghost", onClick: () => setPendingDelete(null) },
          ]}
        />
      ) : null}
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Loader2, Plus, Upload } from "lucide-react";
import { ConsentPanel } from "@/components/consents/consent-panel";

type Session = {
  id: string;
  title: string;
  status: string;
  context_type: string;
  language: string;
  created_at: string;
  overall: number | null;
};

export default function SessionsPage() {
  const t = useTranslations("dashboard");
  const locale = useLocale();
  const router = useRouter();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const [sessions, setSessions] = useState<Session[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [uploadName, setUploadName] = useState("");
  const [error, setError] = useState("");

  const loadSessions = useCallback(async () => {
    const response = await fetch("/api/stagecoach/sessions", { cache: "no-store" });
    if (!response.ok) throw new Error(t("loadError"));
    const body = await response.json();
    setSessions(body.sessions);
  }, [t]);

  useEffect(() => {
    const refresh = () => {
      void loadSessions()
        .catch((reason: Error) => setError(reason.message))
        .finally(() => setLoading(false));
    };
    const initial = window.setTimeout(refresh, 0);
    const timer = window.setInterval(() => {
      void loadSessions().catch(() => undefined);
    }, 5000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [loadSessions]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    try {
      if (!(file instanceof File) || !file.size) throw new Error(t("fileRequired"));
      const create = await fetch("/api/stagecoach/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: form.get("title"),
          context_type: form.get("context_type"),
          language: form.get("language"),
          slot_min: form.get("slot_min") ? Number(form.get("slot_min")) : null,
          qa_in_slot: false,
          camera_setup: form.get("camera_setup"),
        }),
      });
      const created = await create.json();
      if (!create.ok) throw new Error(created.detail || t("createError"));

      const uploadBody = new FormData();
      uploadBody.set("file", file);
      setUploadName(file.name);
      setUploadPct(0);
      const uploaded = await uploadRecording(`/api/stagecoach/sessions/${created.id}/upload`, uploadBody, setUploadPct);
      if (!uploaded.ok) throw new Error(uploaded.detail || t("uploadError"));
      router.push(`${prefix}/sessions/${created.id}`);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "";
      setError(message && message !== "upload failed" ? message : t("uploadError"));
      setSubmitting(false);
      setUploadPct(null);
    }
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">{t("recentSessions")}</h1>
        <button
          type="button"
          data-testid="new-session"
          onClick={() => setShowForm((value) => !value)}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          {t("newSession")}
        </button>
      </div>

      {error && (
        <div role="alert" className="mb-6 rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm">
          {error}
        </div>
      )}

      {showForm && (
        <form
          onSubmit={submit}
          data-testid="session-form"
          className="mb-8 grid gap-4 rounded-lg border bg-card p-6 md:grid-cols-2"
        >
          <label className="grid gap-2 text-sm font-medium">
            {t("title")}
            <input name="title" required maxLength={255} className="rounded-md border bg-background px-3 py-2" />
          </label>
          <label className="grid gap-2 text-sm font-medium">
            {t("presentationType")}
            <select name="context_type" className="rounded-md border bg-background px-3 py-2">
              <option value="keynote">{t("keynote")}</option>
              <option value="exec_briefing">{t("executiveBriefing")}</option>
              <option value="sales_pitch">{t("salesPitch")}</option>
              <option value="class_academic">{t("classAcademic")}</option>
              <option value="virtual_meeting">{t("virtualMeeting")}</option>
            </select>
          </label>
          <label className="grid gap-2 text-sm font-medium">
            {t("language")}
            <select name="language" className="rounded-md border bg-background px-3 py-2">
              <option value="en">English</option>
              <option value="pt-BR">Português (Brasil)</option>
              <option value="auto">{t("autoDetect")}</option>
            </select>
          </label>
          <label className="grid gap-2 text-sm font-medium">
            {t("slotMinutes")}
            <input name="slot_min" type="number" min="1" max="180" className="rounded-md border bg-background px-3 py-2" />
          </label>
          <label className="grid gap-2 text-sm font-medium">
            {t("cameraSetup")}
            <select name="camera_setup" className="rounded-md border bg-background px-3 py-2">
              <option value="to_camera">{t("toCamera")}</option>
              <option value="stage">{t("stage")}</option>
              <option value="screen_recording">{t("screenRecording")}</option>
              <option value="audio_only">{t("audioOnly")}</option>
            </select>
          </label>
          <label className="grid gap-2 text-sm font-medium">
            {t("mediaFile")}
            <input
              name="file"
              type="file"
              required
              data-testid="session-file"
              accept=".mp4,.mov,.webm,.mkv,.m4a,.mp3,.wav,.ogg,.flac,audio/*,video/*"
              className="rounded-md border bg-background px-3 py-2"
            />
          </label>
          <ConsentPanel compact />
          <div className="md:col-span-2">
            <button
              disabled={submitting}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground disabled:opacity-50"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              {submitting ? (
                <span>
                  {uploadPct === null
                    ? t("uploading")
                    : t("uploadProgress", {
                        name: uploadName,
                        pct: String(uploadPct),
                      })}
                </span>
              ) : (
                t("uploadAndAnalyze")
              )}
            </button>
            {submitting && (
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                <div
                  className="h-full bg-primary transition-[width]"
                  style={{ width: `${uploadPct ?? 0}%` }}
                />
              </div>
            )}
          </div>
        </form>
      )}

      {loading ? (
        <div className="flex justify-center p-12"><Loader2 className="h-6 w-6 animate-spin" /></div>
      ) : sessions.length === 0 ? (
        <div className="rounded-lg border bg-card p-8 text-center text-card-foreground" data-testid="empty-sessions">
          <p className="text-muted-foreground">{t("noSessions")}</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => router.push(`${prefix}/sessions/${session.id}`)}
              className="flex items-center justify-between rounded-lg border bg-card p-5 text-left hover:border-primary/50"
            >
              <div>
                <div className="font-semibold">{session.title}</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  {session.context_type.replaceAll("_", " ")} · {session.language} ·{" "}
                  {new Date(session.created_at).toLocaleString()}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-4">
                {typeof session.overall === "number" && (
                  <span className="text-2xl font-semibold tabular-nums">{session.overall}</span>
                )}
                <span className="text-sm text-primary">{nextAction(session.status, t)}</span>
                <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusClass(session.status)}`}>
                  {statusLabel(session.status, t)}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function uploadRecording(
  url: string,
  body: FormData,
  onProgress: (pct: number) => void,
): Promise<{ ok: boolean; detail?: string }> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };
    request.onerror = () => reject(new Error("upload failed"));
    request.onload = () => {
      let detail = "";
      try {
        const payload = JSON.parse(request.responseText) as { detail?: string };
        detail = payload.detail || "";
      } catch {
        detail = "";
      }
      resolve({ ok: request.status >= 200 && request.status < 300, detail });
    };
    request.send(body);
  });
}

function nextAction(
  status: string,
  t: (key: "openReport" | "watchProgress" | "seeFailure" | "startAnalysis") => string,
): string {
  if (status === "ready" || status === "partial") return t("openReport");
  if (status === "failed") return t("seeFailure");
  if (status === "processing" || status === "uploaded") return t("watchProgress");
  return t("startAnalysis");
}

function statusClass(status: string): string {
  if (status === "ready") return "bg-emerald-500/15 text-emerald-700";
  if (status === "failed") return "bg-destructive/10 text-destructive";
  if (status === "partial") return "bg-amber-500/15 text-amber-700";
  if (status === "processing" || status === "uploaded") return "bg-primary/10 text-primary";
  return "bg-muted text-muted-foreground";
}

function statusLabel(
  status: string,
  t: (key: "statusReady" | "statusFailed" | "statusPartial" | "statusProcessing" | "statusCreated") => string,
): string {
  if (status === "ready") return t("statusReady");
  if (status === "failed") return t("statusFailed");
  if (status === "partial") return t("statusPartial");
  if (status === "processing" || status === "uploaded") return t("statusProcessing");
  return t("statusCreated");
}

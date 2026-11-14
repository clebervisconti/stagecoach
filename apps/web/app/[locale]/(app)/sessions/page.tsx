"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Loader2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ConsentPanel } from "@/components/consents/consent-panel";
import { uploadRecordingChunked } from "@/lib/chunked-upload";
import { formatBytes, MAX_UPLOAD_BYTES } from "@/lib/online";
import { uploadErrorCopy } from "@/lib/upload-errors";
import { SessionsHome } from "@/components/sessions/sessions-home";
import type { AnalysisReport } from "@/lib/report-types";
import { greetingPart, numericScores } from "@/lib/overview";

type Session = {
  id: string;
  title: string;
  status: string;
  context_type: string;
  delivery_mode?: string;
  language: string;
  created_at: string;
  overall: number | null;
};

export default function SessionsPage() {
  const t = useTranslations("dashboard");
  const signal = useTranslations("signal");
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
  const [briefing, setBriefing] = useState<AnalysisReport | null>(null);
  const [toast, setToast] = useState("");
  const [onlineModes, setOnlineModes] = useState<"unknown" | "on" | "off">("unknown");
  const online = useTranslations("online");
  const pendingRef = useRef<{ key: string; sessionId: string; uploadId: string | null } | null>(null);

  const loadSessions = useCallback(async () => {
    const response = await fetch("/api/stagecoach/sessions", { cache: "no-store" });
    if (!response.ok) throw new Error(t("loadError"));
    const body = await response.json();
    setSessions(Array.isArray(body.sessions) ? body.sessions : []);
    setError("");
  }, [t]);

  useEffect(() => {
    const refresh = () => {
      void loadSessions()
        .catch((reason: Error) => setError(reason.message))
        .finally(() => setLoading(false));
    };
    fetch("/api/stagecoach/me", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : { online_modes_enabled: false }))
      .then((body: { online_modes_enabled?: boolean }) => setOnlineModes(body.online_modes_enabled ? "on" : "off"))
      .catch(() => setOnlineModes("off"));
    const initial = window.setTimeout(refresh, 0);
    const timer = window.setInterval(() => {
      void loadSessions().catch(() => undefined);
    }, 5000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [loadSessions]);

  const latestReadyId = [...sessions]
    .filter((session) => session.status === "ready" || session.status === "partial")
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]?.id;

  useEffect(() => {
    if (!latestReadyId) return;
    let active = true;
    void fetch(`/api/stagecoach/sessions/${latestReadyId}/report`, { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body: AnalysisReport | null) => {
        if (!active) return;
        if (body?.overall && body.insights) setBriefing(body);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [latestReadyId]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    try {
      if (!(file instanceof File) || !file.size) throw new Error(t("fileRequired"));
      if (file.size > MAX_UPLOAD_BYTES) {
        throw new Error(online("fileTooLarge", { size: formatBytes(file.size), limit: "2 GB" }));
      }
      const key = `${file.name}\0${file.size}\0${file.lastModified}`;
      let sessionId = pendingRef.current?.key === key ? pendingRef.current.sessionId : null;
      if (!sessionId) {
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
        const created = (await create.json().catch(() => ({}))) as { id?: unknown; detail?: unknown };
        if (!create.ok || typeof created.id !== "string") {
          const detail = typeof created.detail === "string" ? created.detail : "";
          throw new Error(detail || t("createError"));
        }
        sessionId = created.id;
        pendingRef.current = { key, sessionId, uploadId: null };
      }

      setUploadName(file.name);
      setUploadPct(0);
      const uploaded = await uploadRecordingChunked({
        sessionId,
        file,
        uploadId: pendingRef.current?.uploadId ?? null,
        onUploadId: (uploadId) => {
          if (pendingRef.current?.sessionId === sessionId) pendingRef.current.uploadId = uploadId;
        },
        onProgress: (next) => setUploadPct(next.pct),
      });
      if (!uploaded.ok) {
        if (pendingRef.current?.sessionId === sessionId) pendingRef.current.uploadId = uploaded.uploadId;
        const copy = uploadErrorCopy({
          fileSize: file.size,
          maxBytes: MAX_UPLOAD_BYTES,
          status: uploaded.status,
          code: uploaded.code,
          detail: uploaded.detail,
          tooLarge: (size) => online("fileTooLarge", { size: formatBytes(size), limit: "2 GB" }),
          proxy: () => online("proxyRejected"),
          network: () => online("uploadFailed"),
          other: (detail) => detail || t("uploadError"),
        });
        throw new Error(copy.message);
      }
      pendingRef.current = null;
      router.push(`${prefix}/sessions/${sessionId}`);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "";
      setError(message && message !== "upload failed" ? message : t("uploadError"));
      setSubmitting(false);
      setUploadPct(null);
    }
  }

  const part = greetingPart(new Date().getHours());
  const greeting = part === "morning" ? signal("greetingMorning") : part === "evening" ? signal("greetingEvening") : signal("greetingAfternoon");
  function openNew() {
    if (onlineModes === "on") {
      router.push(`${prefix}/sessions/new?step=where`);
      return;
    }
    setShowForm((value) => !value);
  }

  return (
    <SessionsHome
      greeting={greeting}
      locale={locale}
      prefix={prefix}
      loading={loading}
      error={error}
      briefing={latestReadyId ? briefing : null}
      points={numericScores(sessions)}
      toast={toast}
      onUndo={() => setToast("")}
      onAdded={() => setToast(signal("addedToPractice"))}
      onNew={openNew}
      sessions={sessions.map((session) => ({
        ...session,
        href: session.status === "layout_review" ? `${prefix}/sessions/${session.id}/layout` : `${prefix}/sessions/${session.id}`,
      }))}
    >
      {showForm ? (
        <form
          onSubmit={submit}
          data-testid="session-form"
          className="cs-panel mb-2 grid gap-4 md:grid-cols-2"
        >
          <Field label={t("title")} htmlFor="session-title">
            <Input id="session-title" name="title" required maxLength={255} />
          </Field>
          <Field label={t("presentationType")} htmlFor="session-type">
            <Select id="session-type" name="context_type">
              <option value="keynote">{t("keynote")}</option>
              <option value="exec_briefing">{t("executiveBriefing")}</option>
              <option value="sales_pitch">{t("salesPitch")}</option>
              <option value="class_academic">{t("classAcademic")}</option>
              <option value="virtual_meeting">{t("virtualMeeting")}</option>
            </Select>
          </Field>
          <Field label={t("language")} htmlFor="session-language">
            <Select id="session-language" name="language">
              <option value="en">English</option>
              <option value="pt-BR">Português (Brasil)</option>
              <option value="auto">{t("autoDetect")}</option>
            </Select>
          </Field>
          <Field label={t("slotMinutes")} htmlFor="session-slot">
            <Input id="session-slot" name="slot_min" type="number" min="1" max="180" />
          </Field>
          <Field label={t("cameraSetup")} htmlFor="session-camera">
            <Select id="session-camera" name="camera_setup">
              <option value="to_camera">{t("toCamera")}</option>
              <option value="stage">{t("stage")}</option>
              <option value="screen_recording">{t("screenRecording")}</option>
              <option value="audio_only">{t("audioOnly")}</option>
            </Select>
          </Field>
          <Field label={t("mediaFile")} htmlFor="session-file">
            <Input
              id="session-file"
              name="file"
              type="file"
              required
              data-testid="session-file"
              accept=".mp4,.mov,.webm,.mkv,.m4a,.mp3,.wav,.ogg,.flac,audio/*,video/*"
            />
          </Field>
          <ConsentPanel compact />
          <div className="md:col-span-2">
            <Button type="submit" disabled={submitting}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Upload className="h-4 w-4" aria-hidden="true" />}
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
            </Button>
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
      ) : null}
    </SessionsHome>
  );
}

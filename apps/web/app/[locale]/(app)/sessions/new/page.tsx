"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { ModeStep } from "@/components/sessions/new/mode-step";
import { RecordingStep, type RecordingDraft, type UploadFailure, type UploadTelemetry } from "@/components/sessions/new/recording-step";
import { isAbortError, uploadRecordingChunked } from "@/lib/chunked-upload";
import { WizardStepper } from "@/components/sessions/new/wizard-stepper";
import {
  formatBytes,
  isDeliveryMode,
  MAX_UPLOAD_BYTES,
  readLastContext,
  readLastMode,
  writeLastContext,
  writeLastMode,
  type DeliveryMode,
} from "@/lib/online";
import { uploadErrorCopy } from "@/lib/upload-errors";

export default function NewSessionPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-[color:var(--text-secondary)]">Loading…</div>}>
      <NewSessionWizard />
    </Suspense>
  );
}

function NewSessionWizard() {
  const t = useTranslations("online");
  const locale = useLocale();
  const router = useRouter();
  const params = useSearchParams();
  const prefix = locale === "en" ? "" : `/${locale}`;
  const step = params.get("step") === "recording" ? "recording" : "where";
  const urlMode = params.get("mode");
  const [picked, setPicked] = useState<DeliveryMode | null>(() => {
    if (typeof window === "undefined") return null;
    return readLastMode();
  });
  const mode = isDeliveryMode(urlMode) ? urlMode : picked;
  const [modeError, setModeError] = useState<string | null>(null);
  const [onlineEnabled, setOnlineEnabled] = useState<boolean | null>(null);
  const [uploading, setUploading] = useState(false);
  const [telemetry, setTelemetry] = useState<UploadTelemetry | null>(null);
  const [uploadError, setUploadError] = useState<UploadFailure | null>(null);
  const lastSubmit = useRef<{
    draft: RecordingDraft;
    file: File;
    deck: File | null;
    duration: number | null;
  } | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const cancelRequested = useRef(false);
  const pendingRef = useRef<{
    fileKey: string;
    sessionId: string;
    uploadId: string | null;
    deckSent: boolean;
  } | null>(null);

  useEffect(() => {
    let active = true;
    fetch("/api/stagecoach/me", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : { online_modes_enabled: false }))
      .then((body: { online_modes_enabled?: boolean }) => {
        if (!active) return;
        const enabled = Boolean(body.online_modes_enabled);
        setOnlineEnabled(enabled);
        if (!enabled) router.replace(`${prefix}/sessions`);
      })
      .catch(() => {
        if (active) router.replace(`${prefix}/sessions`);
      });
    return () => {
      active = false;
    };
  }, [prefix, router]);

  useEffect(() => {
    const n = step === "recording" ? 2 : 1;
    const of = mode === "stage" ? 2 : 3;
    document.title = `${t("newAnalysis")} · ${t("stepOf", { n: String(n), of: String(of) })} · Stage Coach`;
  }, [mode, step, t]);

  const go = useCallback(
    (next: "where" | "recording", nextMode?: DeliveryMode | null) => {
      const chosen = nextMode ?? mode;
      const search = new URLSearchParams();
      search.set("step", next);
      if (chosen) search.set("mode", chosen);
      router.push(`${prefix}/sessions/new?${search.toString()}`);
    },
    [mode, prefix, router],
  );

  function continueFromMode() {
    if (!mode) {
      setModeError("choose");
      return;
    }
    setModeError(null);
    writeLastMode(mode);
    go("recording", mode);
  }

  async function uploadAll(payload: {
    draft: RecordingDraft;
    file: File;
    deck: File | null;
    duration: number | null;
  }) {
    cancelRequested.current = false;
    lastSubmit.current = payload;
    setUploadError(null);
    setUploading(true);
    setTelemetry({ loaded: 0, total: payload.file.size, pct: 0, speed: 0, eta: null });
    const controller = new AbortController();
    abortRef.current = controller;
    const key = `${payload.file.name}\0${payload.file.size}\0${payload.file.lastModified}`;
    try {
      if (pendingRef.current && pendingRef.current.fileKey !== key) {
        const stale = pendingRef.current.sessionId;
        pendingRef.current = null;
        await fetch(`/api/stagecoach/sessions/${stale}`, { method: "DELETE", signal: controller.signal }).catch(
          () => undefined,
        );
      }

      let sessionId = pendingRef.current?.sessionId ?? null;
      if (!sessionId) {
        const create = await fetch("/api/stagecoach/sessions", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            title: payload.draft.title,
            context_type: payload.draft.context_type,
            language: payload.draft.language,
            slot_min: payload.draft.slot_min ? Number(payload.draft.slot_min) : null,
            qa_in_slot: payload.draft.qa_in_slot,
            camera_setup: payload.draft.camera_setup,
            delivery_mode: mode,
            source_kind: "upload",
            rights_attested: payload.draft.rights,
            other_people_appear: payload.draft.other_people_appear,
            target_length_min: mode === "recorded_video" && payload.draft.slot_min ? Number(payload.draft.slot_min) : null,
          }),
          signal: controller.signal,
        });
        const created = (await create.json().catch(() => ({}))) as { id?: unknown; detail?: unknown };
        if (!create.ok || typeof created.id !== "string") {
          const detail = typeof created.detail === "string" ? created.detail : "";
          throw new Error(detail || t("createError"));
        }
        sessionId = created.id;
        pendingRef.current = { fileKey: key, sessionId, uploadId: null, deckSent: false };
        writeLastContext(payload.draft.context_type);
        if (mode) writeLastMode(mode);
      }

      const pending = pendingRef.current;
      if (payload.deck && pending && !pending.deckSent) {
        const deckBody = new FormData();
        deckBody.set("file", payload.deck);
        const decked = await fetch(`/api/stagecoach/sessions/${sessionId}/deck`, {
          method: "POST",
          body: deckBody,
          signal: controller.signal,
        });
        if (!decked.ok) {
          const body = (await decked.json().catch(() => ({}))) as { detail?: unknown };
          const detail = typeof body.detail === "string" ? body.detail : "";
          throw new Error(detail || t("deckError"));
        }
        pending.deckSent = true;
      }

      const uploaded = await uploadRecordingChunked({
        sessionId,
        file: payload.file,
        rightsAttested: payload.draft.rights,
        uploadId: pendingRef.current?.uploadId ?? null,
        signal: controller.signal,
        onUploadId: (uploadId) => {
          if (pendingRef.current?.sessionId === sessionId) pendingRef.current.uploadId = uploadId;
        },
        onProgress: (next) => setTelemetry(next),
      });
      if (!uploaded.ok) {
        if (pendingRef.current?.sessionId === sessionId) pendingRef.current.uploadId = uploaded.uploadId;
        const copy = uploadErrorCopy({
          fileSize: payload.file.size,
          maxBytes: MAX_UPLOAD_BYTES,
          status: uploaded.status,
          code: uploaded.code,
          detail: uploaded.detail,
          tooLarge: (size) => t("fileTooLarge", { size: formatBytes(size), limit: "2 GB" }),
          proxy: () => t("proxyRejected"),
          network: () => t("uploadFailed"),
          other: (detail) => detail || t("uploadError"),
        });
        setUploadError({ kind: copy.kind, message: copy.message });
        setUploading(false);
        return;
      }
      pendingRef.current = null;
      router.push(`${prefix}/sessions/${sessionId}`);
    } catch (reason) {
      if (cancelRequested.current || isAbortError(reason)) {
        setUploading(false);
        return;
      }
      const network = reason instanceof TypeError;
      setUploadError({
        kind: network ? "network" : "other",
        message: reason instanceof Error ? reason.message : t("uploadError"),
      });
      setUploading(false);
    }
  }

  async function cancelUpload() {
    cancelRequested.current = true;
    abortRef.current?.abort();
    const id = pendingRef.current?.sessionId;
    pendingRef.current = null;
    if (id) {
      await fetch(`/api/stagecoach/sessions/${id}`, { method: "DELETE" }).catch(() => undefined);
    }
    setUploading(false);
    setTelemetry(null);
    setUploadError({ kind: "other", message: t("uploadCancelled") });
  }

  if (onlineEnabled !== true) {
    return <div className="p-8 text-sm text-[color:var(--text-secondary)]">{t("loading")}</div>;
  }

  return (
    <div className="min-w-0 overflow-x-hidden px-5 py-8 md:px-16 md:pt-12">
      <WizardStepper
        mode={mode}
        current={step}
        onSelect={(id) => {
          if (id === "where") go("where");
          if (id === "recording" && mode) go("recording");
        }}
      />
      {step === "where" ? (
        <ModeStep
          value={mode}
          error={modeError}
          onChange={(next) => {
            setPicked(next);
            setModeError(null);
          }}
          onContinue={continueFromMode}
          onCancel={() => router.push(`${prefix}/sessions`)}
        />
      ) : mode ? (
        <RecordingStep
          mode={mode}
          lastContext={readLastContext()}
          uploading={uploading}
          telemetry={telemetry}
          uploadError={uploadError}
          onBack={() => go("where")}
          onChangeMode={() => go("where")}
          onSubmit={(payload) => void uploadAll(payload)}
          onCancelUpload={() => void cancelUpload()}
          onRetry={() => lastSubmit.current && void uploadAll(lastSubmit.current)}
        />
      ) : (
        <ModeStep
          value={mode}
          error={modeError}
          onChange={setPicked}
          onContinue={continueFromMode}
          onCancel={() => router.push(`${prefix}/sessions`)}
        />
      )}
    </div>
  );
}

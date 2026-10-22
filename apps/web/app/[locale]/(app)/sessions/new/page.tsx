"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { ModeStep } from "@/components/sessions/new/mode-step";
import { RecordingStep, type RecordingDraft, type UploadTelemetry } from "@/components/sessions/new/recording-step";
import { WizardStepper } from "@/components/sessions/new/wizard-stepper";
import {
  isDeliveryMode,
  readLastContext,
  readLastMode,
  writeLastContext,
  writeLastMode,
  type DeliveryMode,
} from "@/lib/online";

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
  const [uploadError, setUploadError] = useState<string | null>(null);
  const lastSubmit = useRef<{
    draft: RecordingDraft;
    file: File;
    deck: File | null;
    duration: number | null;
  } | null>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const createdId = useRef<string | null>(null);

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
    lastSubmit.current = payload;
    setUploadError(null);
    setUploading(true);
    setTelemetry({ loaded: 0, total: payload.file.size, pct: 0, speed: 0, eta: null });
    try {
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
      });
      const created = await create.json();
      if (!create.ok) throw new Error(created.detail || t("createError"));
      createdId.current = created.id;
      writeLastContext(payload.draft.context_type);
      if (mode) writeLastMode(mode);

      if (payload.deck) {
        const deckBody = new FormData();
        deckBody.set("file", payload.deck);
        const decked = await fetch(`/api/stagecoach/sessions/${created.id}/deck`, {
          method: "POST",
          body: deckBody,
        });
        if (!decked.ok) {
          const body = await decked.json().catch(() => ({}));
          throw new Error(body.detail || t("deckError"));
        }
      }

      const uploadBody = new FormData();
      uploadBody.set("file", payload.file);
      if (payload.draft.rights) uploadBody.set("rights_attested", "true");
      const uploaded = await sendUpload(
        `/api/stagecoach/sessions/${created.id}/upload`,
        uploadBody,
        (next) => setTelemetry(next),
        (request) => {
          xhrRef.current = request;
        },
      );
      if (!uploaded.ok) throw new Error(uploaded.detail || t("uploadError"));
      router.push(`${prefix}/sessions/${created.id}`);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : t("uploadError");
      setUploadError(friendlyUploadError(message, t));
      setUploading(false);
    }
  }

  async function cancelUpload() {
    xhrRef.current?.abort();
    if (createdId.current) {
      await fetch(`/api/stagecoach/sessions/${createdId.current}`, { method: "DELETE" }).catch(() => undefined);
      createdId.current = null;
    }
    setUploading(false);
    setTelemetry(null);
    setUploadError(t("uploadCancelled"));
  }

  if (onlineEnabled !== true) {
    return <div className="p-8 text-sm text-[color:var(--text-secondary)]">{t("loading")}</div>;
  }

  return (
    <div className="px-5 py-8 md:px-16 md:pt-12">
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

function friendlyUploadError(detail: string, t: (key: string, values?: Record<string, string>) => string): string {
  if (/413|larger than|2 GB|limit/i.test(detail)) return t("http413", { limit: "2 GB" });
  if (/longer than|120/i.test(detail)) return t("fileTooLong", { limit: "120" });
  if (/failed|network|dropped/i.test(detail)) return t("uploadFailed");
  return detail;
}

function sendUpload(
  url: string,
  body: FormData,
  onProgress: (value: UploadTelemetry) => void,
  capture: (request: XMLHttpRequest) => void,
): Promise<{ ok: boolean; detail?: string }> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    capture(request);
    const started = Date.now();
    request.open("POST", url);
    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      const elapsed = Math.max(0.2, (Date.now() - started) / 1000);
      const speed = event.loaded / elapsed;
      const remaining = event.total - event.loaded;
      onProgress({
        loaded: event.loaded,
        total: event.total,
        pct: Math.min(100, Math.round((event.loaded / event.total) * 100)),
        speed,
        eta: speed > 0 ? remaining / speed : null,
      });
    };
    request.onerror = () => reject(new Error("upload failed"));
    request.onabort = () => reject(new Error("upload cancelled"));
    request.onload = () => {
      let detail = "";
      try {
        const payload = JSON.parse(request.responseText) as { detail?: string };
        detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail ?? "");
      } catch {
        detail = "";
      }
      resolve({ ok: request.status >= 200 && request.status < 300, detail });
    };
    request.send(body);
  });
}

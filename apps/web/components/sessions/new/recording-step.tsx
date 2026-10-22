"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Activity,
  Camera,
  ChevronDown,
  Mic,
  ShieldCheck,
  TriangleAlert,
  Upload,
  Users,
  X,
} from "lucide-react";
import {
  CONTEXT_TYPES,
  MAX_DURATION_SECONDS,
  MAX_UPLOAD_BYTES,
  formatBytes,
  spokenDuration,
  titleFromFilename,
  type ContextType,
  type DeliveryMode,
} from "@/lib/online";
import { TelemetryProgress } from "@/components/ui/telemetry-progress";

export type RecordingDraft = {
  title: string;
  context_type: ContextType;
  language: "en" | "pt-BR" | "auto";
  slot_min: string;
  qa_in_slot: boolean;
  camera_setup: string;
  other_people_appear: boolean;
  rights: boolean;
};

export type UploadTelemetry = {
  loaded: number;
  total: number;
  pct: number;
  speed: number;
  eta: number | null;
};

type FileMeta = {
  file: File;
  duration: number | null;
  width: number | null;
  height: number | null;
};

function defaultDraft(mode: DeliveryMode, lastContext: ContextType | null): RecordingDraft {
  return {
    title: "",
    context_type: lastContext ?? "keynote",
    language: "auto",
    slot_min: "",
    qa_in_slot: mode === "webinar",
    camera_setup: "to_camera",
    other_people_appear: false,
    rights: false,
  };
}

export function RecordingStep({
  mode,
  lastContext,
  uploading,
  telemetry,
  uploadError,
  onBack,
  onChangeMode,
  onSubmit,
  onCancelUpload,
  onRetry,
}: {
  mode: DeliveryMode;
  lastContext: ContextType | null;
  uploading: boolean;
  telemetry: UploadTelemetry | null;
  uploadError: string | null;
  onBack: () => void;
  onChangeMode: () => void;
  onSubmit: (payload: {
    draft: RecordingDraft;
    file: File;
    deck: File | null;
    duration: number | null;
  }) => void;
  onCancelUpload: () => void;
  onRetry: () => void;
}) {
  const t = useTranslations("online");
  const [draft, setDraft] = useState<RecordingDraft>(() => defaultDraft(mode, lastContext));
  const [media, setMedia] = useState<FileMeta | null>(null);
  const [deck, setDeck] = useState<File | null>(null);
  const [showDeck, setShowDeck] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [rightsError, setRightsError] = useState<string | null>(null);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const deckInput = useRef<HTMLInputElement>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const rightsRef = useRef<HTMLInputElement>(null);
  const progressRef = useRef<HTMLHeadingElement>(null);
  const needsRights = mode === "webinar" || mode === "online_talk" || (mode === "recorded_video" && draft.other_people_appear);

  useEffect(() => {
    (document.getElementById("recording-step-title") as HTMLElement | null)?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    if (uploading) progressRef.current?.focus();
  }, [uploading]);

  const lead =
    mode === "recorded_video" ? t("recordingLeadRecorded") : mode === "stage" ? t("recordingLeadStage") : t("recordingLead");

  const coachItems = useMemo(() => {
    if (mode === "stage") return [t("coachVoice"), t("coachBody"), t("coachSlides")];
    if (mode === "webinar") return [t("coachVoice"), t("coachScreens"), t("coachCamera"), t("coachQa")];
    if (mode === "online_talk") return [t("coachVoice"), t("coachScreens"), t("coachCamera")];
    return [t("coachVoice"), t("coachScreens"), t("coachCamera"), t("coachOpening")];
  }, [mode, t]);

  async function inspectFile(file: File): Promise<FileMeta> {
    if (file.size > MAX_UPLOAD_BYTES) {
      throw new Error(
        t("fileTooLarge", {
          size: formatBytes(file.size),
          limit: "2 GB",
        }),
      );
    }
    const meta: FileMeta = { file, duration: null, width: null, height: null };
    if (file.type.startsWith("audio/") || file.type.startsWith("video/") || /\.(mp4|mov|m4a|wav|webm)$/i.test(file.name)) {
      await new Promise<void>((resolve) => {
        const el = document.createElement(file.type.startsWith("audio/") ? "audio" : "video");
        el.preload = "metadata";
        el.onloadedmetadata = () => {
          meta.duration = Number.isFinite(el.duration) ? el.duration : null;
          if (el instanceof HTMLVideoElement) {
            meta.width = el.videoWidth || null;
            meta.height = el.videoHeight || null;
          }
          URL.revokeObjectURL(el.src);
          resolve();
        };
        el.onerror = () => resolve();
        el.src = URL.createObjectURL(file);
      });
    }
    if (meta.duration && meta.duration > MAX_DURATION_SECONDS) {
      throw new Error(t("fileTooLong", { limit: "120" }));
    }
    return meta;
  }

  async function chooseFile(file: File | undefined) {
    if (!file) return;
    setFileError(null);
    try {
      const next = await inspectFile(file);
      setMedia(next);
      if (!draft.title) {
        setDraft((current) => ({ ...current, title: titleFromFilename(file.name).slice(0, 120) }));
      }
    } catch (reason) {
      setMedia(null);
      setFileError(reason instanceof Error ? reason.message : t("fileRequired"));
    }
  }

  function validate(): boolean {
    let first: HTMLElement | null = null;
    if (!media) {
      setFileError(t("fileRequired"));
      first = fileInput.current;
    }
    if (!draft.title.trim()) {
      setTitleError(t("titleRequired"));
      first = first ?? titleRef.current;
    } else {
      setTitleError(null);
    }
    if (needsRights && !draft.rights) {
      setRightsError(t("rightsError"));
      first = first ?? rightsRef.current;
    } else {
      setRightsError(null);
    }
    first?.focus();
    return !first;
  }

  function submit() {
    if (!validate() || !media) return;
    onSubmit({ draft, file: media.file, deck, duration: media.duration });
  }

  const readOnly = uploading;
  const tooLarge = Boolean(uploadError && /too large|2 GB|413/i.test(uploadError));
  const networkFail = Boolean(uploadError && /failed|dropped|network/i.test(uploadError) && !tooLarge);

  return (
    <div className="mx-auto grid w-full min-w-0 max-w-[1100px] gap-12 lg:grid-cols-[minmax(0,680px)_340px]">
      <div className="min-w-0">
        <p className="cs-eyebrow">{t("newAnalysisMode", { mode: t(`modes.${mode}.title`) })}</p>
        <h1 id="recording-step-title" tabIndex={-1} className="cs-wizard-title mt-3 outline-none">
          {t("recordingTitle")}
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-[color:var(--text-secondary)] md:text-lg md:leading-[30px]">
          {lead}
        </p>

        <div className="mt-8 space-y-6">
          <div>
            <p className="cs-eyebrow">{t("recordingLabel")}</p>
            {uploading && telemetry ? (
              <div className="mt-2 rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] bg-[color:var(--bg-subtle)] p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 ref={progressRef} tabIndex={-1} className="flex items-center gap-2 text-xs uppercase tracking-[0.12em] outline-none">
                      <span className="h-2 w-2 rounded-full bg-[color:var(--text-strong)]" aria-hidden="true" />
                      {t("uploading")}
                    </h2>
                    <p className="mt-2 truncate text-sm" title={media?.file.name}>
                      {media?.file.name}
                    </p>
                  </div>
                  <p className="font-mono text-xl tabular-nums">{`${telemetry.pct}%`}</p>
                </div>
                <TelemetryProgress
                  value={telemetry.pct}
                  label={t("uploadAria", {
                    pct: String(telemetry.pct),
                    eta: telemetry.eta != null ? spokenDuration(telemetry.eta) : t("calculating"),
                  })}
                />
                <p className="mt-3 font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-secondary)]">
                  {t("uploadTelemetry", {
                    loaded: formatBytes(telemetry.loaded),
                    total: formatBytes(telemetry.total),
                    speed: `${Math.max(1, Math.round(telemetry.speed / (1024 * 1024)))} MB/s`,
                    eta: telemetry.eta != null ? `${Math.max(1, Math.round(telemetry.eta))} s` : "—",
                  })}
                </p>
                <p className="mt-2 text-sm text-[color:var(--text-secondary)]">
                  {deck ? t("slidesUploaded") : null} {t("keepTabOpen")}
                </p>
                <div aria-live="polite" className="sr-only">
                  {t("uploadLive", { pct: String(telemetry.pct) })}
                </div>
              </div>
            ) : media ? (
              <div className="file-row mt-2 flex w-full min-w-0 items-center justify-between gap-3 rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] bg-[color:var(--bg-subtle)] p-4">
                <div className="min-w-0">
                  <p className="file-name overflow-hidden text-ellipsis whitespace-nowrap" title={media.file.name}>
                    {media.file.name}
                  </p>
                  <p className="mt-1 font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-secondary)]">
                    {[
                      tooLarge ? "2.4 GB" : formatBytes(media.file.size),
                      media.duration != null ? formatClockSafe(media.duration) : null,
                      media.width && media.height ? `${media.width}×${media.height}` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={readOnly}
                  onClick={() => fileInput.current?.click()}
                  className="shrink-0 text-xs uppercase tracking-[0.08em]"
                >
                  {t("replace")}
                </button>
              </div>
            ) : (
              <label
                className="mt-2 flex min-h-[140px] cursor-pointer flex-col items-start justify-center rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] bg-[color:var(--bg-subtle)] p-5"
                onClick={() => fileInput.current?.click()}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    fileInput.current?.click();
                  }
                }}
                tabIndex={0}
              >
                <Upload className="h-5 w-5" aria-hidden="true" />
                <p className="mt-3 text-sm">
                  {t("dropHere")}{" "}
                  <span className="uppercase tracking-[0.08em]">{t("browseFiles")}</span>
                </p>
                <p className="mt-1 text-sm text-[color:var(--text-secondary)]">{t("fileHint", { limit: "2 GB" })}</p>
              </label>
            )}
            <input
              ref={fileInput}
              type="file"
              data-testid="session-file"
              accept=".mp4,.mov,.m4a,.wav,.webm,.mkv,.mp3,.ogg,.flac,audio/*,video/*"
              className="sr-only"
              aria-label={t("recordingLabel")}
              onChange={(event) => void chooseFile(event.target.files?.[0])}
            />
            {fileError && (
              <p role="alert" className="mt-2 flex items-start gap-2 text-sm text-[color:var(--status-critical)]">
                <X className="mt-0.5 h-4 w-4" aria-hidden="true" />
                {fileError}
              </p>
            )}
          </div>

          <label className="grid gap-2 text-sm">
            <span className="cs-eyebrow">{t("titleLabel")}</span>
            <input
              ref={titleRef}
              name="title"
              value={draft.title}
              readOnly={readOnly}
              maxLength={120}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              className="h-11 rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] bg-[color:var(--bg-subtle)] px-3"
            />
            {titleError && (
              <span role="alert" className="text-[color:var(--status-warning)]">
                {titleError}
              </span>
            )}
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="grid gap-2 text-sm">
              <span className="cs-eyebrow">{t("talkType")}</span>
              <select
                name="context_type"
                value={draft.context_type}
                disabled={readOnly}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, context_type: event.target.value as ContextType }))
                }
                className="h-11 rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] bg-[color:var(--bg-subtle)] px-3"
              >
                {CONTEXT_TYPES.map((id) => (
                  <option key={id} value={id}>
                    {t(`context.${id}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-2 text-sm">
              <span className="cs-eyebrow">{t("language")}</span>
              <select
                name="language"
                value={draft.language}
                disabled={readOnly}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, language: event.target.value as RecordingDraft["language"] }))
                }
                className="h-11 rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] bg-[color:var(--bg-subtle)] px-3"
              >
                <option value="auto">{t("detectAutomatically")}</option>
                <option value="en">English</option>
                <option value="pt-BR">Português (Brasil)</option>
              </select>
            </label>
          </div>

          {mode === "recorded_video" ? (
            <label className="grid gap-2 text-sm">
              <span className="cs-eyebrow">{t("targetLength")}</span>
              <span className="flex items-center gap-2">
                <input
                  name="slot_min"
                  type="number"
                  min={1}
                  max={180}
                  readOnly={readOnly}
                  value={draft.slot_min}
                  onChange={(event) => setDraft((current) => ({ ...current, slot_min: event.target.value }))}
                  className="h-11 w-full rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] bg-[color:var(--bg-subtle)] px-3 font-mono"
                />
                <span className="font-mono text-xs uppercase">{t("min")}</span>
              </span>
              <span className="text-[color:var(--text-secondary)]">{t("targetLengthHelp")}</span>
            </label>
          ) : (
            <label className="grid gap-2 text-sm">
              <span className="cs-eyebrow">{t("slotLength")}</span>
              <span className="flex items-center gap-2">
                <input
                  name="slot_min"
                  type="number"
                  min={1}
                  max={180}
                  readOnly={readOnly}
                  value={draft.slot_min}
                  onChange={(event) => setDraft((current) => ({ ...current, slot_min: event.target.value }))}
                  className="h-11 w-full rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] bg-[color:var(--bg-subtle)] px-3 font-mono"
                />
                <span className="font-mono text-xs uppercase">{t("min")}</span>
              </span>
              <span className="text-[color:var(--text-secondary)]">{t("slotLengthHelp")}</span>
            </label>
          )}

          {(mode === "webinar" || mode === "online_talk") && (
            <div>
              <p id="qa-included-label" className="cs-eyebrow">
                {t("qaIncluded")}
              </p>
              <div className="mt-2 flex h-11 items-center gap-3">
                <button
                  type="button"
                  role="switch"
                  aria-checked={draft.qa_in_slot}
                  aria-labelledby="qa-included-label"
                  disabled={readOnly}
                  onClick={() => setDraft((current) => ({ ...current, qa_in_slot: !current.qa_in_slot }))}
                  className="cs-switch"
                />
                <span className="text-sm">{draft.qa_in_slot ? t("qaYes") : t("qaNo")}</span>
              </div>
            </div>
          )}

          {mode === "stage" && (
            <label className="grid gap-2 text-sm">
              <span className="cs-eyebrow">{t("cameraSetup")}</span>
              <select
                name="camera_setup"
                value={draft.camera_setup}
                disabled={readOnly}
                onChange={(event) => setDraft((current) => ({ ...current, camera_setup: event.target.value }))}
                className="h-11 rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] bg-[color:var(--bg-subtle)] px-3"
              >
                <option value="to_camera">{t("setupToCamera")}</option>
                <option value="stage">{t("setupStage")}</option>
                <option value="screen_recording">{t("setupScreen")}</option>
                <option value="audio_only">{t("setupAudio")}</option>
              </select>
            </label>
          )}

          {mode === "recorded_video" && (
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                disabled={readOnly}
                checked={draft.other_people_appear}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, other_people_appear: event.target.checked }))
                }
              />
              <span>{t("otherPeople")}</span>
            </label>
          )}

          {!showDeck ? (
            <button
              type="button"
              disabled={readOnly}
              onClick={() => setShowDeck(true)}
              className="text-xs uppercase tracking-[0.08em]"
            >
              {t("addSlides")}
            </button>
          ) : (
            <label className="grid gap-2 text-sm">
              <span className="cs-eyebrow">{t("slidesLabel")}</span>
              <input
                ref={deckInput}
                type="file"
                accept=".pptx,.pdf"
                disabled={readOnly}
                onChange={(event) => setDeck(event.target.files?.[0] ?? null)}
              />
              <span className="text-[color:var(--text-secondary)]">{t("slidesHelp")}</span>
            </label>
          )}

          {needsRights && (
            <label className="flex items-start gap-3 text-sm">
              <input
                ref={rightsRef}
                type="checkbox"
                checked={draft.rights}
                disabled={readOnly}
                onChange={(event) => setDraft((current) => ({ ...current, rights: event.target.checked }))}
              />
              <span>{t("rights")}</span>
            </label>
          )}
          {rightsError && (
            <p role="alert" className="flex items-center gap-2 text-sm text-[color:var(--status-warning)]">
              <TriangleAlert className="h-4 w-4" aria-hidden="true" />
              {t("rightsError")}
            </p>
          )}
        </div>

        {uploadError && (
          <div role="alert" className="mt-6 rounded-[var(--radius-sm)] border border-[color:var(--status-critical)] p-4">
            <p className="flex items-start gap-2 text-sm">
              <X className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--status-critical)]" aria-hidden="true" />
              <span>
                <span className="font-display text-xs font-bold uppercase tracking-[0.08em] text-[color:var(--status-critical)]">
                  {tooLarge ? t("fileTooLargeWord") : t("uploadFailedWord")}
                </span>
                <span className="text-[color:var(--text)]">
                  {" "}
                  · {tooLarge ? t("fileTooLarge", { size: "2.4 GB", limit: "2 GB" }) : uploadError}
                </span>
              </span>
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              {networkFail && (
                <button type="button" onClick={onRetry} className="text-xs uppercase tracking-[0.08em]">
                  {t("tryAgain")}
                </button>
              )}
              <button type="button" onClick={() => fileInput.current?.click()} className="text-xs uppercase tracking-[0.08em]">
                {t("chooseAnother")}
              </button>
            </div>
          </div>
        )}

        <div className="mt-10 flex items-center justify-between gap-3">
          <button
            type="button"
            disabled={uploading}
            onClick={onBack}
            className="inline-flex h-11 items-center rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] px-5 text-xs uppercase tracking-[0.08em] disabled:opacity-40"
          >
            {t("back")}
          </button>
          {uploading ? (
            <button
              type="button"
              onClick={onCancelUpload}
              className="inline-flex h-11 items-center rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] px-5 text-xs uppercase tracking-[0.08em]"
            >
              {t("cancelUpload")}
            </button>
          ) : (
            <button
              type="button"
              data-testid="upload-continue"
              onClick={submit}
              className="inline-flex h-11 items-center rounded-[var(--radius-sm)] bg-[color:var(--action-primary)] px-5 text-xs uppercase tracking-[0.08em] text-[color:var(--text-inverse)]"
            >
              {t("uploadContinue")}
            </button>
          )}
        </div>
      </div>

      <aside className="lg:pt-16">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 text-xs uppercase tracking-[0.08em] lg:hidden"
          aria-expanded={railOpen}
          onClick={() => setRailOpen((value) => !value)}
        >
          <span className="inline-flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            {t("howUsed")}
          </span>
          <ChevronDown className={`h-4 w-4 ${railOpen ? "rotate-180" : ""}`} aria-hidden="true" />
        </button>
        <div className={`${railOpen ? "mt-4 block" : "hidden"} space-y-8 rounded-[var(--radius-sm)] border border-[color:var(--line)] p-6 lg:block`}>
          <div>
            <p className="cs-eyebrow">{t("yourSession")}</p>
            <div className="mt-3 flex items-center justify-between gap-2">
              <span className="rounded-full border border-[color:var(--line-strong)] px-3 py-1 text-xs uppercase tracking-[0.08em]">
                {t(`modes.${mode}.title`)}
              </span>
              <button type="button" onClick={onChangeMode} className="text-xs uppercase tracking-[0.08em]">
                {t("change")}
              </button>
            </div>
          </div>
          <div>
            <p className="cs-eyebrow">{t("whatWeCoach")}</p>
            <ul className="mt-3 space-y-2 text-sm text-[color:var(--text-secondary)]">
              {coachItems.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  {item === t("coachVoice") ? (
                    <Mic className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  ) : item === t("coachScreens") ? (
                    <Activity className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  ) : item === t("coachCamera") ? (
                    <Camera className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  ) : (
                    <Users className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  )}
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="cs-eyebrow">{t("whatWeNeverDo")}</p>
            <ul className="mt-3 space-y-2 text-sm text-[color:var(--text-secondary)]">
              <li className="flex gap-2">
                <X className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                {t("neverContent")}
              </li>
              <li className="flex gap-2">
                <X className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                {t("neverFaces")}
              </li>
              <li className="flex gap-2">
                <span className="mt-0.5 inline-block h-4 w-4 shrink-0 rounded-full border border-[color:var(--line-strong)] text-center text-[10px]" aria-hidden="true">
                  i
                </span>
                {t("neverImages")}
              </li>
            </ul>
          </div>
        </div>
      </aside>
    </div>
  );
}

function formatClockSafe(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

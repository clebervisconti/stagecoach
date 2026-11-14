"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

type Drill = {
  id: string;
  title: string;
  instructions: string;
  duration_s: number;
  capture: "text" | "audio" | "video";
  category_id: string;
};

type WeekItem = {
  kind: string;
  title?: string;
  drill_id?: string;
  days_until?: number;
  category_id?: string;
  metric_id?: string;
  target?: number;
};

export default function PracticePage() {
  const t = useTranslations("practice");
  const locale = useLocale();
  const [drills, setDrills] = useState<Drill[]>([]);
  const [week, setWeek] = useState<WeekItem[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [active, setActive] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [recorder, setRecorder] = useState<MediaRecorder | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const focus = params.get("drill");
    if (focus) window.setTimeout(() => setActive(focus), 0);
    void Promise.all([
      fetch(`/api/stagecoach/drills?locale=${locale}`, { cache: "no-store" }).then((response) => response.json()),
      fetch(`/api/stagecoach/practice/week?locale=${locale}`, { cache: "no-store" }).then((response) => response.json()),
    ])
      .then(([drillBody, weekBody]) => {
        setDrills(drillBody.drills || []);
        setWeek(weekBody.items || []);
      })
      .catch(() => setError(t("loadError")));
  }, [locale, t]);

  async function saveText(drill: Drill) {
    setNotice("");
    const response = await fetch(`/api/stagecoach/drills/${drill.id}/attempts`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const body = await response.json();
    if (!response.ok) {
      setError(body.detail || t("loadError"));
      return;
    }
    setNotice(body.result?.note || t("saved"));
    setText("");
  }

  async function toggleRecord(drill: Drill) {
    if (recording && recorder) {
      recorder.stop();
      setRecording(false);
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: drill.capture === "video",
    });
    const chunks: Blob[] = [];
    const media = new MediaRecorder(stream);
    media.ondataavailable = (event) => {
      if (event.data.size) chunks.push(event.data);
    };
    media.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(chunks, { type: media.mimeType || "video/webm" });
      const form = new FormData();
      form.set("file", blob, drill.capture === "video" ? "take.webm" : "take.webm");
      void fetch(`/api/stagecoach/drills/${drill.id}/attempts/upload`, { method: "POST", body: form })
        .then(async (response) => {
          const body = await response.json();
          setNotice(response.ok ? t("saved") : body.detail || t("loadError"));
        })
        .catch(() => setError(t("loadError")));
    };
    media.start();
    setRecorder(media);
    setRecording(true);
  }

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8" data-testid="practice-page">
      <h1 className="mb-2 text-3xl font-bold">{t("heading")}</h1>
      <p className="mb-6 text-sm text-muted-foreground">{t("intro")}</p>
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      {notice ? <p className="mb-4 text-sm">{notice}</p> : null}
      <form
        className="mb-8 rounded-lg border p-4"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const response = await fetch("/api/stagecoach/deck-review", { method: "POST", body: form });
          const body = await response.json();
          setNotice(
            response.ok
              ? `${body.slide_count ?? 0} · ${body.words_per_slide_median ?? ""} · ${body.note || ""}`
              : body.detail || t("loadError"),
          );
        }}
      >
        <h2 className="mb-1 text-lg font-semibold">{t("deck")}</h2>
        <p className="mb-3 text-sm text-muted-foreground">{t("deckHelp")}</p>
        <input name="file" type="file" accept=".pptx" required className="text-sm" />
        <button type="submit" className="ml-3 rounded-md border px-3 py-2 text-sm">
          {t("textSave")}
        </button>
      </form>
      <section className="mb-8 rounded-lg border p-4">
        <h2 className="mb-3 text-lg font-semibold">{t("week")}</h2>
        {week.length === 0 ? <p className="text-sm text-muted-foreground">{t("emptyWeek")}</p> : null}
        <ul className="space-y-2 text-sm">
          {week.map((item, index) => (
            <li key={`${item.kind}-${item.drill_id || item.metric_id || index}`}>
              {item.kind === "talk_date"
                ? item.days_until
                : item.kind === "goal"
                  ? `${item.metric_id || item.category_id} → ${item.target}`
                  : item.title}
            </li>
          ))}
        </ul>
      </section>
      <ul className="space-y-4">
        {drills.map((drill) => (
          <li key={drill.id} id={drill.id} className="rounded-lg border p-4">
            <h3 className="font-medium">{drill.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{drill.instructions}</p>
            <p className="mt-1 text-xs text-muted-foreground">{drill.duration_s}s</p>
            {active === drill.id || drill.capture === "text" ? (
              drill.capture === "text" ? (
                <form
                  className="mt-3 grid gap-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void saveText(drill);
                  }}
                >
                  <textarea
                    value={active === drill.id ? text : ""}
                    onFocus={() => setActive(drill.id)}
                    onChange={(event) => {
                      setActive(drill.id);
                      setText(event.target.value);
                    }}
                    className="min-h-24 rounded-md border bg-background px-3 py-2 text-sm"
                  />
                  <button type="submit" className="w-fit rounded-md border px-3 py-2 text-sm">
                    {t("textSave")}
                  </button>
                </form>
              ) : (
                <button
                  type="button"
                  className="mt-3 rounded-md border px-3 py-2 text-sm"
                  onClick={() => void toggleRecord(drill)}
                >
                  {recording && active === drill.id ? t("stop") : t("record")}
                </button>
              )
            ) : (
              <button type="button" className="mt-3 text-sm underline" onClick={() => setActive(drill.id)}>
                {t("record")}
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

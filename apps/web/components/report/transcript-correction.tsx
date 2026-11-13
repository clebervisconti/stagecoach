"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

export function TranscriptCorrection({ sessionId }: { sessionId: string }) {
  const t = useTranslations("report");
  const [text, setText] = useState("");
  const [note, setNote] = useState("");

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const response = await fetch(`/api/stagecoach/sessions/${sessionId}/transcript-correction`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const body = await response.json();
    setNote(body.signals?.note || body.detail || t("correctionNote"));
  }

  return (
    <form onSubmit={(event) => void save(event)} className="mt-4 grid gap-2" data-testid="transcript-correction">
      <label className="text-sm font-medium">{t("correctTranscript")}</label>
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="min-h-28 rounded-md border bg-background px-3 py-2 text-sm"
      />
      <button type="submit" className="w-fit rounded-md border px-3 py-2 text-sm">
        {t("saveCorrection")}
      </button>
      {note ? <p className="text-sm text-muted-foreground">{note}</p> : null}
    </form>
  );
}

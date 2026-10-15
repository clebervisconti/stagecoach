"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MutableRefObject } from "react";
import { useTranslations } from "next-intl";
import type { ReportEvidence } from "@/lib/report-types";
import {
  evidenceSeekTime,
  formatTimestamp,
  nextMarker,
  playbackProxyUrl,
  playerCommand,
  previousMarker,
  SKIP_S,
} from "@/lib/player";
import { laneMarkers, type TimelinePayload } from "@/lib/timeline";
import { ReportTimeline } from "@/components/report/timeline";

type PlayerProps = {
  sessionId: string;
  evidence: ReportEvidence[];
  captionsVtt?: string;
  seekRef: MutableRefObject<(tStart: number) => void>;
  timeline?: TimelinePayload | null;
};

export function ReportPlayer({
  sessionId,
  evidence,
  captionsVtt,
  seekRef,
  timeline = null,
}: PlayerProps) {
  const t = useTranslations("report");
  const mediaRef = useRef<HTMLVideoElement>(null);
  const [src, setSrc] = useState(`/api/stagecoach/sessions/${sessionId}/media`);
  const [error, setError] = useState("");
  const [currentTime, setCurrentTime] = useState(0);
  const [focusedLaneId, setFocusedLaneId] = useState<string | null>(null);

  const evidenceMarkers = useMemo(
    () => evidence.map((item) => ({ id: item.id, t: item.t_start })),
    [evidence],
  );
  const focusedLane = timeline?.lanes.find((lane) => lane.id === focusedLaneId);
  const markers = focusedLane ? laneMarkers(focusedLane) : evidenceMarkers;

  function applySeek(time: number) {
    const el = mediaRef.current;
    if (!el) return;
    el.currentTime = Math.max(0, time);
    void el.play();
  }

  function seekEvidence(tStart: number) {
    applySeek(evidenceSeekTime(tStart));
  }

  useEffect(() => {
    seekRef.current = seekEvidence;
  });

  useEffect(() => {
    let active = true;
    async function loadPlayback() {
      try {
        const response = await fetch(`/api/stagecoach/sessions/${sessionId}/media/playback`, {
          cache: "no-store",
        });
        if (!response.ok) return;
        const body = (await response.json()) as { url?: string };
        if (active) setSrc(playbackProxyUrl(sessionId, body));
      } catch {
        if (active) setError(t("playbackError"));
      }
    }
    void loadPlayback();
    return () => {
      active = false;
    };
  }, [sessionId, t]);

  const captionUrl = useMemo(() => {
    if (!captionsVtt) return null;
    return URL.createObjectURL(new Blob([captionsVtt], { type: "text/vtt" }));
  }, [captionsVtt]);

  useEffect(() => {
    return () => {
      if (captionUrl) URL.revokeObjectURL(captionUrl);
    };
  }, [captionUrl]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const command = playerCommand(event);
    if (!command) return;
    event.preventDefault();
    const el = mediaRef.current;
    if (!el) return;
    if (command === "toggle") {
      if (el.paused) void el.play();
      else el.pause();
      return;
    }
    if (command === "back") {
      el.currentTime = Math.max(0, el.currentTime - SKIP_S);
      return;
    }
    if (command === "forward") {
      el.currentTime = el.currentTime + SKIP_S;
      return;
    }
    const current = el.currentTime;
    const marker =
      command === "nextMarker" ? nextMarker(markers, current) : previousMarker(markers, current);
    if (marker) seekEvidence(marker.t);
  }

  return (
    <section className="rounded-lg border bg-card p-6" aria-labelledby="player-heading">
      <h2 id="player-heading" className="mb-3 text-xl font-semibold">
        {t("recording")}
      </h2>
      <div
        role="region"
        tabIndex={0}
        onKeyDown={onKeyDown}
        className="rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={t("playerRegion")}
      >
        <video
          ref={mediaRef}
          controls
          preload="metadata"
          className="w-full rounded-md bg-black"
          src={src}
          onTimeUpdate={() => setCurrentTime(mediaRef.current?.currentTime ?? 0)}
          onSeeked={() => setCurrentTime(mediaRef.current?.currentTime ?? 0)}
          onError={() => setError(t("playbackError"))}
        >
          {captionUrl && (
            <track kind="captions" srcLang="en" src={captionUrl} label={t("transcript")} default />
          )}
        </video>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{t("playerHelp")}</p>
      <ReportTimeline
        sessionId={sessionId}
        payload={timeline}
        currentTime={currentTime}
        focusedLaneId={focusedLaneId}
        onFocusLane={setFocusedLaneId}
        onSeek={(time) => applySeek(time)}
      />
      {error && (
        <p role="status" className="mt-2 text-sm text-muted-foreground">
          {error}
        </p>
      )}
      <ul className="mt-4 space-y-2">
        {evidence.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => seekEvidence(item.t_start)}
              className="block w-full rounded-md border p-3 text-left text-sm hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="font-mono text-xs text-primary">▶ {formatTimestamp(item.t_start)}</span>{" "}
              {item.quote || item.text}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

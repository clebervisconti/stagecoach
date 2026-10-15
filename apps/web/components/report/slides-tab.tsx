"use client";

import { useTranslations } from "next-intl";
import { formatTimestamp } from "@/lib/player";
import { formatRatio, formatSeconds, keyframeUrl, type SlidesPayload } from "@/lib/body-slides";

type SlidesTabProps = {
  sessionId: string;
  payload: SlidesPayload | null;
  onSeek: (tStart: number) => void;
};

export function SlidesTab({ sessionId, payload, onSeek }: SlidesTabProps) {
  const t = useTranslations("report");
  if (!payload || !payload.available) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="slides-tab">
        {payload?.skip_reason || t("slidesUnavailable")}
      </p>
    );
  }
  return (
    <div data-testid="slides-tab" className="space-y-4">
      <p className="text-sm text-muted-foreground">{t("slidesHint")}</p>
      <div className="flex gap-4 overflow-x-auto pb-2">
        {payload.slides.map((slide) => {
          const seekable = slide.t_start != null;
          return (
            <article
              key={slide.index}
              className="w-56 shrink-0 rounded-lg border bg-card p-3"
              data-testid="slide-card"
            >
              <button
                type="button"
                className="mb-2 block w-full overflow-hidden rounded bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() => seekable && onSeek(slide.t_start as number)}
                disabled={!seekable}
              >
                {slide.has_keyframe ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={keyframeUrl(sessionId, slide.index)}
                    alt={slide.title || t("slideN", { n: slide.index })}
                    className="h-28 w-full object-cover"
                  />
                ) : (
                  <div className="flex h-28 items-center justify-center text-xs text-muted-foreground">
                    {t("noKeyframe")}
                  </div>
                )}
              </button>
              <h3 className="truncate text-sm font-medium">{slide.title || t("slideN", { n: slide.index })}</h3>
              <dl className="mt-2 space-y-1 text-xs text-muted-foreground">
                <div>
                  {t("dwell")}: {formatSeconds(slide.dwell_s) ?? t("metricNA")}
                  {seekable ? ` · ${formatTimestamp(slide.t_start as number)}` : ""}
                </div>
                <div>
                  {t("words")}: {slide.word_count}
                </div>
                <div>
                  {t("titleType")}: {slide.title_type ?? t("metricNA")}
                </div>
                <div>
                  {t("glanceLevel")}: {slide.glance_level ?? t("metricNA")}
                </div>
                <div>
                  {t("readingPct")}: {formatRatio(slide.reading_overlap) ?? t("metricNA")}
                </div>
                <div>
                  {t("facingScreen")}: {formatSeconds(slide.facing_screen_s) ?? t("metricNA")}
                </div>
              </dl>
              {slide.suggested_title && (
                <p className="mt-2 text-xs" data-testid="ai-suggestion">
                  <span className="rounded bg-amber-100 px-1 py-0.5 font-medium text-amber-900">
                    {t("aiSuggestion")}
                  </span>{" "}
                  {slide.suggested_title}
                </p>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { TriangleAlert } from "lucide-react";
import { ConfidenceLine } from "@/components/layout/confidence-line";
import { ConfirmDialog } from "@/components/layout/confirm-dialog";
import { LayoutLegend } from "@/components/layout/layout-legend";
import { LayoutPreview } from "@/components/layout/layout-preview";
import { NudgePad } from "@/components/layout/nudge-pad";
import { RegionOverlay } from "@/components/layout/region-overlay";
import { RoleControl } from "@/components/layout/role-control";
import { SegmentEditor } from "@/components/layout/segment-editor";
import { SegmentStrip } from "@/components/layout/segment-strip";
import {
  applyRole,
  cameraCount,
  cloneLayout,
  draftsEqual,
  isLastCamera,
  mergeSegments,
  newRegionId,
  nudgeRegion,
  positionWords,
  proposeMerge,
  removeRegion,
  roleKey,
  setWindow,
  splitSegment,
  upsertRegion,
  type DraftRegion,
  type EditorRole,
  type LayoutDraft,
} from "@/lib/layout-edit";
import { confidenceTone, segmentRoles, type LayoutRole, type LayoutView } from "@/lib/online";

export type LayoutHeading = { eyebrow: string; title: string; lead: string };

const primaryClass =
  "inline-flex h-11 w-full items-center justify-center rounded-[var(--radius-sm)] bg-[color:var(--action-primary)] px-5 text-xs uppercase tracking-[0.08em] text-[color:var(--text-inverse)] disabled:opacity-40";
const ghostClass =
  "inline-flex h-11 w-full items-center justify-center rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] px-5 text-xs uppercase tracking-[0.08em] disabled:opacity-40";
const toolClass =
  "inline-flex h-9 shrink-0 items-center justify-center border border-[color:var(--line-strong)] px-3 text-xs uppercase tracking-[0.08em] disabled:opacity-40";

export function LayoutWorkspace({
  layout,
  editing,
  f6,
  consentOff,
  readOnly,
  auto,
  busy,
  saveError,
  sessionHref,
  onHeading,
  onEditing,
  onAccept,
  onSave,
  onDiscard,
}: {
  layout: LayoutView;
  editing: boolean;
  f6: boolean;
  consentOff: boolean;
  readOnly: boolean;
  auto: boolean;
  busy: boolean;
  saveError: boolean;
  sessionHref: string;
  onHeading: (heading: LayoutHeading) => void;
  onEditing: (editing: boolean) => void;
  onAccept: (audioOnly: boolean) => void;
  onSave: (draft: LayoutDraft) => void;
  onDiscard: () => void;
}) {
  const t = useTranslations("online");
  const [baseline] = useState(() => cloneLayout(layout));
  const [draft, setDraft] = useState(baseline);
  const [selected, setSelected] = useState(layout.segments[0]?.index ?? 0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [fine, setFine] = useState(false);
  const [frame, setFrame] = useState({ width: 0, height: 0 });
  const [playhead, setPlayhead] = useState(() => {
    const first = layout.segments[0];
    return first ? (first.t_start + first.t_end) / 2 : 0;
  });
  const [windowMessage, setWindowMessage] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<null | { kind: "delete"; regionId: string } | { kind: "merge" }>(null);
  const [live, setLive] = useState("");
  const announced = useRef(0);
  const onFrame = useCallback((size: { width: number; height: number }) => {
    setFrame((prev) => (prev.width === size.width && prev.height === size.height ? prev : size));
  }, []);

  const segment = draft.segments.find((row) => row.index === selected) ?? draft.segments[0];
  const selectedRegion = segment?.regions.find((region) => region.id === selectedId) ?? null;
  const dirty = !draftsEqual(draft, baseline);
  const noRegions = draft.segments.every((row) => row.regions.length === 0);
  const tone = confidenceTone(
    layout.confidence,
    layout.review_reason,
    layout.segments.map((row) => row.confidence),
  );
  const preview = segment?.preview_url ? `/api/stagecoach${segment.preview_url.replace("/api/v1", "")}` : null;
  const drawRole: EditorRole = !segment?.regions.some((region) => region.role === "camera")
    ? "camera"
    : !segment.regions.some((region) => region.role === "screen")
      ? "screen"
      : "ignore";

  const eyebrow = readOnly
    ? t("layoutEyebrow")
    : f6 && editing
      ? t("layout.eyebrow.f6")
      : editing
        ? t("layout.eyebrow.edit")
        : consentOff
          ? t("layout.layoutCheck")
          : noRegions
            ? t("layout.eyebrow.review")
            : t("checkLayout");
  const title = readOnly
    ? t("usedTitle")
    : saveError
      ? t("layout.title.saveFailed")
      : editing && drawing && noRegions
        ? t("layout.title.draw")
        : editing && draft.analysis_window
          ? t("layout.title.trim")
          : editing && dirty
            ? t("layout.title.editDirty")
            : noRegions
              ? t("layout.title.empty")
              : consentOff
                ? t("layout.consentTitle")
                : t("layoutTitle");
  const lead = readOnly
    ? auto
      ? t("usedLeadAuto")
      : t("usedLeadYou")
    : saveError
      ? t("layout.saveFailedBody")
      : editing && drawing && noRegions
        ? t("layout.lead.draw")
        : editing && draft.analysis_window
          ? t("layout.lead.trim")
          : f6 && editing
            ? t("layout.lead.f6")
            : editing
              ? t("layout.lead.edit")
              : noRegions
                ? t("layout.lead.empty")
                : consentOff
                  ? t("layout.consentBody")
                  : t("layoutLead");

  useEffect(() => {
    onHeading({ eyebrow, title, lead });
  }, [eyebrow, title, lead, onHeading]);

  function replaceRegion(region: DraftRegion) {
    setDraft((prev) => ({ ...prev, segments: upsertRegion(prev.segments, selected, region) }));
  }

  function announce(region: DraftRegion) {
    const now = Date.now();
    if (now - announced.current < 500) return;
    announced.current = now;
    const place = positionWords(region);
    const position =
      place.vertical === "middle" && place.horizontal === "centre"
        ? t("layout.pos.centre")
        : `${t(`layout.pos.${place.vertical}`)} ${t(`layout.pos.${place.horizontal}`)}`;
    setLive(t("layout.regionAria", { role: t(`layout.role.${roleKey(region.role)}`), position, w: place.wPct, h: place.hPct }));
  }

  function previewPixels() {
    if (typeof document !== "undefined") {
      const box = document.querySelector("[data-testid=layout-preview]")?.getBoundingClientRect();
      if (box && box.width > 0 && box.height > 0) return { width: box.width, height: box.height };
    }
    return frame;
  }

  function nudge(dx: number, dy: number, region: DraftRegion = selectedRegion as DraftRegion) {
    const size = previewPixels();
    if (!region || size.width <= 0 || size.height <= 0) return;
    const next = nudgeRegion(region, dx, dy, size.width, size.height);
    replaceRegion(next);
    announce(next);
  }

  function setRole(role: EditorRole) {
    if (!selectedRegion) return;
    setDraft((prev) => ({ ...prev, segments: applyRole(prev.segments, selected, selectedRegion.id, role) }));
  }

  function requestRemove(regionId: string) {
    if (isLastCamera(draft.segments, regionId)) {
      setConfirm({ kind: "delete", regionId });
      return;
    }
    setDraft((prev) => ({ ...prev, segments: removeRegion(prev.segments, selected, regionId) }));
    setSelectedId(null);
  }

  function commitDraw(region: DraftRegion) {
    const id = newRegionId();
    const created = { ...region, id };
    setDraft((prev) => {
      const inserted = upsertRegion(prev.segments, selected, created);
      const segments =
        created.role === "camera" || created.role === "screen"
          ? applyRole(inserted, selected, id, created.role)
          : inserted;
      return { ...prev, segments };
    });
    setSelectedId(id);
    setDrawing(false);
  }

  useEffect(() => {
    if (!editing) return;
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (!target || target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.closest("[role=alertdialog]")) return;
      const regionId = target.closest("[data-region]")?.getAttribute("data-region");
      if (event.key === "Escape") {
        setSelectedId(null);
        setDrawing(false);
        return;
      }
      const region = segment?.regions.find((row) => row.id === regionId);
      if (!regionId || !region) return;
      setSelectedId(regionId);
      const step = event.shiftKey ? 10 : 1;
      const arrows: Record<string, [number, number]> = {
        ArrowLeft: [-step, 0],
        ArrowRight: [step, 0],
        ArrowUp: [0, -step],
        ArrowDown: [0, step],
      };
      if (arrows[event.key]) {
        event.preventDefault();
        nudge(arrows[event.key][0], arrows[event.key][1], region);
      } else if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        requestRemove(region.id);
      } else if (event.key >= "1" && event.key <= "4") {
        const roles: EditorRole[] = ["camera", "screen", "other_participant", "ignore"];
        setDraft((prev) => ({ ...prev, segments: applyRole(prev.segments, selected, region.id, roles[Number(event.key) - 1]) }));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // nudge and requestRemove close over the latest selection on each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing, selectedRegion, frame.width, frame.height, selected, draft.segments]);

  function splitAtPlayhead() {
    const result = splitSegment(draft.segments, selected, playhead);
    if (!result.ok) return;
    setDraft((prev) => ({ ...prev, segments: result.segments }));
  }

  function mergeNow(keep: "left" | "right") {
    const next = mergeSegments(draft.segments, selected, keep);
    if (!next) return;
    setDraft((prev) => ({ ...prev, segments: next }));
    setSelected(next[Math.max(0, next.length - 1)] ? selected - 1 : 0);
    setSelectedId(null);
    setConfirm(null);
  }

  function askMerge() {
    const proposal = proposeMerge(draft.segments, selected);
    if (proposal === "differ") setConfirm({ kind: "merge" });
    else if (proposal === "same") mergeNow("left");
  }

  function changeWindow(start: number, end: number) {
    const result = setWindow(draft.duration_s, start, end);
    if (!result.ok) {
      setWindowMessage(result.reason === "short" ? t("layout.windowShort") : null);
      return;
    }
    setWindowMessage(null);
    setDraft((prev) => ({ ...prev, analysis_window: result.window }));
  }

  const summary = selectedRegion
    ? `${t(`layout.role.${roleKey(selectedRegion.role)}`)} · ${positionWords(selectedRegion).wPct}% × ${positionWords(selectedRegion).hPct}%`
    : t("layout.nothingSelected");
  const canAnalyse = !noRegions && !busy;
  const showEditor = editing && !readOnly;

  function actions() {
    if (readOnly) {
      return (
        <a href={sessionHref} data-testid="back-to-session" className={ghostClass}>
          ← {t("backToSession")}
        </a>
      );
    }
    if (saveError) {
      return (
        <>
          <button type="button" data-testid="try-again" className={primaryClass} disabled={busy} onClick={() => onSave(draft)}>
            {t("layout.cta.tryAgain")}
          </button>
          <button type="button" data-testid="discard" className={ghostClass} disabled={busy} onClick={onDiscard}>
            {t("layout.cta.discard")}
          </button>
        </>
      );
    }
    if (!showEditor && noRegions) {
      return (
        <>
          <button
            type="button"
            data-testid="draw-regions"
            className={primaryClass}
            onClick={() => {
              onEditing(true);
              setDrawing(true);
            }}
          >
            {t("layout.cta.draw")}
          </button>
          <button type="button" data-testid="analyse-audio" className={ghostClass} disabled={busy} onClick={() => onAccept(true)}>
            {t("analyseAudio")}
          </button>
        </>
      );
    }
    if (!showEditor) {
      return (
        <>
          <button type="button" data-testid="looks-right" className={primaryClass} disabled={busy} onClick={() => onAccept(false)}>
            {t("looksRight")}
          </button>
          <button type="button" data-testid="adjust" className={ghostClass} onClick={() => onEditing(true)}>
            {t("layout.cta.adjust")}
          </button>
          <button type="button" data-testid="analyse-audio" className={ghostClass} disabled={busy} onClick={() => onAccept(true)}>
            {t("analyseAudio")}
          </button>
        </>
      );
    }
    if (f6 || dirty) {
      return (
        <>
          <button type="button" data-testid="analyse-layout" className={primaryClass} disabled={!canAnalyse} onClick={() => onSave(draft)}>
            {t("layout.cta.analyseLayout")}
          </button>
          {dirty ? (
            <button type="button" data-testid="discard" className={ghostClass} disabled={busy} onClick={onDiscard}>
              {t("layout.cta.discard")}
            </button>
          ) : (
            <a href={sessionHref} data-testid="back-to-report" className={ghostClass}>
              {t("layout.cta.backToReport")}
            </a>
          )}
        </>
      );
    }
    return (
      <>
        <button type="button" data-testid="looks-right" className={primaryClass} disabled={busy || noRegions} onClick={() => onAccept(false)}>
          {t("looksRight")}
        </button>
        <button type="button" data-testid="done-editing" className={ghostClass} onClick={() => onEditing(false)}>
          {t("layout.cta.doneEditing")}
        </button>
      </>
    );
  }

  const reviewSegment = layout.segments.find((row) => row.index === selected) ?? layout.segments[0];
  const showBanner = (dirty || saveError) && showEditor;
  const legendRoles: LayoutRole[] = showEditor
    ? ["camera", "screen", "other_participant", "ignore"]
    : segmentRoles(reviewSegment);

  return (
    <div className={showEditor ? "pb-80 lg:pb-0" : ""}>
      <p className="sr-only" aria-live="polite">
        {live}
      </p>
      <div className="mt-10 grid min-w-0 items-start gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        {showBanner && (
          <div
            role={saveError ? "alert" : "status"}
            data-testid={saveError ? "layout-save-error" : "unsaved-changes"}
            className="flex gap-3 rounded-[var(--radius-sm)] border border-[color:var(--line-strong)] p-4 lg:col-start-2"
          >
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div>
              <p className="text-xs uppercase tracking-[0.08em]">
                {saveError ? t("layout.status.saveFailed") : t("layout.status.unsaved")}
              </p>
              <p className="mt-1 text-sm text-[color:var(--text-secondary)]">
                {saveError ? t("layout.saveFailedBody") : t("layout.unsavedBody")}
              </p>
            </div>
          </div>
        )}
        <div className={`min-w-0 ${showBanner ? "lg:col-start-1 lg:row-span-2 lg:row-start-1" : ""}`}>
          {showEditor && (
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span data-testid="editing-badge" className="inline-flex h-9 items-center gap-2 border border-[color:var(--line-strong)] px-3 text-xs uppercase tracking-[0.08em]">
                <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--text-strong)]" aria-hidden="true" />
                {t("layout.status.editing")}
              </span>
              <div className="hidden min-w-[280px] lg:block">
                <RoleControl value={selectedRegion?.role ?? null} disabled={!selectedRegion} onChange={setRole} />
              </div>
              <button type="button" data-testid="add-region" className={toolClass} onClick={() => setDrawing(true)}>
                {t("layout.cta.addRegion")}
              </button>
              <button
                type="button"
                data-testid="remove-region"
                className={toolClass}
                disabled={!selectedRegion}
                onClick={() => selectedRegion && requestRemove(selectedRegion.id)}
              >
                {t("layout.cta.remove")}
              </button>
            </div>
          )}
          {showEditor || noRegions ? (
            <RegionOverlay
              src={preview}
              segment={segment}
              editable={showEditor}
              selectedId={selectedId}
              drawing={drawing}
              drawRole={drawRole}
              uncertainRole={tone === "check" ? "camera" : null}
              previewT={layout.preview_t}
              empty={noRegions && !segment?.regions.length}
              onSelect={setSelectedId}
              onChange={replaceRegion}
              onCommit={commitDraw}
              onFrame={onFrame}
            />
          ) : (
            <LayoutPreview
              src={preview}
              segment={reviewSegment}
              previewT={layout.preview_t}
              uncertainRole={tone === "check" ? "camera" : null}
            />
          )}
          {showEditor ? (
            <SegmentEditor
              draft={draft}
              selected={segment?.index ?? 0}
              playhead={playhead}
              message={windowMessage}
              onSelect={setSelected}
              onPlayhead={setPlayhead}
              onSplit={splitAtPlayhead}
              onMerge={askMerge}
              onAdd={splitAtPlayhead}
              onWindow={changeWindow}
            />
          ) : (
            !noRegions && <SegmentStrip segments={layout.segments} selected={reviewSegment?.index ?? 0} onSelect={setSelected} />
          )}
        </div>
        <div className={`space-y-8 ${showBanner ? "lg:col-start-2" : ""}`}>
          {!showEditor && !noRegions && <ConfidenceLine layout={layout} consentOff={consentOff} />}
          {legendRoles.length > 0 && <LayoutLegend roles={legendRoles} />}
          {showEditor && selectedRegion && (
            <div className="hidden lg:block">
              <p className="cs-eyebrow">{t("layout.selected")}</p>
              <p className="mt-2 text-sm">{summary}</p>
            </div>
          )}
          <div
            className={
              showEditor
                ? "space-y-3 max-lg:fixed max-lg:inset-x-0 max-lg:bottom-0 max-lg:z-30 max-lg:max-h-[72vh] max-lg:overflow-auto max-lg:border-t max-lg:border-[color:var(--line-strong)] max-lg:bg-[color:var(--bg)] max-lg:p-4"
                : "space-y-3"
            }
            data-testid={showEditor ? "selection-sheet" : "layout-actions"}
          >
            {showEditor && (
              <div className="lg:hidden">
                <div className="flex items-center justify-between gap-3">
                  <p className="min-w-0 truncate text-xs uppercase tracking-[0.08em]">{summary}</p>
                  <button type="button" data-testid="sheet-done" className="h-11 shrink-0 px-3 text-xs uppercase tracking-[0.08em]" onClick={() => setSelectedId(null)}>
                    {t("layout.cta.done")}
                  </button>
                </div>
                <RoleControl className="mt-3" withTestIds={false} value={selectedRegion?.role ?? null} disabled={!selectedRegion} onChange={setRole} />
              </div>
            )}
            {showEditor && selectedRegion && (
              <NudgePad fine={fine} onFine={setFine} onNudge={nudge} />
            )}
            {actions()}
            {showEditor && <p className="text-xs text-[color:var(--text-tertiary)]">{t("layout.keyboardHint")}</p>}
          </div>
          {cameraCount(draft.segments) === 0 && showEditor && !noRegions && (
            <p className="text-sm text-[color:var(--text-secondary)]">{t("layout.noCamera")}</p>
          )}
        </div>
      </div>
      {confirm?.kind === "delete" && (
        <ConfirmDialog
          title={t("layout.deleteLastCamera")}
          body={t("layout.deleteLastCameraBody")}
          onCancel={() => setConfirm(null)}
          actions={[
            {
              id: "remove",
              label: t("layout.cta.remove"),
              tone: "danger",
              onClick: () => {
                setDraft((prev) => ({ ...prev, segments: removeRegion(prev.segments, selected, confirm.regionId) }));
                setSelectedId(null);
                setConfirm(null);
              },
            },
            { id: "cancel", label: t("cancel"), tone: "ghost", onClick: () => setConfirm(null) },
          ]}
        />
      )}
      {confirm?.kind === "merge" && (
        <ConfirmDialog
          title={t("layout.mergeTitle")}
          body={t("layout.mergeBody")}
          onCancel={() => setConfirm(null)}
          actions={[
            { id: "keep-left", label: t("layout.merge.keepLeft"), onClick: () => mergeNow("left") },
            { id: "keep-right", label: t("layout.merge.keepRight"), onClick: () => mergeNow("right") },
            { id: "cancel", label: t("cancel"), tone: "ghost", onClick: () => setConfirm(null) },
          ]}
        />
      )}
    </div>
  );
}

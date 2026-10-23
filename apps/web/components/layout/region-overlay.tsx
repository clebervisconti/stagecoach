"use client";

import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { useTranslations } from "next-intl";
import { TriangleAlert } from "lucide-react";
import { formatClock } from "@/lib/online";
import {
  boxFromPoints,
  moveRegion,
  newRegionId,
  positionWords,
  resizeRegion,
  roleKey,
  type Corner,
  type DraftRegion,
  type DraftSegment,
  type EditorRole,
} from "@/lib/layout-edit";

type Point = { x: number; y: number };

type Drag =
  | { kind: "move"; id: string; origin: DraftRegion; pointer: Point }
  | { kind: "resize"; id: string; handle: Corner; origin: DraftRegion; pointer: Point }
  | { kind: "draw"; origin: Point; current: Point };

function contentBox(frame: DOMRect, image: HTMLImageElement | null) {
  const naturalW = image && image.naturalWidth > 0 ? image.naturalWidth : 16;
  const naturalH = image && image.naturalHeight > 0 ? image.naturalHeight : 9;
  const scale = Math.min(frame.width / naturalW, frame.height / naturalH);
  const width = naturalW * scale;
  const height = naturalH * scale;
  return {
    left: frame.left + (frame.width - width) / 2,
    top: frame.top + (frame.height - height) / 2,
    width,
    height,
  };
}

export function RegionOverlay({
  src,
  segment,
  editable,
  selectedId,
  drawing,
  drawRole,
  uncertainRole,
  previewT,
  empty,
  onSelect,
  onChange,
  onCommit,
  onFrame,
}: {
  src: string | null;
  segment: DraftSegment | undefined;
  editable: boolean;
  selectedId: string | null;
  drawing: boolean;
  drawRole: EditorRole;
  uncertainRole?: string | null;
  previewT?: number | null;
  empty?: boolean;
  onSelect: (id: string) => void;
  onChange: (region: DraftRegion) => void;
  onCommit: (region: DraftRegion) => void;
  onFrame: (size: { width: number; height: number }) => void;
}) {
  const t = useTranslations("online");
  const frameRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const dragRef = useRef<Drag | null>(null);
  function assignDrag(next: Drag | null) {
    dragRef.current = next;
    setDrag(next);
  }

  function locate(event: { clientX: number; clientY: number }): Point {
    const frame = frameRef.current?.getBoundingClientRect();
    if (!frame) return { x: 0, y: 0 };
    const box = contentBox(frame, imageRef.current);
    return {
      x: Math.min(1, Math.max(0, (event.clientX - box.left) / Math.max(box.width, 1))),
      y: Math.min(1, Math.max(0, (event.clientY - box.top) / Math.max(box.height, 1))),
    };
  }

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const report = () => {
      const box = contentBox(frame.getBoundingClientRect(), imageRef.current);
      onFrame({ width: box.width, height: box.height });
    };
    report();
    const observer = new ResizeObserver(report);
    observer.observe(frame);
    const image = imageRef.current;
    image?.addEventListener("load", report);
    return () => {
      observer.disconnect();
      image?.removeEventListener("load", report);
    };
  }, [onFrame, src]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape" || !dragRef.current) return;
      event.preventDefault();
      event.stopPropagation();
      const current = dragRef.current;
      if (current.kind !== "draw") onChange(current.origin);
      assignDrag(null);
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onChange]);

  function updateDrag(event: { clientX: number; clientY: number }) {
    const current = dragRef.current;
    if (!current) return;
    const point = locate(event);
    if (current.kind === "draw") {
      assignDrag({ ...current, current: point });
      return;
    }
    const dx = point.x - current.pointer.x;
    const dy = point.y - current.pointer.y;
    const next =
      current.kind === "resize"
        ? resizeRegion(current.origin, current.handle, dx, dy)
        : moveRegion(current.origin, dx, dy);
    onChange(next);
  }

  function finishDrag(event: { clientX: number; clientY: number }) {
    const current = dragRef.current;
    if (!current) return;
    if (current.kind === "draw") {
      const region = boxFromPoints(current.origin, locate(event), drawRole, newRegionId());
      if (region) onCommit(region);
    }
    assignDrag(null);
  }

  const regions = segment?.regions ?? [];
  const ghost =
    drag?.kind === "draw"
      ? boxFromPoints(drag.origin, drag.current, drawRole, "ghost") ?? {
          id: "ghost",
          role: drawRole,
          x: drag.current.x,
          y: drag.current.y,
          w: 0.02,
          h: 0.02,
          source: "user" as const,
        }
      : null;

  const description = regions
    .map((region) => {
      const place = positionWords(region);
      const role = t(`layout.role.${roleKey(region.role)}`);
      const position =
        place.vertical === "middle" && place.horizontal === "centre"
          ? t("layout.pos.centre")
          : `${t(`layout.pos.${place.vertical}`)} ${t(`layout.pos.${place.horizontal}`)}`;
      return t("layout.regionAria", { role, position, w: place.wPct, h: place.hPct });
    })
    .join(" ");

  return (
    <figure data-testid={empty ? "layout-empty" : undefined}>
      <div
        ref={frameRef}
        className={`relative aspect-video overflow-hidden bg-black ${empty ? "cs-empty" : ""}`}
        tabIndex={editable ? -1 : 0}
        data-testid="layout-preview"
        aria-describedby="layout-preview-desc"
        onPointerDown={(event) => {
          if (!editable) return;
          const target = event.target as HTMLElement;
          if (target.closest("[data-region]")) return;
          const point = locate(event);
          assignDrag({ kind: "draw", origin: point, current: point });
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => updateDrag(event)}
        onPointerUp={(event) => finishDrag(event)}
        onPointerCancel={() => {
          const current = dragRef.current;
          if (current && current.kind !== "draw") onChange(current.origin);
          assignDrag(null);
        }}
      >
        {src && !empty ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img ref={imageRef} src={src} alt="" className="h-full w-full object-contain" />
        ) : (
          <div className="h-full w-full" />
        )}
        {empty && (
          <p className="pointer-events-none absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-[color:var(--text-secondary)]">
            {t("layout.emptyHint")}
          </p>
        )}
        <div className={editable ? "absolute inset-0" : "pointer-events-none absolute inset-0"}>
          {regions.map((region) => (
            <RegionBox
              key={region.id}
              region={region}
              editable={editable}
              selected={selectedId === region.id}
              uncertain={uncertainRole === region.role}
              onSelect={() => onSelect(region.id)}
              onPointerDown={(event) => {
                if (!editable) return;
                event.stopPropagation();
                const point = locate(event);
                if (drawing) {
                  assignDrag({ kind: "draw", origin: point, current: point });
                } else {
                  onSelect(region.id);
                  const handle = (event.target as HTMLElement).closest("[data-handle]")?.getAttribute("data-handle") as Corner | null;
                  assignDrag(
                    handle
                      ? { kind: "resize", id: region.id, handle, origin: region, pointer: point }
                      : { kind: "move", id: region.id, origin: region, pointer: point },
                  );
                }
                frameRef.current?.setPointerCapture(event.pointerId);
              }}
            />
          ))}
          {ghost && <RegionBox region={ghost} editable={false} selected={false} uncertain={false} drawing />}
        </div>
      </div>
      <p id="layout-preview-desc" className="sr-only">
        {description || t("noRegions")}
      </p>
      <figcaption className="mt-2 font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text-tertiary)]">
        {previewT != null ? t("frameAt", { time: formatClock(previewT) }) : t("previewOnly")}
        {editable ? ` · ${t("layout.nudge.hint")}` : ""}
      </figcaption>
    </figure>
  );
}

function RegionBox({
  region,
  editable,
  selected,
  uncertain,
  drawing,
  onSelect,
  onPointerDown,
}: {
  region: DraftRegion;
  editable: boolean;
  selected: boolean;
  uncertain: boolean;
  drawing?: boolean;
  onSelect?: () => void;
  onPointerDown?: (event: ReactPointerEvent) => void;
}) {
  const t = useTranslations("online");
  const key = roleKey(region.role);
  const kind = key === "screen" ? "screen" : key === "camera" ? "camera" : "ignored";
  const place = positionWords(region);
  const role = t(`layout.role.${key}`);
  const position =
    place.vertical === "middle" && place.horizontal === "centre"
      ? t("layout.pos.centre")
      : `${t(`layout.pos.${place.vertical}`)} ${t(`layout.pos.${place.horizontal}`)}`;
  const label = drawing ? `${role} · ${t("layout.drawing")}` : role;
  const style = {
    left: `${region.x * 100}%`,
    top: `${region.y * 100}%`,
    width: `${Math.max(region.w, 0.02) * 100}%`,
    height: `${Math.max(region.h, 0.02) * 100}%`,
  };
  const className = `cs-region cs-region--${kind} ${editable ? "cs-region--edit" : ""} ${selected ? "cs-region--selected" : ""}`;
  const body = (
    <>
      <span className="cs-region__label">
        {uncertain && <TriangleAlert className="h-3 w-3 shrink-0 text-[color:var(--status-warning)]" aria-hidden="true" />}
        {label}
      </span>
      {selected &&
        (["nw", "ne", "sw", "se"] as const).map((handle) => (
          <span key={handle} data-handle={handle} className={`cs-handle cs-handle--${handle}`} />
        ))}
    </>
  );
  if (!editable) {
    return (
      <div className={className} style={style} aria-hidden="true">
        {body}
      </div>
    );
  }
  return (
    <button
      type="button"
      data-region={region.id}
      data-testid={`region-${region.id}`}
      className={className}
      style={style}
      aria-pressed={selected}
      aria-label={t("layout.regionAria", { role, position, w: place.wPct, h: place.hPct })}
      onFocus={onSelect}
      onClick={onSelect}
      onPointerDown={onPointerDown}
    >
      {body}
    </button>
  );
}

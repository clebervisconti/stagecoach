"""PDF export via Playwright Chromium (issue #49, SPEC §6.8 / §8.9).

Print HTML mirrors the web report sections. Charts are SVG. Keyframes replace
video. The transcript is omitted unless the caller sets include_transcript.
"""

from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECTION_IDS = (
    "cover",
    "opportunities",
    "strengths",
    "categories",
    "time",
    "metrics",
    "drills",
    "methodology",
)

PILLAR_ORDER = (
    "message",
    "story_impact",
    "visuals",
    "voice",
    "body",
    "presence_time",
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _fmt_ts(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = max(0, int(float(seconds)))
    return f"{total // 60:02d}:{total % 60:02d}"


def _radar_svg(pillars: list[dict[str, Any]]) -> str:
    size, cx, cy, radius = 280, 140, 140, 96
    n = max(len(PILLAR_ORDER), 1)
    by_id = {p.get("id"): p for p in pillars}
    rings = []
    for ring in (0.25, 0.5, 0.75, 1.0):
        pts = []
        for i in range(n):
            angle = -math.pi / 2 + i * 2 * math.pi / n
            pts.append(
                f"{cx + radius * ring * math.cos(angle):.1f},{cy + radius * ring * math.sin(angle):.1f}"
            )
        rings.append(
            f'<polygon points="{" ".join(pts)}" fill="none" stroke="#d4d4d8" stroke-width="1"/>'
        )
    vertices = []
    labels = []
    for i, pid in enumerate(PILLAR_ORDER):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        endx, endy = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
        rings.append(
            f'<line x1="{cx}" y1="{cy}" x2="{endx:.1f}" y2="{endy:.1f}" stroke="#d4d4d8"/>'
        )
        pillar = by_id.get(pid) or {}
        score = pillar.get("score")
        if isinstance(score, (int, float)):
            r = (float(score) / 100.0) * radius
            vertices.append(
                f"{cx + r * math.cos(angle):.1f},{cy + r * math.sin(angle):.1f}"
            )
        lx = cx + (radius + 22) * math.cos(angle)
        ly = cy + (radius + 22) * math.sin(angle)
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="11">{_esc(pid.replace("_", " "))}</text>'
        )
    poly = (
        f'<polygon points="{" ".join(vertices)}" fill="rgba(37,99,235,0.25)" stroke="#2563eb" stroke-width="2"/>'
        if vertices
        else ""
    )
    return (
        f'<svg viewBox="0 0 {size} {size}" width="220" height="220" role="img" aria-label="Radar">'
        f"{''.join(rings)}{poly}{''.join(labels)}</svg>"
    )


def build_print_model(
    report: dict[str, Any],
    *,
    transcript: dict[str, Any] | None = None,
    include_transcript: bool = False,
    keyframes: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Pure view model. Does not invent scores. Transcript stays out unless asked."""
    overall = report.get("overall") or {}
    insights = report.get("insights") or {}
    opportunities = list(insights.get("opportunities") or [])[:3]
    strengths = list(insights.get("strengths") or [])
    categories = list(report.get("categories") or [])
    evidence = {e.get("id"): e for e in (report.get("evidence") or [])}
    media = report.get("media") or {}
    session = report.get("session") or {}
    provenance = report.get("provenance") or {}
    slot = session.get("slot_min")
    duration_s = media.get("duration_s")
    actual_min = round(float(duration_s) / 60.0, 1) if duration_s else None
    drills: list[str] = []
    for item in opportunities:
        for drill in item.get("drill_ids") or []:
            if drill not in drills:
                drills.append(str(drill))
    frames = list(keyframes or [])
    return {
        "sections": list(SECTION_IDS),
        "title": session.get("id") or "Session",
        "language": session.get("language") or "en",
        "context_type": session.get("context_type") or "",
        "overall": overall,
        "summary": insights.get("summary") or "",
        "pillars": report.get("pillars") or [],
        "opportunities": opportunities,
        "strengths": strengths,
        "categories": categories,
        "metrics": report.get("metrics") or [],
        "evidence": evidence,
        "keyframes": frames,
        "slot_min": slot,
        "actual_min": actual_min,
        "drills": drills,
        "scoring_config_version": provenance.get("scoring_config_version") or "1.0.0",
        "generated_at": generated_at
        or provenance.get("generated_at")
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "include_transcript": bool(include_transcript),
        "transcript_segments": list((transcript or {}).get("segments") or [])
        if include_transcript
        else [],
        "limitations": (
            "Unavailable categories stay N/A. This is not emotion recognition, "
            "face recognition, or a grading tool."
        ),
        "sources": sorted(
            {src for cat in categories for src in (cat.get("sources") or []) if src}
        ),
    }


def render_print_html(model: dict[str, Any]) -> str:
    """Self-contained print HTML. Charts are SVG. No <video> element."""
    overall = model.get("overall") or {}
    score = overall.get("score")
    band = overall.get("display_band")
    score_line = "—" if score is None else f"{score} ± {band}"
    radar = _radar_svg(list(model.get("pillars") or []))
    opp_html = []
    for item in model.get("opportunities") or []:
        ev_id = (item.get("evidence_ids") or [None])[0]
        ev = (model.get("evidence") or {}).get(ev_id) or {}
        ts = _fmt_ts(ev.get("t_start"))
        frame = ""
        for kf in model.get("keyframes") or []:
            if ev.get("t_start") is not None and kf.get("t") is not None:
                if abs(float(kf["t"]) - float(ev["t_start"])) <= 5:
                    frame = f'<img src="{_esc(kf.get("src") or "")}" alt="keyframe {ts}" width="160"/>'
                    break
        opp_html.append(
            "<article class='card'>"
            f"<h3>{_esc(item.get('title'))}</h3>"
            f"<p>{_esc(item.get('body'))}</p>"
            f"<p class='meta'>Keyframe {ts}</p>{frame}"
            f"<p>{_esc(item.get('fix'))}</p>"
            "</article>"
        )
    if not opp_html:
        opp_html.append("<p>No opportunities were selected.</p>")
    str_html = (
        "".join(
            f"<article class='card'><h3>{_esc(s.get('title'))}</h3><p>{_esc(s.get('body'))}</p></article>"
            for s in (model.get("strengths") or [])
        )
        or "<p>No strengths were selected.</p>"
    )
    rows = []
    for i, cat in enumerate(model.get("categories") or [], start=1):
        ev_id = (cat.get("evidence_ids") or [None])[0]
        ev = (model.get("evidence") or {}).get(ev_id) or {}
        score_cell = "N/A" if cat.get("score") is None else str(cat.get("score"))
        rows.append(
            "<tr>"
            f"<td>{i}</td><td>{_esc(cat.get('id'))}</td>"
            f"<td>{_esc(score_cell)}</td><td>{_esc(cat.get('level') if cat.get('level') is not None else 'N/A')}</td>"
            f"<td>{_esc(cat.get('confidence_label') or 'N/A')}</td>"
            f"<td>—</td><td>{_esc(ev.get('text') or '')}</td>"
            "</tr>"
        )
    metric_rows = "".join(
        "<tr>"
        f"<td>{_esc(m.get('id'))}</td>"
        f"<td>{_esc(m.get('raw_value') if m.get('raw_value') is not None else 'N/A')}</td>"
        f"<td>{_esc(m.get('score') if m.get('score') is not None else 'N/A')}</td>"
        "</tr>"
        for m in (model.get("metrics") or [])
    )
    drill_html = (
        "".join(f"<li>{_esc(d)}</li>" for d in (model.get("drills") or []))
        or "<li>None</li>"
    )
    sources = (
        ", ".join(_esc(s) for s in (model.get("sources") or []))
        or "See docs/research/sources.md"
    )
    transcript_html = ""
    if model.get("include_transcript"):
        segs = "".join(
            f"<p><strong>{_fmt_ts(s.get('start'))}</strong> {_esc(s.get('text'))}</p>"
            for s in (model.get("transcript_segments") or [])
        )
        transcript_html = (
            f'<section id="transcript" class="page"><h2>Transcript</h2>{segs}</section>'
        )
    time_line = (
        f"Planned {model.get('slot_min')} min → actual {model.get('actual_min')} min"
        if model.get("slot_min") and model.get("actual_min") is not None
        else "Slot vs actual is N/A without a planned slot or duration."
    )
    return f"""<!DOCTYPE html>
<html lang="{_esc(model.get("language") or "en")}">
<head>
<meta charset="utf-8"/>
<title>Stage Coach report</title>
<style>
  body {{ font-family: system-ui, sans-serif; color: #18181b; margin: 24px; }}
  h1,h2 {{ page-break-after: avoid; }}
  .page {{ page-break-after: always; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th,td {{ border: 1px solid #e4e4e7; padding: 6px; text-align: left; }}
  .card {{ border: 1px solid #e4e4e7; padding: 12px; margin: 8px 0; }}
  .meta {{ color: #71717a; font-size: 12px; }}
  footer {{ font-size: 11px; color: #71717a; margin-top: 24px; }}
  video {{ display: none !important; }}
</style>
</head>
<body>
<section id="cover" class="page" data-section="cover">
  <h1>Stage Coach</h1>
  <p class="meta">{_esc(model.get("context_type"))}</p>
  <p data-testid="pdf-score">{_esc(score_line)}</p>
  <p>{_esc(model.get("summary"))}</p>
  <div data-chart="radar">{radar}</div>
</section>
<section id="opportunities" class="page" data-section="opportunities">
  <h2>Top opportunities</h2>
  {"".join(opp_html)}
</section>
<section id="strengths" class="page" data-section="strengths">
  <h2>Strengths</h2>
  {str_html}
</section>
<section id="categories" class="page" data-section="categories">
  <h2>Categories</h2>
  <table>
    <thead><tr><th>#</th><th>Category</th><th>Score</th><th>Level</th><th>Confidence</th><th>Δ</th><th>Key evidence</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</section>
<section id="time" class="page" data-section="time">
  <h2>Time</h2>
  <p>{_esc(time_line)}</p>
</section>
<section id="metrics" class="page" data-section="metrics">
  <h2>Metrics</h2>
  <table>
    <thead><tr><th>Metric</th><th>Raw</th><th>Score</th></tr></thead>
    <tbody>{metric_rows}</tbody>
  </table>
</section>
<section id="drills" class="page" data-section="drills">
  <h2>Drills</h2>
  <ul>{drill_html}</ul>
</section>
<section id="methodology" class="page" data-section="methodology">
  <h2>Methodology</h2>
  <p>Scoring config {_esc(model.get("scoring_config_version"))}.</p>
  <p>Sources: {sources}</p>
  <p>{_esc(model.get("limitations"))}</p>
</section>
{transcript_html}
<footer>Generated {_esc(model.get("generated_at"))} · config {_esc(model.get("scoring_config_version"))}</footer>
</body>
</html>
"""


def html_to_pdf(html_text: str, dest: Path) -> Path:
    """Render HTML to PDF with Playwright Chromium. CPU only; no new models."""
    from playwright.sync_api import sync_playwright

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html_text, wait_until="load")
            page.pdf(path=str(dest), format="A4", print_background=True)
        finally:
            browser.close()
    return dest


def export_session_pdf(
    output_dir: Path,
    dest: Path,
    *,
    include_transcript: bool = False,
) -> dict[str, Any]:
    report = _read_json(Path(output_dir) / "report.json") or _read_json(
        Path(output_dir) / "analysis_result.json"
    )
    if not report:
        raise FileNotFoundError("report.json is not ready")
    transcript = _read_json(Path(output_dir) / "transcript.json")
    slides = _read_json(Path(output_dir) / "slides.json")
    keyframes = []
    for slide in slides.get("slides") or []:
        if slide.get("keyframe"):
            keyframes.append(
                {
                    "t": slide.get("keyframe_t") or slide.get("t_start"),
                    "src": slide["keyframe"],
                }
            )
    model = build_print_model(
        report,
        transcript=transcript,
        include_transcript=include_transcript,
        keyframes=keyframes,
    )
    html_text = render_print_html(model)
    html_path = Path(dest).with_suffix(".html")
    html_path.write_text(html_text, encoding="utf-8")
    pdf_path = html_to_pdf(html_text, dest)
    return {
        "path": str(pdf_path),
        "html_path": str(html_path),
        "sections": model["sections"],
        "include_transcript": include_transcript,
        "bytes": pdf_path.stat().st_size if pdf_path.is_file() else 0,
    }

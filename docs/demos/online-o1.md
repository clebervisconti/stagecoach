# Phase O1 demo notes

Walking skeleton for webinar / online talk / recorded video.

## Flow

1. Allowlisted account with `ONLINE_MODES_ENABLED=true` sees **New analysis** → `/sessions/new?step=where`.
2. Four mode cards. Step 2 is one file, no tab bar. Deck uploads first.
3. `tasks.prepare_session` ingest + single-layout detection.
4. First 3 online sessions always review; afterwards only when confidence < 0.80.
5. LOOKS RIGHT · ANALYSE or ANALYSE AUDIO ONLY. ADJUST is hidden.
6. Report: mode badge, core delivery, NOT MEASURED, BODY hidden.

## Evidence

- Playwright screenshots: `/opt/cursor/artifacts/o1-screens/<screen>_<state>_<width>_<theme>.png`
- Unit / API / fixture tests in this PR
- `python scripts/bench_online_cpu.py --run --out /tmp/bench-online-o1.json`

### §13 budgets (fixture-scale, 22 Oct 2026)

Synthetic `composite_pip_tr` (2 s, 1920×1080) on Linux x86_64 Xeon, 4 CPUs. Not a 60-min LION run.

| Stage | Budget (s) | Measured (s) |
|---|---|---|
| ingest | 240 | 0.622 |
| layout | 90 | 0.201 |
| region_crops | 240 | 0.192 |
| production_quality | 60 | 0.116 |

Stage users without the flag keep the existing inline form (scenario 12).

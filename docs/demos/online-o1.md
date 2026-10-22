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

Stage users without the flag keep the existing inline form (scenario 12).

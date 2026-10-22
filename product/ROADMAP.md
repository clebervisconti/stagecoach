# Roadmap

## 0.2 — Private beta (production)

Upload, background audio/text analysis, evidence-linked report, deletion, Cloudflare Access on LION. This is what `stagecoach.cybersphere.com.br` runs until the next release cut.

## 0.4 — Multimodal report and talk-prep (in tree)

Consent-gated vision and slides, content coach on the upload job, talk-prep generators, objectives panel, trends, goals, account export/deletion, personal-baseline badge after three same-language sessions.

## 1.0 — MVP release

Licensed-speech validation, ASR moved off the `tiny` model, alignment on the live job, owner gates closed (Resend DNS, Apple secrets, counsel review), and a recorded live UAT of upload → report → delete.

## 0.6 — Online and recorded sessions

Spec: `docs/online-sessions/SPEC.md`. Delivery mode is orthogonal to context type: stage, webinar, online talk, recorded video. Stage mode stays identical. The flag `ONLINE_MODES_ENABLED` stays off until O4.

Phases O0–O6 are in `product/BACKLOG.md`. Owner decisions OD-1 through OD-10 were approved on 22 Oct 2026 as the spec recommends. Phase O0 (foundations) is implemented on `feat/online-o0`. Do not start O1 from this cut.

MediaPipe 1.1.1 already runs pose on the live LION worker (libegl1 and libgles2). ADR-067 records the arm64 import spike.

## v2 — Practice loop

In-browser recording, live coach overlay, drill redo loops.

## v3 — Teams

Organizations, coaches, cohort analytics, benchmarks. No individual scores for HR evaluation.

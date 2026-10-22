# Stage Coach

## Problem

Presenters need actionable feedback grounded in observable evidence, not vague opinions. Existing tools often grade delivery without showing where a problem happened or how confident the system is.

## MVP user

A single private-beta presenter who uploads an English or Brazilian Portuguese talk and wants a useful audio/text coaching report.

## MVP outcome

At `stagecoach.cybersphere.com.br`, an authenticated beta user can:

1. Create a session and upload audio or video.
2. Watch background processing progress.
3. Open a report with transcript, pace, pitch variation, pauses, fillers, confidence, strengths, and prioritized practice opportunities.
4. Play the uploaded media and seek to evidence timestamps.
5. Delete the session and all local media/artifacts.

## Trust boundaries

- Cloudflare Access protects the private beta before traffic reaches LION.
- The web application is the browser-facing BFF; the API, worker, PostgreSQL, Redis, and media volume bind only to loopback or the private Compose network.
- Raw media never appears in logs.
- Reports describe observable speech signals and never infer emotion or score accent.
- Low-confidence or unavailable categories remain partial/N/A rather than fabricated.

## MVP exclusions

- Video/body/expression scoring.
- Slide/deck scoring.
- Teams, sharing, public benchmarks, and live coaching.
- Production-grade resumable 2 GB uploads; the private beta uses a bounded streaming upload.
- Paid LLM analysis unless a provider key is explicitly provisioned.

## Planned: online and recorded sessions

A presenter can upload a webinar, an online talk, or a recorded video and get delivery feedback that separates the camera tile from the screen. The draft is `docs/online-sessions/SPEC.md`. It does not score whether the subject matter is correct. Stage uploads keep today's behavior. The flag `ONLINE_MODES_ENABLED` is off until the owner closes OD-1 through OD-10 and signs off at phase O4.

## Success criteria

- Live upload → report → delete flow works in English and pt-BR.
- A failed analysis produces a visible, recoverable error.
- All externally reachable traffic uses HTTPS through Cloudflare Tunnel.
- CI, security scans, local e2e, live smoke/UAT, and production health checks pass.

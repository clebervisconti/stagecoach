# Private-beta UAT — SC-MVP-001

## 2026-10-17 access check

`https://stagecoach.cybersphere.com.br/` returned HTTP 302 to Cloudflare Access (`clebervisconti.cloudflareaccess.com`) with no session cookie. The app was not served. Steps 1–7 below were not run: nothing was listening on `127.0.0.1:3107` or `:3000` from this machine, and the production host requires an Access login.

Owner gates that stay closed until an explicit decision: ASR off `tiny`, Resend DNS and secrets, the four Apple secrets, counsel review of `docs/PRIVACY.md`, and KMS. See `deploy/README.md`.

Drive these steps against the running app (local `127.0.0.1:3107` or the Access-protected hostname). Screenshots are not sufficient.

1. Open `/sessions` in English. Empty state is visible. Create a session with a short `.wav` or `.mp4`.
2. Confirm the session row survives a browser refresh while status is `processing`.
3. Wait until status is `partial` or `ready`. Open the report.
4. Confirm overall/confidence/coverage, N/A or partial labels, transcript, and pitch graph.
5. Click an evidence timestamp. The media player seeks to that time within 0.5s.
6. Repeat 1–5 with `language=pt-BR` and `/pt-BR/sessions`.
7. Delete the session. Confirm it disappears from the list and a refresh does not restore it.
8. Without Cloudflare Access cookies, `https://stagecoach.cybersphere.com.br/` must redirect to Access, not serve the app.

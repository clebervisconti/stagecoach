# Stage Coach Backlog

## In progress

### SC-MVP-001 — Private-beta upload-to-report flow

**Priority:** P0  
**Risk:** High (public surface, user media, background processing)  
**Rollback:** Revert the release commit and restart the previous Compose image set; keep the database volume.

Acceptance criteria:

- [ ] Access is denied before Cloudflare authentication.
- [ ] The web BFF authenticates all API calls and the API verifies signed, expiring tokens.
- [ ] Supported media is streamed to a size-bounded private volume with a generated filename.
- [ ] A background job produces ingest, transcript, prosody, and partial report artifacts.
- [ ] Session list and processing state survive browser refreshes.
- [ ] Report shows confidence and N/A/partial coverage honestly.
- [ ] Evidence timestamps seek the media player within ±0.5 seconds.
- [ ] Delete removes database rows and every session file.
- [ ] English and pt-BR UI paths pass e2e UAT.
- [ ] CI, secret scan, dependency scan, and live production verification pass.

## Next

- SC-P1-002 — Add deterministic category metric functions and full scoring-config integration (#25, #30).
- SC-P1-003 — Add content LLM categories when a zero-retention provider key is provisioned (#27–#29).
- SC-P1-004 — Resumable object-storage uploads with tus and lifecycle policy.
- SC-P1-005 — Golden audio fixtures and formal validation log (#35).
- SC-P2-001 — Video, slides, and consented expression description.

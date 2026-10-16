# Privacy, AI Act notes, and incident runbook — Stage Coach

**Status:** Phase 3 engineering draft. **Not legal advice.** Counsel must review purposes, legal bases, DPIA, and AI Act classification before launch.  
**Review date:** before first production launch; re-check articles after Digital Omnibus amendments (Commission AI Act Service Desk text as of 27 July 2026) [S51].  
**Issue:** #69 · SPEC §10

## 1. Intended purpose

Stage Coach is a **self-coaching** tool for adult presenters. A user uploads or records their own talk, receives scores and evidence on observable behaviors (pace, fillers, slides, gestures, audience-facing time, expressions-as-movements), and can plan an upcoming talk. It is **not** a workplace performance-evaluation product, **not** a student-grading product, and **not** an emotion-recognition system.

Users are 18+ in MVP. Education use for minors is out of scope.

## 2. Why this is not emotion recognition

- The product **does not infer emotions** (SPEC §5, §10.4). Expression features detect readily apparent movements (a smile, a frown) for the speaker's own rehearsal. They are never labeled happy / sad / angry / confident.
- AI Act Recital 18 / Commission guidelines: mere detection of expressions, gestures, or movements is not emotion recognition **unless used to identify or infer emotions**. Counting smiles for a presenter is the guidelines' non-emotion example; concluding that someone is happy is emotion recognition [S51].
- Article 5(1)(f) prohibits emotion recognition in workplace and education institutions (medical/safety exceptions). Organization and education tenants (v3) must keep expression analysis as the individual's private self-coaching data, never shared with HR, never exportable to HR systems, never used for hiring, promotion, grading, or performance evaluation.
- Text-only content-tone analysis is not biometric (guidelines). It is still never used to label the speaker's feelings.

## 3. Annex III / high-risk analysis (engineering view)

| Annex III hook | Applies to MVP? | Notes |
|---|---|---|
| 1(c) emotion recognition | **No**, if the design rules above hold | Would become high-risk if we inferred emotions |
| 3(b) education evaluation | **No** if we do not market or configure for institutional grading | Contract terms must forbid it |
| 4(b) worker monitoring / evaluation | **No** if we do not market or configure for employee performance evaluation | v3 org dashboards are opt-in aggregates only, minimum cohort size |

**Transparency (Art. 50):** users are told an AI coach analyzes their recording. Add a clear "AI coach" disclosure in the UI even if Art. 50(1) (systems interacting directly with people) is argued not to apply to async upload.

This is an engineering assessment. Counsel must confirm classification and application dates.

## 4. Data inventory and retention (SPEC §10.1)

| Data | Class | Where | Default retention (user-configurable) |
|---|---|---|---|
| Original upload | Personal; face and voice | Object storage (SSE) | 30 days after analysis; or delete-after-analysis; or keep-until-delete |
| Playback proxy | Same | Object storage | Same as original, or until session delete |
| Audio 16 kHz / analysis proxy | Same | Object storage | Deleted when the job completes |
| Transcript | Personal / possibly confidential | Object storage + DB search | Until session delete |
| Pose/face per-second aggregates | Derived biometric-adjacent (GDPR) / biometric for AI Act Art. 3(34) | Encrypted object storage (SCENC2 envelope) | Until session delete. Raw landmarks only with `keep_detailed_tracking` (30 days) |
| Prosody tracks | Voice-derived | Object storage | Until session delete |
| Scores, evidence, insights | Personal | DB | Until session delete |
| Talk plans, decks, scripts | Personal / business confidential | DB + object storage | Until deletion |
| Account, consents, audit | Personal | DB | Account lifetime. Audit ~1 year (H), no content |
| Human validation ratings | Personal of the rated speaker | DB | Per study consent |

**GDPR:** biometric data is a special category when processed **for unique identification** (Art. 9). We do not identify people from faces or voices. Still: explicit consent (Art. 9(2)(a)) for video and expression analysis, DPIA, minimize, no face/voice templates or identifying embeddings.

**LGPD:** biometric data linked to a natural person is sensitive (Art. 5, II). Granular, prominent, purpose-specific consents in pt-BR. Rights: access, correction, deletion, portability, information about sharing, consent revocation.

**Data residency:** MVP in one region. v3: EU / BR / US per organization — **owner chooses the region**.

## 5. Consents already implemented (issues #37, #38, #50)

- Purposes: `video_analysis`, `expression_analysis`, `keep_detailed_tracking`, plus unused `research_use` and `benchmarks`.
- Append-only; current state is latest per purpose. Defaults off.
- Policy texts in `packages/consent/v1.json`; `consents.version` is SHA-256 of that file.
- Pose/face aggregates are AES-256-GCM; SCENC2 envelope with a local KEK in dev. **KMS is an owner decision** (not enabled).

## 6. Sub-processors

List what is actually wired. Paid / unchosen vendors stay flagged.

| Processor | Purpose | Status | Owner decision |
|---|---|---|---|
| Primary cloud (host + Postgres + object storage) | Hosting | Dev: local Docker / MinIO. Prod host **not chosen** | Yes — region and vendor |
| Redis | Queue / cache | Self-hosted in compose | — |
| Default LLM (LM Studio / Qwen on TIGER) | Prep and content JSON | Local OpenAI-compatible; `LOCAL_LLM_BASE_URL`; no key | Yes — 2026-10-16 |
| Optional LLM (xAI/Grok, OpenAI, Anthropic, Gemini, custom) | User-selected | Off unless the user picks them; "leaves the machine" warning | User choice; still a processor. xAI key optional |
| Email (verification, password reset, deletion confirmation) | Auth + compliance | Resend (D10, free tier) when `RESEND_API_KEY` is set; otherwise console | Yes — Resend |
| Sign in with Apple | OIDC (D9, 2026-10-15) | Disabled until `APPLE_*` secrets exist | Yes — Apple (private relay possible) |
| Error tracking | Sentry or none | `STAGECOACH_ERROR_TRACKING=none`. **No Sentry SDK** | Yes — SaaS / self-hosted / none |
| Antivirus / deck scan | Upload safety | Local sandbox | — |

Never send raw video to third-party LLMs in MVP. Configure the LLM provider for zero data retention / no training where available.

## 7. DPIA notes (engineering checklist, not a finished DPIA)

To complete with counsel:

1. Nature, scope, context, purposes of processing (this document §1–4).
2. Necessity and proportionality (self-coaching; no identification; consents off by default).
3. Risks to speakers (biometric-adjacent video derivatives; confidential talk content; workplace misuse).
4. Measures: granular consent, encryption, retention sweeper, no emotion labels, no HR export, ownership checks, audit without content.
5. Residual risks and whether prior consultation is needed.

Open legal questions for counsel are in §10.

## 8. Account rights (issue #67)

SPEC §7.5 / §10.3:

- **Export:** `POST /me/export` zip of JSON (sessions, scores, evidence, transcripts, plans, consents) + 24 h HMAC media links (`purpose=export`).
- **Delete account:** `DELETE /me` starts a 7-day grace (account stays usable; cancel with `DELETE /me/deletion`). After the due date, `POST /admin/account-deletions/finalize` hard-deletes objects and the user, sends a confirmation email via Resend or the console stand-in, and writes a content-free audit.
- **Delete session:** already implemented (hard delete, content-free audit).

## 9. Incident / breach-notification runbook

Engineering procedure. Legal timelines are from the statutes; counsel confirms applicability.

### 9.1 Detect and contain

1. Page the on-call. Do not write media, transcripts, or emails into tickets or chat.
2. Revoke leaked credentials; rotate `AUTH_SECRET`, object-storage keys, LLM keys, `STAGECOACH_ARTIFACT_KEY` / KEK.
3. Isolate the affected service. Preserve logs (hashes and counts only).

### 9.2 Classify

- Personal data breach? (GDPR Art. 4(12))
- Sensitive / biometric-adjacent data involved?
- Confidential talk content involved?

### 9.3 Notify

| Regime | Clock | Who |
|---|---|---|
| GDPR | **72 hours** after becoming aware, unless unlikely to result in a risk | Supervisory authority; data subjects if high risk |
| LGPD | Notify **ANPD** and affected data subjects (procedure as required by ANPD) | ANPD + subjects |

Draft the notice: nature, categories and approximate numbers, likely consequences, measures taken, contact. No extra personal data in the notice beyond what is required.

### 9.4 After-action

Write an audit row (`audit_log`) with object counts and action name only. Update this runbook if the gap was procedural. Review date: after the incident and at the next launch review.

## 10. Open legal questions for counsel

1. Confirm AI Act classification (not emotion recognition; not Annex III 3(b)/4(b) if contracts forbid institutional grading and employee evaluation).
2. Confirm GDPR Art. 9 analysis for pose/face aggregates when we do **not** uniquely identify.
3. Confirm LGPD legal bases and ANPD notification triggers for a rehearsal-coaching SaaS.
4. DPIA: is prior consultation required?
5. Age gate 18+ and any education-tenant restrictions.
6. Sub-processor SCCs / international transfers once a prod region is chosen.
7. Whether Art. 50 disclosures need specific wording beyond "AI coach".
8. Account-deletion confirmation email is implemented; delivery uses Resend or the console stand-in. Counsel still reviews wording.
9. Apple ID token / private-relay email processing (D9, #68). Google / Microsoft are not used.
10. Digital Omnibus / application-date recheck before launch [S51].

## 11. Owner decisions this document does not take

- **D9** decided 2026-10-15: email+password and Sign in with Apple only (#68). Google / Microsoft not used.
- **D10** decided 2026-10-16: Resend free tier (#67). Cyberlabs still verifies SPF/DKIM.
- Sentry SaaS vs self-hosted vs none
- Production cloud region / vendor
- KMS vs local KEK for SCENC2
- Paid LLM spend beyond the local Qwen default

`docs/DECISIONS.md` is not edited on this branch.

## Contact

Privacy inquiries: TBD (owner sets a contact before launch).

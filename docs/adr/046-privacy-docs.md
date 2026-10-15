# ADR-046: PRIVACY.md AI Act notes, DPIA checklist, sub-processors, incident runbook

**Date:** 2026-10-15  
**Status:** Accepted  
**Phase:** 3  
**Issue:** #69

## Context

SPEC §10 requires an AI Act assessment, DPIA notes, a sub-processor list, retention table, and a breach-notification procedure (GDPR 72 h, LGPD/ANPD) in `docs/PRIVACY.md`. The file was a Phase 0 stub. The section is engineering requirements, not legal advice.

## Decision

- Replace the stub with an engineering assessment: intended purpose, why the system is not emotion recognition, Annex III table, Art. 50 disclosure, retention table, current consents, sub-processors, DPIA checklist, incident runbook, and open questions for counsel.
- Do **not** choose D9 (OAuth), D10 (email), Sentry, cloud region, or KMS. Those stay listed as owner decisions.
- Do **not** implement #67 export/deletion email in this PR.
- `docs/DECISIONS.md` is not edited on this branch.

## Alternatives considered

1. **Treat the assessment as a finished legal DPIA**  
   - ❌ Spec: not legal advice; counsel reviews before launch

2. **Fill sub-processors with guessed vendors**  
   - ❌ Would silently decide paid services

## Consequences

- Launch is still blocked on counsel review and the owner decisions in §11 of PRIVACY.md.

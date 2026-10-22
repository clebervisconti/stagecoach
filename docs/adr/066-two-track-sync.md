# ADR-066: Two-track sync by audio cross-correlation

**Date:** 2026-10-22  
**Status:** Accepted  
**Phase:** O0 (decision only; implementation is O5)

## Decision

Sync uses an in-repo MFCC + cross-correlation offset (BBC R&D method, S75, Apache-2.0). Confidence and fallbacks are recorded. No new paid service.

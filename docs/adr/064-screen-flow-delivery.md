# ADR-064: Screen-flow metrics measure delivery, never content

**Date:** 2026-10-22  
**Status:** Accepted  
**Phase:** O0 (decision only; implementation is O3)

## Decision

Screen-flow scores activity, transitions, alignment, and dead air. They never judge whether on-screen claims are correct. A content-judgment verifier drops that language. A templated fallback is used when the LLM is down.

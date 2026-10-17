# Web app status

Phases 0–3 of the report and prep UI are in the tree.

## In place

- Locale routing for English and pt-BR
- Sign-in form (email + password, Sign in with Apple when the four Apple secrets exist)
- Sessions, report (categories, transcript, voice, timeline, body, slides, objectives), trends, prep editor, settings
- BFF proxy at `app/api/stagecoach/[...path]`

## Still open

- Live UAT of upload → report → delete on the production host (`tests/uat/mvp-flow.md`)
- Apple sign-in stays off until the owner sets the Apple secrets
- In-browser recording is Phase 4 and is not started

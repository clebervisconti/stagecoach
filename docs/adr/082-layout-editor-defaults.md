# ADR-082: Layout editor interaction defaults

**Date:** 2026-10-23
**Status:** Accepted
**Phase:** O2

## Context

O2-DESIGN §16 left nudge size, delete confirmation, merge, the deep link, the OTHER mark, the 390 role control, and discard behaviour open. The build needs one choice so the editor matches the mocks Jonny reviews.

## Decision

- Nudge is 1 pixel of the preview frame. Shift is 10 pixels. The value is converted to the 0–1 coordinates the API stores.
- Deleting the last camera box asks for confirmation, then allows it. Presence is not measured without a camera.
- Merge asks only when the two segments' boxes differ. The choices are keep the earlier boxes, keep the later boxes, or cancel.
- `?edit=1` opens the editor on `/sessions/{id}/layout`. The report action adds `f6=1`, which creates the re-analyse job once, then drops the flag from the URL.
- OTHER uses the same hatch as IGNORE and a different label.
- Below the `lg` breakpoint the role control lives only in the bottom sheet. The desktop chrome keeps it above the preview.
- There is no autosave. Discard reloads the last layout fetched from the server.
- Assigning camera or screen in a segment demotes the previous holder of that role to ignore, because the API allows one of each.
- The OD-3 "when to ask me" settings row stays out of this UI.

## Alternatives considered

- Nudge by 1% of the frame (SPEC F2) — rejected. The design brief and the confirmed default are pixels.
- Soft-block the last camera until another exists — rejected. The confirm dialog is the default.
- Autosave on every arrow key — rejected. Discard would not have a server copy to restore, and the rate limit is for intentional saves.

## Consequences

- Keyboard and the 390 pad move the same distance.
- A version conflict shows the couldn't-save alert and leaves the local boxes in place until discard or a retry that succeeds.

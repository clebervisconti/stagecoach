# O2 layout editor

Adjust detected camera and screen boxes on `/sessions/{id}/layout`, then analyse again without a new upload.

1. Open a session in layout review and choose **Adjust**.
2. Drag, resize, or re-role a box. Arrow keys move 1 px; Shift moves 10 px.
3. Split or merge segments on the strip. Trim the analysis window with the two handles (minimum 60 seconds).
4. **Analyse with this layout** saves and starts analysis.
5. From a finished report, **Change layout & re-analyse** opens the same editor. The transcript is reused when the window is unchanged.

`?edit=1` deep-links into the editor. Discard reloads the server layout. A version conflict keeps the local edit and asks you to try again.

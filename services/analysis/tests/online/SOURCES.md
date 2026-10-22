# Online fixture sources

Synthetic fixtures (`composite_pip_tr`, `screen_only`, `camera_only`) are generated
by `generate_online_fixtures.py` with ffmpeg lavfi. They contain no personal data
and no recordings. Generated video files are git-ignored.

`composite_pip_tr` overlays `fixtures/assets/synthetic_face.png` in the camera
tile. That PNG is a generated drawing (not a photograph, not a real person),
released as CC0. See `fixtures/README.md`.

Optional real-face integration (`@pytest.mark.real_faces`) may download CC0 or
CC-BY talking-head stills into `tests/online/cache/` at test time. That cache is
git-ignored. Record licence and attribution here when a clip is added.

# Online fixture sources

Synthetic fixtures (`composite_pip_tr`, `screen_only`, `camera_only`) are generated
by `generate_online_fixtures.py` with ffmpeg lavfi. They contain no personal data
and no recordings. Generated video files are git-ignored.

Optional real-face integration (`@pytest.mark.real_faces`) may download CC0 or
CC-BY talking-head stills into `tests/online/cache/` at test time. That cache is
git-ignored. Record licence and attribution here when a clip is added.

No CC0 frames are committed in this repository.

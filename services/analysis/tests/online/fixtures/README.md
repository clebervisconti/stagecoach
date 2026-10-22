# Online fixture assets

Generated videos are git-ignored. Manifests and the synthetic face stay in git.

## `assets/synthetic_face.png`

- **What:** A 256×256 generated frontal face drawn with OpenCV ellipses (skin fill, eyes, brows, nose, mouth). It is not a photograph and not a real person.
- **Why:** YuNet needs a face in the `composite_pip_tr` camera tile. A solid tan rectangle classified as `screen_full`.
- **Licence:** Original work in this repository, dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
- **Source:** Drawn by `tests/online/generate_online_fixtures.py` / the generator used to create this PNG. No third-party image, no identifiable person.
- **Use:** Stretched to the PiP tile so YuNet detects it and `grow_tile` can recover the tile (camera and screen IoU ≥ 0.85).

## Generating videos

```bash
# Manifest defaults (2 s, 1920×1080)
python tests/online/generate_online_fixtures.py --out /tmp/online-fixtures

# Real-stack timing clips
python tests/online/generate_online_fixtures.py --out /tmp/online-120 \
  --only composite_pip_tr --duration 120 --resolution 1920x1080
python tests/online/generate_online_fixtures.py --out /tmp/online-60m \
  --only composite_pip_tr --duration 3600 --resolution 1920x1080
```

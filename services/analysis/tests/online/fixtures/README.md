# Online fixture assets

Generated videos are git-ignored. Manifests, the synthetic face, and the
synthetic speech clip stay in git.

## `assets/synthetic_face.png`

- **What:** A 256×256 generated frontal face drawn with OpenCV ellipses (skin fill, eyes, brows, nose, mouth). It is not a photograph and not a real person.
- **Why:** YuNet needs a face in the `composite_pip_tr` camera tile. A solid tan rectangle classified as `screen_full`.
- **Licence:** Original work in this repository, dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
- **Source:** Drawn by `tests/online/generate_online_fixtures.py` / the generator used to create this PNG. No third-party image, no identifiable person.
- **Use:** Stretched to the PiP tile so YuNet detects it and `grow_tile` can recover the tile (camera and screen IoU ≥ 0.85).

## `assets/synthetic_speech.wav`

- **What:** About 12 s of English webinar text spoken by **espeak-ng** `en-us` at 145 wpm, resampled to 16 kHz mono PCM. The generator loops this clip to the video duration.
- **Why:** The previous fixture used `anullsrc` silence. Cyberlabs' 120 s run saw 0 ASR words and 0 VAD segments, so WhisperX alignment never ran.
- **Text (original, not a quotation):** "Welcome to this webinar. Today we will cover three points. First, the plan. Second, the evidence. Third, the next steps. Thank you."
- **Licence:** The waveform is synthetic TTS. [espeak-ng](https://github.com/espeak-ng/espeak-ng) is GPL-3.0. The spoken words are original to this repository. Not a recording of a person and not a recording of Cleber. No third-party voice corpus.
- **Regenerate:** `espeak-ng -v en-us -s 145 -w /tmp/raw.wav "$TEXT"` then `ffmpeg -i /tmp/raw.wav -ar 16000 -ac 1` into this path. `generate_online_fixtures.py` will recreate the file if it is missing and espeak-ng is installed.

Screen-flow tests build gray frames in `tests/online/screen_frames.py`. The manifest `screen_flow_manifest.json` records the acceptance thresholds. Those tests do not commit a video or a recording of a person.

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

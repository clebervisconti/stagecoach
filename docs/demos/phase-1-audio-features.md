# Phase 1: Audio-features stage

**Date:** 2026-10-10  
**Issue:** #24  
**Branch:** `cursor/p1-audio-features-24`

## Summary

The `audio_features` stage reads un-normalized `audio16k.wav` (and optional `transcript.json`) and writes the four artifacts required by SPEC §6.4.

## Artifacts

| File | Contents |
|---|---|
| `prosody.parquet` | 10 ms `time_s`, `f0_hz`, `f0_st`, `voiced`, `intensity_db` |
| `pauses.json` | Duration-binned pauses with `boundary` / `mid_sentence` / `unknown` |
| `syllables.json` | de Jong & Wempe nuclei, phonation time, articulation rate |
| `audio_metrics.json` | PVQ series, SNR, music/noise flags, confidence caps, source keys |

## Demo

```bash
cd services/analysis
pip install -r requirements.txt
pytest tests/test_audio_features.py -v
```

Expected: sine 220 Hz → median F0 ≈ 220 Hz and low PVQ; 150–350 Hz chirp → rising F0 and higher PVQ; white noise → `noise_flag` and SNR confidence cap.

## DAG

`ingest → asr → audio_features` (cpu queue). Parselmouth stays in the worker (ADR-013).

## Acceptance

- [x] Four artifacts written
- [x] Octave-jump removal; speaker-adaptive pitch floor/ceiling
- [x] Pause classification boundary vs mid-sentence
- [x] SNR and music/noise flags feed confidence
- [x] ADR-013 records GPL server-only use
- [x] Unit tests: sine sweeps → F0/PVQ

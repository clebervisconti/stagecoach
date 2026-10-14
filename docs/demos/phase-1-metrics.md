# Phase 1: Metric functions

**Date:** 2026-10-14  
**Issue:** #25  
**Branch:** `cursor/p1-metric-functions-25-4ced`

## Summary

Pure functions in `services/analysis/metrics/` implement every sub-metric in `pace_pausing`, `vocal_variety`, `fluency`, and `time_management`. Names and units match `packages/scoring-config/v1.0.0/scoring.yaml`. After `audio_features` the worker writes `metrics.json`.

## Demo

```bash
cd services/analysis
python -m pytest tests/test_metrics.py -v
```

Expected: WPM of 130 words / 60 s = 130; constant F0 → PVQ 0; 5 um/min at the [S12] no-penalty anchor; 12 um/min at the harmful anchor; SNR 10 dB → confidence 0.3, 20 dB → 1.0.

## Persistence

`ingest → asr → audio_features` (cpu queue) now also writes `metrics.json` with `scoring_config_version`, per-metric `{id,value,unit,basis,source,confidence}`, and the combined filler-rate benchmark note.

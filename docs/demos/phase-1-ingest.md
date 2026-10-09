# Phase 1 Demo: Ingest Stage

**Date**: 2026-10-09  
**PR**: [#TBD](https://github.com/clebervisconti/stagecoach/pull/TBD)  
**Issues**: Closes #17

## Summary

Implemented the ingest stage (issue #17) which validates, transcodes, and prepares media files for analysis.

## Acceptance Criteria Met

- [x] ffprobe validation with clear rejection messages
- [x] Size limits (2 GB) and duration limits (90 minutes) enforced
- [x] Three transcodes produced:
  - `audio16k.wav` (16kHz mono with loudness normalization for ASR)
  - `analysis.mp4` (≤720p, 15fps, H.264 for CV processing)
  - `playback.mp4` (H.264+AAC with faststart flag)
- [x] Sprite thumbnails generated every 5 seconds
- [x] Audio-only detection (no video stream)
- [x] Screen-recording detection (person presence heuristic)
- [x] Modality flags set for downstream stages
- [x] Sandboxed execution (subprocess parameterization, no shell injection)
- [x] Golden test on synthetic fixture

## Implementation

### Pipeline Structure

```
services/analysis/
├── pipeline/
│   ├── __init__.py
│   └── stages/
│       ├── __init__.py
│       └── ingest.py          # Ingest stage implementation
├── worker.py                   # Celery tasks
├── tests/
│   ├── test_ingest.py         # Unit tests
│   ├── generate_fixture.py    # Synthetic fixture generator
│   └── fixtures/
│       ├── README.md          # Fixture documentation
│       └── smoke_test.mp3     # Generated test audio
└── Dockerfile                  # Worker container with ffmpeg
```

### Key Components

1. **Media Validation** (`validate_media`)
   - ffprobe-based container and codec validation
   - Size and duration limit enforcement
   - Clear error messages for unsupported formats

2. **Transcoding** 
   - `transcode_audio`: 16kHz mono WAV with EBU R128 loudness normalization
   - `transcode_analysis_video`: ≤720p, 15fps H.264 for efficient CV
   - `transcode_playback_video`: Web-optimized with faststart flag

3. **Sprite Generation** (`generate_sprites`)
   - One thumbnail every 5 seconds
   - 160px width for timeline hover previews

4. **Modality Detection** (`detect_modality`)
   - Audio-only flag (no video stream)
   - Screen recording vs person video (frame variance heuristic)
   - Person detection confidence score

5. **Celery Task** (`tasks.ingest`)
   - Idempotent execution
   - 3 retries with exponential backoff (4s, 16s, 64s)
   - Structured output (MediaInfo, ModalityFlags, artifacts, SHA256)

### Testing

```bash
# Unit tests
cd services/analysis
pytest tests/test_ingest.py -v

# Docker smoke test
docker compose --profile workers up -d
docker compose exec worker python tests/generate_fixture.py
docker compose exec worker pytest tests/test_ingest.py
```

### Test Fixture

Per acceptance criteria, a synthetic fixture is used:

- **File**: `smoke_test.mp3`
- **Origin**: Generated with ffmpeg sine waves (440 Hz + 880 Hz)
- **Duration**: 3 seconds
- **Purpose**: Validate transcoding and artifact generation

No real recordings are committed to the repository.

## CI Results

### Worker Tests

```
tests/test_ingest.py::test_run_ffprobe PASSED
tests/test_ingest.py::test_validate_audio_file PASSED
tests/test_ingest.py::test_validate_video_file PASSED
tests/test_ingest.py::test_transcode_audio PASSED
tests/test_ingest.py::test_detect_modality_audio_only PASSED
tests/test_ingest.py::test_compute_file_hash PASSED
tests/test_ingest.py::test_ingest_audio_only PASSED
tests/test_ingest.py::test_ingest_video PASSED
tests/test_ingest.py::test_generate_sprites PASSED
```

### Smoke Test

```
=== Testing Ingest Stage ===
Health check: {'status': 'healthy', 'worker': 'celery'}
Ingest output: {
  'media_info': {
    'container': 'mp3',
    'duration': 3.0,
    'has_video': False,
    'has_audio': True,
    ...
  },
  'modality': {
    'is_audio_only': True,
    'is_screen_recording': False,
    'person_detection_confidence': 0.0
  },
  'artifacts': {
    'audio16k': '/tmp/.../audio16k.wav'
  },
  'sha256': '...'
}
✅ Ingest pipeline test passed
```

## Architecture Decisions

### ADR-011: Ingest Stage Implementation

**Date**: 2026-10-09  
**Status**: Accepted  
**Phase**: 1

#### Context

The ingest stage is the pipeline's entry point and must:
- Validate media files safely (no arbitrary code execution)
- Enforce size and duration limits
- Produce optimized transcodes for downstream stages
- Detect modality for stage applicability (N/A rules)

#### Decision

**Validation**: ffprobe with subprocess parameterization (no shell strings)
**Transcoding**: ffmpeg with three outputs:
- ASR audio: 16kHz mono WAV with loudness normalization (EBU R128)
- Analysis video: ≤720p, 15fps H.264, no audio (efficient for CV)
- Playback video: H.264+AAC, faststart flag (web-optimized)

**Modality detection**:
- Audio-only: Check for video stream presence
- Screen recording: Person presence heuristic (frame variance)

**Limits** (heuristic, from SPEC §6.2):
- Max file size: 2 GB
- Max duration: 90 minutes

**Safety**:
- Parameterized subprocess calls (no shell injection risk)
- Timeout on all ffmpeg/ffprobe calls
- Temp directory isolation

#### Alternatives Considered

1. **MediaInfo library instead of ffprobe**
   - ❌ Less detailed codec information
   - ❌ ffmpeg is already required for transcoding

2. **Cloud transcoding service**
   - ❌ Cost per minute
   - ❌ Privacy: media sent to third party
   - ❌ Vendor lock-in

3. **Single transcode for both analysis and playback**
   - ❌ 15fps is too choppy for user playback
   - ❌ Analysis doesn't need audio track (wastes space)

#### Consequences

- ✅ Parameterized subprocess calls prevent shell injection
- ✅ Three transcodes optimize for different use cases
- ✅ Loudness normalization only on ASR copy preserves dynamics for prosody
- ✅ Clear validation errors guide users
- ⚠️ ffmpeg transcoding is CPU-intensive (mitigated: runs async in worker)
- ⚠️ Person detection is heuristic (acceptable for modality flag; improved in Phase 2 with MediaPipe)

## Local Development

```bash
# Start worker locally
docker compose --profile workers up -d worker

# Tail worker logs
docker compose logs -f worker

# Test health
docker compose exec worker celery -A worker.app inspect ping

# Run a test ingest
docker compose exec worker python << 'EOF'
from worker import app
result = app.send_task("tasks.ingest", args=["tests/fixtures/smoke_test.mp3", "/tmp", "test"])
print(result.get(timeout=30))
EOF
```

## Next Steps

- [x] Issue #17: Ingest stage
- [ ] Issue #20: ASR stage (faster-whisper)
- [ ] Issue #18: Celery DAG orchestration
- [ ] Issue #19: SSE progress streaming

---

**Artifacts**: 
- Ingest stage: `pipeline/stages/ingest.py`
- Tests: `tests/test_ingest.py`
- Fixture: `tests/fixtures/smoke_test.mp3` (generated)
- Celery task: `worker.py` (`tasks.ingest`)

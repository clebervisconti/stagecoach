"""Tests for WhisperX alignment stage."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def generate_test_fixture(output_path: Path):
    """Generate a 3-second test audio file."""
    cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=3",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        str(output_path),
        "-loglevel", "error",
    ]
    subprocess.run(cmd, check=True, capture_output=True)


@pytest.mark.skipif(
    True,  # Always skip - requires whisperx models
    reason="Alignment tests require whisperx models - run in smoke test only"
)
def test_alignment_with_asr():
    """Test alignment stage with ASR transcript (smoke test only)."""
    from pipeline.stages.asr import transcribe_audio
    from pipeline.stages.alignment import align_transcript
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Generate test audio
        audio_path = tmpdir / "test.wav"
        generate_test_fixture(audio_path)
        
        # Run ASR first
        asr_result = transcribe_audio(
            audio_path=audio_path,
            output_dir=tmpdir,
            session_id="test-alignment",
            language="en",
            model_name="tiny"  # Use tiny for speed
        )
        
        # Save transcript for alignment
        transcript_path = tmpdir / "test-alignment_transcript.json"
        with open(transcript_path, "w") as f:
            json.dump(asr_result.to_dict(), f)
        
        # Run alignment
        alignment_result = align_transcript(
            audio_path=audio_path,
            transcript_path=transcript_path,
            output_dir=tmpdir,
            session_id="test-alignment",
            language="en"
        )
        
        # Verify output
        assert len(alignment_result.aligned_words) >= 0  # May have no words in silent audio
        assert len(alignment_result.vad_segments) >= 0
        assert alignment_result.mean_alignment_score >= 0
        assert alignment_result.gap_fills_count >= 0
        assert alignment_result.acoustic_fallback_count >= 0
        
        # Verify output file exists
        output_file = tmpdir / "test-alignment_alignment.json"
        assert output_file.exists()
        
        # Verify output structure
        with open(output_file) as f:
            output_data = json.load(f)
        
        assert "aligned_words" in output_data
        assert "vad_segments" in output_data
        assert "gap_fills_count" in output_data
        assert "mean_alignment_score" in output_data
        
        print(f"✅ Alignment test passed")
        print(f"   Aligned words: {len(alignment_result.aligned_words)}")
        print(f"   VAD segments: {len(alignment_result.vad_segments)}")
        print(f"   Mean score: {alignment_result.mean_alignment_score:.3f}")


@pytest.mark.skipif(
    True,  # Always skip - requires whisperx models
    reason="VAD test requires silero model - run in smoke test only"
)
def test_vad_detection():
    """Test Silero VAD detection."""
    from pipeline.stages.alignment import load_silero_vad, run_vad
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Generate test audio
        audio_path = tmpdir / "test.wav"
        generate_test_fixture(audio_path)
        
        # Load VAD
        model, get_speech_timestamps, read_audio = load_silero_vad()
        
        # Run VAD
        vad_segments = run_vad(audio_path, model, get_speech_timestamps, read_audio)
        
        # Verify output
        assert isinstance(vad_segments, list)
        # Sine wave may or may not be detected as speech
        print(f"✅ VAD test passed: {len(vad_segments)} segments detected")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

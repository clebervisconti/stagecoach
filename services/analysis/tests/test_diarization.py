"""Tests for speaker diarization stage."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

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


def test_diarization_fallback():
    """Test diarization fallback mode (no HF_TOKEN)."""
    from pipeline.stages.diarization import diarize_audio, DIARIZATION_ENABLED
    
    # Ensure HF_TOKEN is not set for this test
    old_token = os.environ.pop("HF_TOKEN", None)
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Generate test audio
            audio_path = tmpdir / "test.wav"
            generate_test_fixture(audio_path)
            
            # Run diarization (should use fallback)
            result = diarize_audio(
                audio_path=audio_path,
                output_dir=tmpdir,
                session_id="test-diarization-fallback"
            )
            
            # Verify fallback output
            assert result.enabled is False
            assert result.fallback_mode is True
            assert len(result.segments) == 0
            assert result.primary_speaker is None
            assert result.num_speakers == 0
            
            # Verify output file exists
            output_file = tmpdir / "test-diarization-fallback_diarization.json"
            assert output_file.exists()
            
            # Verify output structure
            with open(output_file) as f:
                output_data = json.load(f)
            
            assert "enabled" in output_data
            assert "segments" in output_data
            assert "fallback_mode" in output_data
            assert output_data["fallback_mode"] is True
            
            print(f"✅ Diarization fallback test passed")
            
    finally:
        # Restore HF_TOKEN if it was set
        if old_token:
            os.environ["HF_TOKEN"] = old_token


@pytest.mark.skipif(
    not os.environ.get("HF_TOKEN"),
    reason="HF_TOKEN not set, skipping pyannote diarization test"
)
def test_diarization_with_token():
    """Test diarization with HF_TOKEN (requires gated model access)."""
    from pipeline.stages.diarization import diarize_audio, DIARIZATION_ENABLED
    
    if not DIARIZATION_ENABLED:
        pytest.skip("Diarization not enabled")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Generate test audio
        audio_path = tmpdir / "test.wav"
        generate_test_fixture(audio_path)
        
        # Run diarization
        result = diarize_audio(
            audio_path=audio_path,
            output_dir=tmpdir,
            session_id="test-diarization-enabled"
        )
        
        # Verify output
        assert result.enabled is True
        assert result.fallback_mode is False
        # Segments may be empty for sine wave
        assert isinstance(result.segments, list)
        assert result.num_speakers >= 0
        
        # Verify output file exists
        output_file = tmpdir / "test-diarization-enabled_diarization.json"
        assert output_file.exists()
        
        print(f"✅ Diarization with token test passed")
        print(f"   Segments: {len(result.segments)}")
        print(f"   Speakers: {result.num_speakers}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

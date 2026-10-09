#!/usr/bin/env python3
"""Generate a synthetic test audio fixture using TTS or a tone.

Per issue #17: Create a tiny synthetic fixture with documented origin
for smoke testing the ingest → ASR pipeline.

This generates a simple tone-based test file with synthesized "speech-like" audio.
Source: Generated programmatically with ffmpeg sine waves.
"""

import subprocess
import sys
from pathlib import Path


def generate_test_fixture(output_path: Path, duration: float = 3.0):
    """Generate a test audio fixture with a tone pattern.
    
    Creates a simple audio file with varying tones that can pass through
    the pipeline. Not real speech, but sufficient for smoke testing.
    
    Args:
        output_path: Where to save the fixture
        duration: Duration in seconds
    """
    # Generate a complex tone (440 Hz + 880 Hz to simulate formants)
    cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration}",
        "-f", "lavfi",
        "-i", f"sine=frequency=880:duration={duration}",
        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first[a]",
        "-map", "[a]",
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        "-y",
        str(output_path),
    ]
    
    print(f"Generating test fixture: {output_path}")
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"✓ Generated {output_path.stat().st_size} bytes")
    

if __name__ == "__main__":
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)
    
    fixture_path = fixtures_dir / "smoke_test.mp3"
    generate_test_fixture(fixture_path)
    
    print(f"\nFixture ready at: {fixture_path}")
    print("Origin: Programmatically generated with ffmpeg sine waves")

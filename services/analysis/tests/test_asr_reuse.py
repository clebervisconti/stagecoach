"""ASR is reused when the analysis window is unchanged, and trimmed otherwise."""

import json
from pathlib import Path

from pipeline.asr_reuse import (
    asr_input_sha,
    ffmpeg_cut_command,
    find_reusable_transcript,
    resolve_asr,
    shift_transcript_times,
    windows_unchanged,
)


def _transcript(word: str, start: float) -> dict:
    return {
        "language": "en",
        "word_count": 1,
        "mean_word_probability": 0.9,
        "segments": [
            {
                "id": 0,
                "text": word,
                "start": start,
                "end": start + 0.4,
                "words": [{"word": word, "start": start, "end": start + 0.4, "probability": 0.9}],
            }
        ],
    }


def test_shift_puts_words_back_on_source_time():
    shifted = shift_transcript_times(_transcript("hello", 1.2), 252.0)
    word = shifted["segments"][0]["words"][0]
    assert word["start"] == 253.2
    assert word["end"] == 253.6
    assert shifted["window_offset_s"] == 252.0


def test_windows_unchanged_treats_a_missing_window_as_the_full_recording():
    assert windows_unchanged(None, None)
    assert not windows_unchanged(None, {"start_s": 0, "end_s": 90})
    assert windows_unchanged({"start_s": 12, "end_s": 80}, {"start_s": 12.02, "end_s": 80.01})


def test_cut_command_is_parameterised():
    command = ffmpeg_cut_command(Path("/in/audio.wav"), Path("/out/audio_window.wav"), 12, 80)
    assert command[0] == "ffmpeg"
    assert "-ss" in command and command[command.index("-ss") + 1] == "12.000"
    assert command[command.index("-to") + 1] == "80.000"
    assert all(";" not in part and "|" not in part for part in command)


def test_reuse_skips_transcription_when_the_window_matches(tmp_path: Path):
    previous = tmp_path / "job-a"
    previous.mkdir()
    window = None
    sha = asr_input_sha("en", window)
    (previous / "transcript.json").write_text(json.dumps(_transcript("kept", 4.0)))
    (previous / "asr_input.json").write_text(json.dumps({"sha": sha, "window": window}))
    fresh = tmp_path / "job-b"
    calls = {"n": 0}

    def transcribe(**_kwargs):
        calls["n"] += 1
        raise AssertionError("ASR should be reused")

    resolution = resolve_asr(
        session_dir=tmp_path,
        job_dir=fresh,
        language="en",
        asr_language="en",
        window=window,
        audio_path=tmp_path / "audio.wav",
        session_id="sess",
        allow_reuse=True,
        transcribe=transcribe,
    )
    assert resolution.reused is True
    assert calls["n"] == 0
    saved = json.loads((fresh / "transcript.json").read_text())
    assert saved["segments"][0]["words"][0]["word"] == "kept"
    assert find_reusable_transcript(tmp_path, fresh, sha, window) == previous / "transcript.json"


def test_changed_window_transcribes_the_cut_and_shifts(tmp_path: Path):
    previous = tmp_path / "job-a"
    previous.mkdir()
    full = None
    (previous / "transcript.json").write_text(json.dumps(_transcript("old", 1)))
    (previous / "asr_input.json").write_text(json.dumps({"sha": asr_input_sha("en", full), "window": full}))
    fresh = tmp_path / "job-b"
    window = {"start_s": 252.0, "end_s": 400.0}
    calls = {"cut": 0, "asr": 0}

    def cut(src, dest, start_s, end_s):
        calls["cut"] += 1
        assert start_s == 252
        assert end_s == 400
        dest.write_bytes(b"wav")
        return dest

    def transcribe(**kwargs):
        calls["asr"] += 1
        assert kwargs["audio_path"].name == "audio_window.wav"
        (kwargs["output_dir"] / "transcript.json").write_text(json.dumps(_transcript("now", 1.0)))

    resolution = resolve_asr(
        session_dir=tmp_path,
        job_dir=fresh,
        language="en",
        asr_language="en",
        window=window,
        audio_path=tmp_path / "audio.wav",
        session_id="sess",
        allow_reuse=True,
        transcribe=transcribe,
        cut_audio=cut,
    )
    assert resolution.reused is False
    assert calls == {"cut": 1, "asr": 1}
    word = json.loads((fresh / "transcript.json").read_text())["segments"][0]["words"][0]
    assert word["word"] == "now"
    assert word["start"] == 253.0
    assert "old" not in (fresh / "transcript.json").read_text()


def test_fallback_reuses_a_job_that_never_wrote_a_marker(tmp_path: Path):
    previous = tmp_path / "job-a"
    previous.mkdir()
    (previous / "transcript.json").write_text(json.dumps(_transcript("plain", 2)))
    (previous / "layout.json").write_text(json.dumps({"analysis_window": None}))
    found = find_reusable_transcript(tmp_path, tmp_path / "job-b", asr_input_sha("en", None), None)
    assert found == previous / "transcript.json"
    assert find_reusable_transcript(tmp_path, tmp_path / "job-b", asr_input_sha("en", {"start_s": 0, "end_s": 90}), {"start_s": 0, "end_s": 90}) is None

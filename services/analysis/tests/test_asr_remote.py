"""ASR stays on this machine unless ASR_BACKEND=http is set explicitly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.stages.asr import transcribe_audio
from pipeline.stages.asr_remote import (
    AsrConfigError,
    AsrHttpError,
    parse_verbose_transcript,
    resolve_asr_backend,
    transcribe_http,
    transcription_endpoint,
)


def test_backend_defaults_to_local_and_ignores_a_url(monkeypatch):
    monkeypatch.delenv("ASR_BACKEND", raising=False)
    monkeypatch.setenv("ASR_HTTP_URL", "http://asr.test/v1")
    assert resolve_asr_backend() == "local"
    monkeypatch.setenv("ASR_BACKEND", "tiger")
    assert resolve_asr_backend() == "local"
    monkeypatch.setenv("ASR_BACKEND", "HTTP")
    assert resolve_asr_backend() == "http"


def test_endpoint_rejects_secrets_and_appends_the_openai_path():
    assert transcription_endpoint("http://asr.test/v1") == "http://asr.test/v1/audio/transcriptions"
    assert transcription_endpoint("https://asr.test") == "https://asr.test/v1/audio/transcriptions"
    assert transcription_endpoint("http://asr.test/custom") == "http://asr.test/custom"
    with pytest.raises(AsrConfigError) as userinfo:
        transcription_endpoint("http://user:secret@asr.test/v1")
    assert "secret" not in str(userinfo.value)
    with pytest.raises(AsrConfigError) as query:
        transcription_endpoint("http://asr.test/v1?token=secret")
    assert "secret" not in str(query.value)
    with pytest.raises(AsrConfigError):
        transcription_endpoint("file:///tmp/audio.wav")


def test_verbose_json_maps_words_and_does_not_zero_a_missing_probability():
    output = parse_verbose_transcript(
        {
            "language": "portuguese",
            "duration": 1.2,
            "segments": [
                {
                    "id": 0,
                    "start": 0.1,
                    "end": 0.8,
                    "text": "olá",
                    "words": [{"word": "olá", "start": 0.1, "end": 0.8}],
                }
            ],
        },
        model="small",
    )
    data = output.to_dict()
    assert data["language"] == "pt"
    assert data["backend"] == "http"
    assert data["model"] == "small"
    assert data["segments"][0]["words"][0]["probability"] == 1.0
    assert data["word_count"] == 1


def test_http_without_a_url_does_not_call_the_network(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASR_BACKEND", "http")
    monkeypatch.delenv("ASR_HTTP_URL", raising=False)
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF")

    def explode(*_args, **_kwargs):
        raise AssertionError("network")

    with pytest.raises(AsrConfigError, match="unset"):
        transcribe_http(audio, tmp_path, "sess", post=explode)
    assert not (tmp_path / "transcript.json").exists()


def test_http_posts_audio_once_and_stores_no_token(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASR_BACKEND", "http")
    monkeypatch.setenv("ASR_HTTP_URL", "http://asr.test/v1")
    monkeypatch.setenv("ASR_HTTP_TOKEN", "super-secret-token")
    monkeypatch.setenv("ASR_MODEL", "small")
    monkeypatch.delenv("CI", raising=False)
    audio = tmp_path / "audio16k.wav"
    audio.write_bytes(b"RIFF")
    calls = []

    class Response:
        status_code = 200

        def __init__(self) -> None:
            self.headers = {"Content-Length": "200"}

        def iter_content(self, _size):
            yield json.dumps(
                {
                    "language": "en",
                    "duration": 0.4,
                    "text": "hello",
                    "segments": [
                        {
                            "id": 0,
                            "start": 0,
                            "end": 0.4,
                            "text": "hello",
                            "words": [{"word": "hello", "start": 0, "end": 0.4, "probability": 0.91}],
                        }
                    ],
                }
            ).encode()

        def close(self):
            return None

    def post(url, headers, data, files, _timeout):
        handle = files["file"][1]
        calls.append(
            {
                "url": url,
                "auth": headers.get("Authorization"),
                "model": data.get("model"),
                "audio": handle.read(),
            }
        )
        return Response()

    result = transcribe_http(audio, tmp_path, "sess", language="en", post=post)
    saved = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    assert calls[0]["url"] == "http://asr.test/v1/audio/transcriptions"
    assert calls[0]["auth"] == "Bearer super-secret-token"
    assert calls[0]["model"] == "small"
    assert calls[0]["audio"] == b"RIFF"
    assert "super-secret-token" not in json.dumps(saved)
    assert saved["backend"] == "http"
    assert saved["segments"][0]["words"][0]["word"] == "hello"
    assert result.word_count == 1


def test_redirect_is_not_followed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASR_BACKEND", "http")
    monkeypatch.setenv("ASR_HTTP_URL", "http://asr.test/v1/audio/transcriptions")
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF")
    calls = {"n": 0}

    class Response:
        status_code = 302

        def __init__(self) -> None:
            self.headers = {"Location": "http://elsewhere.test/steal"}

        def iter_content(self, _size):
            yield b""

        def close(self):
            return None

    def post(*_args, **_kwargs):
        calls["n"] += 1
        return Response()

    with pytest.raises(AsrHttpError, match="redirect"):
        transcribe_http(audio, tmp_path, "sess", post=post)
    assert calls["n"] == 1
    assert not (tmp_path / "transcript.json").exists()


def test_transcribe_audio_dispatches_only_when_http_is_selected(tmp_path: Path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF")
    calls = {"n": 0}

    def fake_http(*_args, **_kwargs):
        calls["n"] += 1
        raise RuntimeError("http-selected")

    monkeypatch.setattr("pipeline.stages.asr_remote.transcribe_http", fake_http)
    monkeypatch.setenv("ASR_BACKEND", "local")
    monkeypatch.setenv("ASR_HTTP_URL", "http://asr.test/v1")

    def stop_local(*_args, **_kwargs):
        raise RuntimeError("stop-before-whisper")

    monkeypatch.setattr("pipeline.stages.asr.load_model", stop_local)
    with pytest.raises(RuntimeError, match="stop-before-whisper"):
        transcribe_audio(audio, tmp_path, "sess", language="en", model_name="tiny")
    assert calls["n"] == 0

    monkeypatch.setenv("ASR_BACKEND", "http")
    with pytest.raises(RuntimeError, match="http-selected"):
        transcribe_audio(audio, tmp_path, "sess", language="en", model_name="tiny")
    assert calls["n"] == 1

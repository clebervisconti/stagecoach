"""Optional HTTP speech recognition. Off unless ASR_BACKEND=http.

The worker keeps faster-whisper on this machine. A configured URL is the only
place audio can go, and only after the owner sets the backend. Redirects are
not followed. Tokens stay in the Authorization header and out of logs and
transcripts.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from pipeline.stages.asr import (
    Segment,
    TranscriptOutput,
    Word,
    get_model_name,
)

logger = logging.getLogger(__name__)

MAX_RESPONSE_BYTES = 16 * 1024 * 1024
DEFAULT_READ_TIMEOUT_S = 900.0


class AsrConfigError(ValueError):
    """The HTTP backend is selected but the URL is missing or unusable."""


class AsrHttpError(RuntimeError):
    """The HTTP backend failed. The message never includes the token or the audio."""


def resolve_asr_backend(env: Mapping[str, str] | None = None) -> str:
    """`http` is the only value that sends audio off this machine.

    Anything else, including a typo, stays on the local faster-whisper path.
    """
    source = env if env is not None else os.environ
    raw = str(source.get("ASR_BACKEND") or "local").strip().lower()
    if raw in {"", "local", "faster-whisper"}:
        return "local"
    if raw == "http":
        return "http"
    logger.warning("ASR_BACKEND=%s is not supported; staying on local faster-whisper", raw)
    return "local"


def transcription_endpoint(raw: str) -> str:
    """Absolute http(s) URL with no userinfo, query, or fragment."""
    text = (raw or "").strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AsrConfigError("ASR_HTTP_URL must be an http(s) URL with a host")
    if parsed.username or parsed.password:
        raise AsrConfigError("ASR_HTTP_URL must not include a username or password")
    if parsed.query or parsed.fragment:
        raise AsrConfigError("ASR_HTTP_URL must not include a query or fragment")
    path = parsed.path.rstrip("/")
    if path in {"", "/"}:
        path = "/v1/audio/transcriptions"
    elif path.endswith("/v1"):
        path = path + "/audio/transcriptions"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def http_timeout_s(env: Mapping[str, str] | None = None) -> tuple[float, float]:
    source = env if env is not None else os.environ
    raw = str(source.get("ASR_HTTP_TIMEOUT_S") or "").strip()
    try:
        read = float(raw) if raw else DEFAULT_READ_TIMEOUT_S
    except ValueError:
        read = DEFAULT_READ_TIMEOUT_S
    read = min(3600.0, max(30.0, read))
    return (10.0, read)


def _language_code(value: Any) -> tuple[str, float]:
    text = str(value or "").strip().lower()
    if text.startswith("pt") or text == "portuguese":
        return "pt", 1.0
    if text.startswith("en") or text == "english":
        return "en", 1.0
    if not text:
        return "en", 0.0
    return "en", 1.0


def _probability(value: Any) -> float:
    """A missing probability is not a low-confidence word.

    The screen-flow guard drops words under 0.4. A server that omits the field
    would otherwise erase the transcript.
    """
    if value is None or value == "":
        return 1.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(1.0, number))


def _word(raw: Mapping[str, Any]) -> Word | None:
    text = str(raw.get("word") or raw.get("text") or "").strip()
    if not text:
        return None
    start = float(raw.get("start") or 0)
    end = float(raw.get("end") or start)
    return Word(word=text, start=start, end=end, probability=_probability(raw.get("probability")))


def parse_verbose_transcript(payload: Mapping[str, Any], *, model: str) -> TranscriptOutput:
    """Map an OpenAI-compatible verbose_json body onto transcript.json."""
    language, language_probability = _language_code(payload.get("language"))
    if payload.get("language_probability") is not None:
        language_probability = _probability(payload.get("language_probability"))
    loose_words = [_word(item) for item in payload.get("words") or [] if isinstance(item, Mapping)]
    loose = [item for item in loose_words if item is not None]
    segments: list[Segment] = []
    for index, raw in enumerate(payload.get("segments") or []):
        if not isinstance(raw, Mapping):
            continue
        start = float(raw.get("start") or 0)
        end = float(raw.get("end") or start)
        words = [_word(item) for item in raw.get("words") or [] if isinstance(item, Mapping)]
        kept = [item for item in words if item is not None]
        if not kept and loose:
            kept = [item for item in loose if item.end >= start and item.start <= end]
        text = str(raw.get("text") or "").strip()
        if not kept and text:
            kept = [Word(word=text, start=start, end=end, probability=1.0)]
        if not text and kept:
            text = " ".join(item.word for item in kept)
        avg = sum(item.probability for item in kept) / len(kept) if kept else 0.0
        segments.append(
            Segment(
                id=int(raw.get("id") if isinstance(raw.get("id"), int) else index),
                text=text,
                start=start,
                end=end,
                words=kept,
                avg_probability=avg,
                no_speech_prob=(
                    _probability(raw.get("no_speech_prob"))
                    if raw.get("no_speech_prob") is not None
                    else 0.0
                ),
            )
        )
    if not segments:
        text = str(payload.get("text") or "").strip()
        duration = float(payload.get("duration") or 0)
        if text:
            segments.append(
                Segment(
                    id=0,
                    text=text,
                    start=0.0,
                    end=duration,
                    words=[Word(word=text, start=0.0, end=duration, probability=1.0)],
                    avg_probability=1.0,
                    no_speech_prob=0.0,
                )
            )
    words = [word for segment in segments for word in segment.words]
    duration = float(payload.get("duration") or 0)
    if duration <= 0 and segments:
        duration = segments[-1].end
    mean = sum(word.probability for word in words) / len(words) if words else 0.0
    return TranscriptOutput(
        language=language,
        language_probability=language_probability,
        model=model,
        segments=segments,
        duration=duration,
        word_count=len(words),
        mean_word_probability=mean,
        backend="http",
    )


def _read_body(response: Any) -> bytes:
    length = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
    if length:
        try:
            if int(length) > MAX_RESPONSE_BYTES:
                raise AsrHttpError("ASR HTTP response is too large")
        except ValueError:
            pass
    chunks: list[bytes] = []
    size = 0
    stream = getattr(response, "iter_content", None)
    if callable(stream):
        for chunk in stream(65536):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise AsrHttpError("ASR HTTP response is too large")
            chunks.append(chunk)
        return b"".join(chunks)
    body = getattr(response, "content", b"") or b""
    if len(body) > MAX_RESPONSE_BYTES:
        raise AsrHttpError("ASR HTTP response is too large")
    return body


def _default_post(url: str, headers: dict[str, str], data: dict[str, str], files: dict, timeout: tuple[float, float]) -> Any:
    import requests

    try:
        return requests.post(
            url,
            headers=headers,
            data=data,
            files=files,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )
    except requests.Timeout as exc:
        raise AsrHttpError("ASR HTTP call timed out") from exc
    except requests.RequestException as exc:
        raise AsrHttpError("ASR HTTP call failed") from exc


def transcribe_http(
    audio_path: Path,
    output_dir: Path,
    session_id: str,
    language: str | None = None,
    model_name: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    post: Callable[..., Any] | None = None,
) -> TranscriptOutput:
    """POST audio16k to the configured transcription URL and write transcript.json."""
    source = env if env is not None else os.environ
    if resolve_asr_backend(source) != "http":
        raise AsrConfigError("ASR HTTP client is only used when ASR_BACKEND=http")
    raw_url = str(source.get("ASR_HTTP_URL") or "").strip()
    if not raw_url:
        raise AsrConfigError("ASR_HTTP_URL is unset")
    url = transcription_endpoint(raw_url)
    if not audio_path.is_file():
        raise AsrConfigError("ASR audio file is missing")
    model = model_name or get_model_name()
    token = str(source.get("ASR_HTTP_TOKEN") or "").strip()
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    form: dict[str, str] = {
        "model": model,
        "response_format": "verbose_json",
        "timestamp_granularities[]": "word",
    }
    if language and language != "auto":
        form["language"] = "pt" if language.startswith("pt") else "en"
    sender = post or _default_post
    host = urlparse(url).hostname
    logger.info("[%s] ASR HTTP transcription host=%s model=%s", session_id, host, model)
    response: Any = None
    try:
        with audio_path.open("rb") as handle:
            response = sender(
                url,
                headers,
                form,
                {"file": (audio_path.name, handle, "audio/wav")},
                http_timeout_s(source),
            )
        status = int(getattr(response, "status_code", 0) or 0)
        if 300 <= status < 400:
            raise AsrHttpError("ASR HTTP endpoint redirected; redirects are not followed")
        body = _read_body(response)
        if status != 200:
            raise AsrHttpError(f"ASR HTTP endpoint returned {status}")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AsrHttpError("ASR HTTP response was not JSON") from exc
        if not isinstance(payload, dict):
            raise AsrHttpError("ASR HTTP response was not a JSON object")
        output = parse_verbose_transcript(payload, model=model)
    finally:
        closer = getattr(response, "close", None)
        if callable(closer):
            closer()
    output_dir.mkdir(parents=True, exist_ok=True)
    document = output.to_dict()
    blob = json.dumps(document)
    if token and len(token) >= 8 and token in blob:
        raise AsrHttpError("ASR transcript included the HTTP token")
    (output_dir / "transcript.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("[%s] ASR HTTP transcription wrote %s words", session_id, output.word_count)
    return output

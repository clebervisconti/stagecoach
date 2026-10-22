"""Silero VAD must never prompt on stdin (torch.hub trust_repo)."""

from __future__ import annotations

import builtins
from pathlib import Path

import torch

from pipeline.stages import alignment


def test_load_silero_vad_never_prompts_and_passes_trust_repo(monkeypatch, tmp_path: Path):
    def boom(*_args, **_kwargs):
        raise AssertionError("input() must not be called while loading Silero VAD")

    monkeypatch.setattr(builtins, "input", boom)
    monkeypatch.delenv("SILERO_VAD_DIR", raising=False)
    monkeypatch.setattr(alignment, "silero_local_dir", lambda: None)

    seen: dict = {}

    def fake_hub_load(repo_or_dir, model, *args, **kwargs):
        seen["repo"] = repo_or_dir
        seen["model"] = model
        seen["kwargs"] = kwargs
        dummy = object()

        def get_speech_timestamps(*_a, **_k):
            return []

        def read_audio(*_a, **_k):
            return None

        return dummy, (get_speech_timestamps, None, read_audio)

    monkeypatch.setattr(torch.hub, "load", fake_hub_load)

    model, get_ts, read_audio = alignment.load_silero_vad()

    assert seen["model"] == "silero_vad"
    assert seen["repo"] == alignment.SILERO_HUB_REPO
    assert seen["kwargs"].get("trust_repo") is True
    assert callable(get_ts) and callable(read_audio)
    assert model is not None


def test_load_silero_vad_prefers_local_checkout(monkeypatch, tmp_path: Path):
    def boom(*_args, **_kwargs):
        raise AssertionError("input() must not be called while loading Silero VAD")

    local = tmp_path / "silero-vad"
    local.mkdir()
    (local / "hubconf.py").write_text("# local checkout\n")

    monkeypatch.setattr(builtins, "input", boom)
    monkeypatch.setenv("SILERO_VAD_DIR", str(local))

    seen: dict = {}

    def fake_hub_load(repo_or_dir, model, *args, **kwargs):
        seen["repo"] = repo_or_dir
        seen["kwargs"] = kwargs
        dummy = object()
        return dummy, (lambda *_a, **_k: [], None, lambda *_a, **_k: None)

    monkeypatch.setattr(torch.hub, "load", fake_hub_load)

    alignment.load_silero_vad()

    assert seen["repo"] == str(local)
    assert seen["kwargs"].get("source") == "local"
    assert seen["kwargs"].get("trust_repo") is True


def test_load_silero_vad_survives_eof_stdin(monkeypatch):
    """This is the LION failure: torch.hub called input() and got EOF."""

    def eof(*_args, **_kwargs):
        raise EOFError("EOF when reading a line")

    monkeypatch.setattr(builtins, "input", eof)
    monkeypatch.setattr(alignment, "silero_local_dir", lambda: None)

    def fake_hub_load(*_args, **kwargs):
        if kwargs.get("trust_repo") is not True:
            # Older torch.hub prompts here and raises EOFError in a container.
            return builtins.input("Do you trust this repo?")
        dummy = object()
        return dummy, (lambda *_a, **_k: [], None, lambda *_a, **_k: None)

    monkeypatch.setattr(torch.hub, "load", fake_hub_load)
    model, _get_ts, _read = alignment.load_silero_vad()
    assert model is not None

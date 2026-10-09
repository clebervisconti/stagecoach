"""Tests for ASR stage."""

import json
import tempfile
from pathlib import Path

import pytest

from pipeline.stages.asr import (
    CI_MODEL,
    DEFAULT_MODEL,
    FILLER_PROMPTS,
    LANGUAGE_CONFIDENCE_THRESHOLD,
    Segment,
    TranscriptOutput,
    Word,
    get_model_name,
)


def test_get_model_name_default():
    """Test default model selection."""
    import os
    
    old_val = os.environ.pop("ASR_MODEL", None)
    old_ci = os.environ.pop("CI", None)
    
    try:
        model = get_model_name()
        assert model == DEFAULT_MODEL
    finally:
        if old_val:
            os.environ["ASR_MODEL"] = old_val
        if old_ci:
            os.environ["CI"] = old_ci


def test_get_model_name_ci_mode():
    """Test CI mode model selection."""
    model = get_model_name(ci_mode=True)
    assert model == CI_MODEL


def test_filler_prompts_exist():
    """Test filler prompts are defined for supported languages."""
    assert "en" in FILLER_PROMPTS
    assert "pt" in FILLER_PROMPTS
    
    assert "um" in FILLER_PROMPTS["en"].lower()
    assert "uh" in FILLER_PROMPTS["en"].lower()


def test_word_serialization():
    """Test Word dataclass serialization."""
    word = Word(
        word="hello",
        start=1.0,
        end=1.5,
        probability=0.95,
    )
    
    data = word.to_dict()
    
    assert data["word"] == "hello"
    assert data["start"] == 1.0
    assert data["end"] == 1.5
    assert data["probability"] == 0.95


def test_segment_serialization():
    """Test Segment dataclass serialization."""
    words = [
        Word("hello", 0.0, 0.5, 0.9),
        Word("world", 0.5, 1.0, 0.95),
    ]
    
    segment = Segment(
        id=0,
        text="hello world",
        start=0.0,
        end=1.0,
        words=words,
        avg_probability=0.925,
        no_speech_prob=0.1,
    )
    
    data = segment.to_dict()
    
    assert data["id"] == 0
    assert data["text"] == "hello world"
    assert len(data["words"]) == 2
    assert data["avg_probability"] == 0.925


def test_transcript_output_serialization():
    """Test TranscriptOutput serialization."""
    words = [Word("test", 0.0, 0.5, 0.9)]
    segments = [
        Segment(
            id=0,
            text="test",
            start=0.0,
            end=0.5,
            words=words,
            avg_probability=0.9,
            no_speech_prob=0.0,
        )
    ]
    
    output = TranscriptOutput(
        language="en",
        language_probability=0.99,
        model="small",
        segments=segments,
        duration=0.5,
        word_count=1,
        mean_word_probability=0.9,
    )
    
    data = output.to_dict()
    
    assert data["language"] == "en"
    assert data["language_probability"] == 0.99
    assert data["model"] == "small"
    assert len(data["segments"]) == 1
    assert data["word_count"] == 1


def test_language_confidence_threshold():
    """Test language confidence threshold is reasonable."""
    assert 0.5 <= LANGUAGE_CONFIDENCE_THRESHOLD <= 1.0
    assert LANGUAGE_CONFIDENCE_THRESHOLD == 0.8

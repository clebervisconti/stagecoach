"""Tests for LLM Client

Tests both cassette mode (no API key required) and live mode (when LLM_API_KEY is set).
Per ADR-007: Skip live tests when API key is absent.
"""

import json
import os
from pathlib import Path

import pytest

from services.analysis.llm import (
    LLMClient,
    LLMAuthError,
    LLMValidationError,
    LLMCostExceededError,
)


# Sample JSON schema for testing
TEST_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "score": {"type": "integer", "minimum": 1, "maximum": 5},
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["summary", "score"],
    "additionalProperties": False,
}


@pytest.fixture
def test_cassette_dir(tmp_path):
    """Create temporary cassette directory"""
    cassette_dir = tmp_path / "cassettes"
    cassette_dir.mkdir()
    return cassette_dir


@pytest.fixture
def mock_config(test_cassette_dir, tmp_path):
    """Create test config file"""
    config = {
        "default_provider": "xai",
        "providers": {
            "xai": {
                "name": "xAI",
                "base_url": "https://api.x.ai/v1",
                "models": {
                    "grok-beta": {
                        "display_name": "Grok Beta",
                        "supports_structured_output": True,
                        "max_tokens": 131072,
                        "price_per_input_token": 0.000005,
                        "price_per_output_token": 0.000015,
                        "temperature_default": 0.4,
                        "temperature_range": [0.0, 2.0],
                    }
                },
            }
        },
        "model_assignments": {"default": "grok-beta"},
        "cost_ceiling_per_analysis": 0.50,
        "timeout": {"default": 60, "long_form": 120},
        "retry": {"max_attempts": 3, "backoff_factor": 2},
        "cassettes": {
            "enabled": True,
            "directory": str(test_cassette_dir),
            "record_mode": "once",
            "match_on": ["method", "uri", "body"],
        },
        "logging": {
            "log_prompts": False,
            "log_responses": False,
            "log_usage": True,
            "log_costs": True,
        },
    }

    config_path = tmp_path / "llm_test.yaml"
    import yaml

    with open(config_path, "w") as f:
        yaml.dump(config, f)

    return config_path


def test_client_init_no_api_key(mock_config, monkeypatch):
    """Test that client raises error when LLM_API_KEY is not set"""
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(
        LLMAuthError, match="LLM_API_KEY environment variable not set"
    ):
        LLMClient(config_path=mock_config, api_key=None)


def test_client_init_with_api_key(mock_config):
    """Test client initialization with API key"""
    client = LLMClient(config_path=mock_config, api_key="test-key")
    assert client.api_key == "test-key"
    assert client.provider_name == "xai"
    assert client.total_cost == 0.0


def test_cassette_save_and_load(mock_config, test_cassette_dir):
    """Test that cassettes are saved and loaded correctly"""
    client = LLMClient(
        config_path=mock_config, api_key="test-key", use_cassettes=True
    )

    # Create a mock cassette manually
    prompt_id = "test_prompt_v1"
    inputs = {"context": "test", "data": [1, 2, 3]}
    schema = TEST_SCHEMA

    cassette_key = client._cassette_key(prompt_id, inputs, schema)
    cassette_path = test_cassette_dir / f"{cassette_key}.json"

    # Save mock response as cassette
    mock_response = {
        "data": {
            "summary": "Test summary",
            "score": 4,
            "evidence": ["evidence1", "evidence2"],
        },
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost_usd": 0.001,
            "model": "grok-beta",
            "provider": "xai",
        },
        "raw_response": {"id": "test"},
        "prompt_id": prompt_id,
        "prompt_version": "1.0.0",
        "model": "grok-beta",
        "temperature": 0.4,
        "created_at": "2026-10-09T00:00:00",
    }

    with open(cassette_path, "w") as f:
        json.dump(mock_response, f)

    # Try to load from cassette
    loaded_response = client._try_load_cassette(prompt_id, inputs, schema)

    assert loaded_response is not None
    assert loaded_response.data == mock_response["data"]
    assert loaded_response.usage.prompt_tokens == 100
    assert loaded_response.usage.cost_usd == 0.001


def test_cost_ceiling_enforcement(mock_config):
    """Test that cost ceiling is enforced"""
    client = LLMClient(
        config_path=mock_config, api_key="test-key", use_cassettes=True
    )

    # Set cost to just below ceiling
    client.total_cost = 0.49
    # This should be fine
    assert client.total_cost < client.cost_ceiling

    # Set cost to exceed ceiling
    client.total_cost = 0.51

    # Next call should fail
    with pytest.raises(LLMCostExceededError, match="Cost ceiling"):
        client.generate_structured(
            prompt_id="test_prompt_v1",
            inputs={"data": "test"},
            schema=TEST_SCHEMA,
        )


def test_cost_tracking_reset(mock_config):
    """Test cost tracking reset"""
    client = LLMClient(config_path=mock_config, api_key="test-key")
    client.total_cost = 0.25
    assert client.total_cost == 0.25

    client.reset_cost_tracking()
    assert client.total_cost == 0.0


@pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="LLM_API_KEY not set - skipping live test",
)
def test_live_api_call(mock_config):
    """
    Test live API call when LLM_API_KEY is set.
    This test is skipped in CI when the key is not present.
    """
    client = LLMClient(config_path=mock_config, use_cassettes=False)

    response = client.generate_structured(
        prompt_id="test_prompt_v1",
        inputs={
            "context": "Evaluate this simple test.",
            "transcript": ["Hello", "world"],
        },
        schema=TEST_SCHEMA,
    )

    # Check response structure
    assert response.data is not None
    assert "summary" in response.data
    assert "score" in response.data
    assert 1 <= response.data["score"] <= 5

    # Check usage stats
    assert response.usage.prompt_tokens > 0
    assert response.usage.completion_tokens > 0
    assert response.usage.cost_usd > 0
    assert response.usage.provider == "xai"

    # Check cost tracking
    assert client.total_cost == response.usage.cost_usd

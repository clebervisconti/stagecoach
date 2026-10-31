"""E3-8: every prompt carries the factual-correctness guard at version 1.0.1."""

from pipeline.prompt_versions import GUARD_SENTENCE, load_prompt_versions
from pipeline.stages.content_llm import write_unavailable_content


def test_every_prompt_file_is_guarded_and_versioned():
    versions = load_prompt_versions()
    assert versions
    assert set(versions.values()) == {"1.0.1"}
    assert "online_flow_v1" in versions
    from pipeline.prompt_versions import prompts_dir

    for path in prompts_dir().glob("*.md"):
        assert GUARD_SENTENCE in path.read_text(encoding="utf-8")


def test_prompt_versions_are_recorded(tmp_path):
    payload = write_unavailable_content(tmp_path, "The language model step didn't finish.")
    recorded = payload["prompt_versions"]
    assert recorded["message_v1"] == "1.0.1"
    assert recorded["online_flow_v1"] == "1.0.1"
    assert recorded["slides_v1"] == "1.0.1"
    assert all(version == "1.0.1" for version in recorded.values())

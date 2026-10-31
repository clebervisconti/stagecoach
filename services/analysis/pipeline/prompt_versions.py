"""Read prompt ids and versions from the markdown front matter."""

from __future__ import annotations

from pathlib import Path

GUARD_SENTENCE = (
    "Judge how ideas are communicated (structure, clarity, support offered to the audience); "
    "never judge whether they are factually correct or technically expert."
)


def prompts_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "prompts"


def load_prompt_versions(root: Path | None = None) -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted((root or prompts_dir()).glob("*.md")):
        prompt_id = path.stem
        version = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("prompt_id:"):
                prompt_id = line.split(":", 1)[1].strip()
            elif line.startswith("version:"):
                version = line.split(":", 1)[1].strip()
        if prompt_id and version:
            found[prompt_id] = version
    return found

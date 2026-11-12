#!/usr/bin/env python3
"""Scan tracked files for personal home paths and URL passwords.

Reads the current tree (`git ls-files`) only. Does not read git history.

A macOS or Linux home path is allowed when the account is the placeholder
YOUR_USERNAME. A URL may include userinfo when the password is ``password``,
``REDACTED``, the same as the username, or an interpolated variable such as
``${POSTGRES_PASSWORD}``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_HOME = re.compile(r"/(?:Users|home)/([A-Za-z0-9._-]+)/")
_USERINFO = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://([^/\s:@]+):([^/\s@]+)@")
_INTERPOLATED = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$|^\$[A-Za-z_][A-Za-z0-9_]*$")
_FAKE_PASSWORDS = frozenset({"password", "REDACTED"})
_PLACEHOLDER_USER = "YOUR_USERNAME"


def home_hits(text: str) -> list[str]:
    return [match.group(0) for match in _HOME.finditer(text) if match.group(1) != _PLACEHOLDER_USER]


def url_hits(text: str) -> list[str]:
    found: list[str] = []
    for match in _USERINFO.finditer(text):
        user, password = match.group(1), match.group(2)
        if password in _FAKE_PASSWORDS or password == user or _INTERPOLATED.fullmatch(password):
            continue
        found.append(match.group(0))
    return found


def self_check() -> None:
    assert home_hits("/Users/YOUR_USERNAME/apps") == []
    assert home_hits("/home/YOUR_USERNAME/apps") == []
    bad_user = "not" + "placeholder"
    assert home_hits("/Users/" + bad_user + "/apps")
    assert home_hits("/home/" + bad_user + "/apps")
    assert url_hits("http://user:password@asr.test/v1") == []
    assert url_hits("http://user:REDACTED@asr.test/v1") == []
    assert url_hits("postgresql://stagecoach:${POSTGRES_PASSWORD}@postgres:5432/stagecoach") == []
    assert url_hits("postgresql://stagecoach:stagecoach@127.0.0.1/none") == []
    assert url_hits("http://user:" + "secret" + "@asr.test/v1")
    assert url_hits("http://asr.test/v1?token=secret") == []
    assert url_hits("http://127.0.0.1:8870") == []


def _tracked_files(root: Path) -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    names = [name.decode() for name in listed.stdout.split(b"\0") if name]
    return [root / name for name in names]


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in _tracked_files(root):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        rel = path.relative_to(root).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if home_hits(line):
                findings.append(f"{rel}:{lineno}: personal home path")
            if url_hits(line):
                findings.append(f"{rel}:{lineno}: URL userinfo is not a placeholder")
    return findings


def main() -> int:
    try:
        self_check()
    except AssertionError:
        print("scan self-check failed", file=sys.stderr)
        return 1
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    findings = scan(root)
    if findings:
        print("\n".join(findings), file=sys.stderr)
        print(f"{len(findings)} finding(s); current tree only, history was not read", file=sys.stderr)
        return 1
    print("ok: no personal home path or non-placeholder URL password in tracked files")
    return 0


if __name__ == "__main__":
    sys.exit(main())

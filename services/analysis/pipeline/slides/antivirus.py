"""Sandbox antivirus for uploaded decks (SPEC §10.5, issue #43).

Structural scan always runs (magic bytes, zip-bomb, macros/JS). ClamAV is
used when `clamscan`/`clamdscan` is on PATH; it is not required in CI.
No network. CPU only.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

MAX_DECK_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_ZIP_RATIO = 100.0
PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"
MACRO_NAMES = ("vbaproject.bin", "vbadata.xml", "macrosheets")
PDF_BAD = (b"/JavaScript", b"/JS ", b"/OpenAction", b"/Launch", b"/EmbeddedFile")


class DeckRejected(ValueError):
    """Deck failed the sandbox scan."""


def sniff_kind(data: bytes) -> str:
    """Return 'pdf' or 'pptx' from magic bytes. Raises DeckRejected otherwise."""
    if len(data) < 8:
        raise DeckRejected("Deck file is too small to identify.")
    if data.startswith(PDF_MAGIC):
        return "pdf"
    if data[:4] == ZIP_MAGIC:
        return "pptx"
    raise DeckRejected("Deck must be a PDF or PPTX (magic-byte sniff).")


def _scan_zip(data: bytes) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise DeckRejected("PPTX container is not a valid zip.") from exc
    if zf.infolist() and zf.infolist()[0].flag_bits & 0x1:
        raise DeckRejected("Encrypted zip decks are not allowed.")
    names = [info.filename.replace("\\", "/") for info in zf.infolist()]
    lower = [n.lower() for n in names]
    if "[content_types].xml" not in lower:
        raise DeckRejected("PPTX is missing [Content_Types].xml.")
    if not any(n.startswith("ppt/") for n in lower):
        raise DeckRejected("PPTX is missing a ppt/ directory.")
    uncompressed = 0
    for info in zf.infolist():
        uncompressed += max(info.file_size, 0)
        name = info.filename.lower()
        if any(bad in name for bad in MACRO_NAMES) or name.endswith((".exe", ".dll", ".js", ".vbs", ".bat")):
            raise DeckRejected("Deck contains disallowed embedded content (macros or executables).")
        if info.file_size > 0 and info.compress_size > 0:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > MAX_ZIP_RATIO and info.file_size > 10 * 1024 * 1024:
                raise DeckRejected("Deck looks like a zip bomb.")
    if uncompressed > MAX_UNCOMPRESSED_BYTES:
        raise DeckRejected("Deck uncompressed size exceeds the sandbox limit.")
    # Encrypted members
    for info in zf.infolist():
        if info.flag_bits & 0x1:
            raise DeckRejected("Encrypted zip members are not allowed.")


def _scan_pdf(data: bytes) -> None:
    head = data[: min(len(data), 2_000_000)]
    if any(token in head for token in PDF_BAD):
        raise DeckRejected("PDF contains disallowed actions or embedded files.")


def clam_scan(path: Path) -> Optional[str]:
    """Return a rejection reason if ClamAV is installed and flags the file."""
    exe = shutil.which("clamdscan") or shutil.which("clamscan")
    if not exe:
        return None
    try:
        result = subprocess.run(
            [exe, "--no-summary", "--stdout", str(path)],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    # 0 clean, 1 hit, 2 error (missing defs, etc.)
    if result.returncode == 1:
        return "ClamAV flagged the deck."
    return None


def scan_deck_bytes(data: bytes, *, filename: str = "deck") -> str:
    """Scan in-memory bytes. Returns 'pdf' or 'pptx'. Raises DeckRejected."""
    if len(data) > MAX_DECK_BYTES:
        raise DeckRejected("Deck exceeds the 50 MB sandbox limit.")
    if len(data) == 0:
        raise DeckRejected("Deck file is empty.")
    kind = sniff_kind(data)
    if kind == "pptx":
        _scan_zip(data)
    else:
        _scan_pdf(data)
    suffix = Path(filename).suffix.casefold()
    if kind == "pdf" and suffix not in {"", ".pdf"}:
        raise DeckRejected("PDF magic bytes do not match the .pdf extension.")
    if kind == "pptx" and suffix not in {"", ".pptx"}:
        raise DeckRejected("PPTX magic bytes do not match the .pptx extension.")
    return kind


def scan_deck_file(path: Path) -> str:
    """Scan a file on disk. Returns kind. Optional ClamAV after the structural scan."""
    data = path.read_bytes()
    kind = scan_deck_bytes(data, filename=path.name)
    hit = clam_scan(path)
    if hit:
        raise DeckRejected(hit)
    return kind

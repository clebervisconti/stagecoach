"""Magic-byte and macro scan for deck uploads (SPEC §10.5). Worker repeats a full sandbox scan."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

MAX_DECK_BYTES = 50 * 1024 * 1024
PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"
MACRO_NAMES = ("vbaproject.bin", "vbadata.xml", "macrosheets")
PDF_BAD = (b"/JavaScript", b"/JS ", b"/OpenAction", b"/Launch", b"/EmbeddedFile")
ALLOWED_DECK_EXTENSIONS = {".pptx", ".pdf"}
ALLOWED_DECK_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/octet-stream",
}


class DeckRejected(ValueError):
    pass


def scan_deck_bytes(data: bytes, filename: str = "deck") -> str:
    if not data:
        raise DeckRejected("Deck file is empty.")
    if len(data) > MAX_DECK_BYTES:
        raise DeckRejected("Deck exceeds the 50 MB limit.")
    if data.startswith(PDF_MAGIC):
        if any(token in data[:2_000_000] for token in PDF_BAD):
            raise DeckRejected("PDF contains disallowed actions or embedded files.")
        suffix = Path(filename).suffix.casefold()
        if suffix not in {"", ".pdf"}:
            raise DeckRejected("PDF magic bytes do not match the .pdf extension.")
        return "pdf"
    if data[:4] == ZIP_MAGIC:
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise DeckRejected("PPTX container is not a valid zip.") from exc
        names = [info.filename.replace("\\", "/").lower() for info in zf.infolist()]
        if "[content_types].xml" not in names or not any(n.startswith("ppt/") for n in names):
            raise DeckRejected("File is not a PPTX deck.")
        for info in zf.infolist():
            name = info.filename.lower()
            if info.flag_bits & 0x1:
                raise DeckRejected("Encrypted zip members are not allowed.")
            if any(bad in name for bad in MACRO_NAMES) or name.endswith((".exe", ".dll", ".js", ".vbs")):
                raise DeckRejected("Deck contains disallowed embedded content.")
        suffix = Path(filename).suffix.casefold()
        if suffix not in {"", ".pptx"}:
            raise DeckRejected("PPTX magic bytes do not match the .pptx extension.")
        return "pptx"
    raise DeckRejected("Deck must be a PDF or PPTX (magic-byte sniff).")

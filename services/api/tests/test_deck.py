"""Deck upload safety (issue #43) without a live database."""

import io
import os
import zipfile

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import pytest

from app.deck_safety import DeckRejected, scan_deck_bytes


def _pptx(*, macro: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
        zf.writestr("ppt/presentation.xml", "<p:presentation/>")
        if macro:
            zf.writestr("ppt/vbaProject.bin", b"MZ")
    return buf.getvalue()


def test_pptx_ok_macro_rejected():
    assert scan_deck_bytes(_pptx(), "deck.pptx") == "pptx"
    with pytest.raises(DeckRejected):
        scan_deck_bytes(_pptx(macro=True), "deck.pptx")


def test_pdf_javascript_rejected():
    with pytest.raises(DeckRejected):
        scan_deck_bytes(b"%PDF-1.4\n1 0 obj << /JavaScript (1) >>", "deck.pdf")


def test_wrong_extension_rejected():
    with pytest.raises(DeckRejected):
        scan_deck_bytes(_pptx(), "deck.pdf")

"""Match video slides to deck pages: TF-IDF cosine, or average-hash when text is sparse."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Optional, Sequence

import numpy as np

WORD = re.compile(r"[A-Za-zÀ-ÿ0-9']+")
SPARSE_WORDS = 8


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD.finditer(text or "")]


def _tfidf_matrix(docs: Sequence[list[str]]) -> np.ndarray:
    vocab: dict[str, int] = {}
    for doc in docs:
        for tok in doc:
            vocab.setdefault(tok, len(vocab))
    if not vocab:
        return np.zeros((len(docs), 1), dtype=np.float64)
    df = np.zeros(len(vocab), dtype=np.float64)
    tfs = []
    for doc in docs:
        counts = Counter(doc)
        vec = np.zeros(len(vocab), dtype=np.float64)
        for tok, n in counts.items():
            vec[vocab[tok]] = 1.0 + math.log(n)
        tfs.append(vec)
        df += (vec > 0).astype(np.float64)
    n = max(len(docs), 1)
    idf = np.log((1.0 + n) / (1.0 + df)) + 1.0
    mat = np.stack(tfs, axis=0) * idf
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return mat / norms


def tfidf_cosine(query: str, corpus: Sequence[str]) -> list[float]:
    docs = [tokenize(query)] + [tokenize(c) for c in corpus]
    mat = _tfidf_matrix(docs)
    q = mat[0]
    scores = []
    for row in mat[1:]:
        scores.append(float(np.dot(q, row)))
    return scores


def ahash64(gray: np.ndarray) -> int:
    """8×8 average hash. Hamming-comparable int."""
    # nearest-neighbor resize without cv2 so tests can pass a tiny array.
    ys = np.linspace(0, gray.shape[0] - 1, 8).astype(int)
    xs = np.linspace(0, gray.shape[1] - 1, 8).astype(int)
    small = gray[np.ix_(ys, xs)].astype(np.float64)
    mean = float(small.mean())
    bits = (small >= mean).astype(np.uint8).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def hamming(a: int, b: int) -> int:
    return int((a ^ b).bit_count())


def match_slide(
    video_text: str,
    deck_pages: Sequence[dict],
    *,
    video_hash: Optional[int] = None,
    page_hashes: Optional[Sequence[Optional[int]]] = None,
) -> dict:
    """Pick a 1-based deck page or none. Sparse OCR falls back to perceptual hash."""
    corpus = [str(p.get("text") or "") for p in deck_pages]
    if not corpus:
        return {"deck_page": None, "score": None, "method": None}
    words = tokenize(video_text)
    if len(words) >= SPARSE_WORDS:
        scores = tfidf_cosine(video_text, corpus)
        best_i = int(np.argmax(scores))
        return {
            "deck_page": int(deck_pages[best_i].get("index") or (best_i + 1)),
            "score": round(float(scores[best_i]), 4),
            "method": "tfidf",
        }
    if video_hash is not None and page_hashes:
        best_i = 0
        best_d = 65
        for i, ph in enumerate(page_hashes):
            if ph is None:
                continue
            d = hamming(video_hash, ph)
            if d < best_d:
                best_d = d
                best_i = i
        if best_d <= 16:
            return {
                "deck_page": int(deck_pages[best_i].get("index") or (best_i + 1)),
                "score": round(1.0 - best_d / 64.0, 4),
                "method": "ahash",
            }
    return {"deck_page": None, "score": None, "method": None}


def content_trigrams(words: Iterable[str]) -> list[tuple[str, str, str]]:
    seq = list(words)
    return list(zip(seq, seq[1:], seq[2:]))


def reading_overlap(slide_text: str, spoken_text: str) -> Optional[float]:
    """Share of slide content-word 3-grams spoken in order during the window (H)."""
    slide_w = tokenize(slide_text)
    spoken_w = tokenize(spoken_text)
    grams = content_trigrams(slide_w)
    if not grams:
        return None
    spoken_tri = set(content_trigrams(spoken_w))
    hits = sum(1 for g in grams if g in spoken_tri)
    return round(hits / len(grams), 4)

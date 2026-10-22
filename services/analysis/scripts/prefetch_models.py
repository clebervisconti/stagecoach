#!/usr/bin/env python3
"""Bake runtime models into the worker image (ADR-073–ADR-075, ADR-078).

Downloads are SHA-256 checked. A mismatch fails the process so a Docker build
cannot ship a swapped model. Runtime still has the same fallbacks.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tarfile
import tempfile
import zipfile
import urllib.request
from pathlib import Path

# Keep these pins next to pipeline/vision/models.py (ADR-062).
YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"

# Silero VAD v6.2.3 (MIT). torch.hub needs hubconf.py + the jit weights.
SILERO_VERSION = "v6.2.3"
SILERO_TARBALL_URL = (
    f"https://github.com/snakers4/silero-vad/archive/refs/tags/{SILERO_VERSION}.tar.gz"
)
SILERO_TARBALL_SHA256 = "bc53dd7437f6f4a04e9bb946081b08db5ad8268df12ffaf10bc147c50294f95b"
SILERO_JIT_RELPATH = "src/silero_vad/data/silero_vad.jit"
SILERO_JIT_SHA256 = "e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720"
SILERO_HUBCONF_SHA256 = "2637a3a91d061a6e921853f5de5430f873c292662b46e5fd61edaf648b4ae5bd"

# Systran/faster-whisper-small (MIT). Hashes from the HF main blob on 22 Oct 2026.
FASTER_WHISPER_REPO = "Systran/faster-whisper-small"
FASTER_WHISPER_DIRNAME = "small"
FASTER_WHISPER_FILES = (
    ("model.bin", "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"),
    ("config.json", "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828"),
    ("tokenizer.json", "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab"),
    ("vocabulary.txt", "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913"),
)

# NLTK tokenizers used by whisperX 3.8.6 (punkt_tab; punkt is the fallback).
NLTK_PACKAGES = (
    {
        "name": "punkt_tab",
        "url": "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/tokenizers/punkt_tab.zip",
        "sha256": "e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106",
        "marker": "tokenizers/punkt_tab/english/abbrev_types.txt",
    },
    {
        "name": "punkt",
        "url": "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/tokenizers/punkt.zip",
        "sha256": "51c3078994aeaf650bfc8e028be4fb42b4a0d177d41c012b6a983979653660ec",
        "marker": "tokenizers/punkt/english.pickle",
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha(path: Path, expected: str, label: str) -> None:
    digest = sha256_file(path)
    if digest != expected:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 mismatch for {label}: got {digest}, expected {expected}")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)


def prefetch_yunet(models_dir: Path) -> Path:
    dest = models_dir / YUNET_FILENAME
    if dest.is_file() and sha256_file(dest) == YUNET_SHA256:
        return dest
    download(YUNET_URL, dest)
    require_sha(dest, YUNET_SHA256, YUNET_FILENAME)
    return dest


def prefetch_silero(models_dir: Path) -> Path:
    dest = models_dir / "silero-vad"
    jit = dest / SILERO_JIT_RELPATH
    hubconf = dest / "hubconf.py"
    if (
        jit.is_file()
        and hubconf.is_file()
        and sha256_file(jit) == SILERO_JIT_SHA256
        and sha256_file(hubconf) == SILERO_HUBCONF_SHA256
    ):
        return dest

    with tempfile.TemporaryDirectory() as tmp:
        tarball = Path(tmp) / "silero-vad.tar.gz"
        download(SILERO_TARBALL_URL, tarball)
        require_sha(tarball, SILERO_TARBALL_SHA256, f"silero-vad {SILERO_VERSION} tarball")
        extract_root = Path(tmp) / "src"
        extract_root.mkdir()
        with tarfile.open(tarball, "r:gz") as archive:
            archive.extractall(extract_root)
        members = [path for path in extract_root.iterdir() if path.is_dir()]
        if len(members) != 1:
            raise RuntimeError(f"expected one silero-vad directory, found {members}")
        unpacked = members[0]
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("hubconf.py", "src", "LICENSE", "LICENSE.txt"):
            source = unpacked / name
            if not source.exists():
                continue
            target = dest / name
            if source.is_dir():
                if target.exists():
                    continue
                _copytree(source, target)
            else:
                target.write_bytes(source.read_bytes())

    require_sha(dest / "hubconf.py", SILERO_HUBCONF_SHA256, "silero-vad hubconf.py")
    require_sha(dest / SILERO_JIT_RELPATH, SILERO_JIT_SHA256, "silero_vad.jit")
    return dest


def prefetch_mediapipe(models_dir: Path) -> list[Path]:
    """Bake pose / hand / face landmarker .task files (SHA from MODEL_REGISTRY)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pipeline.vision.models import MODEL_REGISTRY

    written: list[Path] = []
    for row in MODEL_REGISTRY:
        if not str(row.get("filename", "")).endswith(".task"):
            continue
        dest = models_dir / row["filename"]
        if dest.is_file() and sha256_file(dest) == row["sha256"]:
            written.append(dest)
            continue
        download(row["url"], dest)
        require_sha(dest, row["sha256"], row["filename"])
        written.append(dest)
    if len(written) != 3:
        raise RuntimeError(f"expected 3 MediaPipe .task files, got {written}")
    return written


def prefetch_faster_whisper(models_dir: Path) -> Path:
    dest = models_dir / "faster-whisper" / FASTER_WHISPER_DIRNAME
    dest.mkdir(parents=True, exist_ok=True)
    base = f"https://huggingface.co/{FASTER_WHISPER_REPO}/resolve/main"
    for filename, digest in FASTER_WHISPER_FILES:
        path = dest / filename
        if path.is_file() and sha256_file(path) == digest:
            continue
        download(f"{base}/{filename}", path)
        require_sha(path, digest, f"{FASTER_WHISPER_REPO}/{filename}")
    return dest


def prefetch_nltk(models_dir: Path) -> Path:
    dest = models_dir / "nltk_data"
    tokenizers = dest / "tokenizers"
    tokenizers.mkdir(parents=True, exist_ok=True)
    for package in NLTK_PACKAGES:
        marker = dest / package["marker"]
        if marker.is_file():
            continue
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / f"{package['name']}.zip"
            download(package["url"], archive)
            require_sha(archive, package["sha256"], f"nltk {package['name']} zip")
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(tokenizers)
        if not marker.is_file():
            raise RuntimeError(f"nltk {package['name']} extract missed {marker}")
    return dest


def _copytree(source: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for child in source.rglob("*"):
        relative = child.relative_to(source)
        target = dest / relative
        if child.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(child.read_bytes())


def main() -> int:
    models_dir = Path(os.environ.get("MEDIAPIPE_MODELS_DIR", "/models"))
    models_dir.mkdir(parents=True, exist_ok=True)
    yunet = prefetch_yunet(models_dir)
    silero = prefetch_silero(models_dir)
    tasks = prefetch_mediapipe(models_dir)
    whisper = prefetch_faster_whisper(models_dir)
    nltk_dir = prefetch_nltk(models_dir)
    print(
        f"yunet={yunet} silero={silero} "
        f"mediapipe={[str(path) for path in tasks]} "
        f"faster_whisper={whisper} nltk={nltk_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ADR-073: One pinned torch for the worker on amd64 and arm64

**Date:** 2026-10-22
**Status:** Accepted
**Phase:** O1

## Context

Cyberlabs built the worker from `main` `d1f9d72` on LION (OrbStack, linux/arm64). `torch==2.4.1+cpu` has no aarch64 wheel. `praat-parselmouth==0.4.5` builds from source and needs `g++`, `make` / Ninja, and `CMAKE_POLICY_VERSION_MINIMUM=3.5` on Bookworm's CMake. Installing `requirements-alignment.txt` then floated torch to 2.14.1 over the pin.

PR #149 already split torch by arch. That change is folded here and extended so alignment cannot upgrade torch, compilers are not in the runtime image, and CI builds the full linux/arm64 image.

## Decision

- Pin **torch 2.4.1** and **torchaudio 2.4.1** everywhere the worker installs Python deps.
- linux/amd64: `torch==2.4.1+cpu` / `torchaudio==2.4.1+cpu` from `https://download.pytorch.org/whl/cpu`.
- linux/arm64: `torch==2.4.1` / `torchaudio==2.4.1` from PyPI (CPU manylinux aarch64 wheels).
- `TARGETARCH` selects `requirements-torch-amd64.txt` or `requirements-torch-arm64.txt`. Host installs may use `requirements-torch.txt` (platform markers).
- Alignment installs with `pip install -c requirements-torch-$ARCH.txt`.
- Multi-stage image: build stage has `gcc`, `g++`, `make`, `ninja-build`, `cmake`; runtime stage does not.
- `CMAKE_POLICY_VERSION_MINIMUM=3.5` is set in the build stage only.

## Alternatives considered

1. **Stay on `2.4.1+cpu` for all arches** — rejected; no aarch64 wheel.
2. **Let pyannote float torch 2.14.1** — rejected; two torch versions in one image.
3. **Keep compilers in the final image** — rejected; Cyberlabs asked for a slim runtime.

## Consequences

- `make lion-build` on LION needs no local Dockerfile override.
- CI `Worker arm64 image` builds the image with buildx + QEMU and imports torch, torchaudio, parselmouth, mediapipe, and cv2.
- PR #149's torch split is superseded by this pin plus the multi-stage and alignment constraint.

"""CPU-only vision helpers (issue #38, SPEC §6.5).

OpenFace is not used. Emotion labels are not inferred.
"""

from pipeline.vision.models import MODEL_REGISTRY, ensure_models

__all__ = ["MODEL_REGISTRY", "ensure_models"]

"""Main scoring engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .aggregation import aggregate_category, aggregate_overall
from .confidence import compute_inclusion_factor
from .curves import interpolate_curve
from .opportunities import rank_opportunities

logger = logging.getLogger(__name__)


def resolve_metric_curve(
    metric_def: dict[str, Any],
    *,
    context: str,
    mode: str,
    metric_id: str,
) -> list[list[float]] | None:
    """Resolve a piecewise curve: mode_curves, then context_curves, then curve.

    A missing context_curves key no longer raises. Fall back to `curve`, else
    the keynote context curve, and log the fallback (Appendix C, C11).
    """
    mode_curves = metric_def.get("mode_curves") or {}
    if isinstance(mode_curves, dict) and mode in mode_curves:
        curve = mode_curves[mode]
        return curve if isinstance(curve, list) else None

    context_curves = metric_def.get("context_curves") or {}
    if isinstance(context_curves, dict) and context in context_curves:
        curve = context_curves[context]
        return curve if isinstance(curve, list) else None

    if "curve" in metric_def and isinstance(metric_def["curve"], list):
        if context_curves and context not in context_curves:
            logger.info(
                "No context_curves[%s] for %s; falling back to curve",
                context,
                metric_id,
            )
        return metric_def["curve"]

    if isinstance(context_curves, dict) and context_curves:
        fallback = context_curves.get("keynote")
        if fallback is None:
            fallback = next(iter(context_curves.values()), None)
        if isinstance(fallback, list):
            logger.info(
                "No context_curves[%s] for %s; falling back to keynote/first curve",
                context,
                metric_id,
            )
            return fallback
    return None


class ScoringEngine:
    """Scoring engine that loads a versioned config and computes scores.

    Example:
        >>> engine = ScoringEngine(config_version="1.0.0")
        >>> score = engine.score_metric("fl_filler_sounds_per_min", 7.2, 0.85)
        >>> category_score = engine.score_category("fluency", metrics, "keynote")
        >>> overall = engine.score_overall(categories, "keynote")
    """

    def __init__(self, config_version: str = "1.0.0", config_path: Path | None = None):
        """Initialize scoring engine with a config version.

        Args:
            config_version: Semver version string (e.g. "1.0.0")
            config_path: Optional path to scoring-config directory.
                        Defaults to ../scoring-config relative to this file.
        """
        self.version = config_version

        if config_path is None:
            # Default: packages/scoring-config relative to this package
            config_path = Path(__file__).parent.parent.parent / "scoring-config"

        version_dir = config_path / f"v{config_version}"
        config_file = version_dir / "scoring.yaml"

        if not config_file.exists():
            raise ValueError(f"Scoring config v{config_version} not found at {config_file}")

        with open(config_file) as f:
            self.config: dict[str, Any] = yaml.safe_load(f)

        # Validate version matches
        if self.config.get("version") != config_version:
            raise ValueError(
                f"Config file version {self.config.get('version')} "
                f"does not match requested version {config_version}"
            )

    def score_metric(
        self,
        metric_id: str,
        raw_value: float | str | bool | None,
        confidence: float,
        category_id: str | None = None,
        context: str = "keynote",
        mode: str = "stage",
    ) -> dict[str, Any]:
        """Score a single metric.

        Args:
            metric_id: Metric identifier (e.g. "fl_filler_sounds_per_min")
            raw_value: Raw metric value
            confidence: Confidence in the measurement [0, 1]
            category_id: Optional category for context-dependent metrics
            context: Presentation context type
            mode: Delivery mode (stage, webinar, online_talk, recorded_video)

        Returns:
            Dict with keys: score, included, inclusion_factor
        """
        # Find the metric definition
        metric_def = None
        if category_id:
            cat = self.config["categories"].get(category_id, {})
            metric_def = cat.get("metrics", {}).get(metric_id)
        else:
            # Search all categories
            for cat in self.config["categories"].values():
                if metric_id in cat.get("metrics", {}):
                    metric_def = cat["metrics"][metric_id]
                    break

        if not metric_def:
            raise ValueError(f"Metric {metric_id} not found in config")

        allowed_modes = metric_def.get("modes")
        if isinstance(allowed_modes, list) and mode not in allowed_modes:
            return {
                "score": None,
                "included": False,
                "inclusion_factor": 0.0,
            }

        # Compute inclusion factor
        inclusion_factor = compute_inclusion_factor(confidence, self.config["confidence"])

        # Compute score based on metric type
        if metric_def.get("llm_level"):
            # LLM level judgment: raw_value is a level (1-5, possibly half-steps)
            if raw_value is None:
                score = None
            else:
                level = float(raw_value)
                # Map level to score: score = 20*L - 10
                score = 20 * level - 10
                score = max(0, min(100, score))  # Clamp to [0, 100]

        elif "curve" in metric_def or "context_curves" in metric_def or "mode_curves" in metric_def:
            curve = resolve_metric_curve(
                metric_def, context=context, mode=mode, metric_id=metric_id
            )
            if curve is None:
                # Missing context/mode curve is N/A, never a crash (Appendix C, C11).
                return {
                    "score": None,
                    "included": False,
                    "inclusion_factor": 0.0,
                }
            if raw_value is None or not isinstance(raw_value, (int, float)):
                score = None
            else:
                score = interpolate_curve(curve, float(raw_value))

        elif "mapping" in metric_def:
            # Categorical mapping
            mapping = metric_def["mapping"]
            if raw_value is None:
                score = None
            else:
                score = mapping.get(str(raw_value))
                if score is None:
                    raise ValueError(f"Value {raw_value} not in mapping for {metric_id}")

        else:
            raise ValueError(f"Metric {metric_id} has no scoring method defined")

        return {
            "score": score,
            "included": inclusion_factor > 0,
            "inclusion_factor": inclusion_factor,
        }

    def score_category(
        self,
        category_id: str,
        metrics: list[dict[str, Any]],
        context: str = "keynote",
        mode: str = "stage",
    ) -> dict[str, Any]:
        """Score a category from its sub-metrics.

        Args:
            category_id: Category identifier (e.g. "fluency")
            metrics: List of metric dicts with keys:
                     id, raw_value, confidence, (score, inclusion_factor)
            context: Presentation context type

        Returns:
            Dict with keys: score, level, confidence, applicable, na_reason
        """
        category_def = self.config["categories"].get(category_id)
        if not category_def:
            raise ValueError(f"Category {category_id} not found")
        if mode not in ((self.config.get("modes") or {}) or {"stage": True}):
            mode = "stage"

        return aggregate_category(
            category_id,
            category_def,
            metrics,
            context,
            self.config,
        )

    def score_overall(
        self,
        categories: list[dict[str, Any]],
        context: str = "keynote",
        mode: str = "stage",
    ) -> dict[str, Any]:
        """Compute overall score from category scores.

        Args:
            categories: List of category dicts with keys:
                       id, score, confidence, applicable
            context: Presentation context type

        Returns:
            Dict with keys: score, level, coverage, confidence, display_band, partial
        """
        return aggregate_overall(categories, context, self.config, mode=mode)

    def rank_opportunities(
        self,
        categories: list[dict[str, Any]],
        context: str = "keynote",
        focus_areas: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Rank improvement opportunities by impact.

        Args:
            categories: List of category dicts with scores and confidence
            context: Presentation context type
            focus_areas: Optional list of category IDs to boost

        Returns:
            List of opportunity dicts sorted by impact (highest first)
        """
        return rank_opportunities(categories, context, self.config, focus_areas or [])

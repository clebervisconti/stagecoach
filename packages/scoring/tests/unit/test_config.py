"""Tests for scoring configuration validation."""

import pytest
import yaml
from pathlib import Path


def load_config(version: str = "1.0.0") -> dict:
    """Load a scoring config for testing."""
    config_path = Path(__file__).parent.parent.parent.parent / "scoring-config"
    config_file = config_path / f"v{version}" / "scoring.yaml"
    with open(config_file) as f:
        return yaml.safe_load(f)


class TestConfigValidation:
    """Test that the scoring config meets all requirements."""
    
    def test_config_loads(self):
        """Config file loads without errors."""
        config = load_config()
        assert config["version"] == "1.0.0"
    
    def test_all_context_weights_sum_to_100(self):
        """Each context's category weights sum to 100."""
        config = load_config()
        weights = config["weights"]
        
        for context, context_weights in weights.items():
            total = sum(context_weights.values())
            assert total == 100, f"Context {context} weights sum to {total}, not 100"
    
    def test_all_category_submetric_weights_sum_to_1(self):
        """Each category's sub-metric weights sum to 1.0 (allowing for rounding)."""
        config = load_config()
        categories = config["categories"]
        
        for cat_id, cat_def in categories.items():
            metrics = cat_def.get("metrics", {})
            if not metrics:
                continue
            
            total = sum(m.get("weight", 0) for m in metrics.values())
            # Allow small rounding error
            assert abs(total - 1.0) < 0.001, (
                f"Category {cat_id} metric weights sum to {total}, not 1.0"
            )
    
    def test_all_sources_are_documented(self):
        """Every source key exists in sources.md."""
        config = load_config()
        
        # Load sources.md
        sources_file = Path(__file__).parent.parent.parent.parent.parent / "docs" / "research" / "sources.md"
        with open(sources_file) as f:
            sources_text = f.read()
        
        # Extract all source keys from config
        all_sources = set()
        for cat_def in config["categories"].values():
            all_sources.update(cat_def.get("sources", []))
            
            for metric_def in cat_def.get("metrics", {}).values():
                basis = metric_def.get("basis", {})
                source = basis.get("source", "")
                if source and source != "H":
                    # Split combined sources like "S7_S8"
                    parts = source.replace("_", " ").split()
                    all_sources.update(p for p in parts if p.startswith("S"))
        
        # Check each source key appears in sources.md
        missing = []
        for source in all_sources:
            if source == "H":
                continue  # Heuristic marker, not a source
            
            # Look for **[S#]** pattern
            pattern = f"**[{source}]**"
            if pattern not in sources_text:
                missing.append(source)
        
        assert not missing, f"Sources missing from sources.md: {missing}"
    
    def test_curves_are_well_formed(self):
        """All curves are sorted by x and have valid y values."""
        config = load_config()
        
        for cat_id, cat_def in config["categories"].items():
            metrics = cat_def.get("metrics", {})
            
            for metric_id, metric_def in metrics.items():
                # Check direct curve
                if "curve" in metric_def:
                    curve = metric_def["curve"]
                    self._validate_curve(curve, f"{cat_id}.{metric_id}")
                
                # Check context-specific curves
                if "context_curves" in metric_def:
                    for context, curve in metric_def["context_curves"].items():
                        self._validate_curve(
                            curve, f"{cat_id}.{metric_id}.{context}"
                        )
    
    def _validate_curve(self, curve, name):
        """Validate a single curve."""
        assert len(curve) >= 2, f"Curve {name} has < 2 points"
        
        prev_x = None
        for i, point in enumerate(curve):
            assert len(point) == 2, f"Curve {name} point {i} invalid"
            x, y = point
            
            # Check y is in [0, 100]
            assert 0 <= y <= 100, f"Curve {name} point {i} y={y} not in [0, 100]"
            
            # Check x is sorted
            if prev_x is not None:
                assert x > prev_x, f"Curve {name} point {i} x={x} not sorted"
            prev_x = x
    
    def test_all_contexts_have_weights_for_all_categories(self):
        """Every context has a weight for every category."""
        config = load_config()
        contexts = config["contexts"]
        categories = list(config["categories"].keys())
        
        for context in contexts:
            context_weights = config["weights"].get(context, {})
            missing = set(categories) - set(context_weights.keys())
            assert not missing, (
                f"Context {context} missing weights for: {missing}"
            )
    
    def test_categories_have_required_fields(self):
        """Each category has sources, tractability, and metrics."""
        config = load_config()
        
        for cat_id, cat_def in config["categories"].items():
            assert "sources" in cat_def, f"Category {cat_id} missing sources"
            assert "tractability" in cat_def, f"Category {cat_id} missing tractability"
            assert "metrics" in cat_def, f"Category {cat_id} missing metrics"
            
            # Check tractability is in [0, 1]
            tract = cat_def["tractability"]
            assert 0 <= tract <= 1, (
                f"Category {cat_id} tractability {tract} not in [0, 1]"
            )
    
    def test_metrics_have_required_fields(self):
        """Each metric has weight, unit, and basis."""
        config = load_config()
        
        for cat_id, cat_def in config["categories"].items():
            for metric_id, metric_def in cat_def.get("metrics", {}).items():
                assert "weight" in metric_def, (
                    f"Metric {cat_id}.{metric_id} missing weight"
                )
                assert "unit" in metric_def, (
                    f"Metric {cat_id}.{metric_id} missing unit"
                )
                assert "basis" in metric_def, (
                    f"Metric {cat_id}.{metric_id} missing basis"
                )
                
                basis = metric_def["basis"]
                assert "kind" in basis, (
                    f"Metric {cat_id}.{metric_id} basis missing kind"
                )
                assert "source" in basis, (
                    f"Metric {cat_id}.{metric_id} basis missing source"
                )
                
                # Check kind is valid
                assert basis["kind"] in ["research", "heuristic", "llm_judgment"], (
                    f"Metric {cat_id}.{metric_id} has invalid basis kind"
                )

# Scoring Configuration

Versioned YAML configuration files defining:
- Category and sub-metric weights per context
- Scoring curves (piecewise-linear anchor points)
- Target bands, gates, and minimum evidence rules
- Research source attributions

## Structure

```
v1.0.0/
  scoring.yaml        - Complete scoring configuration
  README.md           - Version notes and changelog
scoring-config.schema.json - JSON Schema for validation
```

## Configuration Format

```yaml
version: 1.0.0
contexts: [keynote, breakout, exec_briefing, ...]
weights:
  keynote: {core_message: 9, structure: 6, ...}
  exec_briefing: {core_message: 10, structure: 9, ...}
categories:
  fluency:
    sources: [S12, S21, S33]
    min_evidence: {speech_s: 120}
    tractability: 1.0
    metrics:
      fl_filler_sounds_per_min:
        weight: 0.40
        unit: "per_min"
        basis: {kind: research, source: S12}
        curve: [[0,100],[1,95],[2,85],[3.5,70],...]
```

## Validation

Every config version must:
- Pass JSON Schema validation
- Have all context weights sum to 100
- Have all category sub-metric weights sum to 1.0
- Reference only source keys that exist in docs/research/sources.md

## Usage

```python
from scoring_config import load_config

config = load_config("1.0.0")
weights = config.weights["keynote"]
curve = config.get_curve("fl_filler_sounds_per_min")
```

## Version History

- **1.0.0** (2026-10-09): Initial MVP configuration

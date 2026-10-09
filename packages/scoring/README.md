# Scoring Engine

Pure Python scoring engine that computes category and overall scores from metric values.

## Features

- Curve interpolation (piecewise-linear)
- LLM level → score mapping
- Confidence-based inclusion factors
- Category aggregation with weights
- N/A handling and gates
- Overall score, coverage, confidence, display band
- Opportunity ranking

## API

```python
from scoring import ScoringEngine

engine = ScoringEngine(config_version="1.0.0")

# Score a single metric
score = engine.score_metric(
    metric_id="fl_filler_sounds_per_min",
    raw_value=7.2,
    confidence=0.85
)

# Score a category from sub-metrics
category_score = engine.score_category(
    category_id="fluency",
    metrics=[...],
    context="keynote"
)

# Compute overall score
overall = engine.score_overall(
    categories=[...],
    context="keynote"
)

# Rank opportunities
opportunities = engine.rank_opportunities(
    categories=[...],
    context="keynote",
    focus_areas=["fluency", "pace_pausing"]
)
```

## Implementation

- `engine.py` - Main ScoringEngine class
- `curves.py` - Curve interpolation
- `confidence.py` - Confidence calculations
- `aggregation.py` - Category and overall aggregation
- `opportunities.py` - Opportunity ranking logic

## Testing

100% test coverage on all scoring logic:

```bash
pytest tests/unit/
pytest tests/integration/
```

Property tests with Hypothesis verify:
- All scores are in [0, 100]
- Curves are monotonic where declared
- Weights sum correctly
- Confidence inclusion is deterministic

# Lexicons Package

Language-specific lexicons for fluency and clarity metrics in Stage Coach.

## Contents

- `en.yaml` — English lexicons
- `pt-BR.yaml` — Brazilian Portuguese lexicons

## Categories

### Filler Sounds
Non-lexical vocalizations (um, uh, er, hmm, etc.) that are always counted as fillers without disambiguation.

### Filler Word Candidates
**Ambiguous words** that may be fillers or legitimate language use depending on context (like, so, basically, né, tipo, então).

**Important:** Every filler word candidate MUST be LLM-disambiguated in context before counting it as a filler. Do not count these automatically.

### Hedges
Uncertainty markers and qualifiers that weaken statements (I think maybe, sort of, acho que, talvez).

### Apologies
Unnecessary apologies and self-deprecating phrases.

### Rush Phrases
Time-pressure indicators that suggest poor time management.

### Vague Quantifiers
Weasel words and imprecise language (a lot, various, muita coisa, várias coisas).

### Signposts
Positive signals: transitions and structural markers that help the audience follow along.

## Usage

Lexicons are loaded by fluency and clarity metric functions and LLM prompts.

```python
import yaml

with open('packages/lexicons/en.yaml') as f:
    en_lexicon = yaml.safe_load(f)

filler_sounds = en_lexicon['filler_sounds']
```

## Sources

- Appendix A of docs/SPEC.md
- Existing `scripts/metrics.py` (carried forward and extended)
- Research basis: Laske & DiGennaro Reed (2024) [S12] on filler impact

## Language Notes

### English
- "like" and "so" are often legitimate connectives or comparisons
- Distinguish between filled pauses and discourse markers by context

### Brazilian Portuguese
- **'é'** (short) is usually the verb 'to be'; only elongated **'éé'/'ééé'** is a filler sound
- **'então'** and **'assim'** are often legitimate connectives or manner expressions
- **'né'** (from "não é?") can be a tag question or a filler
- **'tipo'** can mean "like/kind of" as a comparison or as a filler

All ambiguous cases require LLM disambiguation per the SPEC fluency metrics (§4.4.11).

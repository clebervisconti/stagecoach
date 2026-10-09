# Lexicons

Language-specific word lists for filler detection, hedge detection, and text analysis.

## Structure

```
en.yaml               - English lexicons
pt-BR.yaml            - Brazilian Portuguese lexicons
```

## Format

```yaml
filler_sounds:        # Always fillers (um, uh, ...)
  - um
  - uh
  - er

filler_words_candidates:  # Ambiguous; require LLM disambiguation
  - like
  - "you know"
  - basically

hedges:
  - "i think maybe"
  - "sort of"
  - maybe

apologies:
  - sorry
  - "i apologize"

vague:
  - "a lot"
  - various
  - stuff

signposts:
  - first
  - second
  - "in summary"
```

## Usage

```python
from lexicons import load_lexicon

lex = load_lexicon("en")
filler_sounds = lex["filler_sounds"]
```

## Disambiguation

Words in `filler_words_candidates` are context-dependent:
- "like" as a filler: "It was, like, really hard"
- "like" as a verb: "I like this approach"

The LLM disambiguates these in context during fluency analysis.

## Sources

Lexicons are compiled from:
- Existing Stage Coach metrics.py
- Laske & DiGennaro Reed (2024) [S12]
- Native speaker consultation (pt-BR)

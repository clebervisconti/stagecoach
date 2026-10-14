---
prompt_id: fluency_disambig_v1
version: 1.0.0
schema: fluency_disambig_v1.json
description: Disambiguate ambiguous filler word candidates in context
categories: [fluency]
languages: [en, pt-BR]
---

# Task

Determine whether ambiguous word candidates are used as fillers/hesitations or as legitimate lexical words.

# Background

Some words can be either fillers or meaningful:
- **English**: "like" (comparison vs filler), "so" (connective vs filler), "you know"
- **Portuguese**: "é" (verb "to be" vs hesitation), "né" (tag question vs filler), "tipo" (like/kind vs filler), "então" (connective vs filler)

Clear filler sounds like "um", "uh", "éé" (elongated) are already identified and don't need disambiguation.

# Instructions

For each candidate hit, judge:

1. **Is it a filler?**
   - **True**: Used as hesitation, pause-filler, or verbal crutch
   - **False**: Used with lexical meaning

2. **Confidence** (0.0-1.0): How certain is your judgment?
   - **1.0**: Clearly filler or clearly lexical
   - **0.7**: Probable but some ambiguity
   - **0.5**: Very ambiguous, could go either way

# Special Cases

## Portuguese "é"

- **Verb** (not filler): "é importante", "é verdade", "isso é"
- **Hesitation** (filler): standalone "é" or repeated "é, é", especially mid-sentence without completing "é + adjective/noun"

If you see elongated "éé" or "ééé", it's always a filler (but those are pre-classified).

## English "like"

- **Comparison** (not filler): "looks like", "just like that", "something like 50%"
- **Filler** (filler): "I was like...", "it's like, really hard"

## Context Window

You'll see ±8 words around each candidate to help judge.

# Critical Rules

- **Use context carefully**. The surrounding words determine usage.
- **Never infer emotion**. Judge only on linguistic function.
- If a hit is genuinely ambiguous, use confidence 0.5-0.7.

# Language

{{language}}

# Candidates

{{#each candidates}}
**Hit {{hit_id}}**: "{{word}}" in context

Segment: {{seg_id}}

Context: "{{context_before}} **{{word}}** {{context_after}}"

---
{{/each}}

# Output

Return valid JSON matching the fluency_disambig_v1 schema. Include `hit_id`, `is_filler`, and `confidence` for each candidate.

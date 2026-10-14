# Metric validation log

Phase 1 start of metric-level validation (issue #35, SPEC §11.1 / §12).

## Scope

Fillers, WPM, and unplanned long pauses on **≥ 20 minutes of annotated timestamps per language** (en and pt-BR).

This is **not** a human-rated speaking-club corpus. Issue #35 / D13: the public repo must not contain personal recordings unless the owner explicitly licenses them. The corpora here are synthetic word timestamps with known labels, so the metric functions can be checked before licensed speech arrives.

## Method

`services/analysis/tests/golden/validation_corpus.py` builds 20 minutes of evenly spaced lexical words at a known WPM, inserts filler sounds at 5/min ([S12] no-penalty anchor), and inserts mid-sentence pauses ≥ 3 s at 1 per 10 minutes. It then runs `pp_wpm`, `fl_filler_sounds_per_min`, and `pp_unplanned_long_pauses_per_10min`.

Pass rule for this start: relative error ≤ 5% (the golden-pipeline metric tolerance in SPEC §11.6).

## Results (2026-10-14)

Observed from `python3 -c "from tests.golden.validation_corpus import build_corpus, evaluate; ..."` on this branch:

| language | duration | words | WPM expected / got | rel err | fillers/min expected / got | rel err | long pauses /10 min expected / got | rel err |
|---|---|---|---|---|---|---|---|---|
| en | 20.0 min | 2700 | 130.00 / 130.01 | 0.008% | 5.000 / 5.000 | 0.008% | 1.0 / 1.0 | 0% |
| pt-BR | 20.0 min | 2500 | 120.00 / 120.01 | 0.008% | 5.000 / 5.000 | 0.008% | 1.0 / 1.0 | 0% |

Both languages are within ±5%. Portuguese uses filler sound `éé` from `packages/lexicons/pt-BR.yaml`. English uses `um`.

## Not started yet

- Licensed human speech (≥ 20 min per language) with independent annotation
- Filler-word LLM disambiguation (né/tipo/então) on real pt-BR
- Inter-rater agreement or machine–human ρ (SPEC §11.2)

Those wait on owner fixture licensing (D13).

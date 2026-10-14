# Golden fixtures (issue #35)

Three short **synthetic** audio fixtures, not personal recordings:

| id | language | kind |
|---|---|---|
| `en_clean` | en | clean sine, High/Medium confidence |
| `ptbr_clean` | pt-BR | clean sine, Portuguese filler tokens in the transcript |
| `noisy_low_snr` | en | sine + deterministic noise, SNR 10 dB, Low confidence, excluded from overall |

`audio.wav` and `transcript.json` are generated at test time (gitignored). `python scripts/process_local.py --golden` writes them, runs fusion, and compares to `expected/analysis_result.json` with SPEC §11.6 tolerances (±2 score points, ±5% metric values).

Origin: stdlib `wave` 16 kHz mono PCM. License: CC0 generated test signal.

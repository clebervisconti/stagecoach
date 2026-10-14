# Vision model and dependency licenses (issue #38)

Checked on 2026-10-14. OpenFace is not used.

| Artifact | License | Evidence |
|---|---|---|
| github.com/google-ai-edge/mediapipe | Apache-2.0 | LICENSE fetched 2026-10-14 |
| PyPI `mediapipe` | Apache-2.0 | Package license field + OSI classifier |
| pose_landmarker_full.task float16/1 | Apache-2.0 | Maintainer schmidt-sebastian, [mediapipe#6306](https://github.com/google-ai-edge/mediapipe/issues/6306) (2026-06-10). SHA-256 `5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1` |
| hand_landmarker.task float16/1 | Apache-2.0 | Maintainer: models Apache2 unless noted ([#6355](https://github.com/google-ai-edge/mediapipe/issues/6355), 2026-10-05). SHA-256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` |
| face_landmarker.task float16/1 | Apache-2.0 | Same statement. Blendshape model card: https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Blendshape%20V2.pdf. SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff` |
| cryptography | Apache-2.0 OR BSD-3-Clause | pyca/cryptography LICENSE |
| scipy | BSD-3-Clause | scipy LICENSE.txt |

CPU delegate only. Blendshape scores are numeric coefficients, not emotion labels.

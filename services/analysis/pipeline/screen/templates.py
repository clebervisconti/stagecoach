"""Fixed coaching lines from measured numbers. No model, no pictures."""

from __future__ import annotations

from typing import Any

_DRILLS = {
    "en": [
        {
            "title": "Pause at the change",
            "how": "Stop speaking for a short beat when the screen changes, then start the next point.",
            "practice_time_min": 10,
            "targets_metric": "sf_clean_transition_ratio",
        },
        {
            "title": "Name the next screen",
            "how": "Say what the next screen is for before you move to it.",
            "practice_time_min": 10,
            "targets_metric": "sf_signpost_ratio",
        },
        {
            "title": "Ask the room once",
            "how": "Add one question to the audience in the first ten minutes, then wait.",
            "practice_time_min": 10,
            "targets_metric": "oe_interaction_prompts_per_10min",
        },
    ],
    "pt-BR": [
        {
            "title": "Pausa na troca",
            "how": "Pare de falar por um instante quando a tela muda e depois comece o ponto seguinte.",
            "practice_time_min": 10,
            "targets_metric": "sf_clean_transition_ratio",
        },
        {
            "title": "Nomeie a próxima tela",
            "how": "Diga para que serve a próxima tela antes de mudar.",
            "practice_time_min": 10,
            "targets_metric": "sf_signpost_ratio",
        },
        {
            "title": "Uma pergunta",
            "how": "Faça uma pergunta ao público nos primeiros dez minutos e espere.",
            "practice_time_min": 10,
            "targets_metric": "oe_interaction_prompts_per_10min",
        },
    ],
}


def _language(language: str) -> str:
    return "pt-BR" if str(language or "en").lower().startswith("pt") else "en"


def templated_coaching(
    metrics: list[dict[str, Any]],
    *,
    language: str,
    evidence_id: str = "screen",
) -> dict[str, Any]:
    """Three observations titled from the numbers, three drills, one strength."""
    usable = [
        row
        for row in metrics
        if row.get("applicable") and row.get("value") is not None and str(row.get("id") or "")
    ]
    usable.sort(key=lambda row: str(row.get("id")))
    chosen = usable[:6]
    if len(chosen) < 3:
        chosen = [
            {"id": "sf_clean_transition_ratio", "value": 0, "applicable": True},
            {"id": "sf_signpost_ratio", "value": 0, "applicable": True},
            {"id": "oe_interaction_prompts_per_10min", "value": 0, "applicable": True},
        ]
    observations = []
    for row in chosen[:6]:
        metric_id = str(row["id"])
        value = row.get("value")
        observations.append(
            {
                "title": f"Metric: {metric_id} {value}",
                "detail": f"Measured {metric_id} at {value}.",
                "t": 0,
                "evidence_ids": [evidence_id],
            }
        )
    observations = observations[:6]
    while len(observations) < 3:
        observations.append(
            {
                "title": "Metric: screen_time",
                "detail": "Measured screen time is in the report.",
                "t": 0,
                "evidence_ids": [evidence_id],
            }
        )
    lang = _language(language)
    strength_title = "Você manteve a tela visível." if lang == "pt-BR" else "You kept a screen visible."
    return {
        "observations": observations[:6],
        "drills": [dict(item) for item in _DRILLS[lang]],
        "strengths": [{"title": strength_title, "evidence_ids": [evidence_id]}],
    }

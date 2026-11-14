"""Practice loop, online delivery signals, and talk-series comparison.

Population scores stay on scoring-config 1.0.0. These helpers describe
observable signals and drill attempts. They do not infer emotion, score
accent, or judge whether the subject matter is true.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, cast

DELIVERY_MODES = ("stage", "webinar", "online_talk", "recorded_video")
FILLER_TOKENS = ("um", "uh", "erm", "like", "tipo", "né", "ne", "ahh", "éh")
THROAT_CLEARING = (
    "that's a great question",
    "great question",
    "thanks for the question",
    "boa pergunta",
    "obrigado pela pergunta",
    "obrigada pela pergunta",
)

DRILLS: list[dict[str, Any]] = [
    {
        "id": "bluf_rewrite",
        "pillar": "message",
        "category_id": "core_message",
        "metrics": ["cm_message_identifiable"],
        "duration_s": 60,
        "capture": "text",
        "better_when": "lower_words",
        "title": {"en": "Say the claim in 15 words", "pt-BR": "Diga a tese em 15 palavras"},
        "instructions": {
            "en": "Write the point of the talk as one claim a listener could disagree with. Use 15 words or fewer.",
            "pt-BR": "Escreva o ponto da palestra como uma tese com a qual alguém poderia discordar. Use no máximo 15 palavras.",
        },
    },
    {
        "id": "hook_repeats",
        "pillar": "message",
        "category_id": "opening_close",
        "metrics": ["oc_hook_quality"],
        "duration_s": 45,
        "capture": "audio",
        "better_when": "lower",
        "title": {"en": "Open three ways", "pt-BR": "Abra de três jeitos"},
        "instructions": {
            "en": "Record the first 20 seconds three times. Start on the listener's problem, then stop.",
            "pt-BR": "Grave os primeiros 20 segundos três vezes. Comece pelo problema de quem ouve e pare.",
        },
    },
    {
        "id": "cut_list_rehearsal",
        "pillar": "presence_time",
        "category_id": "time_management",
        "metrics": ["tm_pct_of_slot"],
        "duration_s": 90,
        "capture": "text",
        "better_when": "lower_words",
        "title": {"en": "Cut list", "pt-BR": "Lista de cortes"},
        "instructions": {
            "en": "List what you will drop if the talk runs long, in the order you would cut it.",
            "pt-BR": "Liste o que você corta se o tempo estourar, na ordem em que cortaria.",
        },
    },
    {
        "id": "sixty_second_story",
        "pillar": "story_impact",
        "category_id": "storytelling",
        "metrics": ["sto_story_units"],
        "duration_s": 70,
        "capture": "audio",
        "better_when": "higher",
        "title": {"en": "60-second story", "pt-BR": "História de 60 segundos"},
        "instructions": {
            "en": "Tell one concrete story: who, what changed, and why it matters. Stop at 60 seconds.",
            "pt-BR": "Conte uma história concreta: quem, o que mudou e por que importa. Pare aos 60 segundos.",
        },
    },
    {
        "id": "what_so_what_now_what",
        "pillar": "story_impact",
        "category_id": "impact",
        "metrics": ["imp_cta_strength"],
        "duration_s": 90,
        "capture": "text",
        "better_when": "higher",
        "title": {"en": "What, so what, now what", "pt-BR": "O quê, e daí, e agora"},
        "instructions": {
            "en": "Write three lines: what happened, why the listener should care, and what they should do next.",
            "pt-BR": "Escreva três linhas: o que aconteceu, por que importa para quem ouve e o que essa pessoa faz em seguida.",
        },
    },
    {
        "id": "assertion_titles",
        "pillar": "visuals",
        "category_id": "visual_aids",
        "metrics": ["va_assertion_headline_ratio"],
        "duration_s": 90,
        "capture": "text",
        "better_when": "higher",
        "title": {"en": "Assertion headlines", "pt-BR": "Títulos que afirmam"},
        "instructions": {
            "en": "Rewrite each slide title as a sentence of 12 words or fewer. One title per line.",
            "pt-BR": "Reescreva cada título de slide como uma frase de até 12 palavras. Um título por linha.",
        },
    },
    {
        "id": "five_word_cue",
        "pillar": "visuals",
        "category_id": "visual_aids",
        "metrics": ["va_reading_ratio"],
        "duration_s": 60,
        "capture": "text",
        "better_when": "lower_words",
        "title": {"en": "Five-word cue card", "pt-BR": "Cartão de cinco palavras"},
        "instructions": {
            "en": "Write the cue you will glance at instead of reading the slide. Five words or fewer.",
            "pt-BR": "Escreva a deixa que você olha em vez de ler o slide. No máximo cinco palavras.",
        },
    },
    {
        "id": "pause_instead_of_um",
        "pillar": "voice",
        "category_id": "fluency",
        "metrics": ["fl_filler_sounds_per_min"],
        "duration_s": 60,
        "capture": "audio",
        "better_when": "lower",
        "title": {"en": "Pause instead of um", "pt-BR": "Pausa no lugar do hum"},
        "instructions": {
            "en": "Speak for one minute on your opening. When you need a word, pause. Do not fill the gap.",
            "pt-BR": "Fale um minuto sobre a abertura. Quando faltar uma palavra, pause. Não preencha o vão.",
        },
    },
    {
        "id": "three_readings",
        "pillar": "voice",
        "category_id": "vocal_variety",
        "metrics": ["vv_monotone_windows_ratio"],
        "duration_s": 90,
        "capture": "audio",
        "better_when": "lower",
        "title": {"en": "Three readings", "pt-BR": "Três leituras"},
        "instructions": {
            "en": "Read one paragraph flat, then with an exaggerated rise and fall, then once in a natural voice with one stressed word per sentence.",
            "pt-BR": "Leia um parágrafo reto, depois com subida e descida exageradas, e uma vez em voz natural com uma palavra destacada por frase.",
        },
    },
    {
        "id": "stress_shift",
        "pillar": "voice",
        "category_id": "vocal_variety",
        "metrics": ["vv_emphasis_rate_per_min"],
        "duration_s": 60,
        "capture": "audio",
        "better_when": "higher",
        "title": {"en": "Move the stress", "pt-BR": "Mude a ênfase"},
        "instructions": {
            "en": "Say the same sentence four times, stressing a different word each time.",
            "pt-BR": "Diga a mesma frase quatro vezes, destacando uma palavra diferente a cada vez.",
        },
    },
    {
        "id": "one_thought_one_person",
        "pillar": "body",
        "category_id": "eye_contact",
        "metrics": ["ec_audience_facing_ratio"],
        "duration_s": 60,
        "capture": "video",
        "better_when": "higher",
        "title": {"en": "One thought, one direction", "pt-BR": "Um pensamento, uma direção"},
        "instructions": {
            "en": "Deliver one sentence while your face stays toward the lens or one seat, then move. Record with the camera on.",
            "pt-BR": "Entregue uma frase com o rosto virado para a lente ou para um lugar da plateia, e só então mude. Grave com a câmera ligada.",
        },
    },
    {
        "id": "number_and_size_gestures",
        "pillar": "body",
        "category_id": "gestures_body",
        "metrics": ["gb_gesture_speech_sync"],
        "duration_s": 60,
        "capture": "video",
        "better_when": "higher",
        "title": {"en": "Number and size", "pt-BR": "Número e tamanho"},
        "instructions": {
            "en": "Say two numbers and one size comparison. Let the hands show the number and the size, then return to rest.",
            "pt-BR": "Diga dois números e uma comparação de tamanho. As mãos mostram o número e o tamanho, e voltam ao descanso.",
        },
    },
    {
        "id": "energy_ladder",
        "pillar": "presence_time",
        "category_id": "energy_presence",
        "metrics": ["ep_energy_trajectory"],
        "duration_s": 60,
        "capture": "audio",
        "better_when": "higher",
        "title": {"en": "Energy ladder", "pt-BR": "Escada de energia"},
        "instructions": {
            "en": "Say one line quietly, once at a medium level, and once at the level you want for the close. Stay on the words.",
            "pt-BR": "Diga uma frase baixa, uma vez em nível médio e uma vez no nível que você quer no fecho. Fique nas palavras.",
        },
    },
    {
        "id": "last_20_checkpoint",
        "pillar": "presence_time",
        "category_id": "time_management",
        "metrics": ["tm_end_rush_events"],
        "duration_s": 90,
        "capture": "audio",
        "better_when": "lower",
        "title": {"en": "Last 20 percent", "pt-BR": "Últimos 20 por cento"},
        "instructions": {
            "en": "Rehearse only the closing fifth of the talk at the pace you want when time is short.",
            "pt-BR": "Ensaie só o quinto final da palestra no ritmo que você quer quando o tempo aperta.",
        },
    },
    {
        "id": "answer_first",
        "pillar": "presence_time",
        "category_id": "qa",
        "metrics": ["qa_answer_first_ratio"],
        "duration_s": 90,
        "capture": "text",
        "better_when": "higher",
        "title": {"en": "Answer first", "pt-BR": "Resposta primeiro"},
        "instructions": {
            "en": "Write the answer in the first sentence, then one reason, then the link back to your claim. Skip the thank-you opening.",
            "pt-BR": "Escreva a resposta na primeira frase, depois um motivo e o retorno à sua tese. Pule o agradecimento de abertura.",
        },
    },
]


def drill_by_id(drill_id: str) -> dict[str, Any] | None:
    for drill in DRILLS:
        if drill["id"] == drill_id:
            return drill
    return None


def localize_drill(drill: dict[str, Any], locale: str) -> dict[str, Any]:
    lang = "pt-BR" if str(locale).lower().startswith("pt") else "en"
    return {
        "id": drill["id"],
        "pillar": drill["pillar"],
        "category_id": drill["category_id"],
        "metrics": list(drill["metrics"]),
        "duration_s": drill["duration_s"],
        "capture": drill["capture"],
        "better_when": drill["better_when"],
        "title": drill["title"][lang],
        "instructions": drill["instructions"][lang],
    }


def list_drills(locale: str = "en", category_id: str | None = None) -> list[dict[str, Any]]:
    rows = [localize_drill(drill, locale) for drill in DRILLS]
    if category_id:
        rows = [row for row in rows if row["category_id"] == category_id]
    return rows


def _words(text: str) -> list[str]:
    return re.findall(r"\S+", text.strip())


def _filler_count(text: str) -> int:
    tokens = [token.strip(".,!?;:").lower() for token in _words(text)]
    return sum(1 for token in tokens if token in FILLER_TOKENS)


def score_text_drill(drill_id: str, text: str) -> dict[str, Any]:
    """Score a written drill from the text alone. Missing text stays N/A."""
    drill = drill_by_id(drill_id)
    cleaned = (text or "").strip()
    if drill is None:
        return {"applicable": False, "na_reason": "Unknown drill.", "score": None}
    if not cleaned:
        return {
            "applicable": False,
            "na_reason": "Write the drill before it can be scored.",
            "score": None,
        }
    words = _words(cleaned)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    metrics: dict[str, Any] = {"words": len(words), "lines": len(lines)}
    score = 40
    note = "Counted from the text you saved."
    if drill_id == "bluf_rewrite":
        score = 90 if 3 <= len(words) <= 15 else 45 if len(words) <= 25 else 20
        note = "A claim of 15 words or fewer is the target."
    elif drill_id == "five_word_cue":
        score = 90 if 1 <= len(words) <= 5 else 40
        note = "The cue card target is five words or fewer."
    elif drill_id == "cut_list_rehearsal":
        score = 85 if len(lines) >= 2 else 40
        note = "A cut list needs at least two items in order."
    elif drill_id == "what_so_what_now_what":
        score = 90 if len(lines) >= 3 else 35
        note = "Three lines: what, so what, now what."
    elif drill_id == "assertion_titles":
        short = [line for line in lines if 1 <= len(_words(line)) <= 12]
        ratio = (len(short) / len(lines)) if lines else 0
        metrics["assertion_line_ratio"] = round(ratio, 2)
        score = int(round(40 + 50 * ratio))
        note = "Each line should be a sentence of 12 words or fewer."
    elif drill_id == "answer_first":
        return score_answer(cleaned)
    else:
        fillers = _filler_count(cleaned)
        metrics["fillers"] = fillers
        score = 80 if fillers == 0 else max(20, 80 - fillers * 15)
        note = "Filler tokens in the saved text were counted. This is not an accent score."
    return {
        "applicable": True,
        "drill_id": drill_id,
        "score": score,
        "metrics": metrics,
        "note": note,
        "na_reason": None,
    }


def score_answer(text: str) -> dict[str, Any]:
    """Answer-first shape: the answer is the first sentence, then a reason."""
    cleaned = text.strip()
    if not cleaned:
        return {
            "applicable": False,
            "na_reason": "Write an answer before it can be scored.",
            "score": None,
        }
    lowered = cleaned.lower()
    throat = any(phrase in lowered[:80] for phrase in THROAT_CLEARING)
    first = re.split(r"[.!?]", cleaned, maxsplit=1)[0]
    first_words = len(_words(first))
    total = len(_words(cleaned))
    in_band = 8 <= total <= 180 and first_words <= 25 and not throat
    score = 85 if in_band else 55 if not throat and first_words <= 40 else 30
    return {
        "applicable": True,
        "drill_id": "answer_first",
        "score": score,
        "metrics": {
            "first_sentence_words": first_words,
            "words": total,
            "throat_clearing": throat,
        },
        "note": "The first sentence should be the answer. Thank-you openings wait.",
        "na_reason": None,
    }


def score_transcript_drill(
    drill_id: str, transcript: str, duration_s: float | None
) -> dict[str, Any]:
    """Score an audio drill from a transcript. No transcript stays N/A."""
    drill = drill_by_id(drill_id)
    if drill is None:
        return {"applicable": False, "na_reason": "Unknown drill.", "score": None}
    cleaned = (transcript or "").strip()
    if not cleaned:
        return {
            "applicable": False,
            "na_reason": "This take has no transcript yet, so the drill score is N/A.",
            "score": None,
        }
    words = _words(cleaned)
    fillers = _filler_count(cleaned)
    minutes = max((duration_s or 60) / 60.0, 1 / 60)
    per_min = fillers / minutes
    wpm = len(words) / minutes
    metrics = {
        "words": len(words),
        "fillers": fillers,
        "fillers_per_min": round(per_min, 2),
        "wpm": round(wpm, 1),
        "duration_s": duration_s,
    }
    if drill["better_when"] == "lower":
        score = 90 if per_min <= 2 else 70 if per_min <= 5 else 40
    else:
        score = 80 if 90 <= wpm <= 170 else 55
    return {
        "applicable": True,
        "drill_id": drill_id,
        "score": score,
        "metrics": metrics,
        "note": "Counted from the words in this take. Pace and fillers are observable. Accent is not scored.",
        "na_reason": None,
    }


def attempt_delta(
    current: float | None, previous: float | None, better_when: str
) -> dict[str, Any] | None:
    if current is None or previous is None:
        return None
    delta = float(current) - float(previous)
    if better_when == "lower":
        improved = delta < 0
    elif better_when == "higher":
        improved = delta > 0
    else:
        improved = abs(current) <= abs(previous)
    return {"previous": previous, "current": current, "delta": delta, "improved": improved}


def baseline_sentence(value: float | None, median: float | None) -> str | None:
    """Coaching line after a personal median exists. The population score stays."""
    if value is None or median is None:
        return None
    if value < median:
        relation = "below"
    elif value > median:
        relation = "above"
    else:
        relation = "on"
    return (
        f"This take is {relation} your personal median for this signal. "
        "The report score remains the population score."
    )


def weekly_plan(
    *,
    categories: list[dict[str, Any]],
    goals: list[dict[str, Any]],
    drills: list[dict[str, Any]] | None = None,
    talk_date: date | None = None,
    today: date | None = None,
    locale: str = "en",
) -> dict[str, Any]:
    """Three drills from the weakest applicable categories, plus open goals."""
    today = today or date.today()
    catalog = drills if drills is not None else list_drills(locale)
    applicable = [
        row
        for row in categories
        if row.get("applicable", True) and isinstance(row.get("score"), (int, float))
    ]
    applicable.sort(key=lambda row: float(row["score"]))
    items: list[dict[str, Any]] = []
    used: set[str] = set()
    for row in applicable:
        if len(items) >= 3:
            break
        match = next(
            (
                drill
                for drill in catalog
                if drill["category_id"] == row.get("category_id") and drill["id"] not in used
            ),
            None,
        )
        if match is None:
            continue
        used.add(match["id"])
        items.append(
            {
                "kind": "drill",
                "drill_id": match["id"],
                "title": match["title"],
                "category_id": row.get("category_id"),
                "category_score": row.get("score"),
                "duration_s": match["duration_s"],
            }
        )
    for goal in goals:
        if goal.get("achieved_at"):
            continue
        items.append(
            {
                "kind": "goal",
                "goal_id": goal.get("id"),
                "metric_id": goal.get("metric_id"),
                "category_id": goal.get("category_id"),
                "target": goal.get("target"),
                "comparator": goal.get("comparator"),
            }
        )
    if talk_date is not None:
        days = (talk_date - today).days
        items.insert(
            0,
            {
                "kind": "talk_date",
                "talk_date": talk_date.isoformat(),
                "days_until": days,
            },
        )
    return {
        "week_of": today.isoformat(),
        "items": items,
        "reason": None if items else "Score a talk or set a goal to fill this week.",
    }


def series_compare(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Oldest to newest takes that share language and scoring-config major."""
    ordered = list(rows)
    if len(ordered) < 2:
        return {"ready": False, "reason": "Record at least two takes of this talk.", "deltas": {}}
    comparable: list[dict[str, Any]] = []
    ref_lang = ordered[0].get("language")
    ref_major = str(ordered[0].get("config_version") or "1").split(".")[0]
    for row in ordered:
        major = str(row.get("config_version") or "1").split(".")[0]
        if row.get("language") == ref_lang and major == ref_major:
            comparable.append(row)
    if len(comparable) < 2:
        return {
            "ready": False,
            "reason": "Takes need the same language and scoring-config major version.",
            "deltas": {},
        }
    first, last = comparable[0], comparable[-1]
    deltas: dict[str, float] = {}
    first_cats = first.get("categories") or {}
    last_cats = last.get("categories") or {}
    for key in sorted(set(first_cats) & set(last_cats)):
        a, b = first_cats.get(key), last_cats.get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            deltas[key] = round(float(b) - float(a), 2)
    overall_delta = None
    if isinstance(first.get("overall"), (int, float)) and isinstance(
        last.get("overall"), (int, float)
    ):
        overall_delta = round(float(last["overall"]) - float(first["overall"]), 2)
    return {
        "ready": True,
        "reason": None,
        "from_session_id": first.get("session_id"),
        "to_session_id": last.get("session_id"),
        "overall_delta": overall_delta,
        "deltas": deltas,
        "takes": len(comparable),
    }


def transcript_signals(text: str) -> dict[str, Any]:
    """Observable text signals for a corrected transcript. The session score stays."""
    cleaned = (text or "").strip()
    if not cleaned:
        return {"applicable": False, "na_reason": "The corrected transcript is empty."}
    sentences = [part.strip() for part in re.split(r"[.!?]+", cleaned) if part.strip()]
    lengths = [len(_words(part)) for part in sentences] or [0]
    long_ratio = sum(1 for n in lengths if n > 28) / len(lengths)
    words = _words(cleaned)
    fillers = _filler_count(cleaned)
    per_100 = (fillers * 100 / len(words)) if words else 0
    return {
        "applicable": True,
        "mean_sentence_words": round(sum(lengths) / len(lengths), 1),
        "long_sentence_ratio": round(long_ratio, 2),
        "filler_per_100": round(per_100, 2),
        "words": len(words),
        "note": "These signals describe the corrected transcript. The session score stays on the original analysis.",
    }


def deck_review(slides: list[dict[str, Any]]) -> dict[str, Any]:
    """Slide-text signals. They do not say whether the content is correct."""
    texts = []
    for slide in slides:
        if isinstance(slide, str):
            texts.append(slide.strip())
        elif isinstance(slide, dict):
            texts.append(str(slide.get("text") or slide.get("title") or "").strip())
    texts = [text for text in texts if text]
    if not texts:
        return {"applicable": False, "na_reason": "No slide text was readable."}
    counts = [len(_words(text)) for text in texts]
    counts_sorted = sorted(counts)
    mid = counts_sorted[len(counts_sorted) // 2]
    dense = sum(1 for count in counts if count > 40) / len(counts)
    titles = []
    for text in texts:
        first = text.splitlines()[0] if text else ""
        titles.append(first)
    assertions = 0
    for title in titles:
        n = len(_words(title))
        if 4 <= n <= 12 and not title.lower().startswith(
            ("overview", "agenda", "sumário", "visão geral")
        ):
            assertions += 1
    ratio = assertions / len(titles)
    return {
        "applicable": True,
        "slide_count": len(texts),
        "words_per_slide_median": mid,
        "dense_slide_ratio": round(dense, 2),
        "assertion_headline_ratio": round(ratio, 2),
        "note": "Counted from slide text only. This review does not judge whether the material is true.",
    }


def propose_layout(delivery_mode: str, camera_setup: str) -> dict[str, Any]:
    """Heuristic regions. Other participants are never given a face region."""
    mode = delivery_mode if delivery_mode in DELIVERY_MODES else "stage"
    setup = camera_setup or "stage"
    if mode == "stage" or setup == "audio_only":
        kind = "no_video" if setup == "audio_only" else "stage_wide"
        return {
            "delivery_mode": mode,
            "kind": kind,
            "confidence": 0.9,
            "needs_review": False,
            "segments": [
                {
                    "t_start": 0,
                    "t_end": None,
                    "kind": kind,
                    "regions": [{"role": "camera", "x": 0, "y": 0, "w": 1, "h": 1}]
                    if kind != "no_video"
                    else [],
                }
            ],
        }
    if setup == "to_camera" or mode == "recorded_video" and setup == "to_camera":
        return _segment_layout(mode, "camera_full", 0.8, False, camera_full=True)
    if setup == "screen_recording" and mode == "stage":
        return _segment_layout(mode, "screen_full", 0.7, False, camera_full=False)
    # Online composite: camera tile bottom-right, screen is the rest. Review until a person detector confirms it.
    return {
        "delivery_mode": mode,
        "kind": "composite",
        "confidence": 0.55,
        "needs_review": True,
        "segments": [
            {
                "t_start": 0,
                "t_end": None,
                "kind": "composite",
                "regions": [
                    {"role": "screen", "x": 0.0, "y": 0.0, "w": 0.72, "h": 1.0},
                    {"role": "camera", "x": 0.72, "y": 0.62, "w": 0.26, "h": 0.34},
                    {"role": "ignore", "x": 0.72, "y": 0.0, "w": 0.28, "h": 0.62},
                ],
            }
        ],
    }


def _segment_layout(
    mode: str, kind: str, confidence: float, review: bool, *, camera_full: bool
) -> dict[str, Any]:
    if camera_full:
        regions = [{"role": "camera", "x": 0, "y": 0, "w": 1, "h": 1}]
    else:
        regions = [{"role": "screen", "x": 0, "y": 0, "w": 1, "h": 1}]
    return {
        "delivery_mode": mode,
        "kind": kind,
        "confidence": confidence,
        "needs_review": review,
        "segments": [{"t_start": 0, "t_end": None, "kind": kind, "regions": regions}],
    }


def region_from_normalized(roi: dict[str, Any], width: int, height: int) -> dict[str, Any]:
    """Pixel box from a 0–1 region. Empty boxes are not returned as a crop."""
    width = max(int(width), 1)
    height = max(int(height), 1)
    x = max(0, min(width - 1, int(float(roi.get("x", 0)) * width)))
    y = max(0, min(height - 1, int(float(roi.get("y", 0)) * height)))
    w = max(1, int(float(roi.get("w", 1)) * width))
    h = max(1, int(float(roi.get("h", 1)) * height))
    if x + w > width:
        w = width - x
    if y + h > height:
        h = height - y
    return {"x": x, "y": y, "w": w, "h": h, "role": roi.get("role"), "method": "layout_region"}


def dead_air_seconds(pauses: list[Any] | None, minimum_s: float = 2.0) -> float | None:
    if not pauses:
        return None
    total = 0.0
    found = False
    for pause in pauses:
        if not isinstance(pause, dict):
            continue
        if "duration_s" in pause:
            duration = float(pause["duration_s"])
        elif "start" in pause and "end" in pause:
            duration = float(pause["end"]) - float(pause["start"])
        elif "t_start" in pause and "t_end" in pause:
            duration = float(pause["t_end"]) - float(pause["t_start"])
        else:
            continue
        found = True
        if duration >= minimum_s:
            total += duration
    return total if found else None


def _band_score(value: float, good: float, poor: float, *, higher_is_better: bool) -> int:
    if higher_is_better:
        if value >= good:
            return 85
        if value <= poor:
            return 35
    else:
        if value <= good:
            return 85
        if value >= poor:
            return 35
    return 60


def online_report(
    *,
    delivery_mode: str,
    layout: dict[str, Any] | None,
    duration_s: float | None = None,
    slide_count: int | None = None,
    dead_air_s: float | None = None,
    qa_in_slot: bool = False,
) -> dict[str, Any]:
    """Four heuristic online signals. Stage mode returns them as N/A.

    The population overall is not in this payload.
    """
    mode = delivery_mode if delivery_mode in DELIVERY_MODES else "stage"
    base: dict[str, Any] = {
        "delivery_mode": mode,
        "config_version": "1.1.0",
        "basis": "H",
        "population_overall": None,
        "note": "These signals describe camera, screen, and silence. They do not judge whether the content is true.",
    }
    if mode == "stage":
        na = {
            "applicable": False,
            "score": None,
            "na_reason": "Stage delivery uses the existing report.",
        }
        base["signals"] = {
            "screen_flow": na,
            "camera_presence": na,
            "production_quality": na,
            "audience_prompts": na,
        }
        return base
    duration = (
        float(duration_s) if isinstance(duration_s, (int, float)) and duration_s > 0 else None
    )
    layout = layout or {}
    kind = layout.get("kind")
    camera = _role_box(layout, "camera")
    signals: dict[str, Any] = {}
    if duration and slide_count is not None:
        per_min = (slide_count / duration) * 60
        dead_ratio = (dead_air_s / duration) if dead_air_s is not None else None
        flow = _band_score(per_min, 0.4, 8, higher_is_better=False)
        if dead_ratio is not None and dead_ratio > 0.12:
            flow = min(flow, 45)
        signals["screen_flow"] = {
            "applicable": True,
            "score": flow,
            "transitions_per_min": round(per_min, 2),
            "dead_air_s": dead_air_s,
            "basis": "H",
        }
    else:
        signals["screen_flow"] = {
            "applicable": False,
            "score": None,
            "na_reason": "Screen changes are not measured yet.",
        }
    if camera and kind in {"composite", "camera_full"}:
        area = float(camera.get("w", 0)) * float(camera.get("h", 0))
        presence = 80 if kind == "camera_full" or 0.04 <= area <= 0.2 else 50
        signals["camera_presence"] = {
            "applicable": True,
            "score": presence,
            "camera_area": round(area, 3),
            "basis": "H",
            "note": "Head orientation is not eye contact. Other people in the frame are not measured.",
        }
    else:
        signals["camera_presence"] = {
            "applicable": False,
            "score": None,
            "na_reason": "No camera region is marked.",
        }
    confidence = layout.get("confidence")
    if isinstance(confidence, (int, float)):
        signals["production_quality"] = {
            "applicable": True,
            "score": 80 if confidence >= 0.8 else 55,
            "layout_confidence": confidence,
            "basis": "H",
        }
    else:
        signals["production_quality"] = {
            "applicable": False,
            "score": None,
            "na_reason": "Layout confidence is missing.",
        }
    if mode == "recorded_video":
        signals["audience_prompts"] = {
            "applicable": False,
            "score": None,
            "na_reason": "A recorded video has no live question segment.",
        }
    elif qa_in_slot:
        signals["audience_prompts"] = {
            "applicable": True,
            "score": 70,
            "basis": "H",
            "note": "A question segment was declared. Answer shape is scored in the answer-first drill.",
        }
    else:
        signals["audience_prompts"] = {
            "applicable": False,
            "score": None,
            "na_reason": "No question segment was declared for this session.",
        }
    base["signals"] = signals
    return base


def _role_box(layout: dict[str, Any], role: str) -> dict[str, Any] | None:
    segments = layout.get("segments") or []
    if not segments:
        return None
    first = segments[0]
    if not isinstance(first, dict):
        return None
    regions = first.get("regions") or []
    if not isinstance(regions, list):
        return None
    for region in regions:
        if isinstance(region, dict) and region.get("role") == role:
            return cast(dict[str, Any], region)
    return None


def crop_frame(frame: Any, roi: dict[str, Any]) -> Any:
    """Slice an array image to a normalized region. Other pixels are dropped."""
    height, width = frame.shape[:2]
    box = region_from_normalized(roi, width, height)
    return frame[box["y"] : box["y"] + box["h"], box["x"] : box["x"] + box["w"]]


def evaluate_quota(
    *,
    storage_bytes: int,
    incoming_bytes: int,
    active_jobs: int,
    monthly_seconds: int,
    reserved_seconds: int,
    storage_limit: int,
    active_limit: int,
    monthly_limit: int,
) -> dict[str, Any]:
    """Allow an upload when storage, concurrency, and the minutes cap all fit."""
    if active_jobs >= active_limit:
        return {
            "allowed": False,
            "reason": "An analysis is already running. Wait for it to finish.",
        }
    if storage_bytes + incoming_bytes > storage_limit:
        return {"allowed": False, "reason": "This account is at its storage limit."}
    if monthly_seconds + reserved_seconds > monthly_limit:
        return {"allowed": False, "reason": "This account is at its monthly minutes limit."}
    return {
        "allowed": True,
        "reason": None,
        "storage_bytes": storage_bytes,
        "monthly_seconds": monthly_seconds,
        "active_jobs": active_jobs,
    }


def parse_day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None

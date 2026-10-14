from metrics.fluency_disambig import disambiguate_transcript, disambiguate_words


def _hit(sidecar: dict, token: str) -> dict:
    matches = [item for item in sidecar["disambiguations"] if item["token"] == token]
    assert matches, f"missing {token} in {sidecar['disambiguations']}"
    return matches[0]


def test_ptbr_ne_tipo_entao_clause_rules():
    transcript = {
        "language": "pt-BR",
        "segments": [
            {
                "start": 0.0,
                "end": 12.0,
                "words": [
                    {"word": "Legal", "start": 0.0, "end": 0.4},
                    {"word": "né", "start": 0.4, "end": 0.7},
                    {"word": "foi", "start": 1.0, "end": 1.3},
                    {"word": "tipo", "start": 1.3, "end": 1.6},
                    {"word": "assim", "start": 1.6, "end": 2.0},
                    {"word": "estranho", "start": 2.0, "end": 2.5},
                    {"word": "então", "start": 3.0, "end": 3.4},
                    {"word": "vamos", "start": 3.4, "end": 3.8},
                    {"word": "começar", "start": 3.8, "end": 4.4},
                    {"word": "isso", "start": 5.0, "end": 5.3},
                    {"word": "é", "start": 5.3, "end": 5.5},
                    {"word": "um", "start": 5.5, "end": 5.7},
                    {"word": "tipo", "start": 5.7, "end": 6.0},
                    {"word": "de", "start": 6.0, "end": 6.2},
                    {"word": "reunião", "start": 6.2, "end": 6.8},
                    {"word": "a", "start": 8.0, "end": 8.2},
                    {"word": "gente", "start": 8.2, "end": 8.5},
                    {"word": "então", "start": 8.5, "end": 8.9},
                    {"word": ",", "start": 8.9, "end": 9.0},
                    {"word": "parou", "start": 9.0, "end": 9.5},
                ],
            }
        ],
    }
    sidecar = disambiguate_transcript(transcript)
    tokens = {item["token"] for item in sidecar["disambiguations"]}
    assert {"né", "tipo", "então"}.issubset(tokens)
    assert _hit(sidecar, "né")["is_filler"] is True
    tipo_hits = [item for item in sidecar["disambiguations"] if item["token"] == "tipo"]
    assert tipo_hits[0]["is_filler"] is True
    assert tipo_hits[1]["is_filler"] is False
    entao_hits = [item for item in sidecar["disambiguations"] if item["token"] == "então"]
    assert entao_hits[0]["is_filler"] is False
    assert entao_hits[1]["is_filler"] is True
    assert sidecar["disambiguations"][0]["method"] == "heuristic_v1"


def test_en_like_comparison_is_lexical():
    words = [
        {"word": "It", "start": 0.0, "end": 0.2},
        {"word": "looks", "start": 0.2, "end": 0.4},
        {"word": "like", "start": 0.4, "end": 0.6},
        {"word": "rain", "start": 0.6, "end": 0.9},
        {"word": "I", "start": 1.0, "end": 1.1},
        {"word": "was", "start": 1.1, "end": 1.3},
        {"word": "like", "start": 1.3, "end": 1.5},
        {"word": ",", "start": 1.5, "end": 1.6},
        {"word": "wait", "start": 1.6, "end": 1.9},
    ]
    sidecar = disambiguate_words(words, language="en")
    likes = [item for item in sidecar["disambiguations"] if item["token"] == "like"]
    assert likes[0]["is_filler"] is False
    assert likes[1]["is_filler"] is True

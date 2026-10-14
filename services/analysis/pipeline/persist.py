"""Persist fusion/report artifacts into the result tables (SPEC §7.3)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (TypeError, ValueError):
        return False


def persist_analysis_result(
    *,
    job_id: str,
    analysis: dict[str, Any],
    transcript: Optional[dict[str, Any]] = None,
    database_url: Optional[str] = None,
) -> None:
    """Insert metric, category, overall, evidence, and insight rows.

    No-op when DATABASE_URL is unset or job_id is not a UUID (unit tests / smoke tmp).
    """
    database_url = database_url or os.getenv("DATABASE_URL")
    if not database_url or not _is_uuid(job_id):
        logger.info("Skipping DB persist for job %s", job_id)
        return

    engine = create_engine(database_url)
    now = datetime.utcnow()
    overall = analysis.get("overall") or {}
    session = analysis.get("session") or {}
    provenance = analysis.get("provenance") or {}

    with engine.begin() as conn:
        if transcript is not None:
            conn.execute(
                text(
                    """
                    INSERT INTO transcripts (
                        id, job_id, language, language_prob, asr_model,
                        words_uri, mean_word_prob, created_at
                    ) VALUES (
                        CAST(:id AS UUID), CAST(:job_id AS UUID), :language, :language_prob,
                        :asr_model, :words_uri, :mean_word_prob, :created_at
                    )
                    ON CONFLICT (job_id) DO UPDATE SET
                        language = EXCLUDED.language,
                        words_uri = EXCLUDED.words_uri,
                        mean_word_prob = EXCLUDED.mean_word_prob
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "job_id": job_id,
                    "language": transcript.get("language") or session.get("language") or "en",
                    "language_prob": transcript.get("language_probability") or transcript.get("language_prob"),
                    "asr_model": transcript.get("model") or transcript.get("asr_model"),
                    "words_uri": analysis.get("transcript_ref"),
                    "mean_word_prob": (analysis.get("quality") or {}).get("asr_mean_word_prob"),
                    "created_at": now,
                },
            )

        conn.execute(text("DELETE FROM metric_values WHERE job_id = CAST(:job_id AS UUID)"), {"job_id": job_id})
        for metric in analysis.get("metrics") or []:
            raw = metric.get("raw_value")
            raw_num = raw if isinstance(raw, (int, float)) else None
            conn.execute(
                text(
                    """
                    INSERT INTO metric_values (
                        id, job_id, metric_id, raw_value, unit, score, confidence,
                        source_key, details, created_at
                    ) VALUES (
                        CAST(:id AS UUID), CAST(:job_id AS UUID), :metric_id, :raw_value,
                        :unit, :score, :confidence, :source_key, CAST(:details AS JSONB), :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "job_id": job_id,
                    "metric_id": metric["id"],
                    "raw_value": raw_num,
                    "unit": metric.get("unit"),
                    "score": metric.get("score"),
                    "confidence": metric.get("confidence"),
                    "source_key": (metric.get("basis") or {}).get("source"),
                    "details": json.dumps({"raw_value": raw, "included": metric.get("included")}),
                    "created_at": now,
                },
            )

        conn.execute(text("DELETE FROM category_scores WHERE job_id = CAST(:job_id AS UUID)"), {"job_id": job_id})
        for category in analysis.get("categories") or []:
            conn.execute(
                text(
                    """
                    INSERT INTO category_scores (
                        id, job_id, category_id, score, level, confidence, applicable,
                        na_reason, weight_used, explanation, created_at
                    ) VALUES (
                        CAST(:id AS UUID), CAST(:job_id AS UUID), :category_id, :score, :level,
                        :confidence, :applicable, :na_reason, :weight_used,
                        CAST(:explanation AS JSONB), :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "job_id": job_id,
                    "category_id": category["id"],
                    "score": category.get("score"),
                    "level": category.get("level"),
                    "confidence": category.get("confidence"),
                    "applicable": category.get("applicable"),
                    "na_reason": category.get("na_reason"),
                    "weight_used": category.get("weight_used"),
                    "explanation": json.dumps(
                        {
                            "top_contributors": category.get("top_contributors"),
                            "counterfactual": category.get("counterfactual"),
                            "sources": category.get("sources"),
                        }
                    ),
                    "created_at": now,
                },
            )

        conn.execute(
            text(
                """
                INSERT INTO overall_scores (
                    job_id, overall, coverage, overall_confidence, display_band,
                    context_type, config_version, created_at
                ) VALUES (
                    CAST(:job_id AS UUID), :overall, :coverage, :overall_confidence,
                    :display_band, :context_type, :config_version, :created_at
                )
                ON CONFLICT (job_id) DO UPDATE SET
                    overall = EXCLUDED.overall,
                    coverage = EXCLUDED.coverage,
                    overall_confidence = EXCLUDED.overall_confidence,
                    display_band = EXCLUDED.display_band
                """
            ),
            {
                "job_id": job_id,
                "overall": overall.get("score"),
                "coverage": overall.get("coverage"),
                "overall_confidence": overall.get("confidence"),
                "display_band": overall.get("display_band"),
                "context_type": session.get("context_type"),
                "config_version": provenance.get("scoring_config_version"),
                "created_at": now,
            },
        )

        conn.execute(text("DELETE FROM evidence_items WHERE job_id = CAST(:job_id AS UUID)"), {"job_id": job_id})
        for item in analysis.get("evidence") or []:
            conn.execute(
                text(
                    """
                    INSERT INTO evidence_items (
                        id, job_id, category_id, metric_id, t_start, t_end, modality,
                        kind, quote, measurement, seg_ids, confidence, user_disputed,
                        dispute_note, created_at
                    ) VALUES (
                        CAST(:id AS UUID), CAST(:job_id AS UUID), :category_id, :metric_id,
                        :t_start, :t_end, :modality, :kind, :quote, CAST(:measurement AS JSONB),
                        CAST(:seg_ids AS TEXT[]), :confidence, :user_disputed, :dispute_note, :created_at
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"stagecoach:evidence:{job_id}:{item['id']}")),
                    "job_id": job_id,
                    "category_id": item.get("category_id"),
                    "metric_id": item.get("metric_id"),
                    "t_start": item.get("t_start"),
                    "t_end": item.get("t_end"),
                    "modality": item.get("modality"),
                    "kind": item.get("kind"),
                    "quote": item.get("quote") or item.get("text"),
                    "measurement": json.dumps(item.get("measurement")),
                    "seg_ids": item.get("seg_ids") or [],
                    "confidence": item.get("confidence"),
                    "user_disputed": bool(item.get("user_disputed")),
                    "dispute_note": None,
                    "created_at": now,
                },
            )

        conn.execute(text("DELETE FROM insights WHERE job_id = CAST(:job_id AS UUID)"), {"job_id": job_id})
        insights = analysis.get("insights") or {}
        for kind, rows in (
            ("strength", insights.get("strengths") or []),
            ("weakness", insights.get("weaknesses") or []),
            ("opportunity", insights.get("opportunities") or []),
        ):
            for rank, row in enumerate(rows, start=1):
                conn.execute(
                    text(
                        """
                        INSERT INTO insights (
                            id, job_id, type, rank, category_id, title, body_md, fix_md,
                            drill_ids, evidence_ids, created_at
                        ) VALUES (
                            CAST(:id AS UUID), CAST(:job_id AS UUID), :type, :rank, :category_id,
                            :title, :body_md, :fix_md, CAST(:drill_ids AS TEXT[]),
                            CAST(:evidence_ids AS TEXT[]), :created_at
                        )
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "job_id": job_id,
                        "type": kind,
                        "rank": rank,
                        "category_id": row.get("category_id"),
                        "title": row.get("title"),
                        "body_md": row.get("body"),
                        "fix_md": row.get("fix"),
                        "drill_ids": row.get("drill_ids") or [],
                        "evidence_ids": row.get("evidence_ids") or [],
                        "created_at": now,
                    },
                )
    logger.info("Persisted analysis rows for job %s", job_id)

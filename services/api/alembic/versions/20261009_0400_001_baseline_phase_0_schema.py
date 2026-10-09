"""baseline Phase 0 schema

Revision ID: 001
Revises: 
Create Date: 2026-10-09 04:00:00.000000

Phase 0 baseline migration: users, consents, sessions, media_assets, 
analysis_jobs, job_steps, scoring_configs per §7.3
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable required PostgreSQL extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(255)),
        sa.Column('locale', sa.String(10), nullable=False, server_default='en'),
        sa.Column('timezone', sa.String(50), server_default='UTC'),
        sa.Column(
            'accessibility_profile',
            postgresql.JSONB,
            comment='Disability/speech-difference preferences: seated, limited_mobility, '
                    'one_handed, speech_difference, prefers_no_video_metrics'
        ),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime, nullable=True, index=True),
    )

    # Create consents table (append-only)
    op.create_table(
        'consents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column(
            'purpose',
            sa.String(50),
            nullable=False,
            comment='video_analysis, expression_analysis, keep_detailed_tracking, research_use, benchmarks'
        ),
        sa.Column('granted', sa.Boolean, nullable=False),
        sa.Column('version', sa.String(64), nullable=False, comment='Policy text hash'),
        sa.Column('granted_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('revoked_at', sa.DateTime, nullable=True),
        sa.Column('ip_country', sa.String(2), nullable=True, comment='ISO 3166-1 alpha-2'),
    )
    op.create_index('idx_consents_user_purpose', 'consents', ['user_id', 'purpose', 'granted_at'])

    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('talk_plan_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Link to talk plan (Phase 3)'),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column(
            'context_type',
            sa.String(50),
            nullable=False,
            comment='keynote, breakout, exec_briefing, sales_pitch, virtual_meeting, class_academic, other'
        ),
        sa.Column('language', sa.String(10), nullable=False, comment='en, pt-BR, auto'),
        sa.Column('slot_min', sa.Integer, nullable=True, comment='Target slot length in minutes'),
        sa.Column('qa_in_slot', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('audience_desc', sa.Text, nullable=True),
        sa.Column(
            'camera_setup',
            sa.String(50),
            nullable=False,
            comment='stage, to_camera, screen_recording, audio_only'
        ),
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='uploaded',
            comment='uploaded, processing, ready, partial, failed'
        ),
        sa.Column('primary_speaker_label', sa.String(50), nullable=True, comment='For diarization'),
        sa.Column('focus_areas', postgresql.ARRAY(sa.String), nullable=True, comment='Up to 3 focus category IDs'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Create media_assets table
    op.create_table(
        'media_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column(
            'kind',
            sa.String(50),
            nullable=False,
            comment='original, analysis_proxy, playback, audio16k, deck, keyframe, sprite'
        ),
        sa.Column('storage_uri', sa.String(512), nullable=False, comment='S3/MinIO URI'),
        sa.Column('bytes', sa.Integer, nullable=False),
        sa.Column('duration_s', sa.Float, nullable=True, comment='For video/audio'),
        sa.Column('codec_info', postgresql.JSONB, nullable=True),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('retention_until', sa.DateTime, nullable=False, comment='When to delete from storage'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_media_assets_session_kind', 'media_assets', ['session_id', 'kind'])
    op.create_index('idx_media_assets_retention', 'media_assets', ['retention_until'])

    # Create analysis_jobs table
    op.create_table(
        'analysis_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('scoring_config_version', sa.String(20), nullable=False),
        sa.Column('pipeline_version', sa.String(20), nullable=False),
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='pending',
            comment='pending, running, completed, failed'
        ),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('finished_at', sa.DateTime, nullable=True),
        sa.Column('error', postgresql.JSONB, nullable=True, comment='Error details if failed'),
        sa.Column('cost', postgresql.JSONB, nullable=True, comment='Tokens, GPU seconds, etc.'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now(), index=True),
    )

    # Create job_steps table
    op.create_table(
        'job_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column(
            'stage',
            sa.String(50),
            nullable=False,
            comment='ingest, asr, audio_features, vision, slides, content_llm, fusion_scoring, report'
        ),
        sa.Column('stage_version', sa.String(20), nullable=False),
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='pending',
            comment='pending, running, completed, partial, failed'
        ),
        sa.Column('attempt', sa.Integer, nullable=False, server_default='1'),
        sa.Column('input_hash', sa.String(64), nullable=True, comment='Hash of inputs for idempotency'),
        sa.Column('output_uris', postgresql.JSONB, nullable=True, comment='Storage URIs of outputs'),
        sa.Column(
            'metrics',
            postgresql.JSONB,
            nullable=True,
            comment='duration_s, frames_processed, tokens_used, etc.'
        ),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('finished_at', sa.DateTime, nullable=True),
        sa.Column('error', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_job_steps_job_stage', 'job_steps', ['job_id', 'stage'])

    # Create scoring_configs table
    op.create_table(
        'scoring_configs',
        sa.Column('version', sa.String(20), primary_key=True, comment='Semantic version (e.g., 1.0.0)'),
        sa.Column('yaml', sa.Text, nullable=False, comment='Full YAML content'),
        sa.Column('sha256', sa.String(64), nullable=False, unique=True),
        sa.Column('notes', sa.Text, nullable=True, comment='Change notes for this version'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Seed scoring_configs with v1.0.0
    # This will be populated by a separate seed script
    pass


def downgrade() -> None:
    op.drop_table('job_steps')
    op.drop_table('analysis_jobs')
    op.drop_table('media_assets')
    op.drop_table('sessions')
    op.drop_table('consents')
    op.drop_table('users')
    op.drop_table('scoring_configs')
    
    op.execute('DROP EXTENSION IF EXISTS "citext"')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')

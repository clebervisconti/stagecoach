"""update status values for DAG orchestration

Revision ID: 002_dag_status
Revises: 001
Create Date: 2026-10-09 22:30:00

Per issues #18 and #19:
- Update job_step.status to use "succeeded" instead of "completed"
- Update analysis_job.status to include "partial" state
- Update session.status to start with "created" state
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_dag_status'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update job_steps: completed -> succeeded
    op.execute("""
        UPDATE job_steps SET status = 'succeeded' WHERE status = 'completed';
    """)
    
    # Update analysis_jobs: add partial support (no data migration needed)
    # Update sessions: uploaded -> created (if any)
    op.execute("""
        UPDATE sessions SET status = 'created' WHERE status = 'uploaded';
    """)


def downgrade() -> None:
    # Reverse: succeeded -> completed
    op.execute("""
        UPDATE job_steps SET status = 'completed' WHERE status = 'succeeded';
    """)
    
    # Reverse: created -> uploaded
    op.execute("""
        UPDATE sessions SET status = 'uploaded' WHERE status = 'created';
    """)

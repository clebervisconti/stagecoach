"""model_registry for vision provenance

Revision ID: 005_model_registry
Revises: 004_audit_deletion
Create Date: 2026-10-14 17:15:00

Issue #38 / SPEC §7.3. Seeds MediaPipe Tasks models verified Apache-2.0.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005_model_registry"
down_revision = "004_audit_deletion"
branch_labels = None
depends_on = None

MODELS = [
    {
        "id": "d523416d-7d29-5f20-b386-25c94d3ebf87",
        "component": "vision_pose",
        "model_name": "pose_landmarker_full",
        "version": "float16/1",
        "license": "Apache-2.0",
        "sha": "5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1",
    },
    {
        "id": "1caa6b6d-8645-5c5f-a033-37230befbf16",
        "component": "vision_hands",
        "model_name": "hand_landmarker",
        "version": "float16/1",
        "license": "Apache-2.0",
        "sha": "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
    },
    {
        "id": "4ea32622-c551-51f1-b465-cb9d1e206885",
        "component": "vision_face",
        "model_name": "face_landmarker",
        "version": "float16/1",
        "license": "Apache-2.0",
        "sha": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    },
]


def upgrade() -> None:
    op.create_table(
        "model_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("component", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("license", sa.String(64), nullable=False),
        sa.Column("sha", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_model_registry_component", "model_registry", ["component", "model_name"])
    for row in MODELS:
        op.execute(
            f"""
            INSERT INTO model_registry (id, component, model_name, version, license, sha)
            VALUES (
                '{row["id"]}'::uuid,
                '{row["component"]}',
                '{row["model_name"]}',
                '{row["version"]}',
                '{row["license"]}',
                '{row["sha"]}'
            )
            """
        )


def downgrade() -> None:
    op.drop_index("idx_model_registry_component", table_name="model_registry")
    op.drop_table("model_registry")

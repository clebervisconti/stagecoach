"""Seed scoring_configs table with v1.0.0 from YAML file."""

import hashlib
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "api"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.scoring_config import ScoringConfig


def _seed_version(session, version: str, notes: str) -> None:
    config_path = Path(__file__).parent.parent / "packages" / "scoring-config" / f"v{version}" / "scoring.yaml"
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    yaml_content = config_path.read_text(encoding="utf-8")
    sha256 = hashlib.sha256(yaml_content.encode("utf-8")).hexdigest()
    existing = session.query(ScoringConfig).filter_by(version=version).first()
    if existing:
        print(f"✓ Scoring config v{version} already exists")
        if existing.sha256 != sha256:
            print("  Warning: SHA256 mismatch!")
            print(f"    Database: {existing.sha256}")
            print(f"    File:     {sha256}")
        return
    session.add(
        ScoringConfig(
            version=version,
            yaml=yaml_content,
            sha256=sha256,
            notes=notes,
        )
    )
    session.commit()
    print(f"✓ Seeded scoring_configs with v{version}")
    print(f"  SHA256: {sha256}")


def seed_scoring_config():
    """Load v1.0.0 and v1.1.0 scoring configs and insert into the database."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        _seed_version(
            session,
            "1.0.0",
            "Initial scoring configuration per SPEC §4. "
            "17 categories, 60+ sub-metrics, 6 context weight profiles.",
        )
        _seed_version(
            session,
            "1.1.0",
            "Delivery modes and four online categories (ADR-061). "
            "Stage weights match 1.0.0.",
        )
    except Exception as e:
        session.rollback()
        print(f"Error seeding scoring config: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    seed_scoring_config()

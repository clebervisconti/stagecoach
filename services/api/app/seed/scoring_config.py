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


def seed_scoring_config():
    """Load v1.0.0 scoring config and insert into database.
    
    Idempotent: skips if config already exists.
    """
    # Path to scoring config YAML (mounted in container at /packages)
    config_path = Path("/packages/scoring-config/v1.0.0/scoring.yaml")
    
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        print(f"Ensure packages/ is mounted in the container")
        sys.exit(1)
    
    with open(config_path, "r", encoding="utf-8") as f:
        yaml_content = f.read()
    
    # Calculate SHA256
    sha256 = hashlib.sha256(yaml_content.encode("utf-8")).hexdigest()
    
    # Get database URL from environment
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://stagecoach:dev_password_change_in_prod@localhost:5432/stagecoach"
    )
    
    # Create engine and session
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if v1.0.0 already exists
        existing = session.query(ScoringConfig).filter_by(version="1.0.0").first()
        
        if existing:
            print("✓ Scoring config v1.0.0 already exists")
            if existing.sha256 != sha256:
                print(f"  Warning: SHA256 mismatch!")
                print(f"    Database: {existing.sha256}")
                print(f"    File:     {sha256}")
            return
        
        # Insert new config
        config = ScoringConfig(
            version="1.0.0",
            yaml=yaml_content,
            sha256=sha256,
            notes="Initial scoring configuration per SPEC §4. "
                  "17 categories, 60+ sub-metrics, 6 context weight profiles."
        )
        
        session.add(config)
        session.commit()
        
        print(f"✓ Seeded scoring_configs with v1.0.0")
        print(f"  SHA256: {sha256}")
        
    except Exception as e:
        session.rollback()
        print(f"Error seeding scoring config: {e}")
        sys.exit(1)
    finally:
        session.close()


def main():
    """Entry point for python -m app.seed.scoring_config"""
    seed_scoring_config()

if __name__ == "__main__":
    main()

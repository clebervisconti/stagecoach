"""Test database migrations."""

import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
import tempfile


@pytest.fixture
def test_db_url():
    """Create a temporary test database URL."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return url


def test_migration_upgrade_downgrade(test_db_url):
    """Test that migrations can upgrade and downgrade cleanly."""
    engine = create_engine(test_db_url)
    
    # Drop all tables to start fresh
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    
    # Configure Alembic
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    
    # Run upgrade
    command.upgrade(alembic_cfg, "head")
    
    # Verify tables exist
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        
        expected_tables = [
            "alembic_version",
            "analysis_jobs",
            "consents",
            "job_steps",
            "media_assets",
            "scoring_configs",
            "sessions",
            "users",
            "session_layouts",
        ]
        
        for table in expected_tables:
            assert table in tables, f"Table {table} not created"
        assert "session_layouts" in tables
    
    # Run downgrade
    command.downgrade(alembic_cfg, "base")
    
    # Verify tables are gone (except alembic_version)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name != 'alembic_version'
        """))
        tables = [row[0] for row in result]
        assert len(tables) == 0, f"Tables still exist after downgrade: {tables}"


def test_migration_idempotent(test_db_url):
    """Test that running migrations twice is safe."""
    engine = create_engine(test_db_url)
    
    # Drop all tables to start fresh
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    
    # Configure Alembic
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    
    # Run upgrade twice
    command.upgrade(alembic_cfg, "head")
    command.upgrade(alembic_cfg, "head")  # Should be safe
    
    # Verify tables exist
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        count = result.scalar()
        assert count >= 9, f"Expected at least 9 tables after 011_online_sessions, got {count}"
        names = [
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    """
                )
            )
        ]
        assert "session_layouts" in names

"""Seed database with demo data for development."""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "api"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import User


def seed_demo_user():
    """Create a demo user for development."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://stagecoach:dev_password_change_in_prod@localhost:5432/stagecoach"
    )
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if demo user exists
        demo_email = "demo@stagecoach.example.com"
        existing = session.query(User).filter(User.email == demo_email).first()
        
        if existing:
            print(f"✓ Demo user already exists: {demo_email}")
            return
        
        # Create demo user
        demo_user = User(
            email=demo_email,
            name="Demo User",
            locale="en",
            timezone="UTC",
        )
        
        session.add(demo_user)
        session.commit()
        
        print(f"✓ Created demo user: {demo_email}")
        print(f"  ID: {demo_user.id}")
        print(f"  Name: {demo_user.name}")
        
    except Exception as e:
        session.rollback()
        print(f"Error seeding demo user: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    seed_demo_user()

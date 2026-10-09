# Stage Coach API

FastAPI REST API service.

## Stack

- **Framework**: FastAPI with pydantic v2
- **Database**: PostgreSQL 16 via SQLAlchemy 2
- **Migrations**: Alembic
- **Auth**: JWT verification (Auth.js session tokens)
- **OpenAPI**: Auto-generated docs at `/docs`

## Structure

```
app/
  routers/            - API route modules
  models/             - SQLAlchemy models
  schemas/            - Pydantic request/response schemas
  auth/               - JWT verification, permissions
  db.py               - Database session management
alembic/              - Database migrations
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Create migration
alembic revision --autogenerate -m "description"

# Run tests
pytest
```

## Phase Status

- Phase 0: Health endpoint, minimal setup
- Phase 1+: Full API implementation

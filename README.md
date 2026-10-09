# Stage Coach

An evidence-based presentation coaching platform that analyzes recorded presentations (video or audio) and helps speakers improve through research-grounded feedback.

## Project Status

🚧 **Phase 0 (Foundations)** in progress

- Repository bootstrap complete
- Implementing scoring configuration and engine
- Building foundation for audio + text MVP

## Quick Links

- [Full Specification](docs/SPEC.md) - Complete product and technical specification
- [Architecture Decisions](docs/DECISIONS.md) - ADRs for key technical choices
- [Research Sources](docs/research/sources.md) - Verified research citations
- [Validation Plan](docs/VALIDATION.md) - Methodology and validation results

## Architecture Overview

Stage Coach is a monorepo containing:

- **apps/web** - Next.js web application (React, TypeScript, Tailwind)
- **services/api** - FastAPI REST API (Python 3.11+)
- **services/analysis** - Celery workers for media analysis pipeline
- **packages/scoring-config** - Versioned scoring weights and curves
- **packages/schemas** - JSON schemas and type definitions
- **packages/scoring** - Scoring engine implementation
- **packages/lexicons** - Language-specific lexicons (fillers, hedges, etc.)

## Technology Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, React, Tailwind CSS, shadcn/ui
- **API**: Python 3.11+, FastAPI, pydantic v2
- **Workers**: Celery + Redis queue
- **Database**: PostgreSQL 16 with SQLAlchemy 2
- **Storage**: S3-compatible object storage (MinIO locally)
- **Auth**: Auth.js (NextAuth) with magic links + OAuth
- **Analysis**: faster-whisper, MediaPipe, parselmouth, LLM providers

## Development Setup

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ and pnpm
- Python 3.11+
- Make

### Quick Start

```bash
# Clone and install dependencies
git clone https://github.com/clebervisconti/stagecoach.git
cd stagecoach
make install

# Start development environment
make dev

# Run tests
make test

# View logs
make logs
```

The application will be available at:
- Web app: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001

## Project Principles

1. **Research-grounded**: Every scoring claim traces to published research or is labeled as heuristic
2. **Privacy by default**: Encryption at rest, user-controlled retention, GDPR/LGPD compliance
3. **Transparent scoring**: All weights, curves, and thresholds are versioned and auditable
4. **Responsible AI**: No emotion inference; expression analysis is opt-in and descriptive only
5. **Test-first**: Unit tests for metric functions, golden-file tests for pipeline stages
6. **Reproducible**: Fixed config versions ensure old reports can be regenerated

## Documentation

- **Setup**: See [docs/SETUP.md](docs/SETUP.md) for detailed installation instructions
- **Architecture**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- **API**: See [docs/API.md](docs/API.md) or http://localhost:8000/docs for API reference
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines
- **Privacy**: See [docs/PRIVACY.md](docs/PRIVACY.md) for data handling and compliance

## Phase Roadmap

- ✅ **Phase 0** (Week 1): Foundations - monorepo, DB, config, scoring engine
- 🚧 **Phase 1** (Weeks 2-4): Audio + text MVP - ASR, LLM analysis, basic report
- 📅 **Phase 2** (Weeks 5-7): Video + slides - vision analysis, full report, PDF export
- 📅 **Phase 3** (Weeks 8-10): Talk-prep coach - objectives, trends, personal baselines
- 📅 **Phase 4** (v2): Practice loop - in-browser recording, live feedback, drills
- 📅 **Phase 5** (v3): Teams - organizations, coaches, cohort analytics, benchmarks

## Research Foundation

Stage Coach is built on peer-reviewed research in presentation science, speech prosody, multimodal communication, and instructional design. Every evaluation category references specific studies, and all claims are traceable to published sources or explicitly labeled as heuristic.

Key research areas:
- **Message & Structure**: Minto Pyramid Principle, Duarte's Sparkline, Mayer's multimedia learning principles
- **Voice & Prosody**: Pitch variation quotient (Hincks), charisma acoustics (Niebuhr et al.), disfluency effects (Laske & DiGennaro Reed)
- **Nonverbal**: Gesture systems (McNeill), multimodal assessment (Wörtwein et al., Chen et al.)
- **Fair AI**: ASR bias research (Koenecke et al.), responsible affect analysis guidelines

See [docs/research/sources.md](docs/research/sources.md) for the complete bibliography.

## License

MIT License - see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Stage Coach contributors

## Contact

- **Issues**: https://github.com/clebervisconti/stagecoach/issues
- **Discussions**: https://github.com/clebervisconti/stagecoach/discussions

---

Built with rigor, transparency, and respect for privacy.

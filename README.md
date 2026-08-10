# API Rate Limiting & API Key Management Platform

A production-style API gateway service built with **FastAPI**, **PostgreSQL**, and **Redis**.
Provides API key authentication, configurable per-client rate limiting (Fixed Window algorithm),
usage analytics, and audit logging — the kind of system that sits in front of internal APIs,
SaaS products, or developer platforms to protect them from abuse and uncontrolled consumption.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web framework | FastAPI (async) |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) + Alembic |
| Cache / Rate limiting | Redis 7 |
| Containerisation | Docker + Docker Compose |
| Testing | Pytest + pytest-asyncio + httpx + fakeredis |
| Load testing | Locust |
| Code quality | Ruff |

---

## Architecture

```
HTTP Request (X-API-KEY header)
        │
        ▼
┌──────────────────────────────────────────────┐
│           RateLimitMiddleware                │
│  1. Validate API key    → Postgres (indexed) │
│  2. Check rate limit    → Redis INCR/EXPIRE  │
│  3. Allow / reject      → 200 or 429         │
│  4. Log usage row       → Postgres (async)   │
└──────────────────┬───────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │   Endpoint Handler  │
        │   Service Layer     │
        │   Repository Layer  │
        └─────────────────────┘
```

Full details: [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md)

---

## Quickstart

### Prerequisites
- Docker and Docker Compose installed

### 1. Clone and configure

```bash
git clone <repo-url>
cd api-rate-limiter-platform
cp .env.example .env
```

### 2. Start the stack

```bash
docker-compose up --build
```

This will:
- Start PostgreSQL and Redis
- Run `alembic upgrade head` to create all tables
- Start the FastAPI app on port 8000

### 3. Verify it's running

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "ok", "checks": {"database": "ok", "redis": "ok"}}
```

---

## API Documentation

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | Swagger UI (interactive) |
| http://localhost:8000/redoc | ReDoc |

---

## Quick API Tour

### Register a client

```bash
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Content-Type: application/json" \
  -d '{"client_name": "My Service", "email": "me@example.com", "plan": "free"}'
```

Response:
```json
{"client_id": 1, "api_key": "abc123..."}
```

### Make an authenticated request

```bash
curl http://localhost:8000/api/v1/usage/current \
  -H "X-API-KEY: abc123..."
```

Response includes rate limit headers:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Window: 60
```

### Exceed the rate limit

After 10 requests in 60 seconds (free plan):
```json
{"detail": "Rate limit exceeded"}
```
HTTP 429 Too Many Requests

### View system analytics

```bash
curl http://localhost:8000/api/v1/analytics/system
```

---

## Plan Limits

| Plan | Requests | Window |
|------|----------|--------|
| free | 10 | 60s |
| basic | 50 | 60s |
| premium | 200 | 60s |

Custom limits can be set per-client via `PUT /api/v1/rate-limits/{client_id}`.

---

## Project Structure

```
api-rate-limiter-platform/
├── app/
│   ├── api/v1/endpoints/    # Route handlers (clients, usage, analytics, rate_limits)
│   ├── core/                # config, security, exceptions, constants, auth
│   ├── middleware/          # RateLimitMiddleware (the core of the project)
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic layer
│   ├── repositories/        # Raw DB access (no business rules)
│   └── db/                  # Session, base, Redis client
│
├── tests/
│   ├── unit/                # Service logic, algorithm, security tests
│   ├── integration/         # Full endpoint tests (DB + Redis)
│   ├── middleware/          # Auth + rate limit enforcement tests
│   └── factories/           # factory-boy test data builders
│
├── locust/                  # 3 load test scenarios
├── alembic/                 # DB migrations
├── docs/                    # Architecture, API, DB, performance docs
├── requirements/            # base.txt, test.txt, dev.txt
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── .env.example
```

---

## Development Commands

```bash
make build          # Build and start all containers
make up             # Start containers (no rebuild)
make down           # Stop containers
make logs           # Tail FastAPI logs
make shell          # Shell into the FastAPI container

make migrate        # Run pending Alembic migrations
make makemigration msg="add index"  # Auto-generate a migration

make test           # Run the full test suite
make test-cov       # Run tests with coverage report
make lint           # Run Ruff linter

make locust         # Start Locust web UI (localhost:8089)
```

---

## Running Tests

Tests use SQLite (in-memory) + fakeredis — no real Postgres or Redis needed.

```bash
# Install test deps locally
pip install -r requirements/test.txt

# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=term-missing

# Specific test file
pytest tests/middleware/test_rate_limit_middleware.py -v
```

Target: **75%+ coverage** (per spec).

---

## Load Testing

```bash
# Install dev deps
pip install -r requirements/dev.txt

# Scenario 1: 100 users, valid traffic
locust -f locust/locustfile.py --host=http://localhost:8000 \
       --headless -u 100 -r 10 --run-time 60s --tags scenario1

# Scenario 2: 500 users, exceeding limits
locust -f locust/locustfile.py --host=http://localhost:8000 \
       --headless -u 500 -r 50 --run-time 60s --tags scenario2

# Scenario 3: mixed free + premium
locust -f locust/locustfile.py --host=http://localhost:8000 \
       --headless -u 150 -r 15 --run-time 60s --tags scenario3
```

Full details: [`docs/performance/PERFORMANCE.md`](docs/performance/PERFORMANCE.md)

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) | System design, request lifecycle, layer responsibilities |
| [`docs/database/DATABASE.md`](docs/database/DATABASE.md) | ER diagram, table design, index strategy |
| [`docs/api/API_REFERENCE.md`](docs/api/API_REFERENCE.md) | Full endpoint reference with examples |
| [`docs/performance/PERFORMANCE.md`](docs/performance/PERFORMANCE.md) | Load test scenarios, metrics, interpretation |

---

## Key Design Decisions

**Why Fixed Window?**
Explicit spec requirement. Simple to implement and explain. Known trade-off
(boundary burst) is a deliberate interview talking point about algorithm choice.

**Why Redis for counters, not Postgres?**
INCR is atomic, O(1), and sub-millisecond. Postgres row-level locks add ~10ms
per request — unacceptable on every single authenticated call.

**Why async SQLAlchemy?**
FastAPI's value proposition is async I/O concurrency. Using a sync ORM
undercuts that story. The rate limiter is I/O-bound (Redis + Postgres on
every request), making async the right choice.

**Why are services framework-agnostic?**
Services raise `AppError` subclasses, not `HTTPException`. This means service
logic is testable without FastAPI involved, and the HTTP layer (status codes,
response bodies) is a single translation point in `main.py`'s exception handler.

---

## Resume Description

> Developed a production-style API Rate Limiting and API Key Management Platform using
> FastAPI, PostgreSQL, Redis, and Docker. Implemented custom Starlette middleware for
> API key authentication and Fixed Window rate limiting with Redis-based atomic counters.
> Designed a layered architecture (middleware → endpoints → services → repositories) with
> async SQLAlchemy 2.0, Alembic migrations, per-client configurable limits, usage analytics
> with Redis caching, append-only audit logging, and a 75%+ covered test suite using
> pytest-asyncio, httpx, and fakeredis. Load tested with Locust across three concurrent
> user scenarios (100 / 500 / mixed).

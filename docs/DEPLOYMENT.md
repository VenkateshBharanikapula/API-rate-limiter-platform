# Deployment Guide

## Local Development (Docker Compose)

This is the recommended way to run the project.

### Prerequisites
- Docker >= 24.0
- Docker Compose >= 2.0

### Steps

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Build and start all services
docker-compose up --build

# 3. Verify health
curl http://localhost:8000/health
# Expected: {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}

# 4. Open Swagger UI
open http://localhost:8000/docs
```

### Services started by docker-compose

| Service | Port | Purpose |
|---------|------|---------|
| fastapi | 8000 | The API application |
| postgres | 5432 | Primary database |
| redis | 6379 | Rate limit counters + analytics cache |

### Startup sequence

Docker Compose waits for Postgres and Redis healthchecks to pass before
starting FastAPI. Once FastAPI starts, it runs `alembic upgrade head`
automatically before binding to port 8000.

---

## Environment Variables

Copy `.env.example` to `.env` and adjust values:

```env
# App
APP_NAME="API Rate Limiting & API Key Management Platform"
ENVIRONMENT=local
DEBUG=true
SECRET_KEY=change-this-in-production   # Use: python3 -c "import secrets; print(secrets.token_hex(32))"

# Database (asyncpg for app, psycopg2 for Alembic)
DATABASE_URL=postgresql+asyncpg://ratelimiter:ratelimiter@postgres:5432/ratelimiter
DATABASE_URL_SYNC=postgresql+psycopg2://ratelimiter:ratelimiter@postgres:5432/ratelimiter

# Redis
REDIS_URL=redis://redis:6379/0

# Rate limiting defaults (used when no RateLimitConfig row exists)
DEFAULT_RATE_LIMIT_REQUESTS=10
DEFAULT_RATE_LIMIT_WINDOW_SECONDS=60

# Pagination
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100
```

---

## Running Migrations Manually

```bash
# Apply all pending migrations
make migrate

# Or directly:
docker-compose exec fastapi alembic upgrade head

# Create a new migration after model changes
make makemigration msg="describe your change"

# Roll back one migration
docker-compose exec fastapi alembic downgrade -1

# View migration history
docker-compose exec fastapi alembic history
```

---

## Running Without Docker

If you prefer to run the app directly (requires local Postgres + Redis):

```bash
# Install dependencies
pip install -r requirements/base.txt

# Point .env at your local services
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/ratelimiter
# REDIS_URL=redis://localhost:6379/0

# Run migrations
alembic upgrade head

# Start the app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Running Tests

```bash
# Install test dependencies
pip install -r requirements/test.txt

# Run all tests
pytest

# With coverage report
pytest --cov=app --cov-report=term-missing --cov-report=html
open htmlcov/index.html

# Specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/middleware/ -v
```

Tests use SQLite (in-memory) and fakeredis — no running Postgres or Redis needed.

---

## Load Testing

```bash
# Install dev dependencies (includes locust)
pip install -r requirements/dev.txt

# Start the full stack first
docker-compose up --build

# Run Scenario 1 (headless)
locust -f locust/locustfile.py --host=http://localhost:8000 \
       --headless -u 100 -r 10 --run-time 60s --tags scenario1 \
       --html docs/performance/scenario1_report.html

# Interactive web UI
locust -f locust/locustfile.py --host=http://localhost:8000
# Open http://localhost:8089
```

---

## Production Considerations

This project is designed as a portfolio/resume piece. For a real production
deployment, the following would be added:

1. **Secret management**: move `SECRET_KEY`, DB passwords to a vault (AWS
   Secrets Manager, HashiCorp Vault)

2. **HTTPS**: terminate TLS at a load balancer (nginx, AWS ALB) in front of
   FastAPI

3. **Connection pooling**: PgBouncer between FastAPI and Postgres for connection
   multiplexing at scale

4. **Multiple FastAPI instances**: Redis-backed rate limiting already works
   across instances (counters are shared via Redis) — just scale the FastAPI
   containers

5. **Monitoring**: add Prometheus metrics endpoint + Grafana dashboard
   (see `docs/performance/PERFORMANCE.md` → Future Enhancements)

6. **Admin authentication**: the analytics endpoints currently have no auth.
   In production these would be behind a separate admin API key or internal
   network

7. **Log aggregation**: structured JSON logging to stdout, collected by
   Datadog / CloudWatch / ELK

8. **Alembic in CI**: run `alembic upgrade head` in CI against a test DB before
   deploying, to catch migration failures before they hit production

---

## Troubleshooting

### Container fails to start

```bash
docker-compose logs fastapi
```

Common causes:
- `.env` file missing → `cp .env.example .env`
- Postgres not ready → docker-compose healthcheck should handle this; if not,
  increase the `retries` in the postgres healthcheck

### 401 on every request

- Ensure you are sending `X-API-KEY: <your_key>` (exact header name, exact key value)
- The key is case-sensitive
- Check the client is still active: `GET /api/v1/clients/{id}`

### Rate limit not resetting

- The Fixed Window resets at the next bucket boundary, not exactly 60 seconds
  from your first request. This is expected behaviour.
- Check the `X-RateLimit-Window` header for the window size.

### Alembic revision not found

If you see `Can't locate revision` errors:

```bash
docker-compose exec fastapi alembic history
docker-compose exec fastapi alembic current
```

This usually means the migrations directory wasn't mounted correctly — check
the `volumes:` section in `docker-compose.yml`.

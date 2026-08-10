# API Rate Limiting & API Key Management Platform

A production-style API gateway built with **FastAPI, PostgreSQL, Redis, and Docker**. The platform provides API key authentication, configurable per-client rate limiting, usage analytics, and audit logging.

The system is designed to sit in front of internal APIs, SaaS applications, or developer platforms to protect services from abuse and uncontrolled API consumption.

## Tech Stack

| Layer                 | Technology                               |
| --------------------- | ---------------------------------------- |
| Web Framework         | FastAPI                                  |
| Language              | Python 3.12+                             |
| Database              | PostgreSQL 16                            |
| ORM                   | SQLAlchemy 2.0 (Async)                   |
| Migrations            | Alembic                                  |
| Cache / Rate Limiting | Redis 7                                  |
| Containerization      | Docker & Docker Compose                  |
| Testing               | Pytest, pytest-asyncio, HTTPX, Fakeredis |
| Load Testing          | Locust                                   |
| Code Quality          | Ruff                                     |

## Architecture

```text
                         HTTP Request
                              │
                              │ X-API-KEY
                              ▼
┌─────────────────────────────────────────────────────────┐
│                  Rate Limit Middleware                  │
│                                                         │
│  1. Validate API Key ──────────────► PostgreSQL         │
│                                                         │
│  2. Check Rate Limit ──────────────► Redis              │
│                                      INCR / EXPIRE      │
│                                                         │
│  3. Allow / Reject ────────────────► 200 / 429          │
│                                                         │
│  4. Record Usage ─────────────────► PostgreSQL          │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Endpoint Layer  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Service Layer   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Repository      │
                  │ Layer           │
                  └────────┬────────┘
                           │
                           ▼
                      PostgreSQL
```

Detailed architecture documentation:

* [Architecture](docs/architecture/ARCHITECTURE.md)
* [Database Design](docs/database/DATABASE.md)
* [API Reference](docs/api/API_REFERENCE.md)
* [Performance & Load Testing](docs/performance/PERFORMANCE.md)

## Key Features

### API Key Authentication

Clients authenticate using an API key supplied through the `X-API-KEY` request header.

```http
X-API-KEY: your-api-key
```

### Configurable Rate Limiting

The platform implements a **Fixed Window** rate-limiting algorithm using Redis atomic counters.

Default limits:

| Plan    | Requests |     Window |
| ------- | -------: | ---------: |
| Free    |       10 | 60 seconds |
| Basic   |       50 | 60 seconds |
| Premium |      200 | 60 seconds |

Rate limits can also be customized per client.

### Redis-Based Counters

Redis is used for rate-limit counters because `INCR` provides atomic counter updates with very low latency.

Each request updates a Redis counter associated with the client and rate-limit window.

### Usage Analytics

The platform records API usage and provides analytics endpoints for monitoring consumption and request activity.

### Audit Logging

Important client and administrative operations are recorded using append-only audit logs.

### Async Database Access

The application uses **SQLAlchemy 2.0's asynchronous API** to support non-blocking database operations within FastAPI.

### Layered Architecture

Business logic is separated into:

```text
Middleware
    ↓
API Endpoints
    ↓
Services
    ↓
Repositories
    ↓
Database
```

This keeps HTTP concerns, business logic, and database access independent and easier to test.

## Project Structure

```text
api-rate-limiter-platform/
│
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── analytics.py
│   │       │   ├── clients.py
│   │       │   ├── dependencies.py
│   │       │   ├── rate_limits.py
│   │       │   └── usage.py
│   │       └── router.py
│   │
│   ├── core/
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   └── security.py
│   │
│   ├── db/
│   │   ├── base.py
│   │   ├── redis.py
│   │   └── session.py
│   │
│   ├── middleware/
│   │   └── rate_limiter.py
│   │
│   ├── models/
│   │   ├── audit_log.py
│   │   ├── client.py
│   │   ├── rate_limit.py
│   │   └── usage.py
│   │
│   ├── repositories/
│   │   ├── audit_repository.py
│   │   ├── client_repository.py
│   │   ├── rate_limit_repository.py
│   │   └── usage_repository.py
│   │
│   ├── schemas/
│   ├── services/
│   └── main.py
│
├── alembic/
│   └── versions/
│
├── docs/
│   ├── api/
│   ├── architecture/
│   ├── database/
│   └── performance/
│
├── locust/
│   └── locustfile.py
│
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── test.txt
│
├── tests/
│   ├── factories/
│   ├── fixtures/
│   ├── integration/
│   ├── middleware/
│   └── unit/
│
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── alembic.ini
├── pyproject.toml
├── .env.example
└── README.md
```

## Quick Start

### Prerequisites

Install:

* Docker Desktop
* Git

### 1. Clone the Repository

```bash
git clone https://github.com/VenkateshBharanikapula/API-rate-limiter-platform.git
cd API-rate-limiter-platform
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Update `.env` with your local configuration if necessary.

> **Important:** Never commit `.env` to Git. The repository already includes `.env` in `.gitignore`.

### 3. Start the Application

Build and start the complete stack:

```bash
docker compose up --build
```

The stack starts:

* FastAPI
* PostgreSQL
* Redis
* Alembic database migrations

The API will be available at:

```text
http://localhost:8000
```

### 4. Verify the Application

Health check:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

## API Documentation

Once the application is running:

### Swagger UI

```text
http://localhost:8000/docs
```

### ReDoc

```text
http://localhost:8000/redoc
```

## API Examples

### Register a Client

```bash
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Content-Type: application/json" \
  -d "{\"client_name\":\"My Service\",\"email\":\"me@example.com\",\"plan\":\"free\"}"
```

The response returns a client ID and API key.

Example:

```json
{
  "client_id": 1,
  "api_key": "your-generated-api-key"
}
```

### Make an Authenticated Request

```bash
curl http://localhost:8000/api/v1/usage/current \
  -H "X-API-KEY: your-generated-api-key"
```

A successful response includes rate-limit information such as:

```text
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Window: 60
```

### Exceed the Rate Limit

After the configured request limit has been reached, the API responds with:

```http
HTTP/1.1 429 Too Many Requests
```

Example:

```json
{
  "detail": "Rate limit exceeded"
}
```

## Development Commands

The project includes a `Makefile` for common development tasks.

```bash
make build
```

Build and start the application.

```bash
make up
```

Start the existing containers.

```bash
make down
```

Stop the containers.

```bash
make logs
```

View application logs.

```bash
make shell
```

Open a shell inside the FastAPI container.

```bash
make migrate
```

Run pending Alembic migrations.

```bash
make makemigration msg="add index"
```

Generate a new Alembic migration.

```bash
make test
```

Run the test suite.

```bash
make test-cov
```

Run tests with coverage.

```bash
make lint
```

Run Ruff.

```bash
make locust
```

Start the Locust web interface.

## Testing

The project uses:

* Pytest
* pytest-asyncio
* HTTPX
* Fakeredis

Tests can run without a production PostgreSQL or Redis instance.

Install the test dependencies:

```bash
pip install -r requirements/test.txt
```

Run the complete test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

Run a specific test module:

```bash
pytest tests/middleware/test_rate_limit_middleware.py -v
```

## Load Testing

Locust is used to simulate concurrent API traffic.

### Scenario 1 — Valid Traffic

100 concurrent users:

```bash
locust -f locust/locustfile.py \
  --host=http://localhost:8000 \
  --headless \
  -u 100 \
  -r 10 \
  --run-time 60s \
  --tags scenario1
```

### Scenario 2 — Rate Limit Enforcement

500 concurrent users:

```bash
locust -f locust/locustfile.py \
  --host=http://localhost:8000 \
  --headless \
  -u 500 \
  -r 50 \
  --run-time 60s \
  --tags scenario2
```

### Scenario 3 — Mixed Plans

150 concurrent users:

```bash
locust -f locust/locustfile.py \
  --host=http://localhost:8000 \
  --headless \
  -u 150 \
  -r 15 \
  --run-time 60s \
  --tags scenario3
```

See the complete performance documentation:

[Performance Documentation](docs/performance/PERFORMANCE.md)

## Design Decisions

### Why Fixed Window Rate Limiting?

Fixed Window was selected because it provides a simple and predictable implementation while satisfying the project's requirements.

The main trade-off is the possibility of a boundary burst when requests occur near the transition between two windows.

This provides a useful comparison point against alternative algorithms such as:

* Sliding Window
* Token Bucket
* Leaky Bucket

### Why Redis for Rate-Limit Counters?

Redis provides atomic counter operations through commands such as `INCR`.

This makes it well suited for high-frequency rate-limit checks where counters need to be updated safely across concurrent requests.

### Why Async SQLAlchemy?

FastAPI is designed around asynchronous I/O.

Using SQLAlchemy's asynchronous API allows database operations to integrate naturally with the application's async request handling.

### Why Separate Services and Repositories?

The service layer contains business logic while repositories handle database access.

This separation provides:

* Easier unit testing
* Clearer responsibilities
* Reduced coupling to FastAPI
* Reusable business logic
* Cleaner database access

Services raise application-specific errors rather than FastAPI `HTTPException` instances. HTTP-specific error translation is handled at the application layer.

## Security Considerations

The repository intentionally does **not** contain production secrets.

Environment-specific configuration should be stored in `.env`.

The following files should never be committed:

```text
.env
*.db
*.sqlite3
__pycache__/
```

For production deployments, additional security controls should be considered, including:

* Secret management
* HTTPS/TLS
* API key rotation
* Key hashing
* Database credential rotation
* Redis authentication
* Network isolation
* Request validation
* Structured security logging
* Rate-limit abuse monitoring

## Documentation

| Document                                          | Description                               |
| ------------------------------------------------- | ----------------------------------------- |
| [Architecture](docs/architecture/ARCHITECTURE.md) | System architecture and request lifecycle |
| [Database](docs/database/DATABASE.md)             | Database schema and index strategy        |
| [API Reference](docs/api/API_REFERENCE.md)        | API endpoints and request examples        |
| [Performance](docs/performance/PERFORMANCE.md)    | Load-testing scenarios and analysis       |
| [Deployment](docs/DEPLOYMENT.md)                  | Deployment information                    |

## Future Improvements

Potential improvements include:

* Sliding Window or Token Bucket rate limiting
* Distributed rate limiting across multiple API gateway instances
* API key rotation and revocation
* API key hashing
* Prometheus metrics
* Grafana dashboards
* Distributed tracing
* Background analytics processing
* Redis Cluster support
* Kubernetes deployment
* CI/CD with GitHub Actions

## Portfolio Summary

> Built a production-style API Rate Limiting and API Key Management Platform using FastAPI, PostgreSQL, Redis, and Docker. Implemented API key authentication, Redis-backed Fixed Window rate limiting, per-client configurable limits, usage analytics, audit logging, async SQLAlchemy 2.0, Alembic migrations, layered service/repository architecture, automated testing with pytest and fakeredis, and concurrent load testing with Locust.

## License

This project is available for educational and portfolio purposes. Add an appropriate open-source license before distributing the project for reuse.

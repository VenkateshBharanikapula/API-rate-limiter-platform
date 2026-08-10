# System Architecture

## Overview

The API Rate Limiting & API Key Management Platform is a standalone gateway
service that sits in front of internal APIs or SaaS products and enforces
per-client request limits, authentication, and usage tracking.

```
                    ┌─────────────────────────────────────────────────┐
                    │              FastAPI Application                │
                    │                                                 │
  HTTP Request ───► │  RateLimitMiddleware                            │
  X-API-KEY header  │       │                                         │
                    │       ▼                                         │
                    │  ┌─────────────┐    ┌──────────────────────┐   │
                    │  │  Postgres   │    │       Redis           │   │
                    │  │  api_clients│◄───│  rate_limit counters  │   │
                    │  │  usage rows │    │  analytics cache      │   │
                    │  │  audit_logs │    └──────────────────────┘   │
                    │  └─────────────┘                               │
                    │       │                                         │
                    │       ▼                                         │
                    │  Endpoint Handler → Service → Repository       │
                    │       │                                         │
                    │       ▼                                         │
  HTTP Response ◄── │  JSON Response + X-RateLimit-* headers         │
                    └─────────────────────────────────────────────────┘
```

## Request Lifecycle

Every request follows this path:

```
1. RateLimitMiddleware intercepts the request
      │
2. Path check — exempt? (/, /health, /docs) → skip to handler
      │
3. Extract X-API-KEY header
      │  missing → 401
      │
4. Postgres: SELECT api_clients WHERE api_key = ? (indexed)
      │  not found → 401
      │  is_active = false → 403
      │
5. Redis: INCR rate_limit:{api_key}:{window_bucket}
          EXPIRE key window_seconds
      │  count > requests_allowed → 429 (log blocked usage row)
      │
6. Set request.state.client_id for endpoint access
      │
7. call_next(request) → endpoint handler
      │
8. Add X-RateLimit-Limit / Remaining / Window headers to response
      │
9. asyncio.create_task → log usage row to Postgres (non-blocking)
      │
10. Return response to caller
```

## Layer Responsibilities

| Layer | Location | Responsibility |
|---|---|---|
| Middleware | `app/middleware/` | Auth, rate limit, usage logging on every request |
| Endpoints | `app/api/v1/endpoints/` | Parse request, call service, shape response |
| Services | `app/services/` | Business logic, orchestrates repositories |
| Repositories | `app/repositories/` | Raw DB access (CRUD), no business rules |
| Selectors | `app/selectors/` | Read-heavy / reporting queries (analytics) |
| Models | `app/models/` | SQLAlchemy ORM definitions |
| Schemas | `app/schemas/` | Pydantic request/response contracts |

## Why Redis for Rate Limiting

Redis INCR is:
- **Atomic** — no race conditions without transactions
- **O(1)** — sub-millisecond per operation
- **Self-cleaning** — TTL/EXPIRE means no scheduled cleanup job needed

Postgres counters would require row-level locks and would add ~10ms per
request. At 500 concurrent users that compounds quickly.

## Fixed Window Algorithm

```
window_bucket = floor(unix_timestamp / window_seconds)
redis_key     = f"rate_limit:{api_key}:{window_bucket}"

INCR redis_key          → current_count
EXPIRE redis_key window_seconds

if current_count > requests_allowed:
    return 429
```

**Known trade-off**: a client can double-burst at the window boundary
(exhaust one window in the last second, then exhaust the next window
immediately). This is the well-documented weakness of Fixed Window vs
Sliding Window — worth discussing in interviews as a "what would you
improve" point.

## Docker Architecture

```
┌─────────────────────────────────────────┐
│            docker-compose               │
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │ fastapi  │  │ postgres │  │ redis │ │
│  │ :8000    │  │ :5432    │  │ :6379 │ │
│  └────┬─────┘  └────┬─────┘  └───┬───┘ │
│       │             │             │     │
│       └─────────────┴─────────────┘     │
│              internal network           │
└─────────────────────────────────────────┘
```

Services communicate over Docker's internal network using service names
(`postgres`, `redis`) as hostnames. Only FastAPI's port 8000 is published
to the host.

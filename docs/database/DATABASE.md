# Database Design

## Entity Relationship Diagram

```
┌─────────────────────────────┐
│         api_clients         │
├─────────────────────────────┤
│ id              INTEGER PK  │
│ client_name     VARCHAR(255)│
│ email           VARCHAR(255)│ UNIQUE INDEX
│ api_key         VARCHAR(64) │ UNIQUE INDEX  ← hot lookup path
│ plan            VARCHAR     │ (free/basic/premium)
│ is_active       BOOLEAN     │
│ created_at      TIMESTAMPTZ │
│ updated_at      TIMESTAMPTZ │
└──────────────┬──────────────┘
               │ 1
               │
       ┌───────┼───────────────┐
       │       │               │
       │ 1     │ 0..*          │ 0..*
       ▼       ▼               ▼
┌──────────────────┐  ┌───────────────┐  ┌─────────────────┐
│ rate_limit_      │  │   api_usage   │  │   audit_logs    │
│ configs          │  ├───────────────┤  ├─────────────────┤
├──────────────────┤  │ id         PK │  │ id           PK │
│ id          PK   │  │ client_id  FK │  │ client_id    FK │
│ client_id   FK   │  │ endpoint      │  │ action          │
│ requests_allowed │  │ request_count │  │ metadata   JSON │
│ window_seconds   │  │ was_allowed   │  │ created_at      │
│ created_at       │  │ timestamp     │  └─────────────────┘
│ updated_at       │  └───────────────┘
└──────────────────┘
  UNIQUE(client_id)     INDEX(client_id, timestamp)
```

## Table Descriptions

### api_clients
The root entity. Every API consumer has one row here.
- `api_key` is the credential clients include in `X-API-KEY`. It is indexed
  for O(1) lookups on every authenticated request.
- `plan` drives the default rate limit when no `rate_limit_configs` row exists.
- `is_active` is the on/off switch — the middleware checks this on every request.

### rate_limit_configs
A one-to-one override table. Each client can have at most one row here.
- If a row exists → use `requests_allowed` / `window_seconds` from it.
- If no row → fall back to `PLAN_RATE_LIMITS[client.plan]` in `constants.py`.
- This lets admins grant individual clients custom limits without changing
  their plan tier (e.g. a free client that needs 30 req/min temporarily).

### api_usage
One row per request handled by the middleware (both allowed and blocked).
- `was_allowed` distinguishes successful from rate-limited requests, enabling
  the `successful_requests` / `blocked_requests` split in the analytics APIs.
- The composite index on `(client_id, timestamp)` makes per-client range
  queries (daily/monthly usage, summaries) efficient without a full table scan.
- `request_count` is always 1 in this implementation but the column is kept
  to support future batch/aggregated inserts without a schema change.

### audit_logs
Append-only record of admin/security actions. Never updated, only inserted.
- `metadata` (JSON) is flexible by design — each action type carries different
  contextual data (e.g. rate limit updates record old and new values).
- The `action` enum is validated at the application layer via `AuditAction`.

## Index Strategy

| Table | Index | Reason |
|---|---|---|
| api_clients | `email` UNIQUE | Uniqueness enforcement + lookup by email |
| api_clients | `api_key` UNIQUE | Hot path: every middleware request hits this |
| rate_limit_configs | `client_id` UNIQUE | One config per client, fast FK join |
| api_usage | `(client_id, timestamp)` | Efficient per-client time-range queries |
| api_usage | `timestamp` | System-wide time-range queries |
| audit_logs | `(client_id, created_at)` | Per-client audit history ordering |
| audit_logs | `action` | Filter by action type |

## Migration Strategy

Alembic manages all schema changes. Key conventions:
- Migrations are numbered (`0001_`, `0002_`) for readable ordering.
- `downgrade()` is always implemented — reversible migrations are a hard
  requirement for safe deploys.
- `alembic upgrade head` runs automatically at container startup
  (see `docker-compose.yml` command).
- Never use `Base.metadata.create_all()` in production — Alembic only.

# API Reference

Base URL: `http://localhost:8000/api/v1`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)
Alternative docs: `http://localhost:8000/redoc`

---

## Authentication

All endpoints under `/api/v1/usage/*` and `/api/v1/analytics/client/*`
require a valid API key in the request header:

```
X-API-KEY: your_api_key_here
```

The key is issued once at registration (`POST /api/v1/clients`). If lost,
the client must be re-registered (key rotation endpoint is a planned
enhancement — see `docs/performance/FUTURE.md`).

### Error Responses

| Status | Detail | Cause |
|--------|--------|-------|
| 401 | Invalid API Key | Missing or unrecognised key |
| 403 | Client is disabled | Key valid but client deactivated |
| 429 | Rate limit exceeded | Too many requests in the window |

---

## Client Management

### Register Client

```
POST /api/v1/clients
Content-Type: application/json
```

**Request Body**

```json
{
  "client_name": "Weather Service",
  "email": "admin@weather.com",
  "plan": "free"
}
```

| Field | Type | Required | Values |
|-------|------|----------|--------|
| client_name | string | ✓ | 1–255 chars |
| email | string (email) | ✓ | valid email |
| plan | string | – | `free` (default), `basic`, `premium` |

**Response 201**

```json
{
  "client_id": 1,
  "api_key": "abc123xyz..."
}
```

> ⚠️ The `api_key` is returned **only once**. Store it securely.

**Errors:** 409 (duplicate email), 422 (validation)

---

### Get Client

```
GET /api/v1/clients/{client_id}
```

**Response 200**

```json
{
  "id": 1,
  "client_name": "Weather Service",
  "email": "admin@weather.com",
  "plan": "free",
  "is_active": true,
  "created_at": "2026-06-21T10:00:00Z",
  "updated_at": "2026-06-21T10:00:00Z"
}
```

**Errors:** 404

---

### List Clients

```
GET /api/v1/clients
```

**Query Parameters**

| Param | Type | Description |
|-------|------|-------------|
| search | string | Filter by name or email (case-insensitive) |
| status | string | `active` or `inactive` |
| plan | string | `free`, `basic`, or `premium` |
| ordering | string | Field name, prefix `-` for descending (e.g. `-created_at`) |
| page | int | Page number (default: 1) |
| page_size | int | Items per page (default: 20, max: 100) |

**Response 200**

```json
{
  "total": 42,
  "page": 1,
  "page_size": 20,
  "results": [ { ... }, { ... } ]
}
```

---

### Disable Client

```
PATCH /api/v1/clients/{client_id}/disable
```

Sets `is_active = false`. Subsequent requests from this client return 403.
Writes a `CLIENT_DEACTIVATED` audit log entry.

**Response 200** — updated `ClientRead` object

**Errors:** 404

---

### Enable Client

```
PATCH /api/v1/clients/{client_id}/enable
```

Sets `is_active = true`. Writes a `CLIENT_ACTIVATED` audit log entry.

**Response 200** — updated `ClientRead` object

**Errors:** 404

---

## Rate Limit Configuration

### Get Rate Limit Config

```
GET /api/v1/rate-limits/{client_id}
```

**Response 200**

```json
{
  "id": 1,
  "client_id": 1,
  "requests_allowed": 10,
  "window_seconds": 60,
  "created_at": "2026-06-21T10:00:00Z",
  "updated_at": "2026-06-21T10:00:00Z"
}
```

**Errors:** 404 (client or config not found)

---

### Update Rate Limit Config

```
PUT /api/v1/rate-limits/{client_id}
Content-Type: application/json
```

Upserts the config: creates if no row exists, updates if one does.
Writes a `RATE_LIMIT_UPDATED` audit log entry with old and new values.

**Request Body**

```json
{
  "requests_allowed": 100,
  "window_seconds": 60
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| requests_allowed | int | 1 – 100,000 |
| window_seconds | int | 1 – 86,400 (1 day max) |

**Response 200** — updated `RateLimitConfigRead` object

**Errors:** 404, 422

---

## Usage Tracking

All usage endpoints require `X-API-KEY`. Clients see only their own data.

### Current Usage

```
GET /api/v1/usage/current
X-API-KEY: your_api_key
```

Returns request counts for the last 60 minutes.

**Response 200**

```json
{
  "total": 45,
  "successful": 40,
  "blocked": 5,
  "period": "last_60_minutes",
  "since": "2026-06-21T09:00:00+00:00"
}
```

---

### Daily Usage

```
GET /api/v1/usage/daily
X-API-KEY: your_api_key
```

Returns request counts for today (UTC, midnight to now).

**Response 200**

```json
{
  "total": 120,
  "successful": 115,
  "blocked": 5,
  "period": "today",
  "date": "2026-06-21"
}
```

---

### Monthly Usage

```
GET /api/v1/usage/monthly
X-API-KEY: your_api_key
```

Returns request counts for the current calendar month (UTC).

**Response 200**

```json
{
  "total": 3400,
  "successful": 3380,
  "blocked": 20,
  "period": "current_month",
  "month": "2026-06"
}
```

---

## Analytics

No authentication required (admin-level endpoints).

### Client Summary

```
GET /api/v1/analytics/client/{client_id}
```

**Response 200**

```json
{
  "client_id": 1,
  "total_requests": 1200,
  "successful_requests": 1180,
  "blocked_requests": 20
}
```

---

### Top Clients

```
GET /api/v1/analytics/top-clients?limit=10
```

Returns clients ranked by total request volume. Result cached in Redis
for 60 seconds.

**Response 200**

```json
[
  { "client_id": 3, "client_name": "Finance API", "total_requests": 5400 },
  { "client_id": 1, "client_name": "Weather Service", "total_requests": 1200 }
]
```

**Query Parameters:** `limit` (int, 1–50, default 10)

---

### System Statistics

```
GET /api/v1/analytics/system
```

Platform-wide metrics. Cached in Redis for 60 seconds.

**Response 200**

```json
{
  "total_clients": 24,
  "active_clients": 22,
  "total_requests": 98400,
  "successful_requests": 96100,
  "blocked_requests": 2300,
  "success_rate_pct": 97.66
}
```

---

## Response Headers (Authenticated Requests)

Every request that passes authentication receives these headers:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Max requests allowed in the current window |
| `X-RateLimit-Remaining` | Requests remaining in the current window |
| `X-RateLimit-Window` | Window duration in seconds |

---

## Plan Defaults

| Plan | Requests | Window |
|------|----------|--------|
| free | 10 | 60s |
| basic | 50 | 60s |
| premium | 200 | 60s |

These defaults apply when no custom `RateLimitConfig` row exists for the client.

# Performance Testing

## Overview

Load tests are implemented with [Locust](https://locust.io) in
`locust/locustfile.py`. Three scenarios are defined matching the project spec.

---

## Scenarios

### Scenario 1 — Valid Traffic (100 concurrent users)

Simulates realistic API consumption that stays within free-plan rate limits.

```bash
locust -f locust/locustfile.py \
       --host=http://localhost:8000 \
       --headless \
       -u 100 -r 10 \
       --run-time 60s \
       --tags scenario1 \
       --html docs/performance/scenario1_report.html
```

**Expected results:**
- 0% error rate (all requests within limits)
- p95 response time < 100ms
- Throughput: ~50–80 req/s

---

### Scenario 2 — Heavy Traffic (500 concurrent users)

Hammers the API beyond rate limits. Most requests will receive 429.
The locustfile marks 200 and 429 both as `success` since 429 is the
correct behaviour — failure rate reflects only unexpected errors.

```bash
locust -f locust/locustfile.py \
       --host=http://localhost:8000 \
       --headless \
       -u 500 -r 50 \
       --run-time 60s \
       --tags scenario2 \
       --html docs/performance/scenario2_report.html
```

**Expected results:**
- High 429 rate (expected — rate limits doing their job)
- 0% unexpected error rate
- Redis holding up under INCR load

---

### Scenario 3 — Mixed Traffic (Free + Premium clients)

Demonstrates that premium clients continue to get through while free clients
hit their limits.

```bash
locust -f locust/locustfile.py \
       --host=http://localhost:8000 \
       --headless \
       -u 150 -r 15 \
       --run-time 60s \
       --tags scenario3 \
       --html docs/performance/scenario3_report.html
```

**Expected results:**
- Free clients see 429s at sustained load
- Premium clients stay at 200 throughout
- Validates per-client isolation of Redis counters

---

## Running with Locust Web UI

For interactive testing with the browser dashboard:

```bash
# Start the stack first
docker-compose up --build

# In a separate terminal (with dev deps installed)
pip install -r requirements/dev.txt
locust -f locust/locustfile.py --host=http://localhost:8000
```

Then open `http://localhost:8089` and set:
- Number of users: 100 (Scenario 1) / 500 (Scenario 2)
- Spawn rate: 10 users/second

---

## Key Metrics to Watch

| Metric | What it tells you |
|--------|-------------------|
| Requests/sec (RPS) | Throughput under load |
| p50 / p95 / p99 response time | Tail latency behaviour |
| Failure % | Unexpected errors (not 429s in Scenario 2) |
| Redis memory usage | Counter key footprint |
| Postgres connection pool | Whether pool is a bottleneck |

---

## Interpreting Results

**Good signs:**
- p95 response time stays < 150ms under Scenario 1
- Scenario 2 error rate is 0% (429s handled cleanly)
- Scenario 3 shows clear split between free (429s) and premium (200s)

**Red flags:**
- Timeout errors → connection pool exhaustion (tune `max_connections` in `db/redis.py`)
- 500 errors → unhandled exceptions in middleware (check container logs)
- Response time > 500ms → likely Postgres query without an index hit

---

## Future Enhancements

- **Sliding Window algorithm**: eliminates the boundary burst problem
- **Token Bucket**: better burst tolerance for premium clients
- **Distributed rate limiting**: Redis Cluster for multi-instance deployments
- **Prometheus + Grafana**: real-time metrics dashboards
- **Admin Dashboard UI**: React frontend for the analytics endpoints

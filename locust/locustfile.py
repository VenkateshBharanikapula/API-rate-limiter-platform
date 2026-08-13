"""
Locust load test scenarios (Module: Performance Testing).

Covers all three spec scenarios:

  Scenario 1 — Valid traffic:          100 concurrent users (FreeUser)
  Scenario 2 — Traffic exceeding limits: 500 concurrent users (HeavyUser)
  Scenario 3 — Mixed traffic:          Free + Premium clients (MixedUser)

Run:
    locust -f locust/locustfile.py --host=http://localhost:8000

Or headless (CI-style):
    locust -f locust/locustfile.py --host=http://localhost:8000 \ 
           --headless -u 100 -r 10 --run-time 60s \
           --html docs/performance/report.html

Notes:
  - Each simulated user registers its own API client on_start so keys are
    unique and rate limit counters are independent.
  - HeavyUser deliberately fires requests fast enough to trigger 429s; the
    test tracks these as expected responses (not failures) using
    catch_response so Locust's error rate stat remains meaningful.
  - The locust classes are tagged so you can run a single scenario:
      locust ... --tags scenario1
"""

import random
import uuid

from locust import HttpUser, TaskSet, between, events, tag, task


# ---------------------------------------------------------------------------
# Shared registration helper
# ---------------------------------------------------------------------------

def register_client(client, plan: str = "free") -> str | None:
    """
    Register a new API client and return the issued API key.
    Returns None if registration fails (so the user skips its tasks).
    """
    uid = uuid.uuid4().hex[:8]
    with client.post(
        "/api/v1/clients",
        json={
            "client_name": f"loadtest-{uid}",
            "email": f"loadtest-{uid}@example.com",
            "plan": plan,
        },
        catch_response=True,
        name="[setup] register client",
    ) as resp:
        if resp.status_code == 201:
            return resp.json()["api_key"]
        resp.failure(f"Registration failed: {resp.status_code} {resp.text}")
        return None


# ---------------------------------------------------------------------------
# Scenario 1: Valid traffic — 100 concurrent users within rate limits
# ---------------------------------------------------------------------------

class Scenario1Tasks(TaskSet):
    """Light, realistic usage pattern that stays within the free plan limit."""

    @task(3)
    def get_current_usage(self):
        self.client.get(
            "/api/v1/usage/current",
            headers={"X-API-KEY": self.user.api_key},
            name="/api/v1/usage/current",
        )

    @task(2)
    def get_daily_usage(self):
        self.client.get(
            "/api/v1/usage/daily",
            headers={"X-API-KEY": self.user.api_key},
            name="/api/v1/usage/daily",
        )

    @task(1)
    def get_analytics_system(self):
        self.client.get(
            "/api/v1/analytics/system",
            name="/api/v1/analytics/system",
        )

    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")


@tag("scenario1", "valid_traffic")
class FreeUser(HttpUser):
    """
    Scenario 1: 100 concurrent free-plan users making normal requests.
    wait_time simulates realistic inter-request think time so the per-user
    rate stays well below 10 req/min.
    """
    tasks = [Scenario1Tasks]
    wait_time = between(8, 15)  # 4–7 req/min per user — under the 10/min free limit

    def on_start(self):
        self.api_key = register_client(self.client, plan="free")
        if not self.api_key:
            self.environment.runner.quit()


# ---------------------------------------------------------------------------
# Scenario 2: Heavy traffic — 500 concurrent users exceeding limits
# ---------------------------------------------------------------------------

class Scenario2Tasks(TaskSet):
    """
    Hammers the API as fast as possible. Most requests will receive 429.
    We catch 429 and mark it SUCCESS (it's the correct behaviour, not an
    error) so Locust's failure rate reflects actual unexpected errors only.
    """

    @task
    def hammer_usage(self):
        with self.client.get(
            "/api/v1/usage/current",
            headers={"X-API-KEY": self.user.api_key},
            catch_response=True,
            name="/api/v1/usage/current [heavy]",
        ) as resp:
            if resp.status_code in (200, 429):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task
    def hammer_daily(self):
        with self.client.get(
            "/api/v1/usage/daily",
            headers={"X-API-KEY": self.user.api_key},
            catch_response=True,
            name="/api/v1/usage/daily [heavy]",
        ) as resp:
            if resp.status_code in (200, 429):
                resp.success()
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")


@tag("scenario2", "heavy_traffic")
class HeavyUser(HttpUser):
    """
    Scenario 2: 500 concurrent users with no wait time.
    Designed to saturate rate limiters and validate 429 handling at scale.
    """
    tasks = [Scenario2Tasks]
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.api_key = register_client(self.client, plan="free")
        if not self.api_key:
            self.environment.runner.quit()


# ---------------------------------------------------------------------------
# Scenario 3: Mixed traffic — free + premium clients
# ---------------------------------------------------------------------------

class FreePlanTasks(TaskSet):
    @task
    def usage_request(self):
        with self.client.get(
            "/api/v1/usage/current",
            headers={"X-API-KEY": self.user.api_key},
            catch_response=True,
            name="/api/v1/usage/current [free]",
        ) as resp:
            if resp.status_code in (200, 429):
                resp.success()
            else:
                resp.failure(f"Unexpected: {resp.status_code}")


class PremiumPlanTasks(TaskSet):
    @task(3)
    def usage_request(self):
        self.client.get(
            "/api/v1/usage/current",
            headers={"X-API-KEY": self.user.api_key},
            name="/api/v1/usage/current [premium]",
        )

    @task(2)
    def monthly_usage(self):
        self.client.get(
            "/api/v1/usage/monthly",
            headers={"X-API-KEY": self.user.api_key},
            name="/api/v1/usage/monthly [premium]",
        )

    @task(1)
    def top_clients(self):
        self.client.get(
            "/api/v1/analytics/top-clients",
            name="/api/v1/analytics/top-clients [premium]",
        )


@tag("scenario3", "mixed_traffic", "free")
class MixedFreeUser(HttpUser):
    """Free plan users in the mixed scenario (higher wait = slower fire rate)."""
    tasks = [FreePlanTasks]
    wait_time = between(6, 12)

    def on_start(self):
        self.api_key = register_client(self.client, plan="free")
        if not self.api_key:
            self.environment.runner.quit()


@tag("scenario3", "mixed_traffic", "premium")
class MixedPremiumUser(HttpUser):
    """Premium plan users in the mixed scenario."""
    tasks = [PremiumPlanTasks]
    wait_time = between(1, 3)

    def on_start(self):
        self.api_key = register_client(self.client, plan="premium")
        if not self.api_key:
            self.environment.runner.quit()

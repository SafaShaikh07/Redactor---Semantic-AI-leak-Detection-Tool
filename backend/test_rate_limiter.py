import time
import unittest
from fastapi.testclient import TestClient
from main import app, rate_limiter, SlidingWindowRateLimiter


class TestRateLimiterUnit(unittest.TestCase):
    def test_sliding_window_basic(self):
        limiter = SlidingWindowRateLimiter(limit=5, window_seconds=2.0)
        # 5 requests should pass
        for i in range(5):
            allowed, info = limiter.check_request()
            self.assertTrue(allowed, f"Request {i+1} should be allowed")
            self.assertEqual(info["remaining"], 4 - i)

        # 6th request within window should fail
        allowed, info = limiter.check_request()
        self.assertFalse(allowed, "6th request should be throttled")
        self.assertEqual(info["remaining"], 0)
        self.assertGreaterEqual(info["retry_after"], 1)

        # Status check
        status = limiter.get_status()
        self.assertEqual(status["remaining"], 0)
        self.assertEqual(status["current_requests"], 5)

        # Sleep past window
        time.sleep(2.1)

        # Should be allowed again
        allowed, info = limiter.check_request()
        self.assertTrue(allowed, "Request after window reset should be allowed")
        self.assertEqual(info["remaining"], 4)


class TestRateLimiterIntegration(unittest.TestCase):
    def setUp(self):
        # Reset global rate limiter before each test
        rate_limiter.timestamps.clear()
        self.client = TestClient(app)

    def test_metrics_endpoint_includes_rate_limit(self):
        res = self.client.get("/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("rate_limit", data)
        self.assertEqual(data["rate_limit"]["limit"], 30)
        self.assertEqual(data["rate_limit"]["remaining"], 30)

    def test_normal_typing_simulation(self):
        """Simulate normal fast typing (~600ms per check for 10 seconds = ~16 checks).
        Should never hit rate limit.
        """
        # Reset limiter
        rate_limiter.timestamps.clear()

        # Send 16 checks spaced by 0.05s (simulating 16 checks over window)
        throttled_count = 0
        success_count = 0

        for i in range(16):
            res = self.client.post("/check", json={"text": f"typing check {i}"})
            if res.status_code == 200:
                success_count += 1
                self.assertIn("X-RateLimit-Limit", res.headers)
                self.assertIn("X-RateLimit-Remaining", res.headers)
            elif res.status_code == 429:
                throttled_count += 1

        self.assertEqual(success_count, 16)
        self.assertEqual(throttled_count, 0)

        # Check /metrics reflect remaining = 14
        metrics = self.client.get("/metrics").json()
        self.assertEqual(metrics["rate_limit"]["remaining"], 14)

    def test_rapid_artificial_burst_throttling(self):
        """Simulate rapid artificial requests (50 requests in tight loop).
        First 30 should succeed, remaining 20 should get 429 Too Many Requests.
        """
        rate_limiter.timestamps.clear()

        success_count = 0
        throttled_count = 0

        for i in range(50):
            res = self.client.post("/check", json={"text": f"rapid check {i}"})
            if res.status_code == 200:
                success_count += 1
            elif res.status_code == 429:
                throttled_count += 1
                self.assertIn(res.headers.get("Retry-After"), ["9", "10"])
                self.assertEqual(res.headers.get("X-RateLimit-Remaining"), "0")
                body = res.json()
                self.assertEqual(body["error"], "rate_limit_exceeded")
                self.assertEqual(body["remaining"], 0)

        self.assertEqual(success_count, 30, "First 30 requests should be 200 OK")
        self.assertEqual(throttled_count, 20, "Next 20 requests should be 429 Throttled")

        # Verify /metrics endpoint shows 0 remaining
        metrics = self.client.get("/metrics").json()
        self.assertEqual(metrics["rate_limit"]["remaining"], 0)
        self.assertEqual(metrics["rate_limit"]["current_requests"], 30)


if __name__ == "__main__":
    unittest.main()

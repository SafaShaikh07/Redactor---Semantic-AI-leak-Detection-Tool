import time
import unittest
from fastapi.testclient import TestClient
from main import app, rate_limiter, SlidingWindowRateLimiter
from main import app, rate_limiter, SlidingWindowRateLimiter
from corpus import SEMANTIC_THRESHOLD, analyze_semantic


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
                retry_after = int(res.headers.get("Retry-After", "0"))
                self.assertGreaterEqual(retry_after, 1)
                self.assertLessEqual(retry_after, 10)
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

    def test_repeated_detection_requests(self):
        falcon_positive = [
            "Project Falcon is an unreleased internal initiative scheduled for launch on 15 December.",
            "The unreleased Falcon initiative is scheduled to go live during the middle of December.",
            "Our internal Falcon project is expected to launch around 15 December.",
            "The confidential Falcon programme will be introduced in mid-December.",
            "The Falcon initiative is planned for release during the second half of December.",
        ]
        groups = [
            ("benign", [
                (f"Explain a harmless programming concept, example {index}.", "allow", "none")
                for index in range(10)
            ]),
            ("api_key", [
                (f"API_KEY=sk-test_1234567890abcdef1234567890abcdef item {index}", "redact", "regex")
                for index in range(10)
            ]),
            ("email_phone", [
                (
                    f"Contact test.user{index}@example.com" if index % 2 == 0
                    else f"Call +1-555-555-{index:04d}",
                    "redact",
                    "regex"
                )
                for index in range(10)
            ]),
            ("database_credentials", [
                (f"postgresql://test_user:test_password{index}@localhost:5432/testdb", "block", "regex")
                for index in range(10)
            ]),
            ("falcon_positive", [
                (falcon_positive[index % len(falcon_positive)], "redact", "semantic")
                for index in range(10)
            ]),
            ("falcon_negative", [
                (
                    [
                        "I saw a falcon flying over the mountains during my December vacation.",
                        "We need a general project management plan for our team.",
                        "A harmless public launch announcement for an unrelated product is planned for December.",
                    ][index % 3],
                    "allow",
                    "semantic"
                )
                for index in range(10)
            ]),
            ("mixed", [
                (falcon_positive[index % len(falcon_positive)], "redact", "semantic")
                if index % 2 == 0 else
                (f"Explain a harmless programming concept, example {index}.", "allow", "none")
                for index in range(10)
            ]),
        ]

        request_number = 0
        for group_name, cases in groups:
            with rate_limiter._lock:
                rate_limiter.timestamps.clear()
            latencies = []

            for text, expected_action, mechanism in cases:
                request_number += 1
                semantic_score = analyze_semantic(text).score if mechanism == "semantic" else None
                started = time.perf_counter()
                response = self.client.post("/check", json={"text": text})
                latency_ms = (time.perf_counter() - started) * 1000
                latencies.append(latency_ms)
                data = response.json()
                actual_action = data.get("action", "error")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(actual_action, expected_action)
                if mechanism == "semantic":
                    if expected_action == "redact":
                        self.assertGreaterEqual(semantic_score, SEMANTIC_THRESHOLD)
                    else:
                        self.assertLess(semantic_score, SEMANTIC_THRESHOLD)

                score_text = f"{semantic_score:.4f}" if semantic_score is not None else "n/a"
                print(
                    f"request={request_number} group={group_name} expected={expected_action} "
                    f"actual={actual_action} mechanism={mechanism} score={score_text} "
                    f"latency_ms={latency_ms:.2f} completed={response.status_code == 200}"
                )

            print(
                f"group={group_name} requests={len(cases)} "
                f"avg_ms={sum(latencies) / len(latencies):.2f} max_ms={max(latencies):.2f}"
            )


if __name__ == "__main__":
    unittest.main()

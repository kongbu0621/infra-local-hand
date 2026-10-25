"""Real local HTTP traffic for the candidate gateway's read-only safety checks."""
import socket
import threading
import time
import unittest

from local_hand_mcp import http_observation as observation


class RouteCheckTests(unittest.TestCase):
    def serve_once(self, response, *, delay=0):
        server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen(1)
        self.addCleanup(server.close)
        port = server.getsockname()[1]; requests = []
        def serve():
            try:
                with server.accept()[0] as connection:
                    connection.settimeout(2)
                    requests.append(connection.recv(8192))
                    for block in response:
                        connection.sendall(block)
                        if delay: time.sleep(delay)
            except (OSError, TimeoutError): pass
        thread = threading.Thread(target=serve, daemon=True); thread.start()
        self.addCleanup(thread.join, 2)
        return port, requests

    def test_anonymous_success_is_security_failure_and_no_authorization_sent(self):
        port, requests = self.serve_once([b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\n{}"])
        result = observation.local_check(port, "fixture.invalid", {
            "path": "/mcp", "statuses": [401], "purpose": "anonymous_protected"})
        self.assertEqual("SECURITY_FAILED", result["status"])
        self.assertIn(b"GET /mcp HTTP/1.0", requests[0])
        self.assertNotIn(b"Authorization", requests[0])

    def test_401_and_404_are_real_expected_responses(self):
        for status, purpose in ((401, "anonymous_protected"), (404, "management_hidden")):
            port, _ = self.serve_once([f"HTTP/1.0 {status} Expected\r\nContent-Length: 0\r\n\r\n".encode()])
            self.assertEqual("PASSED", observation.local_check(port, "fixture.invalid", {
                "path": "/mcp", "statuses": [status], "purpose": purpose})["status"])

    def test_wrong_metadata_is_security_failure_but_network_error_is_not(self):
        spec = {"url": "https://fixture.invalid/issuer", "statuses": [200], "purpose": "issuer_metadata",
                "json_equals": {"issuer": "https://fixture.invalid/issuer"}}
        self.assertEqual("SECURITY_FAILED", observation.evaluate(spec, 200, {}, b'{"issuer":"other"}')["status"])
        self.assertEqual("FAILED", observation.evaluate(spec, 503, {}, b'{}')["status"])

    def test_slow_body_has_one_wall_deadline(self):
        port, _ = self.serve_once([b"HTTP/1.0 200 OK\r\n\r\n", *([b"."] * 30)], delay=.05)
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            observation.local_check(port, "fixture.invalid", {"path": "/", "statuses": [200]}, timeout=.15)
        self.assertLess(time.monotonic() - started, .6)

    def test_accepted_anonymous_stream_is_rejected_at_headers(self):
        port, _ = self.serve_once([b"HTTP/1.0 200 OK\r\nContent-Type: text/event-stream\r\n\r\n", b"data: event"], delay=.2)
        result = observation.local_check(port, "fixture.invalid", {
            "path": "/mcp", "statuses": [401], "purpose": "anonymous_protected"}, timeout=.1)
        self.assertEqual("SECURITY_FAILED", result["status"])
        self.assertFalse(result["body_observed"])

    def test_redirect_is_not_followed(self):
        port, requests = self.serve_once([b"HTTP/1.0 302 Found\r\nLocation: https://elsewhere.invalid/\r\nContent-Length: 0\r\n\r\n"])
        self.assertEqual("FAILED", observation.local_check(port, "fixture.invalid", {"path": "/", "statuses": [200]})["status"])
        self.assertEqual(1, len(requests))

    def test_relative_only_paths_and_strict_deny_expectations(self):
        for path in ("https://other/", "//other/", "/path?key=x", "/path#fragment", "/\r\nX:"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                observation.validate_check({"path": path, "statuses": [200]}, path=True)
        with self.assertRaises(ValueError):
            observation.validate_check({"path": "/mcp", "purpose": "anonymous_protected", "statuses": [200]}, path=True)


if __name__ == "__main__": unittest.main()

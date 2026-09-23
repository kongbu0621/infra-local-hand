"""Synthetic issuer tests; no external account, credential or live host access."""
from __future__ import annotations

import asyncio
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs.contract import JobError
from local_hand_mcp.auth import AuthConfig, JWTVerifier

HAS_EXTRA = all(importlib.util.find_spec(name) for name in ("mcp", "jwt", "httpx2", "cryptography"))


class SyntheticIssuer:
    """A bounded HTTP transport fixture, not an authentication bypass."""
    def __init__(self):
        import httpx2
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.key = jwt.algorithms.RSAAlgorithm.to_jwk(self.private.public_key(), as_dict=True)
        self.key.update(kid="key-one", alg="RS256", use="sig")
        self.other_key = jwt.algorithms.RSAAlgorithm.to_jwk(self.other_private.public_key(), as_dict=True)
        self.other_key.update(kid="key-two", alg="RS256", use="sig")
        self.keys = [self.key]
        self.calls = []
        self.status = 200
        self.now = 100.0
        self.configuration = {
            "schema_version": "lh-mcp-auth-v1", "registration": "predefined",
            "issuer": "https://issuer.example", "resource": "http://127.0.0.1:8765/mcp",
            "metadata_url": "https://issuer.example/.well-known/oauth-authorization-server",
            "authorization_endpoint": "https://issuer.example/authorize",
            "token_endpoint": "https://issuer.example/token", "jwks_uri": "https://issuer.example/keys",
            "client_id": "synthetic-client", "redirect_uris": ["http://127.0.0.1:8766/callback"],
            "algorithms": ["RS256"], "subject_map": {"issuer-user-a": "project-owner"},
            "scopes": ["lh:inspect", "lh:submit", "lh:read", "lh:cancel", "lh:reconcile", "lh:evidence"],
            "jwks_ttl_seconds": 120, "refresh_cooldown_seconds": 10, "request_timeout_seconds": 2,
            "clock_skew_seconds": 0, "maximum_token_seconds": 600,
        }
        self.config = AuthConfig.from_dict(self.configuration)
        self.metadata = {name: self.configuration[name] for name in
                         ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")}
        self.metadata.update(response_types_supported=["code"], grant_types_supported=["authorization_code"],
                             code_challenge_methods_supported=["S256"], scopes_supported=self.config.scopes,
                             token_endpoint_auth_methods_supported=["none"])
        self.transport = httpx2.MockTransport(self.handle)
        self.verifier = JWTVerifier(self.config, http_transport=self.transport, clock=lambda: self.now)

    def handle(self, request):
        import httpx2
        self.calls.append(str(request.url))
        data = self.metadata if str(request.url) == self.config.metadata_url else {"keys": self.keys}
        return httpx2.Response(self.status, json=data)

    def token(self, *, claims=None, headers=None, private=None):
        import jwt
        now = int(time.time())
        payload = {"iss": self.config.issuer, "aud": self.config.resource, "sub": "issuer-user-a",
                   "iat": now - 1, "nbf": now - 1, "exp": now + 300,
                   "scope": " ".join(self.config.scopes), "client_id": self.config.client_id}
        payload.update(claims or {})
        return jwt.encode(payload, private or self.private, algorithm="RS256",
                          headers={"kid": "key-one", **(headers or {})})


@unittest.skipUnless(HAS_EXTRA, "Optional pinned MCP extra is not installed")
class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.issuer = SyntheticIssuer()

    async def test_signature_principal_scope_and_token_renewal(self):
        first = await self.issuer.verifier.authenticate(self.issuer.token())
        second = await self.issuer.verifier.authenticate(self.issuer.token(claims={"jti": "renewed"}))
        self.assertEqual(self.issuer.verifier.principal(first), self.issuer.verifier.principal(second))
        self.assertEqual("project-owner", self.issuer.verifier.principal(first).principal_id)
        self.assertEqual(1, len(self.issuer.calls))

    async def test_expired_in_process_authentication_cannot_authorize_a_new_call(self):
        access = await self.issuer.verifier.authenticate(self.issuer.token())
        with patch("local_hand_mcp.auth.time.time", return_value=access.expires_at + 1):
            with self.assertRaises(JobError) as caught:
                self.issuer.verifier.principal(access)
        self.assertEqual(caught.exception.code, "UNAUTHORIZED")

    async def test_in_process_authentication_rechecks_current_jwks_admission(self):
        # A body/dispatch queue may outlive the key used by SDK authentication.
        # No new broker call may use a stale verification after current JWKS
        # admission expires, fails, removes a key, or changes the same kid.
        for change in ("expired", "removed", "same-kid-replaced", "refresh-failed"):
            with self.subTest(change=change):
                issuer = SyntheticIssuer()
                token = issuer.token()
                access = await issuer.verifier.authenticate(token)
                if change == "expired":
                    issuer.now += issuer.config.jwks_ttl_seconds + 1
                else:
                    issuer.now += issuer.config.refresh_cooldown_seconds + 1
                    issuer.keys = [issuer.other_key]
                    if change == "same-kid-replaced":
                        issuer.keys = [{**issuer.other_key, "kid": "key-one"}]
                        issuer.now += issuer.config.jwks_ttl_seconds
                    elif change == "refresh-failed":
                        issuer.status = 503
                    # Trigger the refresh with a genuine signed token; the
                    # old access object remains alive in another request.
                    await issuer.verifier.verify_token(issuer.token(
                        private=issuer.other_private, headers={"kid": "key-two"}))
                    self.assertIsNone(await issuer.verifier.verify_token(token))
                with self.assertRaises(JobError) as caught:
                    issuer.verifier.principal(access)
                self.assertEqual(caught.exception.code, "UNAUTHORIZED")

    async def test_unchanged_key_refresh_preserves_in_process_authentication(self):
        access = await self.issuer.verifier.authenticate(self.issuer.token())
        self.issuer.now += self.issuer.config.jwks_ttl_seconds + 1
        renewed = await self.issuer.verifier.authenticate(self.issuer.token())
        self.assertEqual(self.issuer.verifier.principal(access), self.issuer.verifier.principal(renewed))

    async def test_negative_issuer_audience_time_subject_scope_and_client(self):
        now = int(time.time())
        for claims in ({"iss": "https://other.example"}, {"aud": "another-resource"},
                       {"aud": [self.issuer.config.resource]}, {"exp": now - 1},
                       {"nbf": now + 500}, {"iat": True}, {"exp": now + 10000},
                       {"sub": "other-user"}, {"scope": "unknown"}, {"scope": "lh:read  lh:submit"},
                       {"client_id": "other-client"}):
            with self.subTest(claims=claims):
                self.assertIsNone(await self.issuer.verifier.verify_token(self.issuer.token(claims=claims)))

    async def test_forged_signature_unknown_kid_and_attacker_key_urls(self):
        bad = [self.issuer.token(private=self.issuer.other_private)]
        for headers in ({"kid": "not-admitted"}, {"jku": "https://attacker.example/keys"},
                        {"x5u": "file:///secret"}, {"jwk": self.issuer.key},
                        {"crit": ["custom"]}, {"typ": "unexpected"}):
            bad.append(self.issuer.token(headers=headers))
        for token in bad:
            self.assertIsNone(await self.issuer.verifier.verify_token(token))
        self.assertTrue(all(url == self.issuer.config.jwks_uri for url in self.issuer.calls))

    async def test_unsigned_hmac_opaque_and_malformed_tokens(self):
        import jwt
        tokens = ["opaque", "a.b.c", "x" * 16385, jwt.encode({"sub": "issuer-user-a"}, "", algorithm="none"),
                  jwt.encode({"sub": "issuer-user-a"}, "synthetic-secret-for-negative-test-only", algorithm="HS256", headers={"kid": "key-one"})]
        for token in tokens:
            self.assertIsNone(await self.issuer.verifier.verify_token(token))
        self.assertEqual([], self.issuer.calls)

    async def test_duplicate_signed_claim_is_rejected_after_signature_validation(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        token = self.issuer.token()
        header, payload, _ = token.split(".")
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        raw = raw[:-1] + b',"sub":"issuer-user-a"}'
        payload = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
        signing = f"{header}.{payload}".encode()
        signature = self.issuer.private.sign(signing, padding.PKCS1v15(), hashes.SHA256())
        encoded = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
        self.assertIsNone(await self.issuer.verifier.verify_token(f"{header}.{payload}.{encoded}"))

    async def test_rotation_cooldown_and_expired_jwks_fail_closed(self):
        original = self.issuer.token()
        self.assertIsNotNone(await self.issuer.verifier.verify_token(original))
        rotated = self.issuer.token(private=self.issuer.other_private, headers={"kid": "key-two"})
        self.issuer.keys = [self.issuer.other_key]
        self.assertIsNone(await self.issuer.verifier.verify_token(rotated))
        self.assertEqual(1, len(self.issuer.calls))
        self.issuer.now += 11
        self.assertIsNotNone(await self.issuer.verifier.verify_token(rotated))
        self.assertIsNone(await self.issuer.verifier.verify_token(original))
        self.issuer.now += 121
        self.issuer.status = 503
        self.assertIsNone(await self.issuer.verifier.verify_token(rotated))
        self.assertIsNone(await self.issuer.verifier.verify_token(rotated))
        self.assertEqual(3, len(self.issuer.calls))

    async def test_duplicate_key_ids_and_wrong_algorithm_are_not_accepted(self):
        for keys in ([self.issuer.key, self.issuer.key], [{**self.issuer.key, "alg": "HS256"}],
                     [{**self.issuer.key, "key_ops": ["sign", "verify"]}]):
            self.issuer.keys = keys
            self.issuer.now += 121
            self.assertIsNone(await self.issuer.verifier.verify_token(self.issuer.token()))

    async def test_first_link_and_reauthorization_require_pkce_discovery(self):
        await self.issuer.verifier.validate_issuer_metadata()
        self.issuer.metadata["code_challenge_methods_supported"] = ["plain"]
        with self.assertRaises(JobError):
            await self.issuer.verifier.validate_issuer_metadata()
        self.issuer.metadata["code_challenge_methods_supported"] = ["S256"]
        self.issuer.metadata["jwks_uri"] = "https://attacker.example/keys"
        with self.assertRaises(JobError):
            await self.issuer.verifier.validate_issuer_metadata()

    async def test_issuer_http_errors_are_sanitized(self):
        self.issuer.status = 302
        with self.assertRaises(JobError) as caught:
            await self.issuer.verifier.authenticate(self.issuer.token())
        self.assertNotIn("issuer.example", str(caught.exception))

    async def test_compressed_issuer_documents_are_rejected_before_inflation(self):
        import gzip
        import httpx2

        observed = []

        class CompressedBody(httpx2.AsyncByteStream):
            async def __aiter__(self):
                observed.append("body-consumed")
                yield gzip.compress(json.dumps(self.issuer.metadata).encode())

        # Capture the fixture without making the response object a buffered
        # response: the real client must decide from headers before decoding.
        body = CompressedBody()
        body.issuer = self.issuer
        transport = httpx2.MockTransport(lambda request: httpx2.Response(
            200, headers={"Content-Encoding": "gzip"}, stream=body))
        verifier = JWTVerifier(self.issuer.config, http_transport=transport)
        with self.assertRaises(JobError):
            await verifier.validate_issuer_metadata()
        self.assertEqual([], observed)

    async def test_issuer_document_stream_has_a_finite_read_bound(self):
        import httpx2
        from local_hand_mcp.auth import MAX_AUTH_DOCUMENT

        observed = []

        class EndlessBody(httpx2.AsyncByteStream):
            async def __aiter__(self):
                while True:
                    observed.append(1024)
                    yield b" " * 1024

        requested = []

        def respond(request):
            requested.append(request.headers.get("Accept-Encoding"))
            return httpx2.Response(200, stream=EndlessBody())

        verifier = JWTVerifier(self.issuer.config, http_transport=httpx2.MockTransport(respond))
        with self.assertRaises(JobError):
            await verifier.validate_issuer_metadata()
        self.assertEqual(["identity"], requested)
        self.assertLessEqual(sum(observed), MAX_AUTH_DOCUMENT + 4096)

    def test_private_config_and_untrusted_locations(self):
        for changes in ({"algorithms": ["none"]}, {"jwks_uri": "file:///secret"},
                        {"issuer": "http://remote.example"}, {"registration": "dynamic"},
                        {"clock_skew_seconds": True}, {"jwks_ttl_seconds": 0}, {"secret": "forbidden"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                AuthConfig.from_dict({**self.issuer.configuration, **changes})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auth.json"
            path.write_text(json.dumps(self.issuer.configuration))
            path.chmod(0o600)
            self.assertEqual(self.issuer.config, AuthConfig.from_file(str(path)))
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                AuthConfig.from_file(str(path))
            path.chmod(0o600)
            link = Path(folder) / "alias.json"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                AuthConfig.from_file(str(link))

    def test_failed_file_wrapper_closes_untransferred_auth_descriptor(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auth.json"
            path.write_text(json.dumps(self.issuer.configuration))
            path.chmod(0o600)
            acquired = []
            def fail_wrapper(fd, *args, **kwargs):
                acquired.append(fd)
                raise OSError("synthetic wrapper allocation failure")
            with patch("os.fdopen", side_effect=fail_wrapper):
                with self.assertRaises(ValueError):
                    AuthConfig.from_file(str(path))
            self.assertEqual(1, len(acquired))
            closed = False
            try:
                os.fstat(acquired[0])
            except OSError:
                closed = True
            finally:
                if not closed:
                    os.close(acquired[0])
            self.assertTrue(closed, "The failed wrapper must not retain the opened configuration FD")

    def test_wrapper_failure_survives_a_raw_descriptor_close_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "auth.json"
            path.write_text("{}")
            path.chmod(0o600)
            failure = RuntimeError("synthetic wrapper allocation failure")
            closed = []
            real_close = os.close
            def close_then_fail(fd):
                real_close(fd)
                closed.append(fd)
                raise OSError("synthetic close failure")
            with patch("os.fdopen", side_effect=failure), patch("os.close", side_effect=close_then_fail):
                with self.assertRaises(RuntimeError) as caught:
                    AuthConfig.from_file(str(path))
            self.assertIs(failure, caught.exception)
            self.assertEqual(1, len(closed))


if __name__ == "__main__":
    unittest.main()

"""Startup must validate the same public keys used by token verification."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from test_local_hand_mcp_auth import HAS_EXTRA, SyntheticIssuer
from local_hand_jobs.contract import JobError
from local_hand_mcp.auth import JWTVerifier


@unittest.skipUnless(HAS_EXTRA, "Optional pinned MCP extra is not installed")
class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_keys_are_used_by_the_first_authenticated_call(self):
        issuer = SyntheticIssuer()
        issuer.keys.insert(0, {**issuer.other_key, "use": "enc", "alg": "RSA-OAEP"})
        await issuer.verifier.validate_readiness()
        access = await issuer.verifier.authenticate(issuer.token())
        self.assertEqual("project-owner", issuer.verifier.principal(access).principal_id)
        self.assertEqual([issuer.config.metadata_url, issuer.config.jwks_uri], issuer.calls)

    async def test_unusable_keys_refuse_readiness_and_invalidate_old_admission(self):
        for change in ("empty", "encryption-only", "private", "duplicate", "weak", "malformed"):
            with self.subTest(change=change):
                issuer = SyntheticIssuer()
                access = await issuer.verifier.authenticate(issuer.token())
                issuer.keys = {
                    "empty": [], "encryption-only": [{**issuer.key, "use": "enc"}],
                    "private": [{**issuer.key, "d": "private-material"}],
                    "duplicate": [issuer.key, issuer.key],
                    "weak": [{**issuer.key, "n": "Aw"}], "malformed": [None],
                }[change]
                with self.assertRaises(JobError):
                    await issuer.verifier.validate_readiness()
                with self.assertRaises(JobError):
                    issuer.verifier.principal(access)

    async def test_metadata_mismatch_never_fetches_keys(self):
        issuer = SyntheticIssuer()
        issuer.metadata["jwks_uri"] = "https://untrusted.example/keys"
        with self.assertRaises(JobError):
            await issuer.verifier.validate_readiness()
        self.assertEqual([issuer.config.metadata_url], issuer.calls)

    async def test_asgi_lifespan_does_not_accept_requests_without_signing_keys(self):
        from local_hand_mcp.server import create_app
        from test_local_hand_mcp_server import MemoryBroker

        issuer, broker = SyntheticIssuer(), MemoryBroker()
        issuer.keys = [{**issuer.key, "use": "enc"}]
        app = create_app(broker, issuer.verifier)
        with self.assertRaises(JobError):
            async with app.router.lifespan_context(app):
                self.fail("ASGI startup admitted an issuer without verification keys")
        self.assertEqual([], broker.calls)

    async def test_unavailable_keys_have_a_finite_startup_budget(self):
        import httpx2
        issuer = SyntheticIssuer()
        calls = []

        def respond(request):
            calls.append(str(request.url))
            if str(request.url) == issuer.config.metadata_url:
                return issuer.handle(request)
            return httpx2.Response(503)

        verifier = JWTVerifier(issuer.config, http_transport=httpx2.MockTransport(respond))
        with patch("local_hand_mcp.auth.asyncio.sleep", new_callable=AsyncMock) as sleep:
            with self.assertRaises(JobError):
                await verifier.validate_readiness()
        self.assertEqual([issuer.config.metadata_url] + [issuer.config.jwks_uri] * 6, calls)
        self.assertEqual(5, sleep.await_count)

    async def test_transient_key_failure_retries_only_the_trusted_key_url(self):
        import httpx2
        issuer = SyntheticIssuer()
        calls = []

        def respond(request):
            calls.append(str(request.url))
            if len(calls) == 2:
                return httpx2.Response(503)
            return issuer.handle(request)

        verifier = JWTVerifier(issuer.config, http_transport=httpx2.MockTransport(respond))
        with patch("local_hand_mcp.auth.asyncio.sleep", new_callable=AsyncMock) as sleep:
            await verifier.validate_readiness()
        self.assertEqual([issuer.config.metadata_url, issuer.config.jwks_uri,
                          issuer.config.jwks_uri], calls)
        self.assertEqual([1], [item.args[0] for item in sleep.await_args_list])
        self.assertIsNotNone(await verifier.verify_token(issuer.token()))
        self.assertEqual(3, len(calls))

    async def test_permanent_key_failure_is_not_retried(self):
        import httpx2
        for status in (302, 400, 401, 403, 404):
            with self.subTest(status=status):
                issuer = SyntheticIssuer()

                def respond(request):
                    if str(request.url) == issuer.config.metadata_url:
                        return issuer.handle(request)
                    return httpx2.Response(status)

                verifier = JWTVerifier(issuer.config, http_transport=httpx2.MockTransport(respond))
                with patch("local_hand_mcp.auth.asyncio.sleep", new_callable=AsyncMock) as sleep:
                    with self.assertRaises(JobError):
                        await verifier.validate_readiness()
                sleep.assert_not_awaited()

    async def test_total_deadline_and_cancellation_close_pending_key_read(self):
        import httpx2
        issuer = SyntheticIssuer()
        entered, closed = asyncio.Event(), asyncio.Event()

        async def respond(request):
            if str(request.url) == issuer.config.metadata_url:
                return issuer.handle(request)
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()

        verifier = JWTVerifier(issuer.config, http_transport=httpx2.MockTransport(respond))
        with patch("local_hand_mcp.auth.STARTUP_METADATA_TIMEOUT", 0.03):
            with self.assertRaises(JobError):
                await verifier.validate_readiness()
        self.assertTrue(closed.is_set())
        entered.clear()
        closed.clear()
        task = asyncio.create_task(verifier.validate_readiness())
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(closed.is_set())
        self.assertEqual({}, dict(verifier._key_cache[0]))

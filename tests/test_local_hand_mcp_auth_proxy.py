"""Explicit issuer-document proxy tests; synthetic endpoints and keys only."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import ssl
import tempfile
import time
import unittest
from unittest.mock import patch

from test_local_hand_mcp_auth import HAS_EXTRA, SyntheticIssuer
from local_hand_jobs.contract import JobError
from local_hand_mcp.auth import AuthConfig, JWTVerifier, _DocumentUnavailable


@unittest.skipUnless(HAS_EXTRA, "Optional pinned MCP extra is not installed")
class AuthProxyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.issuer = SyntheticIssuer()

    def config(self, proxy):
        return AuthConfig.from_dict({**self.issuer.configuration, "document_proxy_url": proxy})

    def test_old_config_stays_direct_and_proxy_is_optional(self):
        self.assertIsNone(self.issuer.config.document_proxy_url)
        self.assertEqual(self.issuer.config, self.config(None))
        for proxy in ("http://127.0.0.1:2080", "http://localhost:3128/",
                      "http://[::1]:8080"):
            self.assertEqual(proxy, self.config(proxy).document_proxy_url)
        missing = dict(self.issuer.configuration)
        del missing["jwks_uri"]
        with self.assertRaises(ValueError):
            AuthConfig.from_dict(missing)

    def test_proxy_is_only_an_explicit_loopback_http_endpoint_without_credentials(self):
        for value in ("", False, 2080, [], {}, "http://proxy.example:2080",
                      "http://127.0.0.1", "http://127.0.0.1:0", "http://127.0.0.1:65536",
                      "http://127.0.0.1:2080/path", "http://127.0.0.1:2080?secret",
                      "http://127.0.0.1:2080#secret", "http://user:secret@127.0.0.1:2080",
                      "http://@127.0.0.1:2080", "http://127.0.0.1:2080\n",
                      "socks5://127.0.0.1:2080", "https://127.0.0.1:2080",
                      "http://127.0.0.1.evil.example:2080", "http://[::1%25eth0]:2080"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.config(value)
        with self.assertRaises(ValueError):
            AuthConfig.from_dict({**self.issuer.configuration, "verify": False})

    async def test_proxy_selection_preserves_loopback_bypass_and_tls(self):
        import httpx2
        actual = httpx2.AsyncClient
        observed = []

        def client(**kwargs):
            observed.append(kwargs.copy())
            # Only this test intercepts the selected transport after recording
            # it. Production has no configurable transport or TLS bypass.
            return actual(**{**kwargs, "proxy": None, "transport": self.issuer.transport})

        verifier = JWTVerifier(self.config("http://127.0.0.1:2080"))
        urls = [self.issuer.config.metadata_url, self.issuer.config.jwks_uri,
                "http://localhost:8765/keys", "http://127.0.0.1:8765/keys",
                "http://[::1]:8765/keys", "https://localhost/keys"]
        with patch.object(httpx2, "AsyncClient", side_effect=client), \
                patch.dict(os.environ, {"HTTPS_PROXY": "http://untrusted.example:9999",
                                        "NO_PROXY": "*", "SSL_CERT_FILE": "/nonexistent"}):
            for url in urls:
                await verifier._document(url)
        self.assertEqual(["http://127.0.0.1:2080"] * 2 + [None] * 4,
                         [item["proxy"] for item in observed])
        for options in observed:
            self.assertIs(options["trust_env"], False)
            self.assertIs(options["verify"], True)
            self.assertIs(options["follow_redirects"], False)
            self.assertEqual(self.issuer.config.request_timeout_seconds, options["timeout"])

    async def test_real_loopback_target_bypasses_a_rejecting_proxy(self):
        requests, tasks = [], set()

        async def connection(reader, writer):
            tasks.add(asyncio.current_task())
            try:
                async with asyncio.timeout(3):
                    header = await reader.readuntil(b"\r\n\r\n")
                    requests.append(header)
                    if header.startswith(b"GET /keys HTTP/1.1\r\n"):
                        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                                     b"Content-Length: 2\r\nConnection: close\r\n\r\n{}")
                    else:
                        writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(connection, "127.0.0.1", 0, limit=8192)
        port = server.sockets[0].getsockname()[1]
        try:
            async with server:
                # If the client tries a proxy-style absolute URL or CONNECT,
                # this same listener rejects it instead of serving the target.
                verifier = JWTVerifier(self.config(f"http://127.0.0.1:{port}"))
                self.assertEqual({}, await verifier._document(f"http://127.0.0.1:{port}/keys"))
        finally:
            server.close()
            await server.wait_closed()
            if tasks:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=4)
        self.assertEqual(1, len(requests))
        self.assertTrue(requests[0].startswith(b"GET /keys HTTP/1.1\r\n"))

    async def test_injected_transport_cannot_escape_to_configured_proxy(self):
        requests, tasks = [], set()

        async def reject(reader, writer):
            tasks.add(asyncio.current_task())
            try:
                async with asyncio.timeout(3):
                    requests.append(await reader.readuntil(b"\r\n\r\n"))
                    writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(reject, "127.0.0.1", 0, limit=8192)
        port = server.sockets[0].getsockname()[1]
        try:
            async with server:
                verifier = JWTVerifier(self.config(f"http://127.0.0.1:{port}"),
                                       http_transport=self.issuer.transport)
                # The explicit test transport must handle BOTH documents.
                # No socket, proxy, or external issuer should be contacted.
                await verifier._document(verifier.config.metadata_url)
                token = await verifier.authenticate(self.issuer.token())
                self.assertEqual("project-owner", verifier.principal(token).principal_id)
        finally:
            server.close()
            await server.wait_closed()
            if tasks:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=4)
        self.assertEqual([], requests)
        self.assertEqual([verifier.config.metadata_url, verifier.config.jwks_uri],
                         self.issuer.calls)

    async def test_real_proxy_failure_and_stall_are_bounded_without_direct_fallback(self):
        for response in (b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n", None):
            with self.subTest(response=response):
                requests, tasks = [], set()

                async def reject_or_stall(reader, writer):
                    tasks.add(asyncio.current_task())
                    try:
                        async with asyncio.timeout(3):
                            requests.append(await reader.readuntil(b"\r\n\r\n"))
                            if response:
                                writer.write(response)
                                await writer.drain()
                            else:
                                # The client's total deadline must close the
                                # socket even before CONNECT returns headers.
                                self.assertEqual(b"", await reader.read(1))
                    finally:
                        writer.close()
                        await writer.wait_closed()

                server = await asyncio.start_server(reject_or_stall, "127.0.0.1", 0, limit=8192)
                port = server.sockets[0].getsockname()[1]
                verifier = JWTVerifier(AuthConfig.from_dict({
                    **self.issuer.configuration, "request_timeout_seconds": 1,
                    "document_proxy_url": f"http://127.0.0.1:{port}",
                }))
                started = time.monotonic()
                try:
                    async with server:
                        # Numeric loopback connects without a DNS lookup. Any
                        # attempted direct issuer fallback is a test failure.
                        with patch("socket.getaddrinfo", side_effect=AssertionError("direct DNS forbidden")) as dns, \
                                self.assertLogs("local_hand_mcp.auth", level="WARNING"), \
                                self.assertRaises(_DocumentUnavailable):
                            await asyncio.wait_for(verifier._document(verifier.config.metadata_url), 3)
                        dns.assert_not_called()
                finally:
                    server.close()
                    await server.wait_closed()
                    if tasks:
                        await asyncio.wait_for(asyncio.gather(*tasks), timeout=4)
                self.assertLess(time.monotonic() - started, 3)
                self.assertEqual(1, len(requests))
                self.assertTrue(requests[0].startswith(b"CONNECT issuer.example:443 HTTP/1.1\r\n"))

    async def test_real_connect_tunnel_success_and_untrusted_certificate_rejection(self):
        """Exercise HTTP CONNECT + TLS; never contact an external host."""
        import httpx2
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.x509.oid import NameOID

        key = self.issuer.private
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "issuer.example")])
        now = datetime.now(timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                       .public_key(key.public_key()).serial_number(x509.random_serial_number())
                       .not_valid_before(now - timedelta(days=1))
                       .not_valid_after(now + timedelta(days=1))
                       .add_extension(x509.SubjectAlternativeName(
                           [x509.DNSName("issuer.example")]), critical=False)
                       .sign(key, hashes.SHA256()))
        requests, origins, tasks = [], [], set()
        with tempfile.TemporaryDirectory(prefix="lh-auth-proxy-") as folder:
            cert_file, key_file = Path(folder) / "cert.pem", Path(folder) / "key.pem"
            cert_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
            key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                 serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            key_file.chmod(0o600)
            server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_tls.load_cert_chain(cert_file, key_file)
            trusted_tls = ssl.create_default_context(cafile=str(cert_file))
            self.assertTrue(trusted_tls.check_hostname)
            self.assertEqual(ssl.CERT_REQUIRED, trusted_tls.verify_mode)

            async def connection(reader, writer):
                tasks.add(asyncio.current_task())
                try:
                    async with asyncio.timeout(5):
                        header = await reader.readuntil(b"\r\n\r\n")
                        requests.append(header)
                        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                        await writer.drain()
                        await writer.start_tls(server_tls, ssl_handshake_timeout=3)
                        origin = await reader.readuntil(b"\r\n\r\n")
                        origins.append(origin)
                        path = origin.split(b" ", 2)[1]
                        self.assertIn(path, (b"/.well-known/oauth-authorization-server", b"/keys"))
                        body = json.dumps(self.issuer.metadata if path != b"/keys"
                                          else {"keys": self.issuer.keys}).encode()
                        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                                     + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                                     + body)
                        await writer.drain()
                except (ssl.SSLError, ConnectionError, asyncio.IncompleteReadError, TimeoutError):
                    pass  # The negative case aborts its TLS handshake.
                finally:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except (ssl.SSLError, ConnectionError):
                        pass

            server = await asyncio.start_server(connection, "127.0.0.1", 0, limit=8192)
            port = server.sockets[0].getsockname()[1]
            actual = httpx2.AsyncClient

            def trust_test_issuer(**kwargs):
                self.assertIs(kwargs["verify"], True)
                return actual(**{**kwargs, "verify": trusted_tls})

            try:
                async with server:
                    verifier = JWTVerifier(self.config(f"http://127.0.0.1:{port}"),
                                           clock=lambda: self.issuer.now)
                    # Trust only the synthetic fixture certificate, retaining
                    # certificate and hostname verification in the real client.
                    with patch.object(httpx2, "AsyncClient", side_effect=trust_test_issuer):
                        await verifier.validate_issuer_metadata()
                        original = self.issuer.token()
                        access = await verifier.authenticate(original)
                        self.assertEqual("project-owner", verifier.principal(access).principal_id)
                        self.assertIsNone(await verifier.verify_token(
                            self.issuer.token(private=self.issuer.other_private)))
                        self.issuer.now += self.issuer.config.refresh_cooldown_seconds + 1
                        self.issuer.keys = [self.issuer.other_key]
                        rotated = await verifier.authenticate(self.issuer.token(
                            private=self.issuer.other_private, headers={"kid": "key-two"}))
                        self.assertEqual("project-owner", verifier.principal(rotated).principal_id)
                        with self.assertRaises(JobError):
                            verifier.principal(access)
                        self.assertIsNone(await verifier.verify_token(original))
                        # Trust in a CA is insufficient: the tunnel target
                        # must also match the certificate's DNS identity.
                        with self.assertLogs("local_hand_mcp.auth", level="WARNING") as mismatch, \
                                self.assertRaises(JobError):
                            await verifier._document("https://other.example/keys")
                        self.assertIn("SSLCertVerificationError", "\n".join(mismatch.output))
                        self.assertIn("stage=tls reason=tls_or_local_protocol", "\n".join(mismatch.output))
                        self.assertNotIn("other.example", "\n".join(mismatch.output))
                    # Production defaults must reject that same self-signed
                    # certificate through the same real CONNECT tunnel.
                    with self.assertLogs("local_hand_mcp.auth", level="WARNING") as logs, \
                            self.assertRaises(JobError):
                        await verifier._document(verifier.config.metadata_url)
                    self.assertIn("SSLCertVerificationError", "\n".join(logs.output))
                    self.assertIn("stage=tls reason=tls_or_local_protocol", "\n".join(logs.output))
            finally:
                server.close()
                await server.wait_closed()
                if tasks:
                    await asyncio.wait_for(asyncio.gather(*tasks), timeout=6)
            self.assertEqual(
                [b"CONNECT issuer.example:443 HTTP/1.1"] * 3
                + [b"CONNECT other.example:443 HTTP/1.1", b"CONNECT issuer.example:443 HTTP/1.1"],
                [request.split(b"\r\n", 1)[0] for request in requests])
            self.assertEqual(3, len(origins))
            for request in requests + origins:
                self.assertNotIn(b"authorization:", request.lower())


if __name__ == "__main__":
    unittest.main()

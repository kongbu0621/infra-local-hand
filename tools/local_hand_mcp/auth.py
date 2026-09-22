"""JWT resource-server authentication for an explicitly admitted external issuer.

This module issues no tokens and implements no cryptography. Network locations and
stable subject mappings come exclusively from protected deployment configuration.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import json
import re
import time
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlsplit

from local_hand_jobs.contract import JobError, Principal, strict_loads

MAX_AUTH_DOCUMENT = 65536
MAX_TOKEN = 16384
MAX_KEYS = 32
_TOKEN_PART = re.compile(r"[A-Za-z0-9_-]+\Z")
_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
_SCOPE = re.compile(r"[A-Za-z0-9:._-]{1,128}\Z")
_ALGORITHMS = frozenset({"RS256", "ES256"})


def _deny() -> JobError:
    return JobError("UNAUTHORIZED", "Access token could not be verified")


def _url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Invalid admitted authorization URL")
    parts = urlsplit(value)
    if (parts.username or parts.password or parts.fragment or parts.query
            or not parts.hostname or any(ord(c) < 33 or ord(c) > 126 for c in value)):
        raise ValueError("Invalid admitted authorization URL")
    # Plain HTTP is only meaningful on loopback; no configurable TLS bypass.
    if parts.scheme != "https" and not (
        parts.scheme == "http" and parts.hostname in {"127.0.0.1", "::1", "localhost"}
    ):
        raise ValueError("Authorization URLs require HTTPS or loopback HTTP")
    try:
        parts.port
    except ValueError:
        raise ValueError("Invalid admitted authorization port") from None
    return value


def _positive(value: object, maximum: int) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        raise ValueError("Invalid finite authorization budget")
    return value


@dataclass(frozen=True)
class AuthConfig:
    issuer: str
    resource: str
    metadata_url: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    client_id: str
    redirect_uris: tuple[str, ...]
    algorithms: tuple[str, ...]
    subject_map: Mapping[str, str]
    scopes: tuple[str, ...]
    jwks_ttl_seconds: int
    refresh_cooldown_seconds: int
    request_timeout_seconds: int
    clock_skew_seconds: int
    maximum_token_seconds: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthConfig":
        fields = set(cls.__dataclass_fields__)
        if not isinstance(data, dict) or set(data) != fields | {"schema_version", "registration"}:
            raise ValueError("Authorization configuration has missing or unknown fields")
        if data["schema_version"] != "lh-mcp-auth-v1" or data["registration"] != "predefined":
            raise ValueError("Only admitted predefined OAuth clients are supported")
        values = {key: data[key] for key in fields}
        for key in ("issuer", "resource", "metadata_url", "authorization_endpoint", "token_endpoint", "jwks_uri"):
            values[key] = _url(values[key])
        issuer = urlsplit(values["issuer"])
        base = f"{issuer.scheme}://{issuer.netloc}"
        issuer_path = issuer.path.rstrip("/")
        if values["metadata_url"] not in {
            base + "/.well-known/oauth-authorization-server" + issuer_path,
            base + issuer_path + "/.well-known/openid-configuration",
        }:
            raise ValueError("Authorization metadata must use the issuer's standard discovery location")
        if not isinstance(values["client_id"], str) or not _SCOPE.fullmatch(values["client_id"]):
            raise ValueError("Invalid predefined OAuth client identifier")
        for key in ("redirect_uris", "algorithms", "scopes"):
            value = values[key]
            if (type(value) is not list or not 0 < len(value) <= 32
                    or any(not isinstance(item, str) for item in value) or len(value) != len(set(value))):
                raise ValueError("Invalid authorization allowlist")
            values[key] = tuple(value)
        values["redirect_uris"] = tuple(_url(uri) for uri in values["redirect_uris"])
        if not set(values["algorithms"]) <= _ALGORITHMS:
            raise ValueError("JWT algorithm is outside the fixed asymmetric allowlist")
        if any(not isinstance(s, str) or not _SCOPE.fullmatch(s) for s in values["scopes"]):
            raise ValueError("Invalid admitted OAuth scope")
        subjects = values["subject_map"]
        if type(subjects) is not dict or not 0 < len(subjects) <= 1024:
            raise ValueError("Stable subject admission is required")
        for subject, principal in subjects.items():
            if (not isinstance(subject, str) or not 0 < len(subject) <= 256
                    or any(ord(c) < 33 or ord(c) > 126 for c in subject)
                    or not isinstance(principal, str) or not _NAME.fullmatch(principal)):
                raise ValueError("Invalid stable subject admission")
        values["subject_map"] = MappingProxyType(dict(subjects))
        for key, maximum in (("jwks_ttl_seconds", 3600), ("refresh_cooldown_seconds", 300),
                             ("request_timeout_seconds", 10), ("maximum_token_seconds", 86400)):
            values[key] = _positive(values[key], maximum)
        skew = values["clock_skew_seconds"]
        if type(skew) is not int or not 0 <= skew <= 60:
            raise ValueError("Invalid clock uncertainty bound")
        if values["refresh_cooldown_seconds"] > values["jwks_ttl_seconds"]:
            raise ValueError("JWKS cooldown exceeds cache validity")
        return cls(**values)

    @classmethod
    def from_file(cls, path: str) -> "AuthConfig":
        """Read a private regular configuration without following symlinks."""
        import os
        import stat
        from pathlib import Path

        item = Path(path)
        if not item.is_absolute() or ".." in item.parts:
            raise ValueError("Authorization configuration requires an absolute path")
        try:
            # Do not traverse a replaceable symlink in any ancestor.
            for ancestor in (item, *item.parents):
                info = ancestor.lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise ValueError("Authorization configuration must not use symlinks")
                if ancestor != item and (info.st_uid not in {0, os.geteuid()}
                        or (info.st_mode & 0o022 and not (info.st_mode & stat.S_ISVTX and info.st_uid == 0))):
                    raise ValueError("Authorization configuration has a replaceable ancestor")
            fd = os.open(item, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as source:
                before = os.fstat(source.fileno())
                if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                        or before.st_mode & 0o077 or before.st_nlink != 1):
                    raise ValueError("Authorization configuration is not private and owned")
                raw = source.read(MAX_AUTH_DOCUMENT + 1)
                after = os.fstat(source.fileno())
                current = item.lstat()
                if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
                ) or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
                    raise ValueError("Authorization configuration changed while reading")
        except OSError:
            raise ValueError("Authorization configuration could not be read safely") from None
        if len(raw) > MAX_AUTH_DOCUMENT:
            raise ValueError("Authorization configuration exceeds its size bound")
        return cls.from_dict(strict_loads(raw))

    def challenge(self, *, insufficient_scope: bool = False) -> str:
        part = urlsplit(self.resource)
        metadata = f"{part.scheme}://{part.netloc}/.well-known/oauth-protected-resource{part.path}"
        error = "insufficient_scope" if insufficient_scope else "invalid_token"
        return (f'Bearer error="{error}", error_description="Authentication or authorization required", '
                f'resource_metadata="{metadata}"')


class JWTVerifier:
    """SDK TokenVerifier with bounded, trusted JWKS retrieval and rotation.

    ``http_transport`` is constructor dependency injection, never a configuration
    switch. Tests use synthetic transports while all production requests retain
    TLS validation, fixed URLs, a finite deadline and a bounded response body.
    """

    def __init__(self, config: AuthConfig, *, http_transport=None, clock=time.monotonic):
        self.config = config
        self._http_transport = http_transport
        self._clock = clock
        self._keys: dict[str, Any] = {}
        self._valid_until = 0.0
        self._refresh_after = 0.0
        self._lock = asyncio.Lock()

    async def _document(self, url: str) -> dict[str, Any]:
        import httpx2

        try:
            async with asyncio.timeout(self.config.request_timeout_seconds):
                async with httpx2.AsyncClient(
                    timeout=self.config.request_timeout_seconds, follow_redirects=False,
                    trust_env=False, transport=self._http_transport,
                ) as client:
                    async with client.stream("GET", url, headers={"Accept": "application/json"}) as response:
                        if response.status_code != 200:
                            raise _deny()
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_AUTH_DOCUMENT:
                                raise _deny()
            decoded = strict_loads(bytes(body))
            if not isinstance(decoded, dict):
                raise _deny()
            return decoded
        except Exception:
            raise _deny() from None

    async def validate_issuer_metadata(self) -> None:
        """Refuse first linkage when discovery does not match admitted PKCE flow."""
        metadata = await self._document(self.config.metadata_url)
        expected = {name: getattr(self.config, name) for name in
                    ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")}
        if any(metadata.get(name) != value for name, value in expected.items()):
            raise _deny()
        for key, value in (("response_types_supported", "code"),
                           ("grant_types_supported", "authorization_code"),
                           ("code_challenge_methods_supported", "S256"),
                           ("token_endpoint_auth_methods_supported", "none")):
            if type(metadata.get(key)) is not list or value not in metadata[key]:
                raise _deny()
        scopes = metadata.get("scopes_supported")
        if (type(scopes) is not list or any(not isinstance(scope, str) for scope in scopes)
                or not set(self.config.scopes) <= set(scopes)):
            raise _deny()

    async def _key(self, kid: str, algorithm: str):
        import jwt

        now = self._clock()
        async with self._lock:
            now = self._clock()
            needs_refresh = now >= self._valid_until or (
                kid not in self._keys and now >= self._refresh_after
            )
            if needs_refresh:
                # Failed refreshes neither keep expired keys nor trigger an
                # unbounded issuer request storm from attacker-selected kids.
                if now < self._refresh_after:
                    raise _deny()
                self._refresh_after = now + self.config.refresh_cooldown_seconds
                try:
                    document = await self._document(self.config.jwks_uri)
                    raw_keys = document.get("keys")
                    if type(raw_keys) is not list or not 0 < len(raw_keys) <= MAX_KEYS:
                        raise _deny()
                    keys = {}
                    for item in raw_keys:
                        if not isinstance(item, dict):
                            raise _deny()
                        key_id = item.get("kid")
                        alg = item.get("alg")
                        if (not isinstance(key_id, str) or not _SCOPE.fullmatch(key_id)
                                or key_id in keys or alg not in self.config.algorithms
                                or item.get("use", "sig") != "sig"
                                or item.get("key_ops", ["verify"]) != ["verify"]
                                or any(k in item for k in ("d", "p", "q", "dp", "dq", "qi", "oth", "k"))):
                            raise _deny()
                        key = jwt.PyJWK.from_dict(item, algorithm=alg)
                        if (alg == "RS256" and (key.key_type != "RSA" or not 2048 <= key.key.key_size <= 8192)
                                or alg == "ES256" and (key.key_type != "EC" or key.key.curve.name != "secp256r1")):
                            raise _deny()
                        keys[key_id] = key
                    self._keys = keys
                    self._valid_until = self._clock() + self.config.jwks_ttl_seconds
                except Exception:
                    self._keys = {}
                    self._valid_until = 0.0
                    raise _deny() from None
            if self._clock() >= self._valid_until:
                raise _deny()
            key = self._keys.get(kid)
            if key is None or key.algorithm_name != algorithm:
                raise _deny()
            return key

    @staticmethod
    def _token_object(part: str) -> dict[str, Any]:
        try:
            value = strict_loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
            if not isinstance(value, dict):
                raise _deny()
            return value
        except Exception:
            raise _deny() from None

    async def authenticate(self, token: str):
        import jwt
        from mcp.server.auth.provider import AccessToken

        if not isinstance(token, str) or not 0 < len(token) <= MAX_TOKEN:
            raise _deny()
        parts = token.split(".")
        if len(parts) != 3 or any(not _TOKEN_PART.fullmatch(part) for part in parts):
            raise _deny()
        header = self._token_object(parts[0])
        if (header.get("alg") not in self.config.algorithms
                or not isinstance(header.get("kid"), str) or not _SCOPE.fullmatch(header["kid"])
                or header.get("typ", "JWT") not in ("JWT", "at+jwt")
                or any(name in header for name in ("crit", "jku", "x5u", "jwk", "x5c", "b64"))):
            raise _deny()
        key = await self._key(header["kid"], header["alg"])
        try:
            claims = jwt.decode(
                token, key=key, algorithms=list(self.config.algorithms),
                audience=self.config.resource, issuer=self.config.issuer,
                leeway=self.config.clock_skew_seconds,
                options={"require": ["iss", "aud", "sub", "iat", "nbf", "exp", "scope", "client_id"],
                         "strict_aud": True},
            )
            # PyJWT checks signature before claims; this second strict decoder
            # rejects duplicate claim keys that ordinary JSON decoding loses.
            strict_claims = self._token_object(parts[1])
            if claims != strict_claims:
                raise _deny()
            if any(type(claims[field]) is not int for field in ("iat", "nbf", "exp")):
                raise _deny()
            if (claims["exp"] <= claims["iat"] or claims["nbf"] > claims["exp"]
                    or claims["exp"] - claims["iat"] > self.config.maximum_token_seconds
                    or claims["client_id"] != self.config.client_id):
                raise _deny()
            subject = claims["sub"]
            if subject not in self.config.subject_map:
                raise _deny()
            scopes = claims["scope"]
            if not isinstance(scopes, str) or len(scopes) > 4096:
                raise _deny()
            scope_list = scopes.split(" ")
            if len(scope_list) > 32 or any(not _SCOPE.fullmatch(s) for s in scope_list):
                raise _deny()
            accepted_scopes = sorted(set(scope_list).intersection(self.config.scopes))
            if not accepted_scopes:
                raise _deny()
            return AccessToken(token=token, client_id=self.config.client_id, scopes=accepted_scopes,
                               expires_at=claims["exp"], resource=self.config.resource, subject=subject)
        except Exception:
            raise _deny() from None

    async def verify_token(self, token: str):
        """Official SDK TokenVerifier protocol: invalid credentials return None."""
        try:
            return await self.authenticate(token)
        except JobError:
            return None

    def principal(self, access_token) -> Principal:
        """Map only an SDK-authenticated in-process access token to stable identity."""
        if access_token is None or access_token.subject not in self.config.subject_map:
            raise _deny()
        return Principal(self.config.subject_map[access_token.subject], frozenset(access_token.scopes))

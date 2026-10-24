"""Narrow an already authenticated OS peer by its original network authority.

This is not an authenticator or a grant store. Only an admitted Unix peer may
supply these bounds; they cannot select another identity or enlarge its grants.
The exact request is bound to the scope/deadline, and bearer tokens never cross
this interface. Legacy OS-only maintenance continues without network bounds.
"""
from __future__ import annotations

import hashlib

from .contract import JobError, Principal, TOOL_SCOPES, canonical_bytes


def attach(request: dict, principal: Principal) -> dict:
    principal.require_current()
    if principal.expires_at is None:
        return request
    if 'authorization_bounds' in request:
        raise JobError('UNAUTHORIZED', 'Authorization bounds cannot be replaced')
    return {**request, 'authorization_bounds': {
        'schema': 'lh-forwarded-bounds-v1',
        'principal_id': principal.principal_id,
        'scopes': sorted(principal.scopes),
        'expires_at': principal.expires_at,
        'request_digest': hashlib.sha256(canonical_bytes(request)).hexdigest(),
    }}


def restrict(request: dict, peer: Principal) -> tuple[dict, Principal]:
    """Apply bounds only after the receiver has authenticated and mapped a peer."""
    peer.require_current()
    if 'authorization_bounds' not in request:
        return request, peer
    bounds = request['authorization_bounds']
    body = {key: value for key, value in request.items() if key != 'authorization_bounds'}
    if (type(bounds) is not dict
            or set(bounds) != {'schema', 'principal_id', 'scopes', 'expires_at', 'request_digest'}
            or bounds['schema'] != 'lh-forwarded-bounds-v1'
            or bounds['principal_id'] != peer.principal_id
            or bounds['request_digest'] != hashlib.sha256(canonical_bytes(body)).hexdigest()
            or type(bounds['scopes']) is not list or not bounds['scopes']
            or any(type(scope) is not str or scope not in TOOL_SCOPES.values() for scope in bounds['scopes'])
            or len(bounds['scopes']) != len(set(bounds['scopes']))
            or type(bounds['expires_at']) is not int or bounds['expires_at'] <= 0):
        raise JobError('UNAUTHORIZED', 'Forwarded authorization bounds do not match')
    deadline = bounds['expires_at']
    if peer.expires_at is not None:
        deadline = min(deadline, peer.expires_at)
    narrowed = Principal(peer.principal_id, peer.scopes.intersection(bounds['scopes']), expires_at=deadline)
    narrowed.require_current()
    return body, narrowed

"""Q2 receipt consumption inside the original supervised bootstrap only."""
from __future__ import annotations

import hashlib
import os
import struct

from . import quota_client as client, quota_contract as q, quota_grant as g


def bind_payload(execution, allocation, grant, *, now_ns):
    """Trusted broker adapter: produce the explicit new bounded envelope.

    Selection/consumption of grant and the peer start attestation must already
    be durable. This pure function performs no ledger I/O or grant issuance.
    """
    from . import bootstrap
    grant = g.decode_grant(grant.wire)
    bound = dict(execution, quota_grant_digest=grant.digest)
    g.check_execution(grant, bound, allocation, now_ns=now_ns)
    value = {"version": 2, "execution": bound, "allocation": allocation, "observation": grant.as_dict()}
    # Roundtrip makes a detached value and enforces the existing exec envelope.
    return bootstrap.decode_payload(bootstrap.encode_payload(value))


def _local_roots(grant, descriptors):
    # Linux imports stay in this path; normal package import remains portable.
    import fcntl
    from . import runner
    value = grant.as_dict()
    paths = g.root_paths(value["allocation"])
    q.require(set(descriptors) == set(paths.values()), "LOCAL_ROOT_SET")
    for root in value["roots"]:
        path = paths[root["role"]]
        descriptor = descriptors[path]
        info, current = os.fstat(descriptor), os.stat(path, follow_symlinks=False)
        q.require((info.st_dev, info.st_ino) == (current.st_dev, current.st_ino), "LOCAL_ROOT_CHANGED")
        q.require((info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode) ==
                  tuple(root[key] for key in ("device", "inode", "uid", "gid", "mode")), "LOCAL_ROOT_IDENTITY")
        q.require(runner._mount_for(path)["type"] == root["filesystem"], "LOCAL_FILESYSTEM")
        fsx = bytearray(28)
        fcntl.ioctl(descriptor, 0x801C581F, fsx, True)  # fixed FS_IOC_FSGETXATTR, no quotactl
        flags, _, _, project_id, _ = struct.unpack("=IIIII", fsx[:20])
        q.require(flags == root["xflags"] and project_id == root["project_id"]
                  and flags & 0x200, "LOCAL_PROJECT")


def observe(execution, allocation, observation, descriptors):
    """No marker/plan writes, retry, quota fallback, or allocation release."""
    grant = g.decode_grant(q._canonical(observation, g.GRANT_LIMIT))
    g.check_execution(grant, execution, allocation, now_ns=client._boottime_ns())
    data = grant.as_dict()
    q.require(client._boot_id() == data["request"]["boot_id"], "BOOT_BINDING")
    _local_roots(grant, descriptors)
    result = client.observe(client.Endpoint(**data["endpoint"]), grant.request, data["roots"])
    # Re-decode rather than trusting even a constructed Receipt object.
    result = q.decode_receipt(result.wire, grant.request, data["roots"], now_ns=client._boottime_ns())
    facts = result.as_dict()
    q.require(facts["status"] == "OBSERVED", "OBSERVATION_UNRESOLVED")
    q.require(facts["query"]["cgroup"] == data["query_parent"]["path"] + "/" + grant.request.query_unit,
              "QUERY_PARENT")
    _local_roots(grant, descriptors)
    q.require(client._boot_id() == data["request"]["boot_id"], "BOOT_BINDING")
    g.check_execution(grant, execution, allocation, now_ns=client._boottime_ns())
    q.require(client._boottime_ns() < facts["deadline_ns"], "DEADLINE")
    return {"schema": "local-hand-bootstrap-quota/v1", "grant_digest": grant.digest,
            "request_digest": grant.request.digest, "receipt_digest": hashlib.sha256(result.wire).hexdigest(),
            "domain_hard_bytes": result.domain_hard_bytes, "receipt": facts}

"""Offline consistency review of supplied Q1 bytes, never host admission.

No filesystem, clock, process, request/ticket, journal or query operation lives
here. Source/hash inputs are external pins; equality is not origin proof.
The immutable result cannot be passed to a controller as a permission token.
"""
from __future__ import annotations

from dataclasses import dataclass

from .admission import Manifest, decode_manifest, require, token
from .protected_inputs import RuntimeConfig, decode_runtime, installation_digest, validate_geometry


UNVERIFIED = (
    "ADMINISTRATOR_ORIGIN_AND_SOURCE_BYTES",
    "CONTROLLER_JOURNAL_AND_OS_INSTALLATION",
    "INDEPENDENT_CONTROLLER_SUPERVISION",
    "BOOT_USERNS_AND_SYSTEMD_CGROUP_IDENTITY",
    "ROOT_MOUNT_AND_INDEPENDENT_FILESYSTEM_UUID",
    "ACTUAL_CAPABILITIES_SYSCALLS_AND_QUOTA_ENFORCEMENT",
    "FINITE_JOURNAL_AND_EVIDENCE_CAPACITY",
    "ORIGINAL_DELIVERY_AND_COLLECTOR_EXIT",
)


@dataclass(frozen=True)
class OfflineValidation:
    manifest: Manifest
    runtime: RuntimeConfig

    def as_dict(self):
        """Bounded summary; omit private root paths, account IDs and boot values."""
        manifest, runtime = self.manifest, self.runtime
        return {
            "schema": "local-hand-quota-q1-offline-validation/v1",
            "status": "CONFIG_CONSISTENT", "evidence_class": "OFFLINE_ONLY",
            "host_readiness": "NOT_VERIFIED",
            "source_commit": manifest.source_commit,
            "manifest_digest": manifest.digest, "runtime_digest": runtime.digest,
            "installation_digest": manifest.installation_digest,
            "slot_count": len(manifest.slots),
            "billing_domain_count": len({(slot.filesystem_uuid, slot.project_id) for slot in manifest.slots}),
            "declared_hard_capacity_bytes": manifest.hard_capacity_bytes,
            "query_limits": {
                "max_query_ns": manifest.max_query_ns, "memory_bytes": runtime.memory_bytes,
                "tasks_max": runtime.tasks_max, "cpu_seconds": runtime.cpu_seconds,
                "max_output_bytes": runtime.max_output_bytes,
            },
            "unverified": list(UNVERIFIED),
            "admission_proven": False, "real_e3_accepted": False, "production_supported": False,
        }


def validate_fixture_inputs(manifest_bytes, runtime_bytes, *, manifest_digest, runtime_digest,
                            expected_source_commit, runtime_path, journal_path):
    """Validate two exact snapshots and the complete declared path geometry.

    runtime_path means the intended installed path, not the local snapshot's
    location. Never resolve those declared paths on the inspection computer.
    No current BOOTTIME or request identity is created by offline validation.
    """
    token(expected_source_commit, r"[0-9a-f]{40}")
    manifest = decode_manifest(manifest_bytes, manifest_digest)
    runtime = decode_runtime(runtime_bytes, runtime_digest)
    require(manifest.source_commit == expected_source_commit, "SOURCE_COMMIT_CHANGED")
    require(runtime.manifest_digest == manifest.digest, "MANIFEST_BINDING")
    require(installation_digest(runtime) == manifest.installation_digest, "INSTALLATION_BINDING")
    validate_geometry(runtime, manifest, runtime_path, journal_path)
    return OfflineValidation(manifest, runtime)

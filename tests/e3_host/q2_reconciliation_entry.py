"""Exact host authority, offline readiness, and retained evidence primitives.

The private packager supplies exact source/manifest pins and the already
authorized host wrapper. This module neither discovers hosts nor accepts an
arbitrary command. Existing startup v1 entry and authority are unchanged.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys


def helper(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_entry_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = helper("q2_startup_retry_entry")
delivery = helper("q2_reconciliation_delivery")
encoded, sha, require = old.encoded, old.sha, old.require
SCHEMA = "local-hand-q2-reconciliation-private-entry/v1"
SCOPE = "LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1"
ADMITTED_SCHEMA = "local-hand-q2-reconciliation-live-admitted/v1"
READY_SCHEMA = "local-hand-q2-reconciliation-bootstrap-ready/v1"
COLLECTION_SCHEMA = "local-hand-q2-reconciliation-collection/v1"
BUNDLE_SCHEMA = "local-hand-q2-reconciliation-host-bundle/v1"
AUTHORITY = dict(rule="10d2a5c827964989f41ca6e8eeac3d44de6d0f04",
    baseline="c65ff4e25ea6373aabf8db25d304ee7614b96eb5",
    closure="1491765c64c60a63d6bddf10a049308e404885ca",
    owner_decision="LH-Q2-INSTALLATION-RECONCILIATION-CLOSURE-20260927-01")
FALSE_FIELDS = ("q2_accepted", "q3_accepted", "production_supported")
HOST_AUTHORITY = dict(rule=AUTHORITY["rule"],
    baseline="8402f0cc82d8a0ac0b9a56716bf276f41cafea37",
    closure="271c07cd16140aa5942dcf3fad468003c58b6b0e",
    owner_decision="LH-Q2-HOST-WINDOW-CONSUMPTION-CLOSURE-20260927-01")
HOST_BINDING_FIELDS = {"host_binding_sha256", "host_marker_sha256", "host_bill_sha256", "joint_bill_sha256"}
CONFIG_FIELDS = old.CONFIG_FIELDS | {"authority", "amendment_sha256", "inputs_sha256", "host_window_authority"}
LIVE_FIELDS = {"schema", "status", "attempt_id", "amendment_sha256", "inputs_sha256",
    "source_commit", "source_tree", "clock_anchor_sha256", "live_attestation_sha256", *FALSE_FIELDS,
    *HOST_BINDING_FIELDS}
READY_FIELDS = {"schema", "status", "attempt_id", "amendment_sha256", "inputs_sha256",
    "delivery_sha256", "clock_anchor_sha256", "source_commit", "source_tree",
    "reconciliation_seal_sha256", *FALSE_FIELDS, *HOST_BINDING_FIELDS}
HOST_STORAGE_LIMIT = 3 * 1024**2


def validate_config(config):
    require(type(config) is dict and set(config) == CONFIG_FIELDS and config["schema"] == SCHEMA,
        "RECONCILIATION_HOST_CONFIG")
    require(config["authority"] == AUTHORITY, "RECONCILIATION_HOST_AUTHORITY")
    require(config["host_window_authority"] == HOST_AUTHORITY, "HOST_WINDOW_CONFIG_AUTHORITY")
    for key in ("amendment_sha256", "inputs_sha256"):
        old.digest(config[key])
    require(config["amendment_sha256"] == config["inputs_sha256"], "RECONCILIATION_HOST_INPUT_BINDING")
    # Reuse structural path/resource validation only, never its old run entry.
    structural = {key: config[key] for key in old.CONFIG_FIELDS}
    structural["schema"] = old.SCHEMA
    old.validate_config(structural)
    return config


def checked_live(value, config, anchor, *, ready=False, host_bindings=None):
    fields = READY_FIELDS if ready else LIVE_FIELDS
    require(type(value) is dict and set(value) == fields, "RECONCILIATION_HOST_SIGNAL_FIELDS")
    require(value["schema"] == (READY_SCHEMA if ready else ADMITTED_SCHEMA) and
        value["status"] == ("RECONCILIATION_BOOTSTRAP_READY" if ready else "LIVE_ATTESTED"),
        "RECONCILIATION_HOST_SIGNAL_KIND")
    require(all(value[key] == config[key] for key in
        ("attempt_id", "amendment_sha256", "inputs_sha256", "source_commit", "source_tree")) and
        value["clock_anchor_sha256"] == sha(encoded(anchor)) and
        all(value[key] is False for key in FALSE_FIELDS), "RECONCILIATION_HOST_SIGNAL_BINDING")
    for key in (("delivery_sha256", "reconciliation_seal_sha256") if ready else ("live_attestation_sha256",)):
        old.digest(value[key])
    require(type(host_bindings) is dict and set(host_bindings) == HOST_BINDING_FIELDS,
        "HOST_WINDOW_SIGNAL_BINDINGS_REQUIRED")
    for key in HOST_BINDING_FIELDS:
        old.digest(host_bindings[key])
        require(value[key] == host_bindings[key], "HOST_WINDOW_SIGNAL_BINDING")
    return value


class HostStore:
    """Create-only host evidence with held descriptors and exact membership.

    This class is instantiated only after joint admission. Every successful
    write revalidates all earlier files, so writing the core/bundle verifies
    their inputs both before and after the new durable output. An error poisons
    this instance permanently; partial files are retained and cannot be reused.
    """
    def __init__(self, directory, guard):
        self.path = old.absolute(directory)
        self.guard = guard
        self.fd = None
        self.files = {}
        self._opened = {}
        self._held = None
        self._failed = False
        self._sealed = False
        self._io = helper("q2_reconciliation_io")
        parent = self._io.HeldPath(self.path.parent, guard, directory=True)
        try:
            guard()
            parent.verify()
            os.mkdir(self.path.name, mode=0o700, dir_fd=parent.fd)
            created = self._io.metadata(os.stat(self.path.name, dir_fd=parent.fd, follow_symlinks=False))
            parent.refresh_written_directory()
            guard()
            os.fsync(parent.fd)
            self._held = self._io.HeldPath(self.path, guard, directory=True)
            self.fd = self._held.fd
            info = os.fstat(self.fd)
            require(self._io.metadata(info) == created and info.st_uid == os.geteuid()
                and info.st_gid == os.getegid() and stat.S_IMODE(info.st_mode) == 0o700,
                "RECONCILIATION_HOST_DIRECTORY")
            self.identity = (info.st_dev, info.st_ino)
            parent.verify()
            self.check()
        except BaseException:
            self._failed = True
            self.close()
            raise
        finally:
            try:
                parent.close()
            except BaseException:
                self._failed = True
                self.close()
                raise

    def _names(self):
        names = set()
        with os.scandir(self.fd) as children:
            for child in children:
                self.guard()
                names.add(child.name)
                require(len(names) <= 32, "RECONCILIATION_HOST_MEMBERS_CHANGED")
        return names

    def _verify_file(self, name, record):
        self.guard()
        fd, before, digest, size = record
        require(before is not None, "RECONCILIATION_HOST_PARTIAL_RETAINED")
        require(self._io.metadata(os.fstat(fd)) == before
            and self._io.metadata(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) == before,
            "RECONCILIATION_HOST_FILE_CHANGED")
        require(type(self.files[name]) is bytes and len(self.files[name]) == size
            and sha(self.files[name]) == digest, "RECONCILIATION_HOST_MEMORY_CHANGED")
        require(self._io._digest(fd, self.guard, 4 * delivery.OUTPUT_LIMIT) == digest,
            "RECONCILIATION_HOST_CONTENT_CHANGED")
        require(self._io.metadata(os.fstat(fd)) == before
            and self._io.metadata(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) == before,
            "RECONCILIATION_HOST_FILE_CHANGED")

    def check(self):
        try:
            require(not self._failed and self.fd is not None, "RECONCILIATION_HOST_STORE_UNUSABLE")
            self.guard()
            self._held.verify()
            require(self._names() == set(self._opened) == set(self.files),
                "RECONCILIATION_HOST_MEMBERS_CHANGED")
            identities = {self.identity}
            for name, record in self._opened.items():
                before = record[1]
                require(before is not None, "RECONCILIATION_HOST_PARTIAL_RETAINED")
                identity = before["device"], before["inode"]
                require(identity[0] == self.identity[0] and identity not in identities,
                    "RECONCILIATION_HOST_FILE_ALIAS")
                identities.add(identity)
                self._verify_file(name, record)
            self._held.verify()
        except BaseException:
            self._failed = True
            raise

    def write(self, name, raw):
        try:
            self.check()
            require(not self._sealed, "RECONCILIATION_HOST_STORE_SEALED")
            limit = min(HOST_STORAGE_LIMIT, 4 * delivery.OUTPUT_LIMIT)
            require(type(name) is str and re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,95}", name) and
                type(raw) is bytes and len(raw) <= limit and
                len(self.files) < 32 and sum(len(value) for value in self.files.values()) + len(raw)
                <= limit, "RECONCILIATION_HOST_RETAIN_LIMIT")
            require(name not in self._opened, "RECONCILIATION_HOST_ALREADY_RETAINED")
            fd = os.open(name, self._io.flags() | os.O_RDWR | os.O_CREAT | os.O_EXCL,
                0o600, dir_fd=self.fd)
            self._opened[name] = fd, None, None, None
            created = self._io.metadata(os.fstat(fd))
            require(stat.S_ISREG(created["st_mode"]) and created["nlink"] == 1
                and created["uid"] == os.geteuid() and created["gid"] == os.getegid()
                and stat.S_IMODE(created["st_mode"]) == 0o600 and created["device"] == self.identity[0],
                "RECONCILIATION_HOST_FILE_CHANGED")
            require(self._io.metadata(os.stat(name, dir_fd=self.fd, follow_symlinks=False)) == created,
                "RECONCILIATION_HOST_FILE_CHANGED")
            self._held.refresh_written_directory()
            for offset in range(0, len(raw), 65536):
                self.guard()
                chunk = raw[offset:offset + 65536]
                require(os.write(fd, chunk) == len(chunk), "RECONCILIATION_HOST_SHORT_WRITE")
            self.guard()
            os.fsync(fd)
            current = self._io.metadata(os.fstat(fd))
            require(current["size"] == len(raw) and current["nlink"] == 1 and all(
                current[key] == created[key] for key in ("device", "inode", "st_mode", "uid", "gid", "atime_ns")),
                "RECONCILIATION_HOST_FILE_CHANGED")
            self._opened[name] = fd, current, sha(raw), len(raw)
            self.files[name] = raw
            self.guard()
            os.fsync(self.fd)
            self.check()
        except BaseException:
            self._failed = True
            raise

    def seal(self, *, host_bindings):
        """Bind actual held files once, with no raw duplicate or self-reference.

        This proves only these retained bytes and member identities. It proves
        neither remote exit/EOF/stop nor the filesystem's power-loss durability.
        A caller must separately qualify the filesystem and admit its full bill.
        """
        try:
            self.check()
            require(type(host_bindings) is dict and set(host_bindings) == HOST_BINDING_FIELDS,
                "HOST_WINDOW_SIGNAL_BINDINGS_REQUIRED")
            for value in host_bindings.values():
                old.digest(value)
            members = {name: dict(metadata=copy.deepcopy(record[1]), sha256=record[2], bytes=record[3])
                for name, record in sorted(self._opened.items())}
            require(members and "host-seal.json" not in members, "HOST_WINDOW_SEAL_MEMBERS")
            raw = encoded(dict(schema="local-hand-q2-host-file-seal/v1", members=members,
                directory_identity=list(self.identity), host_bindings=copy.deepcopy(host_bindings),
                sealed_member_names=sorted([*members, "host-seal.json"]),
                self_reference=False, independent_stop_proven=False, q2_accepted=False))
            require(len(raw) <= 64 * 1024, "HOST_WINDOW_SEAL_LIMIT")
            self.write("host-seal.json", raw)
            self.check()
            require(set(self.files) == set(members) | {"host-seal.json"}, "HOST_WINDOW_SEAL_MEMBERS")
            self._sealed = True
            return dict(sha256=sha(raw), bytes=len(raw), members=len(self.files),
                scope="HELD_FILES_ONLY", independent_stop_proven=False, q2_accepted=False)
        except BaseException:
            self._failed = True
            raise

    def close(self):
        error = None
        for fd, *_ in self._opened.values():
            try:
                os.close(fd)
            except OSError as failure:
                error = error or failure
        self._opened.clear()
        if self._held is not None:
            try:
                self._held.close()
            except OSError as failure:
                error = error or failure
            self._held = None
        self.fd = None
        if error is not None:
            raise error


def collection_command(config, ready, anchor, *, host_bindings):
    checked_live(ready, config, anchor, ready=True, host_bindings=host_bindings)
    stage = config["guest_stage"]
    args = ["sudo", "-n", config["guest_python"], "-I", "-B",
        stage + "/tools/q2_reconciliation_collect.py", "--inputs",
        stage + "/reconciliation-inputs.json", "--sha256", config["inputs_sha256"],
        "--implementation-commit", config["source_commit"], "--delivery-envelope",
        stage + "/delivery.json", "--delivery-sha256", ready["delivery_sha256"],
        "--clock-anchor", stage + "/clock-anchor.json", "--clock-anchor-sha256", sha(encoded(anchor)),
        "--seal-sha256", ready["reconciliation_seal_sha256"]]
    return [config["ssh_wrapper"], shlex.join(args)]


def _blocked(reason):
    return dict(schema=SCHEMA, scope="LH-Q2-HOST-WINDOW-CONSUMPTION-v1", status="BLOCKED",
        authority=copy.deepcopy(HOST_AUTHORITY), reason=reason,
        execution_window_started=False, execution_window_consumed=False,
        host_persistence_attempted=False, batch_delivery_issued=False,
        joint_live_admission_observed=False, owner_request_issuance_observed=False,
        offline_only=True, field_reads_performed=False, readiness_proven=False,
        replay_allowed=False, local_read_only_preflight_repeatable=True,
        **dict.fromkeys(FALSE_FIELDS, False))


def offline_inputs(config, inputs, carrier_raw, host_attestation_raw):
    """Validate only supplied bytes; no paths, clocks, or private-input code.

    The package separately verifies every executable tool against actual Git D.
    A manifest's declared D or a successfully decoded bill is not run authority.
    """
    validate_config(config)
    contract = helper("q2_reconciliation_contract")
    contract.keys(inputs, ("manifest_raw", "manifest_sha256", "blobs", "implementation_commit"))
    require(inputs["manifest_sha256"] == config["amendment_sha256"] and
        inputs["implementation_commit"] == config["source_commit"], "HOST_WINDOW_INPUT_BINDING")
    require(type(inputs["manifest_raw"]) is str and len(inputs["manifest_raw"]) <= 3 * 1024**2,
        "HOST_WINDOW_INPUT_SIZE")
    require(type(inputs["blobs"]) is dict and 0 < len(inputs["blobs"]) <= 128,
        "HOST_WINDOW_INPUT_BLOBS")
    for key in inputs["blobs"]:
        contract.digest(key)
    require(all(type(value) is str for value in inputs["blobs"].values()) and
        sum(map(len, inputs["blobs"].values())) <= delivery.INPUT_LIMIT, "HOST_WINDOW_INPUT_SIZE")
    manifest_raw = base64.b64decode(inputs["manifest_raw"], validate=True)
    blobs = {key: base64.b64decode(value, validate=True) for key, value in inputs["blobs"].items()}
    verified = helper("q2_reconciliation_sources").verify(manifest_raw,
        inputs["manifest_sha256"], blobs, implementation_commit=inputs["implementation_commit"])
    execution = verified.execution
    require(execution["attempt_id"] == config["attempt_id"] and
        execution["source"]["commit"] == config["source_commit"] and
        execution["source"]["tree"] == config["source_tree"], "HOST_WINDOW_SOURCE_BINDING")
    require(verified.plan["candidate"]["commit"] == config["candidate"] and
        verified.plan["candidate"]["wheel_sha256"] == config["wheel_sha256"] and
        {key: verified.plan["host"][key] for key in config["guest_pin"]} == config["guest_pin"],
        "HOST_WINDOW_PLAN_BINDING")
    require(str(Path(verified.plan["candidate"]["source"]).parent) == config["guest_stage"],
        "HOST_WINDOW_STAGE_BINDING")
    location = helper("q2_host_window_contract").sources(carrier_raw, host_attestation_raw)
    require(str(Path(config["host_result_directory"]).parent) == location["parent"] and
        config["host_result_directory"] != location["directory"], "HOST_WINDOW_RESULT_LOCATION")
    return verified, location


def run_host(config, *, guest_input_builder=None, inputs=None, carrier_raw=None,
             host_attestation_raw=None, retained_anchors=None):
    """Review exact private bytes without consuming an unsupported live window.

    The Owner closed the host write-order Gate. The retained original mechanisms
    still cannot prove H07's first remote absolute deadline. Host historical
    future commitments and native audit coverage also lack source proof. No
    caller boolean, command or callback can convert those facts into admission.
    The builder is never invoked.

    Record/ACK/seal primitives are tested independently. A complete remote
    dispatcher is not represented as implemented or deployable by this entry.
    """
    report = _blocked("HOST_WINDOW_PRIVATE_INPUTS_REQUIRED")
    try:
        verified, location = offline_inputs(config, inputs, carrier_raw, host_attestation_raw)
        report.update(offline_sources_verified=True, implementation_commit=verified.implementation_commit,
            source_tree=verified.execution["source"]["tree"], manifest_sha256=verified.digest,
            source_count=len(verified.raw_by_path), old_results_unchanged=True)
        proof = helper("q2_host_window_delivery").remote_deadline_proof(retained_anchors,
            host_boot_id=location["expected_boot_id"], guest_boot_id=config["guest_pin"]["boot_id"])
        report["remote_deadline_proof"] = proof
        require(proof["dispatch_allowed"] is False and proof["status"] == "BLOCKED",
            "HOST_WINDOW_UNRECOGNIZED_DEADLINE_MECHANISM")
        report["reason"] = "HOST_WINDOW_REMOTE_DEADLINE_UNPROVEN"
        report["additional_missing_facts"] = ["HOST_HISTORICAL_FUTURE_SOURCE_COVERAGE",
            "NATIVE_AUDIT_SOURCE_BOUND", "SUPPORTED_HOST_FILESYSTEM_ALLOCATION_AND_DURABILITY",
            "HELD_WRAPPER_BYTES_AND_AUTHORIZED_SOURCE_BINDING"]
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        report["reason"] = delivery.reason(error)
    return report


def main():
    print(encoded(_blocked("EXACT_PRIVATE_OFFLINE_PACKAGE_REQUIRED")).decode(), end="")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

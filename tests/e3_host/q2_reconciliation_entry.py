"""Contained host entry and bounded evidence-storage primitives.

The private packager supplies exact source/manifest pins and the already
authorized host wrapper. This module neither discovers hosts nor accepts an
arbitrary command. Existing startup v1 entry and authority are unchanged.
"""
from __future__ import annotations

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
CONFIG_FIELDS = old.CONFIG_FIELDS | {"authority", "amendment_sha256", "inputs_sha256"}
LIVE_FIELDS = {"schema", "status", "attempt_id", "amendment_sha256", "inputs_sha256",
    "source_commit", "source_tree", "clock_anchor_sha256", "live_attestation_sha256", *FALSE_FIELDS}
READY_FIELDS = {"schema", "status", "attempt_id", "amendment_sha256", "inputs_sha256",
    "delivery_sha256", "clock_anchor_sha256", "source_commit", "source_tree",
    "reconciliation_seal_sha256", *FALSE_FIELDS}


def validate_config(config):
    require(type(config) is dict and set(config) == CONFIG_FIELDS and config["schema"] == SCHEMA,
        "RECONCILIATION_HOST_CONFIG")
    require(config["authority"] == AUTHORITY, "RECONCILIATION_HOST_AUTHORITY")
    for key in ("amendment_sha256", "inputs_sha256"):
        old.digest(config[key])
    require(config["amendment_sha256"] == config["inputs_sha256"], "RECONCILIATION_HOST_INPUT_BINDING")
    # Reuse structural path/resource validation only, never its old run entry.
    structural = {key: config[key] for key in old.CONFIG_FIELDS}
    structural["schema"] = old.SCHEMA
    old.validate_config(structural)
    return config


def checked_live(value, config, anchor, *, ready=False):
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
            require(type(name) is str and re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,95}", name) and
                type(raw) is bytes and len(raw) <= 4 * delivery.OUTPUT_LIMIT and
                len(self.files) < 32 and sum(len(value) for value in self.files.values()) + len(raw)
                <= 4 * delivery.OUTPUT_LIMIT, "RECONCILIATION_HOST_RETAIN_LIMIT")
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


def collection_command(config, ready, anchor):
    checked_live(ready, config, anchor, ready=True)
    stage = config["guest_stage"]
    args = ["sudo", "-n", config["guest_python"], "-I", "-B",
        stage + "/tools/q2_reconciliation_collect.py", "--inputs",
        stage + "/reconciliation-inputs.json", "--sha256", config["inputs_sha256"],
        "--implementation-commit", config["source_commit"], "--delivery-envelope",
        stage + "/delivery.json", "--delivery-sha256", ready["delivery_sha256"],
        "--clock-anchor", stage + "/clock-anchor.json", "--clock-anchor-sha256", sha(encoded(anchor)),
        "--seal-sha256", ready["reconciliation_seal_sha256"]]
    return [config["ssh_wrapper"], shlex.join(args)]


def run_host(config, *, guest_input_builder):
    """Contain the entry until the host consumption order has exact authority.

    The approved no-write-before-full-admission order cannot durably consume
    an attempt that fails before admission. No window is started here, and
    this function never reads host history, invokes a wrapper, or writes.
    """
    return dict(schema=SCHEMA, scope=SCOPE, status="BLOCKED",
        reason="HOST_WINDOW_CONSUMPTION_DESIGN_OPEN",
        execution_window_started=False, execution_window_consumed=False,
        host_persistence_attempted=False, batch_delivery_issued=False,
        replay_allowed=False, **dict.fromkeys(FALSE_FIELDS, False))


def main():
    print(encoded(dict(schema=SCHEMA, status="BLOCKED",
        reason="HOST_WINDOW_CONSUMPTION_DESIGN_OPEN", replay_allowed=False,
        **dict.fromkeys(FALSE_FIELDS, False))).decode(), end="")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

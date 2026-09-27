"""One amendment's joint live admission; the old startup interpreter is unchanged.

All mutation methods require the independently verified, newly sealed amendment.
A quote is not a release, and a sealed record is not an owner issuance.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import time


def helper(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_backend_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


startup = helper("q2_startup_retry")
p, c = startup.p, startup.c
RECONCILIATION_BYTES = 1024 ** 2
RECONCILIATION_INODES = 16
LIVE_SCHEMA = "local-hand-q2-installation-reconciliation-live/v1"


def require(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def contains(parent, child):
    return parent == child or Path(parent) in Path(child).parents


def strict_path(value):
    require(type(value) is str and value.startswith("/") and str(Path(value)) == value
        and ".." not in Path(value).parts and len(value.encode()) <= 4096,
        "RECONCILIATION_PATH")
    return value


def scan_summary(scan):
    """Complete entries remain the proof; compact references never replace a scan."""
    return {**{key: scan[key] for key in ("path", "device", "bytes", "inodes")},
        "sha256": sha(c.encoded(scan["entries"]))}


class ReconciliationBackend(startup.StartupRetryBackend):
    """Use only a new-contract-validated view, never decode it as startup v1."""
    def __init__(self, verified, *, issued_ns, deadline_ns, boot_deadline_ns,
                 delivery_envelope, reconciliation_directory, read_only_collection=False):
        # This constructor intentionally does not call StartupRetryBackend.__init__:
        # the new execution view has its own schema and source-class authority.
        require(type(read_only_collection) is bool, "RECONCILIATION_COLLECTION_MODE")
        require(type(issued_ns) is int and type(deadline_ns) is int
            and issued_ns <= time.monotonic_ns() < deadline_ns <= issued_ns + 140 * 10**9,
            "RECONCILIATION_PREPARATION_WINDOW")
        require(type(boot_deadline_ns) is int and time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            < boot_deadline_ns == delivery_envelope["guest_outer_deadline_ns" if read_only_collection else "preparation_deadline_ns"],
            "RECONCILIATION_BOOT_WINDOW")
        self.read_only_collection = read_only_collection
        self.verified = verified
        self.plan = copy.deepcopy(verified.plan)
        p.LinuxBackend.__init__(self, self.plan)
        # The base initialization creates no files/processes. Its default deadline
        # is replaced before any observation by the original absolute envelope.
        self.issued_ns, self.deadline = issued_ns, deadline_ns
        self.boot_deadline_ns = boot_deadline_ns
        self.delivery_envelope = copy.deepcopy(delivery_envelope)
        self.retry = copy.deepcopy(verified.execution)
        self.old = copy.deepcopy(verified.original)
        self.previous_retry = copy.deepcopy(verified.previous_retry)
        self.previous = copy.deepcopy(verified.previous)
        self.histories = [self.old, self.previous]
        self.raw_by_path = dict(verified.raw_by_path)
        self.source_classes = copy.deepcopy(verified.source_classes)
        require(set(self.raw_by_path) == set(self.source_classes)
            and all(type(raw) is bytes for raw in self.raw_by_path.values()),
            "RECONCILIATION_VERIFIED_SOURCES")
        self.reconciliation_directory = strict_path(reconciliation_directory)
        require(self.reconciliation_directory == self.plan["directories"]["reservation"]["path"] + ".reconciliation",
            "RECONCILIATION_RECORD_LOCATION")
        require(self.retry["schema"] != helper("q2_startup_retry_contract").SCHEMA,
            "RECONCILIATION_NOT_LEGACY_AUTHORITY")
        require(delivery_envelope["attempt_id"] == self.retry["attempt_id"]
            and delivery_envelope["boot_id"] == self.plan["host"]["boot_id"],
            "RECONCILIATION_DELIVERY_BINDING")
        for item in self.retry["retained_inputs"]:
            require(not contains(item["path"], self.reconciliation_directory)
                and not contains(self.reconciliation_directory, item["path"]),
                "RECONCILIATION_STATE_OLD_ALIAS")
        for item in self.plan["directories"].values():
            require(not contains(item["path"], self.reconciliation_directory)
                and not contains(self.reconciliation_directory, item["path"]),
                "RECONCILIATION_STATE_RUNTIME_ALIAS")
        self.old_prepared = self.old_handoff = None
        self.old_snapshots = self.attestation = None
        self.old_hashes = dict(self.retry["old_files"])
        self.costs, self.started, self.configuration = {}, set(), {}
        self.candidate_checked = self.skip_candidate = False
        self.prepared_history, self.handoff_history = [], []
        self.reservation_records, self.reservation_proofs = {}, []
        self.held_sources = {}
        self.live_initial = None
        self.live_scans = {}
        self.quote = None
        self.reconciliation_sealed = False
        self.execution_entered = False
        self.seal = None
        self.sealed_documents = None
        self.new_staging_peak = dict(bytes=0, inodes=0)
        self._io = helper("q2_reconciliation_io")
        self._billing = helper("q2_reconciliation_billing")
        self._sources = helper("q2_reconciliation_sources")

    def close(self):
        for held in self.held_sources.values():
            held.close()
        self.held_sources.clear()

    def guard(self):
        require(self.issued_ns <= time.monotonic_ns() < self.deadline
            and time.clock_gettime_ns(time.CLOCK_BOOTTIME) < self.boot_deadline_ns,
            "RECONCILIATION_DEADLINE")

    def old_raw(self, name):
        self.guard(); name = str(name)
        require(name in self.raw_by_path, "RECONCILIATION_UNADOPTED_SOURCE")
        raw = self.raw_by_path[name]
        held = self.held_sources.get(name)
        if held is None:
            held = self._io.read_pinned(name, self.guard,
                expected={"sha256": sha(raw), "bytes": len(raw),
                    **({"source_metadata": self.verified.metadata_baselines[name]["source_metadata"]}
                        if name in self.verified.metadata_baselines else {})},
                max_bytes=max(1, len(raw)), allowed_uids={0, self.plan["account"]["uid"]})
            require(held.data == raw, "RECONCILIATION_SOURCE_CHANGED")
            self.held_sources[name] = held
        else:
            self._io.verify_held(held, self.guard)
        return held.data

    def verify_old_hashes(self):
        for name in sorted(self.raw_by_path):
            self.old_raw(name)

    def scan(self, path, guard):
        # Only the exact prospectively adopted complete tree may supply link
        # texts. Unknown links remain unsupported before readlink is attempted.
        baseline = self.verified.forward_baseline
        expected = None
        if path == baseline["root"] or path == baseline["adjacent_intent"]:
            expected = []
            for item in baseline["entries"]:
                meta = item["source_metadata"]
                name = meta["path"]
                if not contains(path, name):
                    continue
                kind = "file" if meta["type"] == "regular" else meta["type"]
                row = dict(relative_path="." if name == path else str(Path(name).relative_to(path)),
                    type=kind, source_metadata={key: value for key, value in meta.items()
                        if key not in ("path", "type")})
                if kind == "file": row["sha256"] = item["sha256"]
                if kind == "symlink": row["link_target"] = item["link_target"]
                expected.append(row)
        return self._io.snapshot(path, guard, expected=expected,
            allowed_uids={0, self.plan["account"]["uid"]})

    def old_snapshot(self):
        scans = {}
        for item in self.retry["retained_inputs"]:
            if self.new_staging(item):
                continue
            scans[item["path"]] = self.scan(item["path"], self.guard)
        self._sources.verify_live_sources(self.verified, scans)
        return [{"path": path, **scan_summary(scan)} for path, scan in sorted(scans.items())]

    def snapshot(self):
        # Q1 identity, every entry, and all metadata are re-observed using the
        # same protected scanner. The historical proof remains separately pinned.
        result = []
        for pin in self.plan["retained"]:
            scan = self.scan(pin["path"], self.guard)
            root = scan["entries"][0]["source_metadata"]
            require((root["device"], root["inode"]) == (pin["device"], pin["inode"]),
                "RECONCILIATION_Q1_IDENTITY")
            result.append(dict(root=copy.deepcopy(pin), entries=scan["inodes"], sha256=sha(c.encoded(scan["entries"]))))
        return result

    def _scan_costs(self):
        selected = {}
        for item in self.retry["retained_inputs"]:
            if self.new_staging(item) and not os.path.lexists(item["path"]):
                continue
            selected[item["path"]] = item["category"]
        role_categories = dict(reservation="state", state="state", authority="state",
            journal="journal", capture="capture", declarations="capture", session="state", control="state")
        for role, category in role_categories.items():
            path = self.plan["directories"][role]["path"]
            if os.path.lexists(path):
                selected[path] = category
        for role in ("source", "wheel", "destination"):
            path = self.plan["candidate"][role]
            if os.path.lexists(path) and not any(contains(root, path) for root in selected):
                selected[path] = "installation"
        if os.path.lexists(self.reconciliation_directory):
            selected[self.reconciliation_directory] = "state"
        for pin in [*self.plan["retained"], *self.plan["roots"]]:
            path = pin["path"]
            require(not any(contains(root, path) or contains(path, root) for root in selected),
                "RECONCILIATION_QUOTA_TREE_ALIAS")
            selected[path] = "quota"
        scans = {path: self.scan(path, self.guard) for path in selected}
        self.live_scans = scans
        return scans, selected

    def _new_obligations(self):
        plan = self.plan
        def paths(roles):
            return [plan["directories"][role]["path"] for role in roles]
        def devices(roles):
            return sorted({plan["mounts"][plan["directories"][role]["filesystem"]]["device"] for role in roles})
        def row(identity, category, amount, covered, devs, *, categories=None, exclude=()):
            return dict(id=identity, category=category, commitment=amount, covered_paths=covered,
                excluded_paths=list(exclude), accounting_categories=categories or [category], devices=devs)
        assembly = helper("q2_startup_retry_driver")
        state_roles = ("state", "authority", "reservation", "session", "control")
        owner_roles = ("capture", "declarations", "journal")
        stage = str(Path(plan["candidate"]["source"]).parent)
        return [
            row("new-installation", "installation", dict(startup.INSTALL_PEAK),
                [plan["candidate"]["destination"]], [plan["mounts"]["system"]["device"]]),
            row("new-state", "state", dict(bytes=8 * 1024**2 + assembly.ASSEMBLY_RESERVATION_BYTES + c.LIMIT,
                inodes=16 + assembly.ASSEMBLY_RESERVATION_INODES + 4), paths(state_roles), devices(state_roles),
                exclude=[]),
            row("new-owner-pool", "capture", startup.runtime_storage(plan["settings"]),
                paths(owner_roles), devices(owner_roles), categories=["capture", "journal"]),
            row("reconciliation-state", "state", dict(bytes=RECONCILIATION_BYTES, inodes=RECONCILIATION_INODES),
                [self.reconciliation_directory], [plan["mounts"][plan["directories"]["reservation"]["filesystem"]]["device"]]),
            row("new-staging", "installation", dict(self.new_staging_peak),
                [stage, stage + ".intent.json"], [plan["mounts"]["system"]["device"]]),
        ]

    def measure_costs(self):
        self.guard()
        records = {row["path"]: self.old_document(row["path"]) for row in self.retry["reservations"]}
        obligations = startup.reservation_obligations(self.retry, self.histories, records)
        require(tuple(obligations) == tuple(self.verified.obligations), "RECONCILIATION_OBLIGATION_CHANGED")
        scans, expected_roots = self._scan_costs()
        mounts = self.mounts()
        inventory = p.Quota(self.plan["mounts"]["quota"]["source"]).inventory(self.guard)
        device_rows = {}
        for mount in mounts.values():
            row = device_rows.setdefault(mount["device"], dict(device=mount["device"],
                available_bytes=mount["available_bytes"], free_inodes=mount["free_inodes"]))
            row["available_bytes"] = min(row["available_bytes"], mount["available_bytes"])
            row["free_inodes"] = min(row["free_inodes"], mount["free_inodes"])
        quota_mount = mounts["quota"]
        quotas = [dict(uuid=quota_mount["uuid"], device=quota_mount["device"], project=x["project"],
            hard_bytes=x["hard"] * 1024, hard_inodes=x["ihard"], used_bytes=x["space"], used_inodes=x["inodes"])
            for x in inventory]
        quota_expected = [dict(uuid=quota_mount["uuid"], project=x["project_id"], hard_bytes=x["hard_bytes"],
            hard_inodes=x["inode_hard_limit"]) for x in [*self.plan["retained_domains"], *self.plan["roots"]]]
        quote = self._billing.quote_bill(scans, obligations, self._new_obligations(), quotas,
            list(device_rows.values()), installation_targets=[x["candidate"]["destination"] for x in self.histories],
            expected_roots=expected_roots, quota_expected=quota_expected, sealed=self.reconciliation_sealed)
        self.quote = quote
        self._current_mounts, self._current_inventory = mounts, inventory
        self.reservation_records = {name: sha(c.encoded(value)) for name, value in records.items()}
        self.reservation_proofs = obligations
        self.costs = self._billing.startup_costs(quote, proposed=not self.reconciliation_sealed)
        return self.costs

    def capacity(self, mounts, inventory):
        costs = self.measure_costs()
        require(inventory == self._current_inventory, "RECONCILIATION_QUOTA_DRIFT")
        return dict(cumulative_actual=costs, reservations=self.reservation_proofs,
            reservation_records=self.reservation_records, quota_inventory=inventory,
            reconciliation_quote=copy.deepcopy(self.quote), by_device=copy.deepcopy(self.quote["current" if self.reconciliation_sealed else "proposed_after"]["by_device"]),
            quota_unique=dict(hard_bytes=sum(row["hard"] * 1024 for row in inventory),
                hard_inodes=sum(row["ihard"] for row in inventory)))

    def stage_admission(self, staging_bytes, staging_entries):
        c.number(staging_bytes, 1); c.number(staging_entries, 1, 32768)
        self.new_staging_peak = dict(bytes=staging_bytes + 8192, inodes=staging_entries + 3)
        costs = self.measure_costs()
        selected = costs["installation"]
        return dict(installation_reservation_bytes=selected["admitted_bytes"] - self.new_staging_peak["bytes"],
            installation_reservation_inodes=selected["admitted_inodes"] - self.new_staging_peak["inodes"],
            admitted_bytes=selected["admitted_bytes"], admitted_inodes=selected["admitted_inodes"],
            staging_bytes=staging_bytes, staging_entries=staging_entries, costs=costs)

    def effect_admission(self):
        self.guard()
        require(not self.read_only_collection and self.reconciliation_sealed and self.seal is not None,
            "RECONCILIATION_SEAL_REQUIRED")
        self.verify_seal()

    def verify_seal(self):
        require(self.seal is not None, "RECONCILIATION_SEAL_REQUIRED")
        result = helper("q2_reconciliation_records").verify_sealed(self.reconciliation_directory, self.sealed_documents, self.guard)
        require(result["seal"] == self.seal, "RECONCILIATION_SEAL_CHANGED")
        return result

    def reserve(self, plan=None):
        self.effect_admission()
        return super().reserve(plan)

    def prepare(self):
        self.effect_admission()
        return super().prepare()

    def install(self):
        self.effect_admission()
        return super().install()

    def check_parents(self, *, start=False):
        if start:
            self.effect_admission()
        require(all(plan["parents"] == self.plan["parents"] for plan in self.histories),
            "RECONCILIATION_HISTORICAL_PARENT_COVERAGE")
        parent_result = super().check_parents(start=start)
        states = parent_result
        if start:
            # Normalize back to the original read-only observation shape.
            states = super().check_parents(start=False)
        namespaces = audit_namespaces(self.plan, guard=self.guard)
        cgroups = audit_cgroups(self.plan, states, guard=self.guard)
        require(super().check_parents(start=False) == states, "RECONCILIATION_PARENT_DRIFT")
        self.parent_observation = dict(states=states, namespaces=namespaces, cgroups=cgroups)
        return parent_result

    def preflight(self, *, skip_candidate=False):
        # Neither the legacy quote nor a successful source-only inspection may
        # skip the complete first joint observation.
        before = self.verify_host()
        result = super().preflight(skip_candidate=skip_candidate)
        after = self.verify_host()
        require(before == after, "RECONCILIATION_BOOT_CHANGED")
        require(getattr(self, "parent_observation", None) is not None,
            "RECONCILIATION_PARENT_OBSERVATION_MISSING")
        for held in self.held_sources.values():
            self._io.verify_held(held, self.guard)
        if self.reconciliation_sealed:
            self.attestation["reconciliation"] = dict(seal=copy.deepcopy(self.seal),
                source_classes=copy.deepcopy(self.source_classes), historical_atime_preservation_proven=False)
        if self.live_initial is None:
            self.live_initial = self.live_document(before, after)
        return result

    def live_document(self, before=None, after=None):
        require(self.quote is not None and self.attestation is not None,
            "RECONCILIATION_JOINT_ATTESTATION_REQUIRED")
        before = before or self.verify_host()
        after = after or self.verify_host()
        require(before == after, "RECONCILIATION_BOOT_CHANGED")
        value = dict(schema=LIVE_SCHEMA, attempt_id=self.retry["attempt_id"],
            amendment_sha256=self.verified.digest, source_commit=self.verified.implementation_commit,
            boot_before=before, boot_after=after,
            source_classes=copy.deepcopy(self.source_classes),
            historical_atime_preservation_proven=False,
            predecessors=copy.deepcopy(self.attestation["predecessors"]),
            ledgers=copy.deepcopy(self.attestation["ledgers"]),
            historical_units=copy.deepcopy(self.attestation["historical_units"]),
            roots=copy.deepcopy(self.attestation["roots"]),
            q1=copy.deepcopy(self.attestation["q1_snapshot"]),
            preserved_trees=copy.deepcopy(self.attestation["old_snapshots"]),
            parents=copy.deepcopy(self.parent_observation),
            bill=copy.deepcopy(self.quote),
            current_tree_coverage={name: scan_summary(scan) for name, scan in sorted(self.live_scans.items())},
            deadline_ns=self.delivery_envelope["deadline_ns"],
            preparation_deadline_ns=self.delivery_envelope["preparation_deadline_ns"],
            clock_anchor_sha256=self.delivery_envelope["clock_anchor_sha256"])
        require(len(c.encoded(value)) <= 512 * 1024, "RECONCILIATION_ATTESTATION_LIMIT")
        return value

    def verify_preserved(self):
        self.guard()
        result = super().verify_preserved()
        for held in self.held_sources.values():
            self._io.verify_held(held, self.guard)
        if self.reconciliation_sealed:
            self.verify_seal()
        return result

    def recheck_before_record(self):
        require(not self.reconciliation_sealed, "RECONCILIATION_ALREADY_SEALED")
        self.verify_preserved()
        self.measure_costs()
        return self.live_document()

    def accept_new_seal(self, result, documents):
        """Only this call's new create-only seal may advance the same process."""
        require(not self.reconciliation_sealed and result.get("state") == "RECONCILIATION_SEALED"
            and result.get("replay") is False, "RECONCILIATION_NEW_SEAL_REQUIRED")
        require(set(documents) == {"evidence-adoption.json", "reconciliation-intent.json",
            "live-attestation.json", "reconciliation-record.json"}, "RECONCILIATION_RECORD_SET")
        helper("q2_reconciliation_driver").validate_documents(self.verified, self.delivery_envelope,
            self.reconciliation_directory, documents)
        self.sealed_documents = dict(documents)
        self.seal = copy.deepcopy(result["seal"])
        self.reconciliation_sealed = True
        self.verify_seal()
        self.verify_preserved()
        self.measure_costs()
        return self.seal

    def load_sealed_for_collection(self, documents):
        require(self.read_only_collection, "RECONCILIATION_COLLECTION_MODE_REQUIRED")
        helper("q2_reconciliation_driver").validate_documents(self.verified, self.delivery_envelope,
            self.reconciliation_directory, documents)
        result = helper("q2_reconciliation_records").verify_sealed(self.reconciliation_directory,
            documents, self.guard)
        self.sealed_documents, self.seal = dict(documents), copy.deepcopy(result["seal"])
        self.reconciliation_sealed = True
        return result

    def collection_preservation(self, receipt):
        """Read-only historical proof after issuance, allowing new root payload."""
        require(type(receipt) is dict and receipt.get("retry", {}).get("attestation_sha256")
            == sha(c.encoded(receipt["retry"]["attestation"])), "RECONCILIATION_COLLECTION_RECEIPT")
        expected = receipt["retry"]["attestation"]
        self.verify_host(); self.verify_old_hashes()
        predecessors, ledgers = self.attest_predecessors()
        trees, q1, units = self.old_snapshot(), self.snapshot(), self.historical_units()
        require(predecessors == expected["predecessors"] and ledgers == expected["ledgers"]
            and trees == expected["old_snapshots"] and q1 == expected["q1_snapshot"]
            and units == expected["historical_units"], "RECONCILIATION_COLLECTION_PRESERVATION")
        for held in self.held_sources.values():
            self._io.verify_held(held, self.guard)
        self.verify_host()
        return dict(old_bytes_preserved=True, old_ledgers_preserved=True,
            historical_results_unchanged=True, historical_atime_preservation_proven=False,
            source_classes=copy.deepcopy(self.source_classes), predecessors=predecessors,
            ledgers=ledgers, trees=trees, q1=q1, units=units)


from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import stat


MAX_NODES = 1024
MAX_KERNEL_BYTES = 4 * 1024 * 1024
MAX_EVIDENCE_BYTES = 128 * 1024
CGROUP_FILES = ("cgroup.procs", "cgroup.threads", "cgroup.events", "cgroup.type",
                "cgroup.controllers", "cgroup.subtree_control", "memory.max",
                "memory.swap.max", "pids.max", "cpu.max", "memory.events",
                "memory.events.local", "pids.events", "pids.current")
NAMESPACES = ("user", "mnt", "pid", "cgroup", "net", "ipc", "uts")
CAP_FIELDS = ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def identity(info):
    return dict(device=info.st_dev, inode=info.st_ino, mode=info.st_mode,
                uid=info.st_uid, gid=info.st_gid, nlink=info.st_nlink)


def checked_path(value):
    require(type(value) is str and value.startswith("/") and value != "/"
            and len(value.encode()) <= 4096 and "\0" not in value
            and str(PurePosixPath(value)) == value
            and all(part not in (".", "..", "") for part in value.split("/")[1:]),
            "RECON_KERNEL_PATH")
    return value


class KernelReader:
    """Fixed proc/cgroup2 reader with held ancestry and checked final identities.

    Kernel pseudo-files intentionally do not use ordinary-evidence O_NOATIME
    rules. Every normal path component is opened with O_NOFOLLOW. The sole
    following operation is a validated kernel proc namespace/executable magic
    link beneath a held numeric process directory, never a supplied file path.
    """
    def __init__(self, guard, *, max_bytes=MAX_KERNEL_BYTES):
        self.guard = guard
        self.max_bytes = max_bytes
        self.bytes_read = 0
        self.nodes = 0

    def _guard(self):
        self.guard()
        require(self.bytes_read <= self.max_bytes, "RECON_KERNEL_READ_BOUND")

    def _root(self, path):
        checked_path(path)
        if path == "/proc" or path.startswith("/proc/"):
            return "/proc", 0x9FA0
        if path == "/sys/fs/cgroup" or path.startswith("/sys/fs/cgroup/"):
            return "/sys/fs/cgroup", 0x63677270
        raise ValueError("RECON_KERNEL_ROOT")

    @contextmanager
    def directory(self, path):
        self._guard()
        root, magic = self._root(path)
        parts = path.strip("/").split("/")
        descriptors = []
        edges = []
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            fd = os.open("/", flags)
            descriptors.append(fd)
            for index, part in enumerate(parts):
                self._guard()
                child = os.open(part, flags, dir_fd=fd)
                descriptors.append(child)
                pin = identity(os.fstat(child))
                require(stat.S_ISDIR(pin["mode"]), "RECON_KERNEL_DIRECTORY")
                edges.append((fd, part, child, pin))
                fd = child
                if "/" + "/".join(parts[:index + 1]) == root:
                    buffer = ctypes.create_string_buffer(256)
                    libc = ctypes.CDLL(None, use_errno=True)
                    if libc.fstatfs(fd, buffer) != 0:
                        raise OSError(ctypes.get_errno(), "fstatfs")
                    observed = ctypes.c_long.from_buffer(buffer).value
                    require(observed == magic, "RECON_KERNEL_FILESYSTEM")
            yield fd
            self._guard()
            for parent, name, child, pin in reversed(edges):
                require(identity(os.fstat(child)) == pin
                        and identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) == pin,
                        "RECON_KERNEL_ANCESTRY_CHANGED")
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    def _read_at(self, fd, name, limit):
        require(type(limit) is int and 0 < limit <= 1024 * 1024
                and "/" not in name and name not in (".", ".."), "RECON_KERNEL_READ_ARGUMENT")
        self._guard()
        handle = os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=fd)
        try:
            pin = identity(os.fstat(handle))
            require(stat.S_ISREG(pin["mode"]) and not pin["mode"] & 0o002, "RECON_KERNEL_FILE_TYPE")
            blocks = []
            length = 0
            while True:
                self._guard()
                block = os.read(handle, min(16384, limit + 1 - length))
                if not block:
                    break
                blocks.append(block)
                length += len(block)
                self.bytes_read += len(block)
                require(length <= limit, "RECON_KERNEL_FILE_BOUND")
            require(identity(os.fstat(handle)) == pin
                    and identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) == pin,
                    "RECON_KERNEL_FILE_CHANGED")
            return b"".join(blocks)
        finally:
            os.close(handle)

    def read(self, path, limit=65536):
        checked_path(path)
        with self.directory(str(PurePosixPath(path).parent)) as fd:
            return self._read_at(fd, PurePosixPath(path).name, limit)

    def absent(self, path):
        """Prove the first missing component beneath a held cgroup2 root."""
        checked_path(path)
        require(path.startswith("/sys/fs/cgroup/"), "RECON_CGROUP_ROOT")
        parts = path.removeprefix("/sys/fs/cgroup/").split("/")
        def visit(fd, remaining):
            self._guard()
            name = remaining[0]
            try:
                pin = identity(os.stat(name, dir_fd=fd, follow_symlinks=False))
            except FileNotFoundError:
                self._guard()
                try:
                    os.stat(name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    return True
                raise ValueError("RECON_CGROUP_ABSENCE_DRIFT")
            require(stat.S_ISDIR(pin["mode"]), "RECON_CGROUP_ENTRY_TYPE")
            if len(remaining) == 1:
                return False
            with self._child(fd, name, pin) as child:
                return visit(child, remaining[1:])
        with self.directory("/sys/fs/cgroup") as fd:
            return visit(fd, parts)

    def _magic(self, fd, name, pattern):
        self._guard()
        before = identity(os.stat(name, dir_fd=fd, follow_symlinks=False))
        require(stat.S_ISLNK(before["mode"]), "RECON_PROC_MAGIC_LINK")
        text = os.readlink(name, dir_fd=fd)
        require(len(text.encode()) <= 4096 and re.fullmatch(pattern, text), "RECON_PROC_MAGIC_TARGET")
        target = os.open(name, os.O_PATH | os.O_CLOEXEC, dir_fd=fd)
        try:
            target_info = identity(os.fstat(target))
            require(identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) == before
                    and os.readlink(name, dir_fd=fd) == text,
                    "RECON_PROC_MAGIC_CHANGED")
            if name in NAMESPACES:
                require(target_info["inode"] == int(text.rsplit("[", 1)[1][:-1]), "RECON_NAMESPACE_LINK_IDENTITY")
            elif name == "exe":
                require(stat.S_ISREG(target_info["mode"]) and target_info["uid"] == 0
                        and target_info["mode"] & 0o022 == 0 and not text.endswith(" (deleted)"),
                        "RECON_PROC_EXECUTABLE")
            return dict(text=text, identity=target_info)
        finally:
            os.close(target)

    def process(self, pid):
        require(type(pid) is int and 0 < pid < 2**31, "RECON_PROCESS_PID")
        with self.directory(f"/proc/{pid}") as fd:
            before = self._read_at(fd, "stat", 16384)
            result = dict(identity=identity(os.fstat(fd)), stat=before.decode("utf-8"),
                          status=self._read_at(fd, "status", 65536).decode("utf-8"),
                          cmdline=self._read_at(fd, "cmdline", 65536).decode("utf-8"),
                          cgroup=self._read_at(fd, "cgroup", 16384).decode("utf-8"),
                          exe=self._magic(fd, "exe", r"/[^\x00\n]+"), namespaces={})
            ns = os.open("ns", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                ns_pin = identity(os.fstat(ns))
                for name in NAMESPACES:
                    result["namespaces"][name] = self._magic(ns, name, re.escape(name) + r":\[[1-9][0-9]*\]")
                require(identity(os.fstat(ns)) == ns_pin
                        and identity(os.stat("ns", dir_fd=fd, follow_symlinks=False)) == ns_pin,
                        "RECON_PROC_NAMESPACE_CHANGED")
            finally:
                os.close(ns)
            after = self._read_at(fd, "stat", 16384)
            require(process_stat(before.decode())["identity"] == process_stat(after.decode())["identity"],
                    "RECON_PROCESS_REUSED")
            return result

    def tree(self, path):
        """Read every descendant directory; never follow a filesystem link."""
        checked_path(path)
        require(path.startswith("/sys/fs/cgroup/"), "RECON_CGROUP_ROOT")
        rows = []
        def visit(fd, name, depth):
            self._guard()
            self.nodes += 1
            require(self.nodes <= MAX_NODES and depth <= 64, "RECON_CGROUP_SCAN_BOUND")
            before = identity(os.fstat(fd))
            names = sorted(os.listdir(fd))
            require(len(names) <= 32768, "RECON_CGROUP_MEMBER_BOUND")
            data = {item: self._read_at(fd, item, 65536).decode("ascii") for item in CGROUP_FILES}
            children = []
            types = {}
            for item in names:
                self._guard()
                info = os.stat(item, dir_fd=fd, follow_symlinks=False)
                require(not stat.S_ISLNK(info.st_mode), "RECON_CGROUP_SYMLINK")
                require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), "RECON_CGROUP_ENTRY_TYPE")
                types[item] = identity(info)
                if stat.S_ISDIR(info.st_mode):
                    children.append(item)
            delegation = identity(os.stat("cgroup.procs", dir_fd=fd, follow_symlinks=False))
            rows.append(dict(path=name, identity=before, files=data, children=children,
                             delegation=delegation))
            for child in children:
                with self._child(fd, child, types[child]) as child_fd:
                    visit(child_fd, name + "/" + child, depth + 1)
            require(sorted(os.listdir(fd)) == names and identity(os.fstat(fd)) == before,
                    "RECON_CGROUP_TREE_CHANGED")
            for item, pin in types.items():
                require(identity(os.stat(item, dir_fd=fd, follow_symlinks=False)) == pin,
                        "RECON_CGROUP_ENTRY_CHANGED")
            # A process can appear/disappear without changing directory identity.
            for item in ("cgroup.procs", "cgroup.threads", "cgroup.events"):
                require(self._read_at(fd, item, 65536).decode("ascii") == data[item],
                        "RECON_CGROUP_MEMBERS_CHANGED")
        with self.directory(path) as fd:
            visit(fd, path.removeprefix("/sys/fs/cgroup"), 0)
        return rows

    @contextmanager
    def _child(self, parent, name, pin):
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
        try:
            require(identity(os.fstat(fd)) == pin, "RECON_CGROUP_CHILD_CHANGED")
            yield fd
            require(identity(os.fstat(fd)) == pin
                    and identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) == pin,
                    "RECON_CGROUP_CHILD_CHANGED")
        finally:
            os.close(fd)


def process_stat(text):
    require(type(text) is str and " (" in text and ") " in text, "RECON_PROC_STAT")
    lead, rest = text.rsplit(") ", 1)
    fields = rest.split()
    require(len(fields) >= 20, "RECON_PROC_STAT")
    pid = int(lead.split(" (", 1)[0])
    ppid, start = int(fields[1]), int(fields[19])
    require(pid > 0 and ppid >= 0 and start > 0 and fields[0] not in ("Z", "X", "x"), "RECON_PROC_STAT")
    return dict(identity=[pid, ppid, start], comm=lead.split(" (", 1)[1], state=fields[0])


def status_fields(text):
    result = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        require(separator and key not in result, "RECON_PROC_STATUS")
        result[key] = value.strip()
    require(set(CAP_FIELDS) | {"Uid", "Gid", "Groups", "NoNewPrivs", "Pid", "PPid", "Threads"} <= set(result),
            "RECON_PROC_STATUS_FIELDS")
    for field in CAP_FIELDS:
        require(re.fullmatch(r"[0-9a-fA-F]{1,16}", result[field]), "RECON_PROC_CAPABILITY")
        result[field] = int(result[field], 16)
    for field in ("Uid", "Gid"):
        values = result[field].split()
        require(len(values) == 4 and all(re.fullmatch(r"[0-9]+", v) for v in values), "RECON_PROC_IDS")
        result[field] = [int(v) for v in values]
    for field in ("NoNewPrivs", "Pid", "PPid", "Threads"):
        require(re.fullmatch(r"[0-9]+", result[field]), "RECON_PROC_NUMBER")
        result[field] = int(result[field])
    require(result["NoNewPrivs"] in (0, 1), "RECON_PROC_NNP")
    groups = result["Groups"].split()
    require(all(re.fullmatch(r"[0-9]+", g) for g in groups), "RECON_PROC_GROUPS")
    result["Groups"] = [int(g) for g in groups]
    return result


def process_evidence(raw):
    parsed = process_stat(raw["stat"])
    values = status_fields(raw["status"])
    require(parsed["identity"][:2] == [values["Pid"], values["PPid"]], "RECON_PROC_IDENTITY")
    selected = (*CAP_FIELDS, "Uid", "Gid", "Groups", "NoNewPrivs", "Pid", "PPid", "Threads")
    require(set(raw["namespaces"]) == set(NAMESPACES), "RECON_NAMESPACE_SET")
    return dict(identity=raw["identity"], process=parsed, status={key: values[key] for key in selected},
                namespaces=raw["namespaces"], exe=raw["exe"], cmdline=raw["cmdline"], cgroup=raw["cgroup"])


def audit_namespaces(plan, *, reader=None, guard=lambda: None):
    """Observe init and this supervisor, requiring the same initial namespaces."""
    reader = reader or KernelReader(guard)
    guard()
    boot = reader.read("/proc/sys/kernel/random/boot_id", 128).decode("ascii").strip()
    require(boot == plan["host"]["boot_id"], "RECON_BOOT_CHANGED")
    pid = os.getpid()
    initial = process_evidence(reader.process(1))
    own = process_evidence(reader.process(pid))
    pin = plan["host"]["initial_userns"]
    for process in (initial, own):
        observed = process["namespaces"]["user"]["identity"]
        require({key: observed[key] for key in ("device", "inode")} == pin, "RECON_INITIAL_USERNS")
    for name in NAMESPACES:
        require(initial["namespaces"][name] == own["namespaces"][name], "RECON_NAMESPACE_CHANGED")
    require(own["status"]["Uid"] == own["status"]["Gid"] == [0] * 4
            and initial["process"]["comm"] == "systemd", "RECON_ADMIN_IDENTITY")
    require(process_evidence(reader.process(1)) == initial and process_evidence(reader.process(pid)) == own,
            "RECON_NAMESPACE_PROCESS_DRIFT")
    require(reader.read("/proc/sys/kernel/random/boot_id", 128).decode("ascii").strip() == boot,
            "RECON_BOOT_CHANGED")
    guard()
    return dict(boot_id=boot, initial=initial, administrator=own)


def numbers(text, code):
    words = text.split()
    require(all(re.fullmatch(r"[1-9][0-9]*", v) for v in words), code)
    values = [int(v) for v in words]
    require(len(set(values)) == len(values) and all(v < 2**31 for v in values), code)
    return sorted(values)


def pairs(text, code):
    result = {}
    for line in text.splitlines():
        parts = line.split()
        require(len(parts) == 2 and parts[0] not in result and re.fullmatch(r"[0-9]+", parts[1]), code)
        result[parts[0]] = int(parts[1])
    require(result, code)
    return result


def limit_check(files, expected):
    require({"cpu", "memory", "pids"} <= set(files["cgroup.controllers"].split()), "RECON_PARENT_CONTROLLERS")
    for name, value in (("memory.max", expected["memory_bytes"]), ("memory.swap.max", 0),
                        ("pids.max", expected["tasks_max"])):
        require(files[name].strip() == str(value), "RECON_PARENT_LIMIT")
    value = files["cpu.max"].split()
    require(len(value) == 2 and all(re.fullmatch(r"[1-9][0-9]*", v) for v in value)
            and int(value[0]) * 1000000 == int(value[1]) * expected["cpu_quota_per_sec_usec"], "RECON_PARENT_CPU")


def _state(state, unit, *, manager=False):
    require(state.get("Id") == unit and state.get("LoadState") == "loaded"
            and state.get("ActiveState") in ("active", "inactive")
            and state.get("Job") in ("", "0") and state.get("ControlPID") == "0", "RECON_PARENT_UNIT_STATE")
    if state["ActiveState"] == "inactive":
        require(state.get("MainPID") == "0" and state.get("ControlGroup") == ""
                and state.get("SubState") == "dead", "RECON_PARENT_INACTIVE")
    elif manager:
        require(state.get("SubState") == "running" and re.fullmatch(r"[1-9][0-9]*", state.get("MainPID", "")),
                "RECON_MANAGER_PID")
    else:
        require(state.get("MainPID") == "0" and state.get("SubState") == "active", "RECON_PARENT_SLICE")


def audit_cgroups(plan, observed, *, reader=None, guard=lambda: None):
    """Cover all relevant parent descendants twice; allow only proved manager.

    No command may execute inside an observed parent while this function runs.
    The manager's MainPID is permitted exclusively in its own init.scope. An
    additional sd-pam or any other process is BLOCKED rather than name-allowed.
    """
    reader = reader or KernelReader(guard)
    guard()
    account, parents = plan["account"], plan["parents"]
    manager, states = observed["manager"], observed["parents"]
    unit = f"user@{account['uid']}.service"
    _state(manager, unit, manager=True)
    expected_manager = f"/user.slice/user-{account['uid']}.slice/{unit}"
    require(set(states) == set(parents) if manager["ActiveState"] == "active"
            else set(states) == set(parents) - {"ordinary"}, "RECON_PARENT_SET")
    paths, absent = {}, []
    for role, value in states.items():
        _state(value, parents[role]["unit"])
        path = (expected_manager + "/" if role == "ordinary" else "/") + parents[role]["unit"]
        if value["ActiveState"] == "active":
            require(value.get("ControlGroup") == path, "RECON_PARENT_PATH")
            paths[path] = (role, parents[role])
        else:
            absent.append(path)
    manager_process = None
    if manager["ActiveState"] == "active":
        require(manager.get("ControlGroup") == expected_manager and manager.get("User") == str(account["uid"])
                and manager.get("Delegate") == "yes", "RECON_MANAGER_BINDING")
        paths[expected_manager] = ("manager", parents["ordinary"])
        manager_pid = int(manager["MainPID"])
        manager_process = process_evidence(reader.process(manager_pid))
        initial = process_evidence(reader.process(1))
        require(initial["process"]["comm"] == "systemd" and initial["status"]["Uid"] == [0] * 4,
                "RECON_SYSTEMD_INIT")
        values = manager_process["status"]
        require(values["Uid"] == [account["uid"]] * 4 and values["Gid"] == [account["gid"]] * 4
                and set(values["Groups"]) <= {account["gid"]}
                and all(values[name] == 0 for name in ("CapInh", "CapPrm", "CapEff", "CapAmb")),
                "RECON_MANAGER_ACCOUNT_CAPABILITIES")
        argv = manager_process["cmdline"].split("\0")
        require(len(argv) == 3 and argv[-1] == "" and argv[1] == "--user"
                and argv[0].split("/")[-1] == "systemd"
                and manager_process["exe"] == initial["exe"]
                and manager_process["process"]["identity"][:2] == [manager_pid, 1]
                and manager_process["cgroup"] == "0::" + expected_manager + "/init.scope\n",
                "RECON_MANAGER_PROCESS_IDENTITY")
        for name in NAMESPACES:
            require(manager_process["namespaces"][name] == initial["namespaces"][name], "RECON_MANAGER_NAMESPACE")
    else:
        absent.append(expected_manager)

    def snapshot():
        result = {}
        for path in absent:
            guard()
            require(reader.absent("/sys/fs/cgroup" + path), "RECON_INACTIVE_CGROUP_PRESENT")
        # Manager subtree already includes the ordinary parent's entire tree.
        roots = [path for path in paths if not any(path.startswith(other + "/") for other in paths)]
        for root in sorted(roots):
            for row in reader.tree("/sys/fs/cgroup" + root):
                guard()
                path, files = checked_path(row["path"]), row["files"]
                require(path == root or path.startswith(root + "/"), "RECON_CGROUP_ESCAPE")
                require(path not in result and set(files) == set(CGROUP_FILES), "RECON_CGROUP_COVERAGE")
                owners = {0, account["uid"]} if path == expected_manager or path.startswith(expected_manager + "/") else {0}
                groups = {0, account["gid"]} if len(owners) > 1 else {0}
                for pin in (row["identity"], row["delegation"]):
                    require(pin["uid"] in owners and pin["gid"] in groups and not pin["mode"] & 0o002,
                            "RECON_CGROUP_PERMISSION")
                members = numbers(files["cgroup.procs"], "RECON_CGROUP_PROCS")
                threads = numbers(files["cgroup.threads"], "RECON_CGROUP_THREADS")
                events = pairs(files["cgroup.events"], "RECON_CGROUP_EVENTS")
                require(events.get("frozen") == 0 and files["cgroup.type"].strip() == "domain", "RECON_CGROUP_TYPE")
                permitted = manager_process is not None and path == expected_manager + "/init.scope"
                require(members == ([manager_pid] if permitted else []), "RECON_CGROUP_BUSY")
                require(threads == ([manager_pid] if permitted else []), "RECON_CGROUP_THREADS_BUSY")
                populated = manager_process is not None and path in (expected_manager, expected_manager + "/init.scope")
                require(events.get("populated") == int(populated), "RECON_CGROUP_POPULATED")
                current = files["pids.current"].strip()
                require(current == ("1" if populated else "0"), "RECON_CGROUP_TASKS")
                for key in ("memory.events", "memory.events.local", "pids.events"):
                    pairs(files[key], "RECON_CGROUP_EVENT_FIELDS")
                if path in paths:
                    role, expected = paths[path]
                    limit_check(files, expected)
                    if role == "manager":
                        require({"cpu", "memory", "pids"} <= set(files["cgroup.subtree_control"].split()),
                                "RECON_MANAGER_CONTROLLERS")
                    if role == "ordinary":
                        pin = row["delegation"]
                        require(pin["uid"] == account["uid"] and pin["mode"] & 0o200,
                                "RECON_ORDINARY_DELEGATION")
                result[path] = row
        require(set(paths) <= set(result), "RECON_CGROUP_PARENT_MISSING")
        for path, row in result.items():
            require({path + "/" + name for name in row["children"]}
                    == {p for p in result if str(PurePosixPath(p).parent) == path}, "RECON_CGROUP_DESCENDANTS_MISSING")
        return result

    first = snapshot()
    second = snapshot()
    require(first == second, "RECON_CGROUP_DRIFT")
    if manager_process is not None:
        require(process_evidence(reader.process(manager_pid)) == manager_process, "RECON_MANAGER_DRIFT")
    result = dict(nodes=list(first.values()), absent_paths=sorted(absent), manager_process=manager_process,
                  node_count=len(first), manager_extra_processes_allowed=False)
    raw = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    require(len(raw) <= MAX_EVIDENCE_BYTES, "RECON_CGROUP_EVIDENCE_BOUND")
    guard()
    return dict(result, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))

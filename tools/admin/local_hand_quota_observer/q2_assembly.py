"""Create-only administrator assembly for one original preflight reservation.

The finite template is a protected fixture declaration, never client input.
Only the authenticated resident bridge supplies the immutable preparation. No
account, directory, mount, quota or cgroup is provisioned here. This first-phase
assembler cannot create fresh journals to evade predecessor closure checks.
All I/O runs in the independently supervised administrator, never the broker.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import PurePosixPath
import stat

from local_hand_jobs import bootstrap, budget, quota_contract as q, quota_grant as g
from local_hand_jobs.contract import JobError
from . import q2_config as c
from .q2_journal import Journal
from .protected_inputs import read_protected, verify_file

SCHEMA = "local-hand-q2-assembly/v1"
_STATIC = {"schema", "source_commit", "tools_path", "entry", "package_files", "programs",
           "abi", "initial_userns", "capacity", "evidence"}
_GRANT = {"schema", "request", "allocation", "endpoint", "query_parent", "management_parent",
          "roots", "management"}


@dataclass(frozen=True, slots=True)
class Template:
    wire: bytes

    @property
    def digest(self):
        return hashlib.sha256(self.wire).hexdigest()

    def data(self):
        return q._load(self.wire, c.LIMIT, 18)


def decode(raw, digest):
    q.require(hashlib.sha256(raw).hexdigest() == digest, "ASSEMBLY_DIGEST")
    value = q._load(raw, c.LIMIT, 18)
    q._keys(value, {"schema", "purpose", "id", "installation", "grant", "original_budgets",
                    "broker_generation", "output", "journal", "service", "peer"})
    q.require(value["schema"] == SCHEMA and value["purpose"] == "ISOLATED_Q2_PREFLIGHT", "ASSEMBLY_SCHEMA")
    q.match(value["id"], r"[0-9a-f]{32}")
    q._keys(value["installation"], _STATIC)
    q._keys(value["grant"], _GRANT)
    grant = value["grant"]
    q._keys(grant["request"], q._REQUEST_KEYS - {"deadline_ns", "observation_grant_digest"})
    q.require(grant["request"]["phase"] == "preflight"
              and grant["allocation"]["namespace"] == "job", "ASSEMBLY_FIRST_PHASE_ONLY")
    q._keys(grant["management"], g._MANAGEMENT_KEYS - {"issued_ns"})
    generation = value["broker_generation"]
    q.require(type(generation) is list and len(generation) == 2, "ASSEMBLY_GENERATION")
    for item in generation: q.integer(item, 1)
    try: budget._validate_limits(value["original_budgets"])
    except JobError: raise q.QuotaError("ASSEMBLY_ORIGINAL_BUDGET") from None
    for key in ("output", "journal"): c.identity(value[key])
    q.require(not c.overlap(value["output"]["path"], value["journal"]["path"]), "ASSEMBLY_GEOMETRY")
    q._keys(value["service"], {"parent", "control_path", "accept_ns", "max_connections"})
    q._keys(value["peer"], {"parent", "executable", "runner"})
    c.identity(value["peer"]["parent"])
    c.identity(value["peer"]["executable"])
    q._keys(value["peer"]["runner"], {"path", "sha256"})
    q.canonical_path(value["peer"]["runner"]["path"])
    q.match(value["peer"]["runner"]["sha256"], r"[0-9a-f]{64}")
    return Template(raw)


def load(path, digest):
    return decode(read_protected(path, c.LIMIT), digest)


def build_grant(template, snapshot, *, session, clock):
    """Pure selection: the original budget/allocation are copied unchanged.

    clock is the trusted administrator's current CLOCK_BOOTTIME observation;
    it is never taken from a broker message. Root identities, authority and all
    adjustable values come from the protected template instead of the message.
    """
    template = decode(template.wire, template.digest)
    value = template.data()
    q.match(session, r"[0-9a-f]{64}")
    budget._validate_clock(clock)
    q._keys(snapshot, {"preparation", "observation", "pending", "closed"})
    q.require(all(snapshot[k] is None for k in ("observation", "pending", "closed")), "ASSEMBLY_ALREADY_STARTED")
    prep = snapshot["preparation"]
    q._keys(prep, {"phase", "session", "budget", "allocation", "generation"})
    fixed = value["grant"]
    q.require(prep["session"] == session and prep["generation"] == value["broker_generation"]
              and prep["phase"] == "preflight" and prep["allocation"] == fixed["allocation"], "ASSEMBLY_PREPARATION")
    allocation = fixed["allocation"]
    try:
        budget.validate_grant(prep["budget"], namespace="job", phase="preflight",
            execution_id=allocation["execution_id"], record_id=allocation["record_id"],
            operation_id=allocation["operation_id"], original_budgets=value["original_budgets"])
    except JobError: raise q.QuotaError("ASSEMBLY_ORIGINAL_BUDGET") from None
    q.require(clock["boot_id"] == fixed["request"]["boot_id"] == prep["budget"]["boot_id"]
              and prep["budget"]["reserved_boottime_ns"] <= clock["boottime_ns"], "ASSEMBLY_CLOCK")
    end = budget.phase_deadline_ns(prep["budget"]) - prep["budget"]["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS
    request = dict(fixed["request"], deadline_ns=end)
    candidate = dict(fixed, request=request, budget=prep["budget"], predecessors=[],
                     management=dict(fixed["management"], issued_ns=clock["boottime_ns"]))
    grant = g.decode_grant(q._canonical(candidate, g.GRANT_LIMIT))
    g.check_capacity(value["installation"]["capacity"], [grant])
    return grant


def _argv(template, grant, argv, now_ns):
    value = template.data(); peer = value["peer"]
    q.require(type(argv) is list and len(argv) == 5 and argv[:4] ==
              [peer["executable"]["path"], "-I", peer["runner"]["path"], "--bootstrap"], "ASSEMBLY_BOOTSTRAP_ARGV")
    try: payload = bootstrap.decode_payload(argv[4])
    except JobError: raise q.QuotaError("ASSEMBLY_BOOTSTRAP_PAYLOAD") from None
    q._keys(payload, {"version", "execution", "allocation", "observation"})
    q.require(type(payload["version"]) is int and payload["version"] == 2
              and payload["allocation"] == grant.as_dict()["allocation"]
              and payload["observation"] == grant.as_dict(), "ASSEMBLY_BOOTSTRAP_BINDING")
    g.check_execution(grant, payload["execution"], payload["allocation"], now_ns=now_ns)
    raw = b"\0".join(argument.encode("utf-8") for argument in argv) + b"\0"
    q.require(len(raw) <= 131072 and all("\0" not in argument for argument in argv), "ASSEMBLY_COMMAND_LIMIT")
    return hashlib.sha256(raw).hexdigest()


def _file(directory, name, raw):
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
    try:
        pending = memoryview(raw)
        while pending:
            count = os.write(descriptor, pending)
            q.require(count > 0, "ASSEMBLY_WRITE")
            pending = pending[count:]
        os.fsync(descriptor)
        info = os.fstat(descriptor)
        q.require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o600
                  and info.st_nlink == 1 and info.st_size == len(raw), "ASSEMBLY_FILE")
        return {"device": info.st_dev, "inode": info.st_ino}
    finally:
        os.close(descriptor)


def _empty(descriptor):
    with os.scandir(descriptor) as entries:
        q.require(next(entries, None) is None, "ASSEMBLY_CONSUMED")


def _directory(pin, *, empty=False):
    descriptor = c.pinned_directory(pin)
    try:
        info = os.fstat(descriptor)
        q.require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700, "ASSEMBLY_PRIVATE")
        if empty: _empty(descriptor)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _configuration(template, grant, command, journal_pin, session_pin):
    value = template.data(); key = grant.request.as_dict()["request_id"]
    peer = value["peer"]
    data = dict(value["installation"], grants={key: grant.as_dict()},
        peers={key: dict(parent=peer["parent"], executable=peer["executable"], command_sha256=command)},
        journal=dict(path=value["journal"]["path"], pin=journal_pin), session=session_pin,
        service=dict(value["service"], request_id=key, end_ns=grant.request.as_dict()["deadline_ns"]))
    raw = q._canonical(data, c.LIMIT)
    return c.decode(raw, value["output"]["path"] + "/observer.json", hashlib.sha256(raw).hexdigest())


def _administrator():
    q.require(os.geteuid() == 0, "ASSEMBLY_ADMINISTRATOR")


def install(template, grant, *, bootstrap_argv, session, clock):
    """Create immutable artifacts once in already provisioned protected dirs.

    The caller derives bootstrap_argv from the trusted installed execution plan
    and shared core builder, never from the nonroot process. Partial results,
    fsync uncertainty and the reservation are retained; this API never resumes,
    replaces, truncates, removes or retries an earlier assembly.
    """
    _administrator()
    template = decode(template.wire, template.digest)
    grant = g.decode_grant(grant.wire); value = template.data()
    # Reconstruct the declared preparation to ensure callers cannot swap a
    # built grant before persistence. No new budget or deadline is generated.
    prep = dict(phase="preflight", session=session, budget=grant.as_dict()["budget"],
                allocation=grant.as_dict()["allocation"], generation=value["broker_generation"])
    built = build_grant(template, dict(preparation=prep, observation=None, pending=None, closed=None),
                        session=session, clock=dict(clock, boottime_ns=grant.as_dict()["management"]["issued_ns"]))
    q.require(built == grant, "ASSEMBLY_GRANT_CHANGED")
    budget._validate_clock(clock)
    q.require(clock["boot_id"] == grant.request.as_dict()["boot_id"] and
              grant.as_dict()["management"]["issued_ns"] <= clock["boottime_ns"] < grant.request.as_dict()["deadline_ns"], "ASSEMBLY_DEADLINE")
    command = _argv(template, grant, bootstrap_argv, clock["boottime_ns"])
    output = value["output"]["path"]
    key = grant.request.as_dict()["request_id"]
    dummy = {"device": 0, "inode": 1}
    preflight = _configuration(template, grant, command,
        {"directory": {k: value["journal"][k] for k in dummy},
         "files": {name: dummy for name in ("lock", "policy", key + ".cell")}},
        dict(dummy, path=output + "/session"))
    reservation = q._canonical(dict(schema="local-hand-q2-assembly-reservation/v1",
        id=value["id"], template_digest=template.digest, grant_digest=grant.digest,
        session=session, created_ns=clock["boottime_ns"]), 4096) + b"\n"
    management = grant.as_dict()["management"]
    # Existing grant accounting covers query cells/output. Add every assembly
    # artifact, the bounded management record and session marker explicitly.
    baseline = g.CELL_BYTES + sum(g._rounded(stage["output_bytes"]) + 8192 for stage in management["stages"].values())
    overhead = g._rounded(len(preflight.wire) + 1024) + 4096 + 65536 + 4096
    q.require(management["storage_bytes"] >= baseline + overhead
              and management["storage_inodes"] >= 11, "ASSEMBLY_STORAGE")
    descriptors = []
    try:
        target = _directory(value["output"], empty=True); descriptors.append(target)
        journal = _directory(value["journal"], empty=True); descriptors.append(journal)
        evidence = _directory(value["installation"]["evidence"], empty=True); descriptors.append(evidence)
        q.require(len({(os.fstat(fd).st_dev, os.fstat(fd).st_ino) for fd in descriptors}) == 3, "ASSEMBLY_DIRECTORY_ALIAS")
        # Check trusted program/source bytes before consuming the sequence.
        peer = value["peer"]
        descriptor = c.open_protected(peer["executable"]["path"])
        try:
            info = os.fstat(descriptor)
            q.require((info.st_dev, info.st_ino) == (peer["executable"]["device"], peer["executable"]["inode"])
                      and info.st_mode & 0o111, "ASSEMBLY_PEER_EXECUTABLE")
        finally: os.close(descriptor)
        verify_file(peer["runner"]["path"], peer["runner"]["sha256"])
        reserved = _file(target, "reservation.json", reservation)
        os.fsync(target)
        session_pin = _file(target, "session", b"")
        record_pin = _file(target, "management.jsonl", b"")
        pin = Journal.provision(value["journal"]["path"], value["installation"]["capacity"], [grant])
        q.require(pin["directory"] == {k: value["journal"][k] for k in dummy}, "ASSEMBLY_JOURNAL_CHANGED")
        config = _configuration(template, grant, command, pin, dict(session_pin, path=output + "/session"))
        _file(target, "observer.json", config.wire)
        os.fsync(target)
        # Full program verification is required before returning usable config.
        checked = c.load(config.path, config.digest)
        return dict(config=checked, management_record=dict(record_pin, path=output + "/management.jsonl"),
                    reservation=dict(reserved, path=output + "/reservation.json"))
    finally:
        for descriptor in reversed(descriptors): os.close(descriptor)

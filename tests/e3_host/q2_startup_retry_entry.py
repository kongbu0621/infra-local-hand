"""Fixed one-shot host orchestration for the approved startup-failure retry.

Machine pins and the immutable guest bootstrap are private inputs. This module
never chooses a host, searches for an SSH connection or offers a command runner.
Only the fixed probe, bounded management service and read-only collector exist.
Every client shares one deadline and one output pool; captured failures remain
failures. A retained host reservation forbids replay after partial completion.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import sys
import time

SCHEMA = "local-hand-q2-supervisor-startup-retry-private-entry/v1"
READY_SCHEMA = "local-hand-q2-supervisor-startup-retry-bootstrap-ready/v1"
COLLECTION_SCHEMA = "local-hand-q2-supervisor-startup-retry-collection/v1"
COMPLETION_SCHEMA = "local-hand-q2-supervisor-startup-retry-host-completion/v1"
BUNDLE_SCHEMA = "local-hand-q2-supervisor-startup-retry-host-bundle/v1"
CANDIDATE = "b49d3df3d1e76813faf08e59ab4975e25279c2fc"
WHEEL_SHA256 = "c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b"
CONFIG_FIELDS = {"schema", "attempt_id", "source_commit", "source_tree", "candidate", "wheel_sha256",
                 "host_result_directory", "old_host_files", "guest_pin", "ssh_wrapper", "guest_python",
                 "guest_stage", "guest_outer_unit"}
MAX_INPUT_BYTES = 16 * 1024**2
MAX_OLD_BYTES = 32 * 1024**2
MAX_OLD_FILES = 256
NS = 10**9
PROBE = b'''import json,os,socket,time
from pathlib import Path
before=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
a=os.stat('/proc/self/ns/user');b=os.stat('/proc/1/ns/user')
assert os.getuid()==os.geteuid()==os.getgid()==os.getegid()==0
assert (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)
after=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert before==after
print(json.dumps(dict(hostname=socket.gethostname(),boot_id=after,initial_userns=dict(device=a.st_dev,inode=a.st_ino),boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME)),sort_keys=True,separators=(',',':')))
'''


def require(ok, code):
    if not ok:
        raise ValueError(code)


def helper(name):
    spec = importlib.util.spec_from_file_location("_startup_retry_entry_" + name,
                                                  Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def absolute(value):
    require(type(value) is str and value.startswith("/") and not value.startswith("//")
            and str(PurePosixPath(value)) == value and value != "/"
            and ".." not in PurePosixPath(value).parts and "\\" not in value and "\0" not in value
            and len(value) <= 4096, "STARTUP_ENTRY_PATH")
    return Path(value)


def digest(value, length=64):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value),
            "STARTUP_ENTRY_DIGEST")


def file_pin(value):
    require(type(value) is dict and set(value) == {"path", "sha256"}, "STARTUP_ENTRY_FILE_PIN")
    absolute(value["path"]); digest(value["sha256"])


def validate_config(config):
    require(type(config) is dict and set(config) == CONFIG_FIELDS and config["schema"] == SCHEMA,
            "STARTUP_ENTRY_CONFIG")
    helper("q2_startup_retry_delivery").token(config["attempt_id"])
    digest(config["source_commit"], 40); digest(config["source_tree"], 40)
    require(config["candidate"] == CANDIDATE and config["wheel_sha256"] == WHEEL_SHA256,
            "STARTUP_ENTRY_FROZEN_CANDIDATE")
    out = absolute(config["host_result_directory"])
    stage = absolute(config["guest_stage"])
    require(stage.name != "tools", "STARTUP_ENTRY_STAGE")
    require(config["guest_python"] == "/usr/bin/python3.12", "STARTUP_ENTRY_PYTHON")
    require(type(config["guest_outer_unit"]) is str and re.fullmatch(r"[a-z][a-z0-9-]{7,95}\.service",
                                                                  config["guest_outer_unit"]),
            "STARTUP_ENTRY_UNIT")
    pins = config["old_host_files"]
    require(type(pins) is list and 2 <= len(pins) <= MAX_OLD_FILES, "STARTUP_ENTRY_PREDECESSORS")
    wrapper = absolute(config["ssh_wrapper"])
    seen = {str(wrapper)}
    require(wrapper != out and out not in wrapper.parents and wrapper not in out.parents, "STARTUP_ENTRY_PATH_ALIAS")
    for pin in pins:
        file_pin(pin); path = absolute(pin["path"])
        require(str(path) not in seen and path != out and out not in path.parents and path not in out.parents,
                "STARTUP_ENTRY_PATH_ALIAS")
        seen.add(str(path))
    guest = config["guest_pin"]
    require(type(guest) is dict and set(guest) == {"hostname", "boot_id", "initial_userns"},
            "STARTUP_ENTRY_GUEST_PIN")
    require(type(guest["hostname"]) is str and 0 < len(guest["hostname"]) <= 253
            and re.fullmatch(r"[A-Za-z0-9_.-]+", guest["hostname"]), "STARTUP_ENTRY_HOSTNAME")
    helper("q2_startup_retry_delivery").boot(guest["boot_id"])
    namespace = guest["initial_userns"]
    require(type(namespace) is dict and set(namespace) == {"device", "inode"}
            and all(type(namespace[key]) is int and namespace[key] > 0 for key in namespace),
            "STARTUP_ENTRY_NAMESPACE")
    return config


def identity(info):
    return {key: getattr(info, key) for key in ("st_dev", "st_ino", "st_uid", "st_gid", "st_mode",
                                               "st_size", "st_nlink", "st_atime_ns", "st_mtime_ns", "st_ctime_ns")}


def protected_directory(path):
    """Pin all ancestors without reading/enumerating them or following links."""
    path = str(path)
    require(path == "/" or absolute(path), "STARTUP_ENTRY_PATH")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for part in (".", *PurePosixPath(path).parts[1:]):
            if part != ".":
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                os.close(fd); fd = child
            info = os.fstat(fd)
            require(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, os.geteuid())
                    and not info.st_mode & 0o6022, "STARTUP_ENTRY_ANCESTOR_PROTECTION")
        return fd
    except BaseException:
        os.close(fd); raise


def read_pinned(pin, guard, *, maximum=MAX_OLD_BYTES, executable=False, observe_digest=False):
    """No protected-read fallback: denied O_NOATIME fails the batch closed."""
    if observe_digest:
        require(type(pin) is dict and set(pin) == {"path", "sha256"} and pin["sha256"] is None, "STARTUP_ENTRY_FILE_PIN")
    else:
        file_pin(pin)
    guard(); path = absolute(pin["path"])
    parent = protected_directory(path.parent)
    fd = None
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=parent)
        before = identity(os.fstat(fd))
        require(stat.S_ISREG(before["st_mode"]) and before["st_nlink"] == 1
                and before["st_uid"] in (0, os.geteuid()) and not before["st_mode"] & 0o6022
                and before["st_size"] <= maximum
                and (not executable or bool(before["st_mode"] & 0o111)), "STARTUP_ENTRY_FILE_PROTECTION")
        raw = bytearray()
        while len(raw) <= maximum:
            guard(); block = os.read(fd, min(65536, maximum + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        require(len(raw) == before["st_size"] <= maximum and (observe_digest or sha(raw) == pin["sha256"]),
                "STARTUP_ENTRY_OLD_HOST_CHANGED")
        require(identity(os.fstat(fd)) == before
                and identity(os.stat(path.name, dir_fd=parent, follow_symlinks=False)) == before,
                "STARTUP_ENTRY_FILE_CHANGED")
        # Re-open the complete ancestry to reject a renamed parent/substituted path.
        checked_parent = protected_directory(path.parent)
        try:
            require(identity(os.stat(path.name, dir_fd=checked_parent, follow_symlinks=False)) == before,
                    "STARTUP_ENTRY_PATH_CHANGED")
        finally:
            os.close(checked_parent)
        guard()
        return bytes(raw), before
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def read_history(config, guard):
    result = {}; seen = set(); total = 0
    for pin in config["old_host_files"]:
        raw, info = read_pinned(pin, guard, maximum=MAX_OLD_BYTES - total)
        total += len(raw); key = (info["st_dev"], info["st_ino"])
        require(key not in seen, "STARTUP_ENTRY_OLD_HOST_ALIAS"); seen.add(key)
        result[pin["path"]] = {"sha256": sha(raw), "identity": info}
    return result


def guest_command(config):
    """Fixed management boundary; no client-provided systemd properties."""
    argv = ["sudo", "-n", "/usr/bin/systemd-run", "--system", "--no-ask-password", "--wait", "--pipe",
            "--service-type=exec", "--unit=" + config["guest_outer_unit"], "--property=Restart=no",
            "--property=RuntimeMaxSec=270s", "--property=TimeoutStopSec=3s", "--property=KillMode=control-group",
            "--property=ExitType=cgroup", "--property=MemoryMax=536870912", "--property=MemorySwapMax=0",
            "--property=TasksMax=64", "--property=CPUQuota=100%", "--property=LimitCPU=300", "--property=UMask=0077",
            config["guest_python"], "-I", "-B", "-"]
    return [config["ssh_wrapper"], shlex.join(argv)]


def collection_command(config, ready, anchor_digest, output_limit):
    stage = config["guest_stage"]
    for key in ("retry_sha256", "delivery_sha256"):
        digest(ready[key])
    digest(anchor_digest)
    require(type(output_limit) is int and 16384 <= output_limit <= 2 * 1024**2,
            "STARTUP_ENTRY_COLLECTION_OUTPUT")
    argv = ["sudo", "-n", config["guest_python"], "-I", "-B", stage + "/tools/q2_startup_retry_collect.py",
            "--retry", stage + "/retry.json", "--sha256", ready["retry_sha256"], "--delivery-envelope",
            stage + "/delivery.json", "--delivery-sha256", ready["delivery_sha256"],
            "--clock-anchor-sha256", anchor_digest, "--output-limit", str(output_limit)]
    return [config["ssh_wrapper"], shlex.join(argv)]


def records(raw, delivery):
    values = []; invalid = 0
    for line in raw.splitlines():
        if not line:
            continue
        try:
            value = delivery.document(line, maximum=delivery.OUTPUT_LIMIT)
            require(len(values) < 128, "STARTUP_ENTRY_RECORD_COUNT")
            values.append(value)
        except (ValueError, UnicodeError):
            invalid += 1
    return values, invalid


def run_host(config, *, guest_input_builder):
    """Consume the explicit private batch once; return evidence, never acceptance.

    ``guest_input_builder(anchor)`` must return immutable pinned bootstrap bytes.
    It is supplied by the private packager, not by a generic command-line option.
    This entry must itself run from hash-verified public D bytes.
    """
    validate_config(config)
    require(sys.platform.startswith("linux") and callable(guest_input_builder), "STARTUP_ENTRY_PLATFORM")
    delivery = helper("q2_startup_retry_delivery"); base = helper("q2_prepare_delivery")
    # This origin precedes every wrapper/history read, clock probe and process.
    boot_issued = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    issued = time.monotonic_ns()
    deadline = issued + delivery.HOST_NS
    boot_deadline = boot_issued + delivery.HOST_NS
    def guard(reserve_ns=0):
        mono_now = time.monotonic_ns()
        boot_now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        delivery.validate_host_clock(issued_ns=issued, deadline_ns=deadline, boottime_issued_ns=boot_issued,
                                     monotonic_now_ns=mono_now, boottime_now_ns=boot_now)
        require(issued <= mono_now < deadline - reserve_ns
                and boot_issued <= boot_now < boot_deadline - reserve_ns,
                "STARTUP_ENTRY_DEADLINE")
    out = absolute(config["host_result_directory"])
    parent = protected_directory(out.parent)
    try:
        guard(); os.mkdir(out.name, mode=0o700, dir_fd=parent); os.fsync(parent)
    finally:
        os.close(parent)
    report = dict(schema=SCHEMA, status="INCOMPLETE", attempt_id=config["attempt_id"],
                  source_commit=config["source_commit"], source_tree=config["source_tree"],
                  candidate=config["candidate"], wheel_sha256=config["wheel_sha256"],
                  issued_ns=issued, deadline_ns=deadline, boottime_issued_ns=boot_issued,
                  boottime_deadline_ns=boot_deadline, preparation_observed=False, batch_delivery_issued=False,
                  owner_request_issued=None, owner_request_issuance_observed=False, owner_report_observed=False, independent_stop_proven=False, runtime_tree_empty_proven=False,
                  guest_sealed=False, collection_complete=False, q2_accepted=False, q3_accepted=False,
                  production_supported=False, replay_allowed=False, old_attempts_remain_incomplete=True)
    # Once mkdir succeeds, all subsequent failures retain that replay barrier.
    base.write(out / "intent.json", encoded(report)); base.sync_dir(out)
    probe = capture = collection = None; before = None; wrapper_identity = None; wrapper_digest = None; anchor = None
    def wrapper_check():
        nonlocal wrapper_identity, wrapper_digest
        raw, current = read_pinned({"path": config["ssh_wrapper"], "sha256": wrapper_digest}, guard,
            maximum=1024**2, executable=True, observe_digest=wrapper_digest is None)
        # The interpreter may update its script's atime during real execution.
        # The wrapper is observed current input, not preserved historical evidence.
        current = {key: value for key, value in current.items() if key != "st_atime_ns"}
        if wrapper_identity is None:
            wrapper_identity, wrapper_digest = current, sha(raw)
            report["wrapper_observation"] = dict(path=config["ssh_wrapper"], sha256=wrapper_digest,
                                                identity=current, historical_digest_claimed=False)
        require(current == wrapper_identity and sha(raw) == wrapper_digest, "STARTUP_ENTRY_WRAPPER_CHANGED")
    def capture_phase(name, argv, *, until, prior=0, stdin=None, output_limit=None):
        wrapper_check()
        value = delivery.capture_once(argv, host_issued_ns=issued, host_deadline_ns=deadline,
            deadline_ns=until, host_boottime_issued_ns=boot_issued, prior_captured_bytes=prior, stdout_path=out / (name + ".stdout"),
            stderr_path=out / (name + ".stderr"), stdin_path=stdin, output_limit=output_limit)
        base.write(out / (name + "-capture.json"), encoded(value))
        return value
    try:
        before = read_history(config, guard); report["old_host_before"] = before
        wrapper_check(); base.write(out / "probe-input.py", PROBE)
        send = time.monotonic_ns()
        probe = capture_phase("probe", [config["ssh_wrapper"],
            shlex.join(["sudo", "-n", config["guest_python"], "-I", "-B", "-"])],
            until=min(deadline - 30 * NS, send + 10 * NS), stdin=out / "probe-input.py", output_limit=16384)
        receive = time.monotonic_ns()
        guard()
        require(probe["complete"] and probe["returncode"] == 0, "STARTUP_ENTRY_PROBE_INCOMPLETE")
        sample = delivery.document((out / "probe.stdout").read_bytes())
        require(set(sample) == {"hostname", "boot_id", "initial_userns", "boottime_ns"}
                and {key: sample[key] for key in config["guest_pin"]} == config["guest_pin"],
                "STARTUP_ENTRY_GUEST_CHANGED")
        anchor = delivery.make_clock_anchor(host_issued_ns=issued, host_deadline_ns=deadline,
            host_probe_send_ns=send, host_probe_receive_ns=receive, guest_boot_id=sample["boot_id"],
            guest_sample_ns=sample["boottime_ns"], expected_boot_id=config["guest_pin"]["boot_id"])
        base.write(out / "clock-anchor.json", encoded(anchor))
        guest = guest_input_builder(anchor)
        require(type(guest) is bytes and 0 < len(guest) <= MAX_INPUT_BYTES, "STARTUP_ENTRY_GUEST_INPUT")
        compile(guest, "<pinned-startup-retry-bootstrap>", "exec")
        base.write(out / "guest-input.py", guest); base.sync_dir(out); guard(20 * NS)
        report["batch_delivery_issued"] = True
        capture = capture_phase("guest", guest_command(config), until=deadline - 20 * NS,
            prior=probe["total_captured_bytes"], stdin=out / "guest-input.py")
        values, invalid = records((out / "guest.stdout").read_bytes(), delivery)
        report.update(guest_records=values, invalid_guest_record_lines=invalid)
        ready = [value for value in values if value.get("schema") == READY_SCHEMA]
        prepared = [value for value in values if value.get("schema") ==
                    "local-hand-q2-supervisor-startup-retry-driver-result/v1"
                    and value.get("status") == "STARTUP_RETRY_PREPARED"]
        require(len(prepared) <= 1, "STARTUP_ENTRY_DUPLICATE_PREPARED")
        if prepared:
            prepared = prepared[0]; issuance = prepared.get("new_request_issuance", {})
            require(prepared.get("attempt_id") == config["attempt_id"]
                    and prepared.get("source_commit") == config["candidate"]
                    and prepared.get("orchestration_source", {}).get("commit") == config["source_commit"]
                    and prepared.get("runtime_candidate", {}).get("commit") == config["candidate"]
                    and prepared.get("runtime_candidate", {}).get("wheel_sha256") == config["wheel_sha256"]
                    and issuance.get("schema") == "local-hand-q2-new-request-issuance/v1"
                    and issuance.get("attempt_id") == config["attempt_id"]
                    and issuance.get("original_owners_issued") is True
                    and issuance.get("original_verdicts_retained") is True, "STARTUP_ENTRY_PREPARED_BINDING")
            report.update(preparation_observed=True, owner_request_issued=True, owner_request_issuance_observed=True)
        terminal = values[-1] if values else {}
        report["guest_terminal_status"] = terminal.get("status")
        report["guest_sealed"] = terminal.get("sealed") is True
        # These are explicitly observations of the owner record; independent
        # evidence remains subject to original Q2 review, not a host inference.
        report["owner_report_observed"] = terminal.get("schema") == "local-hand-q2-handoff-result/v1"
        if len(ready) == 1:
            ready = ready[0]
            require(set(ready) == {"schema", "status", "attempt_id", "retry_sha256", "delivery_sha256", "clock_anchor_sha256",
                                              "q2_accepted", "q3_accepted", "production_supported"}
                    and ready["status"] == "STARTUP_RETRY_BOOTSTRAP_READY"
                    and ready["attempt_id"] == config["attempt_id"]
                    and all(ready[key] is False for key in ("q2_accepted", "q3_accepted", "production_supported"))
                    and ready["clock_anchor_sha256"] == sha(encoded(anchor)), "STARTUP_ENTRY_READY_BINDING")
            guard(7 * NS)
            available = delivery.OUTPUT_LIMIT - capture["total_captured_bytes"] - 4096
            require(available >= 16384, "STARTUP_ENTRY_COLLECTION_OUTPUT")
            collection = capture_phase("collection", collection_command(config, ready, sha(encoded(anchor)), available),
                until=deadline - 5 * NS, prior=capture["total_captured_bytes"])
            if collection["complete"]:
                # Collector bundles can exceed the envelope's 16 KiB bound.
                collected = delivery.document((out / "collection.stdout").read_bytes(), maximum=delivery.OUTPUT_LIMIT)
                report["collection_record"] = collected
                report["collection_complete"] = (collection["returncode"] == 0
                    and collected.get("schema") == COLLECTION_SCHEMA and collected.get("status") == "COLLECTED"
                    and collected.get("scope") == "LH-Q2-SUPERVISOR-STARTUP-RETRY-v1"
                    and all(collected.get(key) is False for key in ("q2_accepted", "q3_accepted", "production_supported"))
                    and collected.get("attempt_id") == config["attempt_id"]
                    and collected.get("retry_sha256") == ready["retry_sha256"]
                    and collected.get("delivery_sha256") == ready["delivery_sha256"]
                    and collected.get("clock_anchor_sha256") == sha(encoded(anchor)))
        else:
            require(not ready, "STARTUP_ENTRY_DUPLICATE_READY")
        report["old_host_preserved"] = read_history(config, guard) == before
        wrapper_check()
        if (capture["complete"] and capture["returncode"] == 0 and invalid == 0 and report["old_host_preserved"]
                and report["preparation_observed"] and report["owner_report_observed"]
                and report["guest_sealed"] and terminal.get("status") == "SUPERVISOR_CLOSED"
                and report["collection_complete"]):
            report["status"] = "RUN_RECORDED"
    except Exception as error:
        # Only static codes/types, never arbitrary remote error strings.
        reason = str(error)
        report["error"] = {"type": type(error).__name__, "reason": reason if re.fullmatch(r"[A-Z0-9_]{1,128}", reason)
                           else "STARTUP_ENTRY_FAILURE"}
    finally:
        if wrapper_identity is not None:
            try:
                wrapper_check(); report["wrapper_unchanged"] = True
            except Exception as error:
                report["wrapper_unchanged"] = False
                report["wrapper_error"] = type(error).__name__
                report["status"] = "INCOMPLETE"
        # Re-attest history even when the original guest returned nonzero.
        if before is not None and "old_host_preserved" not in report:
            try:
                report["old_host_preserved"] = read_history(config, guard) == before
            except Exception as error:
                report["old_host_preserved"] = False
                report["preservation_error"] = type(error).__name__
        report["transport"] = delivery.final_report(attempt_id=config["attempt_id"], host_issued_ns=issued,
            host_deadline_ns=deadline, host_boottime_issued_ns=boot_issued,
            finished_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
            probe_capture=probe, guest_capture=capture, collect_capture=collection,
            error=report.get("error"))
        report["capture_finished_ns"] = time.monotonic_ns()
        report["capture_within_original_deadline"] = (report["capture_finished_ns"] <= deadline
            and time.clock_gettime_ns(time.CLOCK_BOOTTIME) <= boot_deadline)
        if not report["capture_within_original_deadline"]:
            report["status"] = "INCOMPLETE"
        report["host_finalization_pending"] = True
        base.write(out / "report.json", encoded(report)); base.sync_dir(out)
        names = ["intent.json", "probe-input.py", "probe.stdout", "probe.stderr", "probe-capture.json",
                 "clock-anchor.json", "guest.stdout", "guest.stderr", "guest-capture.json", "collection.stdout",
                 "collection.stderr", "collection-capture.json", "report.json"]
        compact = {}
        for name in names:
            path = out / name
            if path.exists():
                raw = path.read_bytes()
                compact[name] = {"bytes": len(raw), "sha256": sha(raw), "data": base64.b64encode(raw).decode()}
        # The durable core can be proven inside one compressed upload. The final
        # upload and process exit are separately observed, never self-certified.
        core = encoded(dict(schema=BUNDLE_SCHEMA, files=compact))
        base.write(out / "evidence-core.json", core); base.sync_dir(out)
        fsynced = time.monotonic_ns()
        completion = dict(schema=COMPLETION_SCHEMA, attempt_id=config["attempt_id"], issued_ns=issued,
            deadline_ns=deadline, core_fsynced_ns=fsynced, core_sha256=sha(core),
            core_within_original_deadline=(fsynced <= deadline
                and time.clock_gettime_ns(time.CLOCK_BOOTTIME) <= boot_deadline), original_status=report["status"],
            proof_scope="EXACT_EVIDENCE_CORE_FSYNC; UPLOAD_FSYNC_AND_PROCESS_EXIT_SEPARATE",
            q2_accepted=False, replay_allowed=False)
        completion_raw = encoded(completion)
        base.write(out / "completion.json", completion_raw); base.sync_dir(out)
        bundle = gzip.compress(encoded(dict(schema=BUNDLE_SCHEMA, core_sha256=sha(core), files=compact,
                                             completion=completion)), mtime=0)
        base.write(out / "q2-startup-retry-result.json.gz", bundle); base.sync_dir(out)
        upload_fsynced = time.monotonic_ns()
        finalization = dict(schema="local-hand-q2-supervisor-startup-retry-host-finalization/v1",
            attempt_id=config["attempt_id"], issued_ns=issued, deadline_ns=deadline,
            upload_fsynced_ns=upload_fsynced, upload_sha256=sha(bundle),
            upload_within_original_deadline=(upload_fsynced <= deadline
                and time.clock_gettime_ns(time.CLOCK_BOOTTIME) <= boot_deadline), q2_accepted=False,
            proof_scope="UPLOAD_BUNDLE_FSYNC; FINALIZATION_WRITE_AND_PROCESS_EXIT_SEPARATE")
        base.write(out / "finalization.json", encoded(finalization)); base.sync_dir(out)
        finished = time.monotonic_ns()
        report.update(finished_ns=finished, host_finalization_pending=False, completion=completion,
                      finalization=finalization, within_original_deadline=(finished <= deadline
                          and time.clock_gettime_ns(time.CLOCK_BOOTTIME) <= boot_deadline))
        if not report["within_original_deadline"]:
            report["status"] = "INCOMPLETE"; report["finalization_error"] = "STARTUP_ENTRY_FINALIZATION_DEADLINE"
        report["upload_path"] = str(out / "q2-startup-retry-result.json.gz")
    return report


def main():
    print(encoded(dict(schema=SCHEMA, status="BLOCKED", reason="EXPLICIT_APPROVED_PRIVATE_ENTRY_REQUIRED",
                       replay_allowed=False, q2_accepted=False, q3_accepted=False,
                       production_supported=False)).decode(), end="")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

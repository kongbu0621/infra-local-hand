from __future__ import annotations

import array
import copy
import hashlib
import json
import os
import socket
import struct
import sys
import unittest
from unittest import mock

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "NOT_RUN: q2 namespace reference and SCM ancillary checks are Linux-only"
    )

from e3_host import q2_namespace_reference as m


def context_raw(case_id: str = "N01") -> bytes:
    value = {
        "schema": m.CONTEXT_SCHEMA,
        "scope": m.SCOPE,
        "purpose": m.PURPOSE,
        "case_id": case_id,
        "source_digest": "a" * 64,
        "runtime_digest": "b" * 64,
        "fixture_digest": "c" * 64,
        "ordinary": {"uid": 1000, "gid": 1000, "groups": [1000, 1000, 2000]},
    }
    return m.canonical(value, m.CONTEXT_BYTES_MAX)


def synthetic_context_raw(case_id: str = "N01") -> bytes:
    """Bind the harness only to this test process's ordinary identity."""

    if os.geteuid() == 0:
        uid = gid = 65534
        groups: list[int] = []
    else:
        uid, gid = os.getuid(), os.getgid()
        if uid == 0 or gid == 0:
            raise unittest.SkipTest(
                "NOT_RUN: exact ordinary synthetic identity is unavailable"
            )
        groups = sorted(os.getgroups())
    value = {
        "schema": m.CONTEXT_SCHEMA,
        "scope": m.SCOPE,
        "purpose": m.PURPOSE,
        "case_id": case_id,
        "source_digest": "4" * 64,
        "runtime_digest": "5" * 64,
        "fixture_digest": "6" * 64,
        "ordinary": {"uid": uid, "gid": gid, "groups": groups},
    }
    return m.canonical(value, m.CONTEXT_BYTES_MAX)


def observation(role: str, pid: int, generation: str = "d" * 64) -> m.ProcessObservation:
    raw = f"Name:\ttest\nThreads:\t1\nNStgid:\t{pid}\nNSpid:\t{pid}\n".encode()
    status = m.parse_status(raw, pid)
    credential = m.Credential(pid, 1000, 1000)
    pid_ns = m.NamespaceIdentity("pid", 7, 101, m.CLONE_NEWPID)
    mnt_ns = m.NamespaceIdentity("mnt", 7, 102, m.CLONE_NEWNS)
    return m.ProcessObservation(
        role, credential, (1000, 1000, 2000), status, pid_ns, mnt_ns, generation
    )


def evidence() -> m.ReferenceEvidence:
    first = {
        "G": observation("G", 100),
        "R": observation("R", 101),
        "O": observation("O", 102),
    }
    second = {
        role: observation(role, item.credential.pid) for role, item in first.items()
    }
    coordinator_first = {"R": copy.deepcopy(first["R"]), "O": copy.deepcopy(first["O"])}
    coordinator_second = {
        "R": copy.deepcopy(second["R"]),
        "O": copy.deepcopy(second["O"]),
    }
    return m.ReferenceEvidence(
        first,
        second,
        coordinator_first,
        coordinator_second,
        {"R": True, "O": True},
        {"R": True, "O": True},
        40,
        {"G": 22, "R": 13, "O": 13},
        2,
        3,
    )


def protocol(case_id: str = "N01") -> m.ReferenceProtocol:
    context = m.validate_context(context_raw(case_id))
    return m.ReferenceProtocol(
        context,
        evidence(),
        g_pid=100,
        r_pid=101,
        o_pid=102,
        start_boottime_ns=1_000_000_000,
        start_monotonic_ns=2_000_000_000,
        deadline_boottime_ns=21_000_000_000,
        deadline_monotonic_ns=22_000_000_000,
    )


def drive(instance: m.ReferenceProtocol) -> None:
    for spec in m.FRAME_PLAN:
        nonce = b"r" * 32 if spec.counter == 6 else b"o" * 32 if spec.counter == 7 else None
        raw = instance.encode_next(nonce)
        rights = ()
        if spec.rights:
            source = instance.evidence.initial[spec.sender]
            rights = (source.pid_namespace, source.mnt_namespace)
        instance.advance(raw, m.Credential(instance.pids[spec.sender], 1000, 1000), rights)


def report_bindings(instance: m.ReferenceProtocol) -> dict[str, object]:
    return {
        "expected_session_id": instance.session_id,
        "expected_frame_chain_digest": hashlib.sha256(
            m.canonical(instance.frame_digests, m.CONTEXT_BYTES_MAX)
        ).hexdigest(),
        "expected_account": instance.account.snapshot(),
    }


class CanonicalInputTests(unittest.TestCase):
    def test_context_binds_fixed_case_source_runtime_fixture_and_duplicate_groups(self):
        raw = context_raw()
        context = m.validate_context(
            raw,
            hashlib.sha256(raw).hexdigest(),
            expected_identity=(1000, 1000, (1000, 1000, 2000)),
        )
        self.assertEqual("N01", context.case_id)
        self.assertEqual((1000, 1000, 2000), context.groups)
        self.assertEqual(m.CASE_IDS, tuple(f"N{n:02d}" for n in range(1, 13)))

    def test_context_rejects_noncanonical_duplicate_extra_and_free_locator_fields(self):
        raw = context_raw()
        value = json.loads(raw)
        cases = {
            "whitespace": json.dumps(value).encode(),
            "duplicate": raw[:-1] + b',"case_id":"N01"}',
            "pid": m.canonical({**value, "pid": 123}, m.CONTEXT_BYTES_MAX),
            "path": m.canonical({**value, "path": "/proc/1"}, m.CONTEXT_BYTES_MAX),
            "command": m.canonical({**value, "command": ["sh"]}, m.CONTEXT_BYTES_MAX),
            "case": m.canonical({**value, "case_id": "N13"}, m.CONTEXT_BYTES_MAX),
            "root": m.canonical(
                {**value, "ordinary": {"uid": 0, "gid": 1000, "groups": [1000]}},
                m.CONTEXT_BYTES_MAX,
            ),
            "groups": m.canonical(
                {**value, "ordinary": {"uid": 1000, "gid": 1000, "groups": [2000, 1000]}},
                m.CONTEXT_BYTES_MAX,
            ),
            "root_group": m.canonical(
                {**value, "ordinary": {"uid": 1000, "gid": 1000, "groups": [0, 1000]}},
                m.CONTEXT_BYTES_MAX,
            ),
            "too_many_groups": m.canonical(
                {
                    **value,
                    "ordinary": {
                        "uid": 1000,
                        "gid": 1000,
                        "groups": list(range(m.MAX_SUPPLEMENTARY_GROUPS + 1)),
                    },
                },
                m.CONTEXT_BYTES_MAX,
            ),
        }
        for name, candidate in cases.items():
            with self.subTest(name=name), self.assertRaises(m.ContractError):
                m.validate_context(candidate)

    def test_status_requires_single_level_single_thread_exact_pid(self):
        valid = b"Threads:\t1\nNStgid:\t19\nNSpid:\t19\n"
        self.assertEqual((19,), m.parse_status(valid, 19).nspid)
        for raw in (
            valid.replace(b"Threads:\t1", b"Threads:\t2"),
            valid.replace(b"NSpid:\t19", b"NSpid:\t1 19"),
            valid + b"NSpid:\t19\n",
            valid.replace(b"NStgid:\t19\n", b""),
            valid.replace(b"NSpid:\t19", b"NSpid:\t+19"),
        ):
            with self.subTest(raw=raw), self.assertRaises(m.ContractError):
                m.parse_status(raw, 19)


class EvidenceAndProtocolTests(unittest.TestCase):
    def test_held_child_source_and_recheck_fail_closed(self):
        context = m.validate_context(context_raw())
        for fault in ("coordinator", "recheck", "namespace", "pidfd", "identity"):
            item = evidence()
            if fault == "coordinator":
                bad = observation("R", 101, "e" * 64)
                item.coordinator_initial["R"] = bad
            elif fault == "recheck":
                item.rechecked["O"] = observation("O", 102, "e" * 64)
            elif fault == "namespace":
                old = item.initial["O"]
                item.initial["O"] = m.ProcessObservation(
                    "O",
                    old.credential,
                    old.groups,
                    old.status,
                    m.NamespaceIdentity("pid", 7, 999, m.CLONE_NEWPID),
                    old.mnt_namespace,
                    old.generation,
                )
            elif fault == "pidfd":
                item.pidfd_alive_rechecked["R"] = False
            else:
                old = item.initial["R"]
                item.initial["R"] = m.ProcessObservation(
                    "R",
                    m.Credential(101, 1001, 1000),
                    old.groups,
                    old.status,
                    old.pid_namespace,
                    old.mnt_namespace,
                    old.generation,
                )
            with self.subTest(fault=fault), self.assertRaises(m.ContractError):
                item.validate(context, {"G": 100, "R": 101, "O": 102})

    def test_exact_fifteen_frame_sequence_binds_roles_pins_nonces_and_rights(self):
        instance = protocol()
        original_r_digest = instance.evidence.initial["R"].digest
        # The verifier detached its held evidence from caller-owned mappings.
        external = evidence()
        detached = m.ReferenceProtocol(
            instance.context,
            external,
            g_pid=100,
            r_pid=101,
            o_pid=102,
            start_boottime_ns=1_000_000_000,
            start_monotonic_ns=2_000_000_000,
            deadline_boottime_ns=21_000_000_000,
            deadline_monotonic_ns=22_000_000_000,
        )
        external.initial["R"] = observation("R", 101, "e" * 64)
        self.assertEqual(original_r_digest, detached.evidence.initial["R"].digest)
        drive(instance)
        self.assertTrue(instance.complete)
        self.assertEqual(15, instance.counter)
        self.assertEqual(64, instance.account.random_bytes)
        self.assertEqual(15, instance.account.frames)
        self.assertLessEqual(instance.account.frame_bytes, m.FRAME_PAYLOAD_BYTES_MAX)
        self.assertEqual(
            [
                "SETUP_R",
                "SOURCE_R",
                "SETUP_O",
                "SOURCE_O",
                "START_CHALLENGE",
                "CHALLENGE_A",
                "RESPONSE_A",
                "CHALLENGE_B",
                "RESPONSE_B",
                "ROUND1_RESULT",
                "ROUND1_RESULT",
                "RECHECK",
                "RECHECK",
                "ROUND2_RESULT",
                "ROUND2_RESULT",
            ],
            [spec.kind for spec in m.FRAME_PLAN],
        )
        with self.assertRaisesRegex(m.ContractError, "PROTOCOL_EXTRA_FRAME"):
            instance.advance(b"{}", m.Credential(100, 1000, 1000))

    def test_each_binding_or_sequence_fault_is_rejected_before_counter_advances(self):
        mutations = ("counter", "role", "session", "source", "runtime", "context", "body", "credential", "rights")
        for fault in mutations:
            instance = protocol()
            raw = instance.encode_next()
            value = json.loads(raw)
            credential = m.Credential(100, 1000, 1000)
            rights = ()
            if fault == "counter":
                value["counter"] = 2
            elif fault == "role":
                value["sender"] = "R"
            elif fault == "session":
                value["session_id"] = "f" * 64
            elif fault == "source":
                value["source_digest"] = "f" * 64
            elif fault == "runtime":
                value["runtime_digest"] = "f" * 64
            elif fault == "context":
                value["context_digest"] = "f" * 64
            elif fault == "body":
                value["body"]["r_pid"] += 1
            elif fault == "credential":
                credential = m.Credential(101, 1000, 1000)
            else:
                rights = (
                    instance.evidence.initial["G"].pid_namespace,
                    instance.evidence.initial["G"].mnt_namespace,
                )
            candidate = m.canonical(value, m.FRAME_BYTES_MAX)
            with self.subTest(fault=fault), self.assertRaises(m.ContractError):
                instance.advance(candidate, credential, rights)
            self.assertEqual(0, instance.counter)

    def test_nonce_replay_wrong_rights_and_old_frame_are_rejected(self):
        instance = protocol()
        for spec in m.FRAME_PLAN[:5]:
            raw = instance.encode_next()
            rights = ()
            if spec.rights:
                source = instance.evidence.initial[spec.sender]
                rights = (source.pid_namespace, source.mnt_namespace)
            instance.advance(raw, m.Credential(instance.pids[spec.sender], 1000, 1000), rights)
        raw = instance.encode_next(b"r" * 32)
        source = instance.evidence.initial["R"]
        with self.assertRaises(m.ContractError):
            instance.advance(
                raw,
                m.Credential(101, 1000, 1000),
                (source.mnt_namespace, source.pid_namespace),
            )
        instance.advance(
            raw,
            m.Credential(101, 1000, 1000),
            (source.pid_namespace, source.mnt_namespace),
        )
        with self.assertRaisesRegex(m.ContractError, "PROTOCOL_NONCE_INDEPENDENCE"):
            instance.encode_next(b"r" * 32)

    def test_ceiling_account_rejects_overrun_and_bool_as_integer(self):
        account = m.CeilingAccount()
        for _ in range(m.FRAME_COUNT):
            account.add_frame(1, 0)
        with self.assertRaises(m.ContractError):
            account.add_frame(1, 0)
        with self.assertRaises(m.ContractError):
            m.CeilingAccount().add_frame(True, 0)
        for role, maximum in m.INSTALLED_FD_MAX.items():
            account.observe_fd_peak(role, maximum)
        self.assertEqual(48, sum(account.installed_fd_peak.values()))
        account.observe_fd_peak("G", 22, 2)
        self.assertEqual(50, sum(account.installed_fd_peak.values()) + account.queued_fd_peak)

    def test_standalone_report_cannot_claim_outer_fixture_success(self):
        instance = protocol()
        drive(instance)
        report = m.build_report(instance)
        bindings = report_bindings(instance)
        value = m.validate_report(report, instance.context, **bindings)
        self.assertEqual("REFERENCE_RELATION_MATCHED", value["component_status"])
        self.assertEqual("NOT_RUN", value["fixture_qualification"])
        self.assertEqual(len(report), value["protocol"]["stdout_bytes"])
        self.assertEqual(instance.context.fixture_digest, value["fixture_digest"])
        self.assertFalse(value["readiness"]["field_ready"])
        forged = json.loads(report)
        forged["fixture_qualification"] = "FIXTURE_LIVE_REFERENCE_MATCHED"
        with self.assertRaises(m.ContractError):
            m.validate_report(
                m.canonical(forged, m.STDOUT_BYTES_MAX), instance.context, **bindings
            )

    def test_report_rejects_stale_session_frame_chain_and_account(self):
        instance = protocol()
        drive(instance)
        report = m.build_report(instance)
        bindings = report_bindings(instance)
        original = json.loads(report)
        for name, mutate, reason in (
            ("session", lambda value: value.__setitem__("session_id", "e" * 64),
             "REPORT_SESSION_BINDING"),
            ("frame-chain", lambda value: value["protocol"].__setitem__(
                "frame_chain_digest", "e" * 64), "REPORT_FRAME_CHAIN_BINDING"),
            ("account", lambda value: value["protocol"]["installed_fd_peak"].__setitem__(
                "G", 21), "REPORT_ACCOUNT_BINDING"),
        ):
            candidate = copy.deepcopy(original)
            mutate(candidate)
            with self.subTest(name=name), self.assertRaisesRegex(m.ContractError, reason):
                m.validate_report(
                    m.canonical(candidate, m.STDOUT_BYTES_MAX),
                    instance.context,
                    **bindings,
                )


class SyntheticHarnessTests(unittest.TestCase):
    _UNAVAILABLE = {
        "SYNTHETIC_LINUX_INTERFACE_UNAVAILABLE",
        "SYNTHETIC_CREDENTIAL_TRANSPORT_UNAVAILABLE",
        "SYNTHETIC_ORDINARY_IDENTITY_UNAVAILABLE",
    }

    def run_harness(self, fault: str = "NONE") -> dict[str, object]:
        result = dict(m.run_synthetic_harness(synthetic_context_raw(), fault=fault))
        self.assertEqual(m.Outcome.NOT_RUN.value, result["fixture_qualification"])
        for key in (
            "held_procfs_proven",
            "nsfs_proven",
            "native_fixture_executed",
            "field_ready",
            "allow_run",
        ):
            self.assertIs(False, result[key])
        self.assertNotEqual(
            m.Outcome.FIXTURE_LIVE_REFERENCE_MATCHED.value, result["status"]
        )
        if result["reason"] in self._UNAVAILABLE:
            self.assertEqual(m.Outcome.NOT_RUN.value, result["status"])
            self.assertEqual(0, result["direct_forks"])
            self.assertEqual(0, result["frames"])
            self.assertTrue(result["fd_cleanup_complete"])
            self.skipTest(f"NOT_RUN: {result['reason']}")
        return result

    def test_wait_child_never_falls_back_to_blocking_waitpid(self):
        with (
            mock.patch.object(m.os, "waitpid", return_value=(0, 0)) as waitpid,
            mock.patch.object(m.os, "kill") as kill,
            mock.patch.object(m.time, "monotonic", side_effect=(0.0, 6.0, 8.0)),
            mock.patch.object(m.time, "sleep"),
        ):
            result = m._wait_child(12345, terminate=False)
        self.assertEqual(
            {
                "exited": False,
                "exit_code": None,
                "signal": None,
                "already_reaped": False,
            },
            result,
        )
        kill.assert_called_once_with(12345, m.signal.SIGKILL)
        self.assertGreaterEqual(waitpid.call_count, 2)
        self.assertTrue(
            all(call.args == (12345, os.WNOHANG) for call in waitpid.call_args_list)
        )

    def test_normal_chain_is_real_transport_but_never_native_pass(self):
        result = self.run_harness()
        self.assertEqual(m.Outcome.NOT_RUN.value, result["status"])
        self.assertEqual(
            "HELD_PROCFS_NSFS_NATIVE_FIXTURE_NOT_PROVEN", result["reason"]
        )
        self.assertEqual(2, result["direct_forks"])
        self.assertEqual(m.FRAME_COUNT, result["frames"])
        self.assertTrue(result["g_go_eof"])
        self.assertTrue(result["control_eof"])
        self.assertTrue(result["child_cross_eof_exit_bound"])
        self.assertTrue(result["fd_cleanup_complete"])
        self.assertEqual({"R", "O"}, set(result["child_waits"]))
        self.assertTrue(
            all(row["exit_code"] == 0 for row in result["child_waits"].values())
        )
        account = result["account"]
        self.assertEqual(m.FRAME_COUNT, account["frames"])
        self.assertEqual(m.RANDOM_BYTES_EXACT, account["random_bytes"])
        self.assertEqual(m.TASKS_EXACT, account["tasks"])
        self.assertLessEqual(account["queued_fd_peak"], m.QUEUED_FD_MAX)

    def test_stale_session_is_retained_before_second_frame(self):
        result = self.run_harness("STALE_SESSION")
        self.assertEqual(m.Outcome.BLOCKED_RETAINED.value, result["status"])
        self.assertEqual("FRAME_SESSION", result["reason"])
        self.assertEqual(2, result["direct_forks"])
        self.assertEqual(1, result["frames"])
        self.assertTrue(result["g_go_eof"])
        self.assertFalse(result["control_eof"])
        self.assertFalse(result["child_cross_eof_exit_bound"])
        self.assertTrue(result["fd_cleanup_complete"])

    def test_early_child_exit_is_unknown_and_reaped(self):
        result = self.run_harness("EARLY_EXIT")
        self.assertEqual(m.Outcome.UNKNOWN_RETAINED.value, result["status"])
        self.assertEqual("RECEIVE_EOF", result["reason"])
        self.assertEqual(2, result["direct_forks"])
        self.assertEqual(1, result["frames"])
        self.assertEqual({"R", "O"}, set(result["child_waits"]))
        self.assertTrue(result["fd_cleanup_complete"])
        self.assertFalse(result["child_cross_eof_exit_bound"])

    def test_extra_sixteenth_frame_is_rejected_after_fixed_plan(self):
        result = self.run_harness("EXTRA_FRAME")
        self.assertEqual(m.Outcome.BLOCKED_RETAINED.value, result["status"])
        self.assertEqual("SYNTHETIC_O_CONTROL_EXTRA_FRAME", result["reason"])
        self.assertEqual(m.FRAME_COUNT, result["frames"])
        self.assertFalse(result["control_eof"])
        self.assertFalse(result["child_cross_eof_exit_bound"])
        self.assertTrue(result["fd_cleanup_complete"])

    def test_eof_wait_and_fd_recovery_preserve_caller_handle(self):
        sentinel_read, sentinel_write = os.pipe()
        try:
            before = os.fstat(sentinel_read)
            first = self.run_harness()
            second = self.run_harness()
            after = os.fstat(sentinel_read)
            self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
            self.assertNotEqual(first["session_id"], second["session_id"])
            for result in (first, second):
                self.assertTrue(result["g_go_eof"])
                self.assertTrue(result["control_eof"])
                self.assertTrue(result["child_cross_eof_exit_bound"])
                self.assertTrue(result["fd_cleanup_complete"])
        finally:
            os.close(sentinel_read)
            os.close(sentinel_write)


@unittest.skipUnless(sys.platform.startswith("linux"), "NOT_RUN: Linux-only held-fd checks")
class LinuxHeldInterfaceTests(unittest.TestCase):
    def test_actual_self_status_and_nsfs_types_when_available(self):
        if os.getuid() == 0 or os.getgid() == 0:
            self.skipTest("NOT_RUN: exact ordinary non-root identity is unavailable")
        try:
            with open("/proc/self/status", "rb", buffering=0) as stream:
                raw = stream.read(m.STATUS_BYTES_MAX + 1)
            status = m.parse_status(raw, os.getpid())
            pid_fd = os.open("/proc/self/ns/pid", os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
            mnt_fd = os.open("/proc/self/ns/mnt", os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
        except (OSError, m.ContractError) as error:
            self.skipTest(f"NOT_RUN: fixed proc/ns interface unavailable: {type(error).__name__}")
        try:
            self.assertEqual(os.getpid(), status.pid)
            self.assertEqual("pid", m.namespace_from_fd(pid_fd, "pid").kind)
            self.assertEqual("mnt", m.namespace_from_fd(mnt_fd, "mnt").kind)
        finally:
            os.close(pid_fd)
            os.close(mnt_fd)

    def test_real_direct_child_seqpacket_credentials_rights_pidfd_and_wait(self):
        if os.getuid() == 0 or os.getgid() == 0:
            self.skipTest("NOT_RUN: exact ordinary non-root identity is unavailable")
        if not hasattr(os, "pidfd_open"):
            self.skipTest("NOT_RUN: pidfd_open unavailable")
        try:
            parent, child_socket = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        except (OSError, PermissionError) as error:
            self.skipTest(f"NOT_RUN: anonymous SEQPACKET unavailable: {error.errno}")
        parent.settimeout(m.SYNTHETIC_TIMEOUT_SECONDS)
        child_socket.settimeout(m.SYNTHETIC_TIMEOUT_SECONDS)
        try:
            m.enable_passcred(parent)
        except (OSError, m.ContractError) as error:
            parent.close()
            child_socket.close()
            self.skipTest(f"NOT_RUN: SO_PASSCRED unavailable: {type(error).__name__}")
        control_read, control_write = os.pipe()
        child = os.fork()
        if child == 0:
            try:
                parent.close()
                os.close(control_write)
                pid_fd = os.open("/proc/self/ns/pid", os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
                mnt_fd = os.open("/proc/self/ns/mnt", os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
                try:
                    m.send_packet(child_socket, b'{"probe":"held-direct-child"}', (pid_fd, mnt_fd))
                finally:
                    os.close(pid_fd)
                    os.close(mnt_fd)
                if os.read(control_read, 1) != b"x":
                    os._exit(91)
                os._exit(0)
            except BaseException:
                os._exit(92)
        child_socket.close()
        os.close(control_read)
        pidfd = -1
        waited = False
        try:
            try:
                pidfd = os.pidfd_open(child, 0)
                packet = m.receive_packet(
                    parent,
                    expected_credential=m.Credential(child, os.getuid(), os.getgid()),
                    expected_fd_count=2,
                )
            except (OSError, m.ContractError) as error:
                os.write(control_write, b"x")
                wait_result = m._wait_child(child, terminate=False)
                waited = (wait_result["exited"] or wait_result["signal"] is not None
                    or wait_result["already_reaped"])
                self.skipTest(f"NOT_RUN: direct-child held interface unavailable: {type(error).__name__}")
            try:
                self.assertEqual(b'{"probe":"held-direct-child"}', packet.payload)
                child_pid_ns = m.namespace_from_fd(packet.fds[0], "pid")
                child_mnt_ns = m.namespace_from_fd(packet.fds[1], "mnt")
                parent_pid = os.open("/proc/self/ns/pid", os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
                parent_mnt = os.open("/proc/self/ns/mnt", os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
                try:
                    self.assertEqual(m.namespace_from_fd(parent_pid, "pid"), child_pid_ns)
                    self.assertEqual(m.namespace_from_fd(parent_mnt, "mnt"), child_mnt_ns)
                finally:
                    os.close(parent_pid)
                    os.close(parent_mnt)
            finally:
                for fd in packet.fds:
                    os.close(fd)
            os.write(control_write, b"x")
            wait_result = m._wait_child(child, terminate=False)
            waited = (wait_result["exited"] or wait_result["signal"] is not None
                or wait_result["already_reaped"])
            self.assertTrue(wait_result["exited"])
            self.assertEqual(0, wait_result["exit_code"])
            # This is a component observation only: no supplied cgroup,
            # pause, accounting, outer EOF, or seal exists, so full fixture
            # qualification accurately remains NOT_RUN.
            self.assertGreaterEqual(pidfd, 0)
        finally:
            parent.close()
            os.close(control_write)
            if pidfd >= 0:
                os.close(pidfd)
            if not waited:
                m._wait_child(child, terminate=True)


class AncillaryFailureTests(unittest.TestCase):
    def test_packet_io_refuses_an_unbounded_or_wrong_socket(self):
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        try:
            with self.assertRaisesRegex(m.ContractError, "SOCKET_NOT_BOUNDED_SEQPACKET"):
                m.send_packet(left, b"x")
            left.settimeout(m.SYNTHETIC_TIMEOUT_SECONDS + 1.0)
            with self.assertRaisesRegex(m.ContractError, "SOCKET_NOT_BOUNDED_SEQPACKET"):
                m.send_packet(left, b"x")
        finally:
            left.close()
            right.close()

    def test_credentials_count_truncation_unknown_and_rights_are_fail_closed(self):
        expected = m.Credential(123, 1000, 1000)
        cred = (socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("=3i", 123, 1000, 1000))
        for name, items, flags, count in (
            ("missing", [], 0, 0),
            ("duplicate", [cred, cred], 0, 0),
            ("wrong", [(socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("=3i", 124, 1000, 1000))], 0, 0),
            ("truncated", [cred], socket.MSG_CTRUNC, 0),
            ("unknown", [cred, (socket.SOL_SOCKET, 9999, b"x")], 0, 0),
            ("rights-missing", [cred], 0, 2),
        ):
            with self.subTest(name=name), self.assertRaises(m.ContractError):
                m.validate_ancillary(items, flags, expected_credential=expected, expected_fd_count=count)

    def test_rejected_extra_rights_are_closed(self):
        expected = m.Credential(123, 1000, 1000)
        read_fd, write_fd = os.pipe()
        duplicate = os.dup(read_fd)
        data = array.array("i", [duplicate]).tobytes()
        ancillary = [
            (socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("=3i", 123, 1000, 1000)),
            (socket.SOL_SOCKET, socket.SCM_RIGHTS, data),
        ]
        try:
            with self.assertRaises(m.ContractError):
                m.validate_ancillary(
                    ancillary, 0, expected_credential=expected, expected_fd_count=0
                )
            with self.assertRaises(OSError):
                os.fstat(duplicate)
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_truncated_or_prior_unknown_ancillary_still_closes_later_rights(self):
        expected = m.Credential(123, 1000, 1000)
        cred = (socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("=3i", 123, 1000, 1000))
        for name, prefix, flags in (
            ("truncated", [], socket.MSG_CTRUNC),
            ("unknown-first", [(socket.SOL_SOCKET, 9999, b"x")], 0),
        ):
            read_fd, write_fd = os.pipe()
            duplicate = os.dup(read_fd)
            rights = (
                socket.SOL_SOCKET,
                socket.SCM_RIGHTS,
                array.array("i", [duplicate]).tobytes(),
            )
            try:
                with self.subTest(name=name), self.assertRaises(m.ContractError):
                    m.validate_ancillary(
                        [cred, *prefix, rights],
                        flags,
                        expected_credential=expected,
                        expected_fd_count=1,
                    )
                with self.assertRaises(OSError):
                    os.fstat(duplicate)
            finally:
                os.close(read_fd)
                os.close(write_fd)


if __name__ == "__main__":
    unittest.main()

"""Q1 LOGIC_ONLY bindings/exit facts, plus real anonymous-pipe backpressure.

No systemd, quota syscall, account, mount or service is created by these tests.
Manager observations below are fixtures, never claimed as host observations.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from admin.local_hand_quota_observer import admission as a, supervision as s


BOOT = "01234567-89ab-cdef-0123-456789abcdef"
GENERATION = "1" * 32
INVOCATION = "a" * 32
NOW = 1_000_000_000


def encoded(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def fixture():
    return {
        "schema": "local-hand-quota-q1-manifest/v1", "authority_digest": "a" * 64,
        "installation_digest": "b" * 64, "source_commit": "c" * 40, "boot_id": BOOT,
        "epoch": "d" * 32, "query_uid": 0, "query_euid": 0,
        "abi": {"fsxattr_bytes": 28, "dqblk_bytes": 72, "qstatv_bytes": 160},
        "cgroup_parent": "/synthetic-quota.slice", "max_query_ns": 2_000_000_000,
        "slots": [{"ref": "test-root", "generation": GENERATION, "path": "/synthetic/quota/root",
                   "filesystem": "ext4", "filesystem_uuid": BOOT,
                   "root": {"device": 41, "inode": 52, "uid": 1501, "gid": 1501,
                            "mode": stat.S_IFDIR | 0o700},
                   "project_id": 73, "xflags": 0x200, "hard_bytes": 123 * 1024}]}


def decode(value=None):
    raw = encoded(fixture() if value is None else value)
    return a.decode_manifest(raw, hashlib.sha256(raw).hexdigest())


def report(manifest=None):
    manifest = manifest or decode()
    slot = manifest.slots[0]
    root = dict(vars(slot.root))
    return {
        "schema": "local-hand-quota-abi/v1", "status": "OBSERVED", "code": "QUOTA_FACTS_OBSERVED",
        "real_e3_accepted": False, "production_supported": False, "admission_proven": False,
        "quota_syscall_attempts": 3, "uid": manifest.query_uid, "euid": manifest.query_euid, "root_fd": 3,
        "abi": dict(zip(("fsxattr_bytes", "dqblk_bytes", "qstatv_bytes"), manifest.abi)),
        "root": root, "root_after": dict(root), "filesystem_magic": 0xEF53,
        "project": {"id": 73, "xflags": 0x200}, "project_after": {"id": 73, "xflags": 0x200},
        "enforcement": {"version": 1, "flags": 0x30}, "enforcement_after": {"version": 1, "flags": 0x30},
        "quota": {"valid_mask": 63, "hard_blocks_1024": 123, "hard_bytes": 123 * 1024},
        "calls": [{"name": name, "rc": 0, "errno": 0} for name in a.SUCCESS_CALLS]}


def binding(manifest=None, **changes):
    arguments = dict(slot_ref="test-root", generation=GENERATION, request_id="e" * 32,
                     allocation_digest="f" * 64, execution_id="2" * 32, phase="preflight",
                     now_ns=NOW, phase_deadline_ns=NOW + 9_000_000_000)
    arguments.update(changes)
    return s.bind_query(manifest or decode(), **arguments)


def observation(bound, **changes):
    result = s.UnitObservation(BOOT, bound.unit, INVOCATION, bound.cgroup, NOW,
                               True, True, True, True, True, True, 1, 0)
    return replace(result, **changes)


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 Linux ABI contract")
class AdmissionTests(unittest.TestCase):
    def test_exact_snapshot_is_immutable_and_rejects_changed_bytes(self):
        manifest = decode()
        self.assertEqual(manifest.hard_capacity_bytes, 123 * 1024)
        self.assertEqual(manifest.slot("test-root", GENERATION), manifest.slots[0])
        with self.assertRaises(FrozenInstanceError):
            manifest.slots[0].project_id = 99
        with self.assertRaisesRegex(a.Rejected, "MANIFEST_DIGEST"):
            a.decode_manifest(encoded(fixture()) + b" ", manifest.digest)
        for ref, gen in [("/etc", GENERATION), ("test-root", "9" * 32), ("unknown", GENERATION)]:
            with self.subTest(ref=ref, gen=gen), self.assertRaises(a.Rejected):
                manifest.slot(ref, gen)

    def test_untrusted_json_is_bounded_and_strict(self):
        for raw in (b'{"schema":1,"schema":2}', b'{"x":NaN}', b'{"x":1.0}', b'{"x":"\\ud800"}',
                    b'[]' * 2, b'[' * 1000 + b'0' + b']' * 1000,
                    b'{"x":' + b'9' * 100 + b'}', b' ' * (a.MAX_MANIFEST_BYTES + 1), b'\xff'):
            with self.subTest(raw=raw[:30]), self.assertRaises(a.Rejected):
                a.decode_manifest(raw, hashlib.sha256(raw).hexdigest())
        for key, replacement in [("query_uid", True), ("max_query_ns", 0), ("max_query_ns", 30_000_000_001),
                                 ("epoch", "../epoch"), ("slots", []), ("source_commit", "HEAD")]:
            value = fixture()
            value[key] = replacement
            with self.subTest(key=key, replacement=replacement), self.assertRaises(a.Rejected):
                decode(value)
        value = fixture()
        value["command"] = "/bin/sh"
        with self.assertRaises(a.Rejected):
            decode(value)

    def test_paths_roots_projects_and_limits_are_fixed(self):
        cases = [("path", "/"), ("path", "/a/../b"), ("path", "/a//b"), ("path", "//a/b"),
                 ("path", "/a/%i"), ("path", "/a/$UID"), ("path", "/a\nb"), ("filesystem", "ext3"),
                 ("project_id", 0), ("project_id", True), ("xflags", 0), ("hard_bytes", 0),
                 ("hard_bytes", 1025), ("hard_bytes", 2**64)]
        for key, replacement in cases:
            value = fixture()
            value["slots"][0][key] = replacement
            with self.subTest(key=key, replacement=replacement), self.assertRaises(a.Rejected):
                decode(value)
        for mode in (stat.S_IFREG | 0o700, stat.S_IFDIR | 0o777, stat.S_IFDIR | 0o4700):
            value = fixture()
            value["slots"][0]["root"]["mode"] = mode
            with self.assertRaises(a.Rejected):
                decode(value)

    def two_roots(self):
        value = fixture()
        other = deepcopy(value["slots"][0])
        other.update(ref="other", path="/synthetic/quota/other")
        other["root"]["inode"] += 1
        value["slots"].append(other)
        return value

    def test_shared_domain_counts_once_but_conflicts_and_aliases_fail(self):
        value = self.two_roots()
        self.assertEqual(decode(value).hard_capacity_bytes, 123 * 1024)
        value["slots"][1]["project_id"] += 1
        self.assertEqual(decode(value).hard_capacity_bytes, 246 * 1024)
        for modify in (
            lambda x: x.update(ref="test-root"),
            lambda x: x.update(path="/synthetic/quota/root/child"),
            lambda x: x.update(filesystem_uuid="99999999-9999-9999-9999-999999999999"),
            lambda x: x.update(hard_bytes=1024),
            lambda x: x["root"].update(inode=52),
            lambda x: x["root"].update(device=42),
        ):
            value = self.two_roots()
            modify(value["slots"][1])
            with self.assertRaises(a.Rejected):
                decode(value)

    def test_report_rejects_drift_bad_calls_and_false_success_claims(self):
        manifest = decode()
        good = report(manifest)
        good["calls"][5]["errno"] = 4  # successful rc is authoritative, errno is retained
        self.assertEqual(a.match_report(encoded(good), manifest, manifest.slots[0]), good)
        changes = (
            lambda x: x["root"].update(inode=53), lambda x: x["root_after"].update(uid=1502),
            lambda x: x["root_after"].update(uid=True), lambda x: x["project"].update(id=74),
            lambda x: x["project_after"].update(xflags=0), lambda x: x["enforcement"].update(flags=16),
            lambda x: x["enforcement_after"].update(flags=49), lambda x: x["quota"].update(hard_bytes=1024),
            lambda x: x["quota"].update(hard_blocks_1024=246), lambda x: x["quota"].update(valid_mask=2),
            lambda x: x["abi"].update(dqblk_bytes=128), lambda x: x.update(euid=1501),
            lambda x: x.update(filesystem_magic=0), lambda x: x.update(root_fd=4),
            lambda x: x.update(admission_proven=True), lambda x: x.update(quota_syscall_attempts=4),
            lambda x: x["calls"][5].update(rc=-1, errno=1), lambda x: x["calls"].pop(),
            lambda x: x["calls"][1].update(rc=0x200000), lambda x: x["calls"][0].update(rc=True),
            lambda x: x.update(extra="unexpected"), lambda x: x.update(schema="local-hand-quota-abi/v2"),
        )
        for index, change in enumerate(changes):
            value = deepcopy(good)
            change(value)
            with self.subTest(index=index), self.assertRaises(a.Rejected):
                a.match_report(encoded(value), manifest, manifest.slots[0])


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux pipe/ABI observation core")
class MonitorTests(unittest.TestCase):
    def complete(self, monitor):
        monitor.feed(encoded(report(monitor.binding.manifest)), now_ns=NOW)
        monitor.eof(now_ns=NOW)

    def test_binding_caps_deadline_and_keeps_identity_stable_on_recovery(self):
        bound = binding()
        self.assertEqual(bound.deadline_ns, NOW + 2_000_000_000)
        self.assertEqual(binding(phase_deadline_ns=NOW + 10).deadline_ns, NOW + 10)
        self.assertEqual(bound.unit, binding().unit)
        self.assertNotEqual(bound.unit, binding(allocation_digest="3" * 64).unit)
        self.assertNotEqual(bound.unit, binding(execution_id="4" * 32).unit)
        recovered = s.QueryMonitor(bound, recovered=True, original_invocation=INVOCATION)
        self.assertIs(recovered.binding, bound)
        self.assertFalse(hasattr(recovered, "start"))
        with self.assertRaises(a.Rejected):
            binding(phase_deadline_ns=NOW)

    def test_output_and_exit_are_both_required(self):
        bound = binding()
        for flag in ("delivery_settled", "admission_fenced", "job_empty", "unit_terminal",
                     "cgroup_empty", "collectors_stopped"):
            with self.subTest(flag=flag):
                monitor = s.QueryMonitor(bound)
                self.complete(monitor)
                waiting = monitor.inspect(observation(bound, **{flag: False}), now_ns=NOW)
                self.assertEqual(waiting.status, "WAITING")
                self.assertFalse(waiting.query_stopped)
                matched = monitor.inspect(observation(bound), now_ns=NOW)
                self.assertEqual(matched.status, "OBSERVED")
                self.assertTrue(matched.facts_match)
                self.assertFalse(matched.admission_proven or matched.real_e3_accepted or matched.production_supported)
        monitor = s.QueryMonitor(bound)
        monitor.feed(encoded(report()), now_ns=NOW)
        self.assertEqual(monitor.inspect(observation(bound), now_ns=NOW).reason, "PIPE_EOF_REQUIRED")

    def test_identity_change_is_sticky_even_if_later_restored(self):
        bound = binding()
        for changes in ({"boot_id": "9" * 36}, {"unit": bound.unit + "extra"}, {"cgroup": "/other"},
                        {"invocation_id": "b" * 32}, {"observed_ns": NOW - 1}, {"job_empty": 1}):
            with self.subTest(changes=changes):
                monitor = s.QueryMonitor(bound)
                monitor.inspect(observation(bound, cgroup_empty=False), now_ns=NOW)
                self.complete(monitor)
                self.assertEqual(monitor.inspect(observation(bound, **changes), now_ns=NOW).status, "UNKNOWN")
                self.assertEqual(monitor.inspect(observation(bound), now_ns=NOW).status, "UNKNOWN")

    def test_timeout_kill_and_nonzero_exit_never_become_success(self):
        bound = binding()
        for changes in ({"exec_main_code": 2, "exec_main_status": 9}, {"exec_main_status": 3},
                        {"exec_main_code": None, "exec_main_status": None}):
            monitor = s.QueryMonitor(bound)
            self.complete(monitor)
            self.assertEqual(monitor.inspect(observation(bound, **changes), now_ns=NOW).status, "UNKNOWN")
        monitor = s.QueryMonitor(bound)
        self.complete(monitor)
        result = monitor.inspect(observation(bound, observed_ns=bound.deadline_ns), now_ns=bound.deadline_ns)
        self.assertEqual(result.reason, "DEADLINE_EXPIRED")
        self.assertTrue(result.query_stopped)  # stopped is separate from timely, usable facts

    def test_recovery_does_not_reconstruct_lost_output_or_invocation(self):
        bound = binding()
        for original in (None, INVOCATION):
            monitor = s.QueryMonitor(bound, recovered=True, original_invocation=original)
            self.complete(monitor)
            result = monitor.inspect(observation(bound), now_ns=NOW)
            self.assertEqual(result.reason, "OUTPUT_LOST_ON_RECOVERY")
            self.assertEqual(result.query_stopped, original is not None)
            self.assertFalse(result.facts_match)
        monitor = s.QueryMonitor(bound, recovered=True, original_invocation=INVOCATION)
        result = monitor.inspect(observation(bound, invocation_id="b" * 32), now_ns=NOW)
        self.assertFalse(result.query_stopped)

    def test_partial_duplicate_oversize_and_extra_output_retain_unknown(self):
        bound = binding()
        raw = encoded(report())
        for data in (raw[:-2], raw + raw, raw.replace(b'"root_fd":3', b'"root_fd":3,"root_fd":3'),
                     b"x" * (a.MAX_REPORT_BYTES + 1)):
            monitor = s.QueryMonitor(bound)
            monitor.feed(data, now_ns=NOW)
            monitor.eof(now_ns=NOW)
            self.assertEqual(monitor.inspect(observation(bound), now_ns=NOW).status, "UNKNOWN")
            self.assertEqual(monitor.raw_prefix, data[:a.MAX_REPORT_BYTES])
        monitor = s.QueryMonitor(bound)
        self.complete(monitor)
        monitor.feed(b" ", now_ns=NOW)
        self.assertEqual(monitor.inspect(observation(bound), now_ns=NOW).reason, "BYTES_AFTER_EOF")

    def test_real_pipe_held_open_returns_without_waiting(self):
        bound = binding()
        monitor = s.QueryMonitor(bound)
        reader, writer = os.pipe()
        self.addCleanup(os.close, reader)
        self.addCleanup(os.close, writer)
        os.set_blocking(reader, False)
        started = time.monotonic()
        monitor.read_once(reader, now_ns=NOW)  # no bytes, writer still open
        self.assertLess(time.monotonic() - started, 1)
        raw = encoded(report())
        os.write(writer, raw)
        monitor.read_once(reader, now_ns=NOW)
        self.assertEqual(monitor.raw_prefix, raw)
        self.assertEqual(monitor.inspect(observation(bound), now_ns=NOW).reason, "PIPE_EOF_REQUIRED")
        monitor.read_once(reader, now_ns=NOW)
        expired = monitor.inspect(observation(bound, observed_ns=bound.deadline_ns,
                                               cgroup_empty=False), now_ns=bound.deadline_ns)
        self.assertEqual(expired.reason, "DEADLINE_EXPIRED")
        self.assertFalse(expired.query_stopped)

    def test_real_pipe_fragmentation_and_eof(self):
        bound = binding()
        monitor = s.QueryMonitor(bound)
        reader, writer = os.pipe()
        self.addCleanup(os.close, reader)
        os.set_blocking(reader, False)
        raw = encoded(report())
        try:
            for part in (raw[:50], raw[50:]):
                os.write(writer, part)
                monitor.read_once(reader, now_ns=NOW)
        finally:
            os.close(writer)
        monitor.read_once(reader, now_ns=NOW)
        self.assertEqual(monitor.inspect(observation(bound), now_ns=NOW).status, "OBSERVED")

    def test_blocking_and_regular_fds_are_rejected_before_read(self):
        bound = binding()
        reader, writer = os.pipe()
        self.addCleanup(os.close, reader)
        self.addCleanup(os.close, writer)
        monitor = s.QueryMonitor(bound)
        monitor.read_once(reader, now_ns=NOW)
        self.assertEqual(monitor.inspect(observation(bound), now_ns=NOW).reason, "NONBLOCKING_PIPE_REQUIRED")
        with tempfile.TemporaryFile() as stream:
            monitor = s.QueryMonitor(bound)
            monitor.read_once(stream.fileno(), now_ns=NOW)
            self.assertEqual(monitor.inspect(observation(bound), now_ns=NOW).reason, "NONBLOCKING_PIPE_REQUIRED")

    def test_descriptor_replacement_and_clock_reversal_are_not_recovery(self):
        bound = binding()
        monitor = s.QueryMonitor(bound)
        first_read, first_write = os.pipe()
        other_read, other_write = os.pipe()
        for fd in (first_read, first_write, other_read, other_write):
            self.addCleanup(os.close, fd)
        os.set_blocking(first_read, False)
        os.set_blocking(other_read, False)
        monitor.read_once(first_read, now_ns=NOW)
        monitor.read_once(other_read, now_ns=NOW)
        self.assertEqual(monitor.inspect(observation(bound), now_ns=NOW).reason, "PIPE_CHANGED")
        for clock in (NOW - 1, True):
            monitor = s.QueryMonitor(bound)
            self.complete(monitor)
            result = monitor.inspect(observation(bound, observed_ns=clock), now_ns=clock)
            self.assertEqual(result.reason, "CLOCK_UNCERTAIN")
            self.assertFalse(result.query_stopped)


if __name__ == "__main__":
    unittest.main()

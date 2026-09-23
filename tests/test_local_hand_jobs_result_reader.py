"""Bounded IPC and real local-file races; kernel supervision is simulated.

These tests do not establish a working production cgroup or NAS environment.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs import bootstrap, budget, result_reader, runner
from local_hand_jobs.contract import JobError
from test_local_hand_jobs_runner import admitted_bootstrap_plan, budgeted_plan


class ResultReaderTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        roots = {name: str(self.root / name) for name in ("work", "evidence", "temporary")}
        plan = budgeted_plan({"phase": "preflight", "execution": {"kind": "host.inspect",
            "roots": roots, "writable": list(roots.values()), "readonly": []}})
        self.stack.enter_context(admitted_bootstrap_plan(plan, self.root))
        grant = plan["budget_grant"]
        self.execution_id = grant["execution_id"]
        helper_unit = "lhj-" + hashlib.sha256(self.execution_id.encode()).hexdigest() + ".service"
        self.helper = {"unit": helper_unit, "boot_id": grant["boot_id"], "invocation_id": "a" * 32,
                       "cgroup": "/fixture.slice/" + helper_unit, "exit_code": 0}
        self.reader_unit = result_reader.unit_name(self.execution_id)
        self.reader = {"unit": self.reader_unit, "boot_id": grant["boot_id"], "invocation_id": "b" * 32,
                       "cgroup": "/fixture.slice/" + self.reader_unit}
        self.payload = {"execution_id": self.execution_id, "phase": "preflight", "operation_id": "fixture",
            "budget_grant": grant, "budgets": grant["limits"], "supervision_version": 3,
            "bootstrap_allocation": plan["bootstrap_allocation"], "parent_mount_namespace": "parent-namespace",
            "phase_deadline_boottime_ns": budget.phase_deadline_ns(grant) - budget.NANOSECONDS,
            "runtime_cap_us": 20 * 1000 * 1000, "reader_unit": self.reader_unit, "unit": self.reader_unit,
            "helper_identity": self.helper, "result_name": result_reader.result_name(self.execution_id)}
        self.value = {"execution_id": self.execution_id, "phase": "preflight", "outcome": "SUCCEEDED",
            "effects_checked": True, "facts": {"elapsed_seconds": 1.25}, "helper_started": True,
            "prepared": {"files": {"runtime/file": "a" * 64}}, "seal_record": {"format": "fixture"}}
        self.path = Path(self.payload["bootstrap_allocation"]["roots"]["evidence"]) / self.payload["result_name"]
        self.path.write_bytes(json.dumps(self.value).encode())

    def parser(self):
        return result_reader.PipeReader(self.execution_id, "preflight", self.reader_unit, self.helper)

    def frames(self, *, value=None):
        ready = {"version": 1, "type": "READY", "execution_id": self.execution_id, "phase": "preflight",
                 "reader_identity": self.reader, "helper_identity": self.helper}
        result = {**ready, "type": "RESULT", "result": self.value if value is None else value}
        return ready, result

    def wire(self, *, value=None):
        return b"".join(result_reader._frame_bytes(frame) for frame in self.frames(value=value))

    def collect(self):
        return result_reader._read_result(self.payload, self.payload["bootstrap_allocation"],
            (self.payload["budget_grant"], self.payload["phase_deadline_boottime_ns"]))

    @contextlib.contextmanager
    def simulated_host(self):
        output = io.BytesIO()
        with mock.patch.object(result_reader.sys, "stdout", mock.Mock(buffer=output)), \
             mock.patch.object(result_reader.os, "readlink", return_value="child-namespace"), \
             mock.patch.object(result_reader.os, "access", return_value=False), \
             mock.patch.object(runner, "_mount_for", return_value={"options": "ro"}), \
             mock.patch.object(runner, "_verify_cgroup_limits", return_value={"cgroup": self.reader["cgroup"]}) as verify, \
             mock.patch.dict(os.environ, {"INVOCATION_ID": self.reader["invocation_id"]}):
            yield output, verify

    def test_split_frames_require_independent_identity_and_finish_without_parent_storage(self):
        wire = self.wire()
        with mock.patch.object(os, "open", side_effect=AssertionError("parent storage open")), \
             mock.patch.object(os, "stat", side_effect=AssertionError("parent storage stat")), \
             mock.patch.object(Path, "read_bytes", side_effect=AssertionError("parent storage read")):
            parser = self.parser()
            parser.bind_reader({key: value for key, value in self.reader.items() if key != "unit"})
            for offset in range(0, len(wire), 7):
                parser.feed(wire[offset:offset + 7])
                self.assertIsNone(parser.result)
            self.assertTrue(parser.ready)
            self.assertTrue(parser.complete)
            parser.finish()
            self.assertEqual(self.value, parser.result)
            # Callers cannot mutate a retained verified result through aliases.
            parser.result["facts"].clear()
            self.assertEqual(1.25, parser.result["facts"]["elapsed_seconds"])

    def test_extra_truncated_out_of_order_and_oversized_frames_fail_permanently(self):
        ready, result = map(result_reader._frame_bytes, self.frames())
        for raw in (b"", ready[:3], ready, ready + result[:-1], result,
                    ready + result + b"x", ready + result + ready,
                    struct.pack("!I", result_reader.MAX_READY_BYTES + 1),
                    ready + struct.pack("!I", result_reader.MAX_FRAME_BYTES + 1)):
            with self.subTest(length=len(raw)):
                parser = self.parser()
                parser.bind_reader(self.reader)
                with self.assertRaises(JobError):
                    parser.feed(raw)
                    parser.finish()
                self.assertIsNone(parser.result)
                with self.assertRaises(JobError): parser.feed(self.wire())
        parser = self.parser()
        with self.assertRaises(JobError): parser.feed(b"x" * (result_reader.MAX_TRANSPORT_BYTES + 1))
        self.assertEqual(0, len(parser._buffer))
        # Frame-header allowance cannot be spent on an oversized result body.
        parser = self.parser()
        value = {**self.value, "extra": "x" * result_reader.MAX_RESULT_BYTES}
        with self.assertRaises(JobError): parser.feed(self.wire(value=value))

    def test_result_and_both_invocation_identities_are_bound(self):
        mutations = [lambda r, v: r.update(execution_id="another"),
            lambda r, v: r.update(phase="business"), lambda r, v: r.update(version=True),
            lambda r, v: r["helper_identity"].update(invocation_id="c" * 32),
            lambda r, v: r["helper_identity"].update(exit_code=False),
            lambda r, v: r["reader_identity"].update(invocation_id="c" * 32),
            lambda r, v: v["result"].update(phase="business"),
            lambda r, v: v["result"].update(execution_id="another"),
            lambda r, v: v["reader_identity"].update(invocation_id="d" * 32)]
        for mutate in mutations:
            ready, result = copy.deepcopy(self.frames())
            mutate(ready, result)
            parser = self.parser()
            parser.bind_reader(self.reader)
            with self.assertRaises(JobError):
                parser.feed(result_reader._frame_bytes(ready) + result_reader._frame_bytes(result))
                parser.finish()
        parser = self.parser()
        parser.feed(self.wire())
        with self.assertRaises(JobError): parser.finish()
        parser = self.parser()
        parser.feed(self.wire())
        with self.assertRaises(JobError): parser.bind_reader({**self.reader, "invocation_id": "e" * 32})

    def test_strict_result_json_preserves_large_metadata_and_floats(self):
        value = {**self.value, "metadata": "有效元数据" * 10000, "stages": [{"elapsed_seconds": 0.0125}]}
        raw = json.dumps(value, ensure_ascii=False).encode()
        self.assertGreater(len(raw), 65536)
        self.path.write_bytes(raw)
        self.assertEqual(value, self.collect())
        parser = self.parser()
        parser.feed(self.wire(value=value))
        parser.bind_reader(self.reader)
        parser.finish()
        self.assertEqual(value, parser.result)

    def test_strict_json_rejects_duplicates_nonfinite_unicode_depth_and_nodes(self):
        raw_cases = (b'{"a":1,"a":2}', b'{"nested":{"a":1,"a":2}}', b'{"a":NaN}',
            b'{"a":Infinity}', b'{"a":-Infinity}', b'{"a":1e1000}', b'{"a":"\\ud800"}',
            b'{"a":"\xff"}', b'{} {}', b'[' * 66 + b'0' + b']' * 66)
        for raw in raw_cases:
            with self.subTest(raw=raw[:50]), self.assertRaises(JobError):
                result_reader._strict_json(raw, result_reader.MAX_RESULT_BYTES)
        with mock.patch.object(result_reader, "MAX_JSON_NODES", 5), self.assertRaises(JobError):
            result_reader._strict_json(b'[1,2,3,4,5]', 1024)

    def test_payload_rejects_free_paths_commands_identity_and_deadline_extensions(self):
        valid = bootstrap.decode_payload(bootstrap.encode_payload(self.payload))
        result_reader._validate_payload(valid)
        changes = ({"result_name": "../result.json"}, {"result_path": str(self.path)},
            {"command": ["anything"]}, {"supervision_version": 2}, {"unit": self.helper["unit"]},
            {"phase_deadline_boottime_ns": self.payload["phase_deadline_boottime_ns"] + 1},
            {"runtime_cap_us": 100000000000}, {"helper_identity": {**self.helper, "boot_id": "0" * 36}})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(JobError):
                result_reader._validate_payload({**self.payload, **change})
        with self.assertRaises(JobError):
            result_reader._validate_payload({**self.payload, "parent_mount_namespace": "n" * 65536})

    def test_child_emits_ready_only_after_real_supervision_checks_and_result_after_read(self):
        with self.simulated_host() as (output, verify):
            self.assertEqual(0, result_reader.run(self.payload))
            self.assertEqual(3, verify.call_args.args[0]["budgets"]["cpu_seconds"])
        parser = self.parser()
        parser.feed(output.getvalue())
        parser.bind_reader(self.reader)
        parser.finish()
        self.assertEqual(self.value, parser.result)

    def test_child_namespace_cgroup_invocation_and_expiry_fail_before_task_storage(self):
        for failure in ("namespace", "cgroup", "invocation", "deadline", "boot"):
            with self.subTest(failure=failure), self.simulated_host() as (output, verify), \
                 mock.patch.object(result_reader, "_read_result") as read:
                with contextlib.ExitStack() as stack:
                    if failure == "namespace":
                        stack.enter_context(mock.patch.object(os, "readlink", return_value="parent-namespace"))
                    elif failure == "cgroup": verify.side_effect = JobError("IO_UNCERTAIN", "not isolated")
                    elif failure == "invocation": stack.enter_context(mock.patch.dict(os.environ, {"INVOCATION_ID": ""}))
                    elif failure == "deadline":
                        stack.enter_context(mock.patch.object(budget, "current_clock", return_value={
                            "boot_id": self.helper["boot_id"], "boottime_ns": self.payload["phase_deadline_boottime_ns"]}))
                    else:
                        stack.enter_context(mock.patch.object(budget, "current_clock", return_value={
                            "boot_id": "00000000-0000-0000-0000-000000000000",
                            "boottime_ns": self.payload["budget_grant"]["reserved_boottime_ns"]}))
                    with self.assertRaises(JobError): result_reader.run(self.payload)
                read.assert_not_called()
                self.assertEqual(b"", output.getvalue())

    def test_child_read_failure_keeps_ready_but_never_emits_success(self):
        self.path.unlink()
        with self.simulated_host() as (output, verify), self.assertRaises(FileNotFoundError):
            result_reader.run(self.payload)
        parser = self.parser()
        parser.feed(output.getvalue())
        self.assertTrue(parser.ready)
        self.assertFalse(parser.complete)
        parser.bind_reader(self.reader)
        with self.assertRaises(JobError): parser.finish()

    def test_root_binding_replacement_and_result_links_are_rejected(self):
        root = self.path.parent
        old = root.with_name("original-evidence")
        root.rename(old)
        root.mkdir(mode=0o700)
        with self.assertRaises(JobError): self.collect()
        root.rmdir()
        old.rename(root)
        target = self.path.with_name("link-target")
        self.path.rename(target)
        self.path.symlink_to(target)
        with self.assertRaises(OSError): self.collect()
        self.path.unlink()
        os.link(target, self.path)
        with self.assertRaises(JobError): self.collect()
        self.path.unlink()
        os.mkfifo(self.path, 0o600)
        with self.assertRaises(JobError): self.collect()

    def test_same_inode_same_size_rewrite_and_name_replacement_during_read_are_rejected(self):
        raw = self.path.read_bytes()
        for mutation in ("same_inode", "replace_file", "replace_root"):
            with self.subTest(mutation=mutation):
                fired = False
                real_read = os.read
                def read(descriptor, maximum):
                    nonlocal fired
                    data = real_read(descriptor, maximum)
                    if not fired:
                        fired = True
                        if mutation == "same_inode":
                            self.path.write_bytes(raw.replace(b"SUCCEEDED", b"CANCELLED"))
                        elif mutation == "replace_file":
                            replacement = self.path.with_name("replacement")
                            replacement.write_bytes(raw)
                            os.replace(replacement, self.path)
                        else:
                            self.path.parent.rename(self.root / "saved-evidence")
                            self.path.parent.mkdir(mode=0o700)
                    return data
                with mock.patch.object(os, "read", side_effect=read), self.assertRaises(JobError): self.collect()
                if mutation == "replace_root":
                    self.path.parent.rmdir()
                    (self.root / "saved-evidence").rename(self.path.parent)
                self.path.write_bytes(raw)

    def test_os_read_overflow_and_declared_size_limit_are_both_rejected(self):
        real_read = os.read
        extended = False
        def growing_read(descriptor, maximum):
            nonlocal extended
            data = real_read(descriptor, maximum)
            if not extended:
                extended = True
                with self.path.open("ab") as stream:
                    stream.write(b"x" * result_reader.MAX_RESULT_BYTES)
            return data
        with mock.patch.object(os, "read", side_effect=growing_read), \
             self.assertRaisesRegex(JobError, "exceeds its fixed byte bound"):
            self.collect()
        self.path.write_bytes(b"x" * (result_reader.MAX_RESULT_BYTES + 1))
        with mock.patch.object(os, "read") as read, self.assertRaises(JobError): self.collect()
        read.assert_not_called()

    def test_deadline_is_checked_again_after_blocked_read_returns(self):
        real_read = os.read
        expired = False
        def read(descriptor, maximum):
            nonlocal expired
            data = real_read(descriptor, maximum)
            expired = True
            return data
        real_clock = budget.current_clock
        def clock():
            return ({"boot_id": self.helper["boot_id"], "boottime_ns": self.payload["phase_deadline_boottime_ns"]}
                    if expired else real_clock())
        with mock.patch.object(os, "read", side_effect=read), mock.patch.object(budget, "current_clock", side_effect=clock), \
             self.assertRaises(JobError): self.collect()


if __name__ == "__main__":
    unittest.main()

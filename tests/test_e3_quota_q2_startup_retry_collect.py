"""Real local files/pipes with explicitly modeled historical/systemd facts.

These tests cannot grant guest, original-stop, or Q2 acceptance evidence.
"""
import base64
import copy
import errno
import gzip
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from e3_host import q2_startup_retry_collect as c
from e3_host import q2_startup_retry_delivery as d


class Windows(unittest.TestCase):
    boot = "12345678-1234-1234-1234-123456789abc"

    def window(self):
        anchor = d.make_clock_anchor(host_issued_ns=100*d.NS, host_deadline_ns=400*d.NS,
            host_probe_send_ns=103*d.NS, host_probe_receive_ns=107*d.NS,
            guest_boot_id=self.boot, guest_sample_ns=900*d.NS, expected_boot_id=self.boot)
        envelope = d.guest_envelope(anchor, attempt_id="startup01", guest_boot_id=self.boot, guest_now_ns=901*d.NS)
        return anchor, envelope, d.sha(d.encoded(anchor))

    def test_exact_new_window_accepts_collection_after_preparation_not_after_outer_bound(self):
        anchor, envelope, digest = self.window()
        for given in (None, anchor):
            self.assertEqual(1189*d.NS, c.fixed_envelope(given, envelope, "startup01", boot_id=self.boot,
                now_ns=1173*d.NS, anchor_sha256=digest))
            for now in (1189*d.NS, 1192*d.NS):
                with self.assertRaisesRegex(ValueError, "WINDOW_EXPIRED"):
                    c.fixed_envelope(given, envelope, "startup01", boot_id=self.boot, now_ns=now, anchor_sha256=digest)

    def test_old_schema_other_attempt_unknown_field_or_refreshed_window_rejected(self):
        anchor, envelope, digest = self.window()
        for field, value in (("schema", "local-hand-q2-cpuquota-retry-delivery/v1"),
                ("attempt_id", "other01"), ("boot_id", "87654321-1234-1234-1234-123456789abc"),
                ("extra", True), ("guest_outer_deadline_ns", envelope["guest_outer_deadline_ns"]+d.NS),
                ("preparation_deadline_ns", envelope["preparation_deadline_ns"]+d.NS),
                ("deadline_ns", envelope["deadline_ns"]+d.NS), ("stop_ns", 4*d.NS)):
            changed = dict(envelope); changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                c.fixed_envelope(anchor, changed, "startup01", boot_id=self.boot, now_ns=1173*d.NS,
                                 anchor_sha256=digest)
        with self.assertRaisesRegex(ValueError, "ANCHOR_DIGEST"):
            c.fixed_envelope(None, envelope, "startup01", boot_id=self.boot, now_ns=1173*d.NS, anchor_sha256="f"*64)

    def test_no_argument_and_nonlinux_entry_block_before_clock_reader_or_contract(self):
        arguments = [[], ["--retry", "unused", "--sha256", "0"*64, "--clock-anchor-sha256", "0"*64,
                          "--delivery-envelope", "unused", "--delivery-sha256", "0"*64]]
        for argv in arguments:
            with self.subTest(argv=argv), patch.object(c.sys, "platform", "win32"), \
                    patch.object(c.time, "clock_gettime_ns", side_effect=AssertionError("clock used"), create=True) as clock, \
                    patch.object(c, "Reader", side_effect=AssertionError("reader used")) as reader, \
                    patch.object(c, "helper", side_effect=AssertionError("helper used")) as helper, \
                    patch.object(c.sys, "stdout", new_callable=io.StringIO) as out:
                self.assertEqual(3, c.main(argv))
                self.assertFalse(json.loads(out.getvalue())["q2_accepted"])
                clock.assert_not_called(); reader.assert_not_called(); helper.assert_not_called()


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux protected noatime files")
class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.guard = lambda: None
        self.reader = c.Reader(self.guard, uids=(os.geteuid(),), root=str(self.root)); self.addCleanup(self.reader.close)

    def write(self, name, raw):
        path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw); path.chmod(0o600); return path

    def fixture(self):
        directories = {role:dict(path=str(self.root/("new-"+role))) for role in
                       ("reservation", "authority", "state", "capture", "declarations", "journal")}
        for pin in directories.values(): Path(pin["path"]).mkdir(mode=0o700)
        retry = dict(attempt_id="startup01", source={"commit":"a"*40}, candidate={"commit":"b"*40},
                     directories=directories, predecessors=[{"kind":"CPUQUOTA_PARSE_BEFORE_CHILD"},
                     {"kind":"SUPERVISOR_STARTED_PERMISSION_FAILURE"}])
        attestation = dict(predecessors=[], ledgers=[dict(sha256="a"*64), dict(sha256="b"*64)],
            unused_ledgers=True, unused_roots=True, roots=[], old_snapshots=[], q1_snapshot=[], historical_units=[],
            reservations=[], original_files_preserved=True)
        receipt = dict(schema=c.RECEIPT_SCHEMA, status="STARTUP_RETRY_RESOURCES_PREPARED",
            attempt_id=retry["attempt_id"], retry_sha256=c.sha(c.encoded(retry)), plan_sha256="c"*64, q2_accepted=False,
            q3_accepted=False, production_supported=False, fixture_generated=False, facts={},
            delivery_envelope={}, delivery_sha256=c.sha(c.encoded({})), clock_anchor_sha256=None,
            retry=dict(directory={}, original_files_preserved=True,
                attestation=attestation, attestation_sha256=c.sha(c.encoded(attestation))))
        path = Path(directories["reservation"]["path"])/c.RECEIPT_NAME
        path.write_bytes(c.encoded(receipt)); path.chmod(0o600)
        delivery = path.with_name("delivery-envelope.json"); delivery.write_bytes(c.encoded({})); delivery.chmod(0o600)
        quota = self.root/"quota"; quota.mkdir(mode=0o700)
        return retry, dict(roots=[dict(path=str(quota), project_id=123)], parents={}), receipt, path

    def collect(self, retry, original, *, preservation=None, runtime=None):
        preservation = preservation or (lambda *args, **kwargs: dict.fromkeys(c.PRESERVATION_FLAGS, True))
        runtime = runtime or (lambda *args: dict(parent_trees_empty=True, new_runtime_services_stopped=True))
        return c.collect(retry, original, {}, None, plan_sha256="c"*64, guard=self.guard, reader=self.reader, deadline_ns=1,
                         runtime_observer=runtime, preservation_observer=preservation)

    def test_actual_bytes_atime_and_input_verdicts_unchanged_with_modeled_preservation(self):
        retry, original, receipt, path = self.fixture()
        old = self.write("old/verdict.json", b'{"status":"INCOMPLETE","sealed":false}\n')
        new = self.write("new-capture/result.json", b'{"status":"INCOMPLETE","reason":"PermissionError"}\n')
        for name in (old, new, new.parent): os.utime(name, ns=(10**9, 2*10**9))
        before = {name:name.stat() for name in (old, new, new.parent)}
        value = self.collect(retry, original)
        self.assertTrue(value["complete"]); self.assertFalse(value["q2_accepted"])
        for name, info in before.items():
            self.assertEqual(info, name.stat()); self.assertEqual(info.st_atime_ns, name.stat().st_atime_ns)
        report = c.bundle_report(value, output_limit=65536)
        self.assertEqual("COLLECTED", report["status"])
        self.assertFalse(report["original_eof_proven"]); self.assertFalse(report["remote_stop_proven"])
        raw = gzip.decompress(base64.b64decode(report["bundle"]["data"], validate=True))
        self.assertEqual(c.sha(raw), report["bundle"]["raw_sha256"])
        self.assertEqual("INCOMPLETE", json.loads(base64.b64decode(next(row for row in json.loads(raw)["files"]
            if row.get("path") == str(new))["content_base64"]))["status"])

    def test_backend_cannot_overwrite_scope_or_acceptance_and_roots_need_not_remain_empty(self):
        retry, original, _, _ = self.fixture()
        self.write("quota/current-operation.txt", b"new run output")
        retained = dict.fromkeys(c.PRESERVATION_FLAGS, True)
        retained.update(scope="OTHER", complete=True, q2_accepted=True)
        observer = Mock(return_value=retained)
        value = self.collect(retry, original, preservation=observer)
        self.assertTrue(value["complete"]); self.assertEqual(c.SCOPE, value["scope"]); self.assertFalse(value["q2_accepted"])
        self.assertEqual(["current-operation.txt"], value["roots"][0]["members"])
        observer.assert_called_once(); self.assertNotIn("unused", value["roots"][0])
        self.assertEqual(dict(guard=self.guard, deadline_ns=1), observer.call_args.kwargs)

    def test_each_historical_preservation_failure_prevents_complete_collection(self):
        retry, original, _, _ = self.fixture()
        for flag in c.PRESERVATION_FLAGS:
            with self.subTest(flag=flag):
                retained = dict.fromkeys(c.PRESERVATION_FLAGS, True); retained[flag] = False
                value = self.collect(retry, original, preservation=lambda *a, **k:retained)
                self.assertFalse(value["complete"]); self.assertEqual("INCOMPLETE", c.bundle_report(value, output_limit=65536)["status"])

    def test_wrong_receipt_schema_plan_digest_or_missing_second_ledger_never_calls_backend(self):
        retry, original, receipt, path = self.fixture()
        for case in ("schema", "plan", "bound_plan", "attempt", "ledgers", "attestation", "acceptance", "unknown"):
            changed = copy.deepcopy(receipt)
            if case == "schema": changed["schema"] = "local-hand-q2-cpuquota-retry-preparation/v1"
            elif case == "plan": changed["retry_sha256"] = "f"*64
            elif case == "bound_plan": changed["plan_sha256"] = "f"*64
            elif case == "attempt": changed["attempt_id"] = "other01"
            elif case == "acceptance": changed["q2_accepted"] = True
            elif case == "unknown": changed["unrecognized"] = True
            else:
                changed["retry"]["attestation"]["ledgers"].pop()
                if case == "ledgers": changed["retry"]["attestation_sha256"] = c.sha(c.encoded(changed["retry"]["attestation"]))
            path.write_bytes(c.encoded(changed))
            reader = c.Reader(self.guard, uids=(os.geteuid(),), root=str(self.root))
            try:
                backend = Mock(side_effect=AssertionError("backend must not run"))
                value = c.collect(retry, original, {}, None, plan_sha256="c"*64, guard=self.guard, reader=reader, deadline_ns=1,
                    runtime_observer=lambda *args:{}, preservation_observer=backend)
                self.assertFalse(value["complete"]); backend.assert_not_called()
            finally: reader.close()

    def test_another_window_or_missing_original_delivery_cannot_recollect_as_complete(self):
        retry, original, receipt, path = self.fixture()
        for mode in ("changed", "missing"):
            changed = copy.deepcopy(receipt)
            if mode == "changed": changed["delivery_envelope"] = {"different_window":True}
            else: changed.pop("delivery_sha256")
            path.write_bytes(c.encoded(changed))
            reader = c.Reader(self.guard, uids=(os.geteuid(),), root=str(self.root))
            try:
                backend = Mock()
                value = c.collect(retry, original, {}, None, plan_sha256="c"*64, guard=self.guard, reader=reader, deadline_ns=1,
                    runtime_observer=lambda *args:{}, preservation_observer=backend)
                self.assertFalse(value["complete"]); backend.assert_not_called()
                self.assertEqual("INCOMPLETE", c.bundle_report(value, output_limit=65536)["status"])
            finally: reader.close()

    def test_read_rejects_special_files_permissions_aliases_and_detects_replacement(self):
        original = self.write("evidence/result.json", b"retained")
        for kind in ("symlink", "hardlink", "fifo", "writable"):
            target = self.root/kind
            if kind == "symlink": target.symlink_to(original)
            elif kind == "hardlink": os.link(original, target)
            elif kind == "fifo": os.mkfifo(target)
            else: target.write_bytes(b"bad"); target.chmod(0o666)
            with self.subTest(kind=kind), self.assertRaises((OSError, ValueError)): self.reader.read(str(target))
            target.unlink()
        self.reader.read(str(original)); original.rename(original.with_suffix(".old")); original.write_bytes(b"retained")
        with self.assertRaisesRegex(ValueError, "CHANGED"): self.reader.stable()

    def test_final_noatime_denial_never_falls_back_to_read(self):
        path = self.write("evidence/result.json", b"retained"); original = os.open
        def opened(name, flags, **kwargs):
            if name == path.name:
                self.assertTrue(flags & os.O_NOATIME); raise PermissionError(errno.EPERM, "private secret path")
            self.assertFalse(flags & os.O_NOATIME); return original(name, flags, **kwargs)
        with patch.object(c.os, "open", side_effect=opened) as calls, patch.object(c.os, "read") as read:
            with self.assertRaises(PermissionError): self.reader.read(str(path))
            self.assertEqual(1, sum(call.args[0] == path.name for call in calls.call_args_list)); read.assert_not_called()

    def test_oversize_new_receipt_and_regular_file_respect_separate_bounds(self):
        self.write("evidence/"+c.RECEIPT_NAME, b"x"*(c.io.FILE_LIMIT+1))
        self.assertEqual(2, len(self.reader.tree(str(self.root/"evidence"))))
        self.write("other/regular.json", b"x"*(c.io.FILE_LIMIT+1))
        with self.assertRaisesRegex(ValueError, "FILE_LIMIT"): self.reader.tree(str(self.root/"other"))


class Reports(unittest.TestCase):
    def test_output_bound_marks_omission_never_truncates_or_mutates_input(self):
        raw = os.urandom(100000)
        value = dict(complete=True, attempt_id="startup01", files=[dict(path="/synthetic/result", kind="file",
            sha256=c.sha(raw), content_base64=base64.b64encode(raw).decode())])
        before = copy.deepcopy(value); report = c.bundle_report(value, output_limit=16384)
        self.assertEqual(before, value); self.assertLessEqual(len(c.encoded(report)), 16384)
        self.assertEqual("INCOMPLETE", report["status"]); self.assertFalse(report["q2_accepted"])
        retained = json.loads(gzip.decompress(base64.b64decode(report["bundle"]["data"])))
        self.assertEqual(c.sha(raw), retained["files"][0]["sha256"])
        self.assertEqual("WIRE_OUTPUT_LIMIT", retained["files"][0]["content_omitted"])

    def test_error_reason_omits_arbitrary_messages_paths_and_input(self):
        self.assertEqual("PermissionError", c.failure(PermissionError(errno.EACCES, "private secret", "/private/node")))
        self.assertEqual("ValueError", c.failure(ValueError("private secret")))
        self.assertEqual("COLLECT_SOURCE_CHANGED", c.failure(ValueError("COLLECT_SOURCE_CHANGED")))
        record = c.error_record("historical-preservation", PermissionError(errno.EACCES, "private secret", "/private/node"))
        self.assertEqual(errno.EACCES, record["errno"])
        self.assertNotIn("private", c.encoded(record).decode())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux bounded real pipe capture")
    def test_nonzero_read_client_exit_and_both_eofs_are_complete_failure_capture(self):
        end = time.clock_gettime_ns(time.CLOCK_BOOTTIME)+3*d.NS
        value = c.command([sys.executable, "-I", "-B", "-c", "import os;os.write(2,b'failure');os._exit(3)"],
                          guard=lambda:None, deadline_ns=end)
        self.assertTrue(value["complete"]); self.assertEqual(3, value["returncode"])
        self.assertEqual(["stderr", "stdout"], value["eof"])
        self.assertEqual(b"failure", base64.b64decode(value["stderr_base64"]))


if __name__ == "__main__": unittest.main()

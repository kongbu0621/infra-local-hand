"""Read-only collector contracts over protected real temporary files.

Owner/runtime documents are synthetic; these checks establish neither live
supervision nor guest acceptance. No test calls a preparation/effect API.
"""
import base64
import copy
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from e3_host import q2_reconciliation_collect as r
from e3_host import q2_reconciliation_delivery as delivery
from e3_host import q2_reconciliation_records as records


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux protected no-atime files")
class ProtectedCollection(unittest.TestCase):
    def setUp(self):
        home = Path.home()
        if any(os.stat(path).st_mode & 0o022 for path in (home, *home.parents)):
            self.skipTest("No protected local temporary parent")
        self.tmp = tempfile.TemporaryDirectory(prefix="q2-collect-test-", dir=home)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.reader = r.Reader(lambda: None)
        self.addCleanup(self.reader.close)

    def file(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        raw = value if isinstance(value, bytes) else r.encoded(value)
        path.write_bytes(raw); path.chmod(0o600)
        return path

    def test_read_retains_metadata_atime_and_rechecks_actual_bytes(self):
        path = self.file("evidence/item.json", {"a": 1})
        before = r.io.metadata(path.stat())
        self.assertEqual(r.encoded({"a": 1}), self.reader.read(str(path)))
        self.reader.stable()
        self.assertEqual(before, r.io.metadata(path.stat()))
        path.write_bytes(r.encoded({"a": 2}))
        with self.assertRaises(ValueError): self.reader.stable()

    def test_directory_member_change_and_path_replacement_are_rejected(self):
        path = self.file("evidence/item.json", {"a": 1})
        self.reader.tree(str(path.parent))
        self.file("evidence/extra", b"extra")
        with self.assertRaises(ValueError): self.reader.stable()
        other = r.Reader(lambda: None)
        try:
            other.read(str(path)); path.rename(path.with_name("retained"))
            path.symlink_to(path.with_name("retained"))
            with self.assertRaises(ValueError): other.stable()
        finally: other.close()

    def test_total_budget_hardlink_and_symlink_refuse_without_fallback(self):
        path = self.file("plain", b"bytes")
        small = r.Reader(lambda: None, max_raw=4)
        try:
            with self.assertRaisesRegex(ValueError, "COLLECT_TOTAL_LIMIT"): small.read(str(path))
        finally: small.close()
        path.with_name("alias").symlink_to(path)
        with self.assertRaises(OSError): self.reader.read(str(path.with_name("alias")))
        os.link(path, path.with_name("hardlink"))
        with self.assertRaises(ValueError): self.reader.read(str(path))

    def fixture(self):
        from test_e3_quota_q2_prepare_run import plan as owner_fixture
        owner = owner_fixture()
        envelope = dict(boot_id=owner["boot_id"], issued_ns=1, deadline_ns=130*r.NS,
            clock_anchor_sha256="c"*64)
        directories = {}
        for role in ("reservation", "authority", "state", "capture", "declarations", "journal"):
            path = self.root / role; path.mkdir(mode=0o700)
            directories[role] = dict(path=str(path))
        for role, parent, name in (("output", "capture", "owner_output"),
                ("declarations", "declarations", "owner_declarations")):
            path = self.root / parent / name; path.mkdir(mode=0o700)
            info = path.stat()
            owner[role] = dict(path=str(path), device=info.st_dev, inode=info.st_ino)
        candidate = dict(commit="b"*40, tree="e"*40, wheel_sha256="f"*64)
        runtime_source = dict(commit=candidate["commit"], tree=candidate["tree"], files={})
        owner["template"]["launcher"]["source"] = {key: runtime_source[key] for key in ("commit", "files")}
        owner["template"]["launcher"]["assembly"]["installation"]["source_commit"] = candidate["commit"]
        execution = dict(attempt_id="collect01", directories=directories, source=dict(commit="d"*40,
            tree="a"*40, files={}), scope=r.SCOPE, rule="1"*40, baseline="2"*40,
            closure="3"*40, owner_decision={"event": "synthetic"})
        plan = dict(directories=directories, candidate=candidate,
            settings=dict(identity=dict(id=owner["preparation_id"])))
        verified = SimpleNamespace(execution=execution, plan=plan, source_classes={},
            digest="4"*64, implementation_commit="d"*40)
        docs = {name: records.encoded(dict(synthetic=name)) for name in records.DOCUMENT_NAMES}
        seal, _ = records.make_seal(docs)
        attest = {key: [] for key in r.legacy.ATTESTATION_FIELDS}
        attest.update(unused_ledgers=True, unused_roots=True, original_files_preserved=True,
            ledgers=[{}, {}], reconciliation=dict(seal=seal, source_classes={},
                historical_atime_preservation_proven=False))
        folder = self.root / "reservation"; info = folder.stat()
        receipt = dict(schema=r.legacy.RECEIPT_SCHEMA, status="STARTUP_RETRY_RESOURCES_PREPARED",
            attempt_id=execution["attempt_id"], retry_sha256=r.sha(r.encoded(execution)),
            plan_sha256=r.sha(r.encoded(plan)), facts=dict(installation=dict(source=runtime_source)),
            retry=dict(directory=dict(path=str(folder),
                device=info.st_dev, inode=info.st_ino), attestation=attest,
                attestation_sha256=r.sha(r.encoded(attest)), original_files_preserved=True),
            q2_accepted=False, q3_accepted=False, production_supported=False, fixture_generated=False,
            delivery_envelope=envelope, delivery_sha256=r.sha(r.encoded(envelope)),
            clock_anchor_sha256=envelope["clock_anchor_sha256"])
        self.file("reservation/" + r.legacy.RECEIPT_NAME, receipt)
        prepared = dict(schema="local-hand-q2-supervisor-startup-retry-driver-result/v1",
            status="STARTUP_RETRY_PREPARED", attempt_id=execution["attempt_id"],
            source_commit=candidate["commit"],
            retry_receipt_sha256=r.sha(r.encoded(receipt)), orchestration_source=execution["source"],
            runtime_candidate=candidate, delivery_sha256=r.sha(r.encoded(envelope)),
            clock_anchor_sha256=envelope["clock_anchor_sha256"], q2_accepted=False,
            q3_accepted=False, production_supported=False,
            **{key: execution[key] for key in ("scope", "rule", "baseline", "closure", "owner_decision")})
        self.file("reservation/prepared.json", prepared)
        self.file("reservation/handoff.json", owner)
        fixture = copy.deepcopy(owner["template"])
        for env in (fixture["supervisor_envelope"], fixture["launcher"]["controller_envelope"]):
            env.update(issued_ns=2*r.NS, deadline_ns=2*r.NS + env["controller"]["runtime_max_usec"]*1000)
        issued = dict(schema="local-hand-q2-issued-handoff/v1", plan=owner, fixture=fixture)
        original = dict(unit="synthetic.service", invocation_id="8"*32, cgroup_device=1, cgroup_inode=2)
        result = dict(schema="local-hand-q2-handoff-result/v1", status="CLOSURE_OBSERVED_SEAL_PENDING",
            sealed=False, original=original, evidence=owner["output"]["path"], stopped=True,
            cleanup_errors=[], owner_self_exit_verified=False, original_management_session_exit_required=True,
            q2_accepted=False, q3_accepted=False, production_supported=False)
        child = dict(schema="local-hand-q2-supervisor-handoff-result/v1",
            envelope_sha256=r.sha(r.encoded(issued)), original=original,
            result=dict(schema="local-hand-q2-supervisor-result/v1", status="CONTROLLER_CLOSED", sealed=True,
                q3_accepted=False, production_supported=False, independent_supervisor_stop_required=True),
            completed_ns=3*r.NS)
        bound_fixture = copy.deepcopy(fixture)
        bound_fixture["supervisor_envelope"]["controller"].update(
            {key: original[key] for key in r.helper("q2_prepare_run").DYNAMIC})
        child["bound_fixture_sha256"] = r.sha(r.encoded(bound_fixture))
        out = {name: {} for name in r.helper("q2_prepare_run").FILES if name != "seal.json"}
        out.update({"reservation.json": dict(schema="local-hand-q2-original-handoff/v1",
                plan_sha256=r.sha(r.encoded(owner)), envelope_sha256=r.sha(r.encoded(issued))),
            "invocation.json": original, "result.json": result, "child-result.json": child,
            "capture.json": dict(schema="local-hand-q2-outer-capture/v1", complete=True, returncode=0,
                eof=["stderr", "stdout"], error=None, close_errors=[], independent_stop_required=True,
                q3_accepted=False, production_supported=False, started_ns=2*r.NS,
                deadline_ns=owner["owner_envelope"]["deadline_ns"]),
            "supervisor.stdout": dict(schema="local-hand-q2-handoff-result/v1",
                status="CONTROLLER_CLOSED", q3_accepted=False, production_supported=False),
            "supervisor.stderr": b""})
        out["capture.json"].update(stdout_sha256=r.sha(r.encoded(out["supervisor.stdout"])),
            stderr_sha256=r.sha(out["supervisor.stderr"]))
        dec = {name: {} for name in r.helper("q2_prepare_run").DECLARATIONS}
        dec.update({"envelope.json": issued, "supervisor-result.json": child,
            "bound-supervisor.json": bound_fixture, "fixture-check.json": dict(
                schema="local-hand-q2-fixture-check/v1", status="CHECKED", scope="READ_ONLY_EXISTING_PREREQUISITES",
                q2_accepted=False, q3_accepted=False, production_supported=False,
                independent_supervisor_stop_required=True, checks=[dict(check="synthetic", status="PASS")])})
        pins = {}
        for role, values in (("output", out), ("declarations", dec)):
            for name, value in values.items():
                relative = str(Path(owner[role]["path"]).relative_to(self.root)) + "/" + name
                path = self.file(relative, value)
                raw = value if isinstance(value, bytes) else r.encoded(value)
                pins[str(path)] = dict(bytes=len(raw), sha256=r.sha(raw))
        owner_seal = dict(schema="local-hand-q2-handoff-seal/v1", status="SUPERVISOR_CLOSED",
            envelope_sha256=r.sha(r.encoded(issued)), original=original, files=pins,
            owner_self_exit_verified=False, original_management_session_exit_required=True,
            q2_accepted=False, q3_accepted=False, production_supported=False)
        self.file("capture/owner_output/seal.json", owner_seal)
        return verified, envelope, receipt, seal, result

    def test_new_receipt_accepts_exact_reconciliation_extension(self):
        verified, envelope, receipt, seal, _ = self.fixture()
        self.assertEqual(receipt, r.checked_receipt(verified, envelope, self.reader, seal))
        self.reader.stable()

    def test_receipt_rejects_legacy_attestation_and_window_renewal(self):
        verified, envelope, receipt, seal, _ = self.fixture()
        changed = dict(envelope, deadline_ns=envelope["deadline_ns"]+1)
        with self.assertRaisesRegex(ValueError, "COLLECT_ORIGINAL_DELIVERY_CHANGED"):
            r.checked_receipt(verified, changed, self.reader, seal)
        different = dict(seal, status="OTHER")
        with self.assertRaisesRegex(ValueError, "COLLECT_RECONCILIATION_RECEIPT"):
            r.checked_receipt(verified, envelope, self.reader, different)

    def test_owner_actual_sealed_bytes_bind_terminal_without_self_exit_claim(self):
        verified, envelope, receipt, _, result = self.fixture()
        proof = r.checked_owner(verified, envelope, receipt, self.reader)
        self.assertEqual(dict(result, status="SUPERVISOR_CLOSED", sealed=True), proof["expected_terminal"])
        self.assertEqual(14, len(proof["sealed_members"]))
        self.assertFalse(proof["expected_terminal"]["owner_self_exit_verified"])
        self.reader.stable()

    def test_owner_rejects_source_or_receipt_substitution(self):
        verified, envelope, receipt, _, _ = self.fixture()
        changed = copy.deepcopy(verified); changed.execution["source"]["tree"] = "9"*40
        with self.assertRaisesRegex(ValueError, "COLLECT_PREPARED_BINDING"):
            r.checked_owner(changed, envelope, receipt, self.reader)
        with self.assertRaisesRegex(ValueError, "COLLECT_PREPARED_BINDING"):
            r.checked_owner(verified, envelope, dict(receipt, facts={"changed": True}), self.reader)

    def test_owner_missing_or_extra_member_rejects_before_terminal_projection(self):
        verified, envelope, receipt, _, _ = self.fixture()
        self.file("capture/owner_output/extra", b"must retain but not accept")
        with self.assertRaisesRegex(ValueError, "COLLECT_OWNER_MEMBERS"):
            r.checked_owner(verified, envelope, receipt, self.reader)

    def test_owner_sealed_member_changed_before_read_rejects_hash(self):
        verified, envelope, receipt, _, _ = self.fixture()
        self.file("capture/owner_output/controls.json", {"forged": True})
        with self.assertRaisesRegex(ValueError, "COLLECT_OWNER_SEAL_BINDING"):
            r.checked_owner(verified, envelope, receipt, self.reader)

    def rewrite_owner_and_seal(self, changes):
        for path, value in changes.items(): self.file(path, value)
        path = self.root / "capture/owner_output/seal.json"
        seal = json.loads(path.read_bytes())
        for name in seal["files"]:
            raw = Path(name).read_bytes()
            seal["files"][name] = dict(bytes=len(raw), sha256=r.sha(raw))
        self.file("capture/owner_output/seal.json", seal)

    def test_resealed_capture_hash_errors_and_original_deadline_are_rejected(self):
        verified, envelope, receipt, _, _ = self.fixture()
        path = "capture/owner_output/capture.json"
        original = json.loads((self.root / path).read_bytes())
        changes = {"stdout_sha256": "0"*64, "stderr_sha256": "0"*64,
            "close_errors": ["stdout"], "deadline_ns": original["deadline_ns"]+1,
            "started_ns": original["deadline_ns"], "independent_stop_required": False}
        for key, value in changes.items():
            with self.subTest(key=key):
                self.rewrite_owner_and_seal({path: dict(original, **{key: value})})
                reader = r.Reader(lambda: None)
                try:
                    with self.assertRaisesRegex(ValueError, "COLLECT_OWNER_CAPTURE_BINDING"):
                        r.checked_owner(verified, envelope, receipt, reader)
                finally: reader.close()

    def test_resealed_child_digest_completion_and_stop_scope_are_rejected(self):
        verified, envelope, receipt, _, _ = self.fixture()
        path = "capture/owner_output/child-result.json"
        original = json.loads((self.root / path).read_bytes())
        mutations = [
            ("COLLECT_OWNER_BOUND_FIXTURE", dict(original, bound_fixture_sha256="0"*64)),
            ("COLLECT_OWNER_CHILD_WINDOW", dict(original, completed_ns=130*r.NS)),
            ("COLLECT_OWNER_CHILD_WINDOW", dict(original, completed_ns=True)),
            ("COLLECT_OWNER_CHILD_BINDING", dict(original,
                result=dict(original["result"], independent_supervisor_stop_required=False))),
            ("COLLECT_OWNER_CHILD_BINDING", dict(original, result=dict(original["result"], q3_accepted=True)))]
        for reason, child in mutations:
            with self.subTest(reason=reason, child=child):
                self.rewrite_owner_and_seal({path: child,
                    "declarations/owner_declarations/supervisor-result.json": child})
                reader = r.Reader(lambda: None)
                try:
                    with self.assertRaisesRegex(ValueError, reason):
                        r.checked_owner(verified, envelope, receipt, reader)
                finally: reader.close()

    def test_resealed_bound_fixture_and_failed_checker_are_rejected(self):
        verified, envelope, receipt, _, _ = self.fixture()
        bound_path = "declarations/owner_declarations/bound-supervisor.json"
        check_path = "declarations/owner_declarations/fixture-check.json"
        bound = json.loads((self.root / bound_path).read_bytes())
        check = json.loads((self.root / check_path).read_bytes())
        changed = copy.deepcopy(bound)
        changed["supervisor_envelope"]["controller"]["cgroup_inode"] += 1
        cases = [("COLLECT_OWNER_BOUND_FIXTURE", {bound_path: changed, check_path: check}),
            ("COLLECT_OWNER_FIXTURE_CHECK", {bound_path: bound, check_path: dict(check, status="BLOCKED")}),
            ("COLLECT_OWNER_FIXTURE_CHECK", {bound_path: bound,
                check_path: dict(check, checks=[dict(check="synthetic", status="BLOCKED")])})]
        for reason, changes in cases:
            with self.subTest(reason=reason):
                self.rewrite_owner_and_seal(changes)
                reader = r.Reader(lambda: None)
                try:
                    with self.assertRaisesRegex(ValueError, reason):
                        r.checked_owner(verified, envelope, receipt, reader)
                finally: reader.close()

    def test_partial_reconciliation_seal_remains_incomplete_and_never_prepares(self):
        verified, envelope, _, _, _ = self.fixture()
        folder = self.root / "reservation.reconciliation"; folder.mkdir(mode=0o700)
        self.file("reservation.reconciliation/evidence-adoption.json", {})
        backend = SimpleNamespace(reconciliation_directory=str(folder))
        value = r.collect(verified, envelope, {}, backend=backend, reader=self.reader, seal_sha256="a"*64)
        self.assertFalse(value["complete"])
        self.assertIn("reconciliation-seal", [error["stage"] for error in value["errors"]])
        self.assertNotIn("owner_proof", value)
        self.assertEqual(["evidence-adoption.json"], os.listdir(folder))

    def test_full_collector_reads_actual_five_file_seal_and_owner_without_effect_api(self):
        verified, envelope, receipt, _, _ = self.fixture()
        folder = str(self.root / "reservation.reconciliation")
        docs = {name: records.encoded(dict(synthetic=name)) for name in records.DOCUMENT_NAMES}
        result = records.write_once(folder, docs, lambda: None)
        # Source semantics and live history belong to their separately tested
        # backend. This local collector fixture exposes ONLY read-only methods.
        backend = SimpleNamespace(reconciliation_directory=folder,
            load_sealed_for_collection=lambda retained: records.verify_sealed(folder, retained, lambda: None),
            collection_preservation=lambda observed: dict(old_bytes_preserved=observed == receipt,
                old_ledgers_preserved=True, historical_results_unchanged=True,
                historical_atime_preservation_proven=False, source_classes={}))
        value = r.collect(verified, envelope, {}, backend=backend, reader=self.reader,
            seal_sha256=r.sha(records.encoded(result["seal"])))
        self.assertTrue(value["complete"], value["errors"])
        self.assertEqual(5, len([row for row in value["files"]
            if row["role"] == "reconciliation" and row["kind"] == "file"]))
        self.assertEqual("SUPERVISOR_CLOSED", value["owner_proof"]["expected_terminal"]["status"])
        self.assertFalse(value["remote_stop_proven"])


class CollectionEnvelopeAndWire(unittest.TestCase):
    def test_expired_window_rejects_before_inputs_read_or_source_verification(self):
        anchor = delivery.legacy.make_clock_anchor(host_issued_ns=100*r.NS, host_deadline_ns=400*r.NS,
            host_probe_send_ns=110*r.NS, host_probe_receive_ns=112*r.NS, guest_sample_ns=1000*r.NS,
            guest_boot_id="12345678-1234-1234-1234-123456789abc", expected_boot_id="12345678-1234-1234-1234-123456789abc")
        envelope = delivery.guest_envelope(anchor, attempt_id="collect01", guest_boot_id=anchor["guest_boot_id"],
            guest_now_ns=1010*r.NS)
        raw = {"/clock": r.encoded(anchor), "/delivery": r.encoded(envelope)}
        observed = []
        def read(path, **_):
            observed.append(path)
            return raw[path]  # Any attempt to read the large input fails this test.
        reader = SimpleNamespace(read=read, close=lambda: None)
        def source(name):
            self.assertEqual("q2_reconciliation_delivery", name)
            return delivery
        args = ["--inputs", "/inputs", "--sha256", "a"*64, "--implementation-commit", "b"*40,
            "--delivery-envelope", "/delivery", "--delivery-sha256", r.sha(raw["/delivery"]),
            "--clock-anchor", "/clock", "--clock-anchor-sha256", r.sha(raw["/clock"]),
            "--seal-sha256", "c"*64]
        with patch.object(r, "Reader", return_value=reader), patch.object(r, "helper", side_effect=source), \
                patch.object(r.sys, "flags", SimpleNamespace(isolated=1)), \
                patch.object(r.sys, "dont_write_bytecode", True), patch.object(r.os, "getuid", return_value=0), \
                patch.object(r.os, "geteuid", return_value=0), patch.object(r.Path, "read_text", return_value=anchor["guest_boot_id"]), \
                patch.object(r.time, "clock_gettime_ns", return_value=envelope["guest_outer_deadline_ns"]), \
                patch("builtins.print") as output:
            self.assertEqual(3, r.main(args))
        self.assertEqual(["/clock", "/delivery"], observed)
        self.assertEqual("RECONCILIATION_ORIGINAL_WINDOW_EXPIRED", json.loads(output.call_args.args[0])["reason"])

    def test_original_clamped_window_and_anchor_cannot_be_renewed(self):
        anchor = delivery.legacy.make_clock_anchor(host_issued_ns=100*r.NS, host_deadline_ns=400*r.NS,
            host_probe_send_ns=110*r.NS, host_probe_receive_ns=112*r.NS, guest_sample_ns=1000*r.NS,
            guest_boot_id="12345678-1234-1234-1234-123456789abc", expected_boot_id="12345678-1234-1234-1234-123456789abc")
        envelope = delivery.guest_envelope(anchor, attempt_id="collect01", guest_boot_id=anchor["guest_boot_id"],
            guest_now_ns=1010*r.NS)
        end = r.fixed_envelope(anchor, envelope, "collect01", boot_id=anchor["guest_boot_id"],
            now_ns=1011*r.NS, anchor_sha256=r.sha(r.encoded(anchor)))
        self.assertEqual(end, envelope["guest_outer_deadline_ns"] - 2*r.NS)
        for bad in (dict(envelope, deadline_ns=envelope["deadline_ns"]+1), envelope):
            with self.assertRaises(ValueError):
                r.fixed_envelope(anchor, bad, "collect01", boot_id=anchor["guest_boot_id"],
                    now_ns=end, anchor_sha256=r.sha(r.encoded(anchor)))

    def test_wire_overflow_is_explicit_incomplete_and_bundle_hashes_match(self):
        value = dict(complete=True, files=[dict(path="synthetic", content_base64=base64.b64encode(os.urandom(40000)).decode())])
        report = r.bundle_report(value, output_limit=16384)
        self.assertEqual("INCOMPLETE", report["status"])
        self.assertEqual("COLLECT_WIRE_CONTENT_LIMIT", report["reason"])
        compressed = base64.b64decode(report["bundle"]["data"])
        raw = gzip.decompress(compressed)
        self.assertEqual(r.sha(raw), report["bundle"]["raw_sha256"])
        self.assertEqual(r.sha(compressed), report["bundle"]["sha256"])
        self.assertFalse(json.loads(raw)["complete"])
        self.assertIn("content_base64", value["files"][0])
        for key in ("remote_stop_proven", "original_eof_proven", "q2_accepted", "q3_accepted", "production_supported"):
            self.assertFalse(report[key])

    def test_no_argument_cli_does_not_inspect_or_create_files(self):
        result = subprocess.run([sys.executable, "-I", "-B", r.__file__], capture_output=True, timeout=10)
        self.assertEqual(3, result.returncode); self.assertEqual(b"", result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual("EXPLICIT_RECONCILIATION_WINDOW_REQUIRED", value["reason"])
        self.assertTrue(value["read_only"]); self.assertFalse(value["replay_allowed"])


if __name__ == "__main__": unittest.main()

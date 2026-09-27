"""Dual-failure models and real retained-file checks; no guest acceptance claim."""
import copy
import importlib.util
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("Q2 administrative attestation requires Linux no-atime ownership and quota interfaces")

spec = importlib.util.spec_from_file_location("_startup_backend_tests", Path(__file__).parent / "e3_host/q2_startup_retry.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def startup_fixture(second=True):
    controller = dict(cgroup="/lhqsupervisor.slice/lhqold.service", cpu_quota_per_sec_usec=1000000,
        runtime_max_usec=100000000, timeout_stop_usec=1000000, memory_bytes=64 * 1024**2,
        tasks_max=32, limit_cpu_seconds=100, unit="lhqold.service")
    template = dict(supervisor_envelope=dict(controller=controller), launcher=dict(
        controller_envelope=dict(controller=dict(controller, runtime_max_usec=85000000, unit="lhqtarget.service")),
        resident=dict(entry=dict(path="/old/source/tests/e3_host/q2_resident.py")),
        assembly=dict(installation=dict(programs=dict(systemd_run=dict(path="/usr/bin/systemd-run"),
            python=dict(path="/old/python"))))))
    handoff = dict(template=template, declarations=dict(path="/old/declarations"),
        owner_envelope=dict(issued_ns=10**9, deadline_ns=121 * 10**9))
    fixture = copy.deepcopy(template)
    for role in (fixture["supervisor_envelope"], fixture["launcher"]["controller_envelope"]):
        role.update(issued_ns=2 * 10**9, deadline_ns=2 * 10**9 + role["controller"]["runtime_max_usec"] * 1000)
    envelope = dict(schema="local-hand-q2-issued-handoff/v1", plan=handoff, fixture=fixture)
    eraw, hraw = m.c.encoded(envelope), m.c.encoded(handoff)
    argv = (m.supervisor_argv if second else m.legacy.legacy_argv)(envelope, "/old/declarations/envelope.json", m.p.sha(eraw))
    output = m.c.encoded(m.PERMISSION_FAILURE) if second else b""
    error = b"" if second else m.legacy.ERROR
    control = dict(Id="lhqold.service", LoadState="not-found", ActiveState="inactive", SubState="dead",
        MainPID="0", ControlPID="0", InvocationID="", ControlGroup="", Job="", ExecMainCode="0", ExecMainStatus="0")
    def record(value):
        raw = "".join(key + "=" + val + "\n" for key, val in value.items()).encode()
        return dict(complete=True, returncode=0, eof=["stderr", "stdout"], error=None, stderr_hex="", stdout_hex=raw.hex())
    controls = [record(control), record(dict(control, LoadState="loaded", Job="42") if second else control)]
    capture = dict(schema="local-hand-q2-outer-capture/v1", client_pid=200, close_errors=[], complete=True,
        started_ns=2 * 10**9, deadline_ns=121 * 10**9, eof=["stderr", "stdout"], error=None,
        independent_stop_required=True, production_supported=False, q3_accepted=False,
        pipe_identities=dict(stdout=[1, 2], stderr=[1, 3]), returncode=3 if second else 1,
        stdout_sha256=m.p.sha(output), stderr_sha256=m.p.sha(error))
    delivery = dict(argv_sha256=m.p.sha(m.c.encoded(argv)), unit="lhqold.service", started_ns=capture["started_ns"],
        deadline_ns=capture["deadline_ns"])
    if second: delivery["cpu_quota_format"] = "systemd-percent-hundredths/v1"
    values = {"capture.json": capture, "delivery.json": delivery,
        "reservation.json": dict(envelope_sha256=m.p.sha(eraw), plan_sha256=m.p.sha(hraw)),
        "result.json": dict(schema="local-hand-q2-handoff-result/v1", status="INCOMPLETE", scope="Q2_ONLY",
            reason="SUPERVISOR_DELIVERY_UNCERTAIN", sealed=False, q2_accepted=False, cleanup_errors=[], evidence={},
            original_management_session_exit_required=True, owner_self_exit_verified=False,
            production_supported=False, q3_accepted=False), "stop.json": {}, "controls.json": controls}
    raw = {name: m.c.encoded(value) for name, value in values.items()}
    raw.update({"supervisor.stdout": output, "supervisor.stderr": error})
    prepared = dict(q2_accepted=False, original_owner_issued=True, original_verdict_retained=True,
        schema="local-hand-q2-cpuquota-retry-driver-result/v1", status="RETRY_PREPARED") if second else dict(
            status="RECOVERED_PREPARED", q2_accepted=False, first_request_issuance=dict(original_request_unissued=True))
    return raw, eraw, hraw, prepared


def reservation_fixture():
    from test_e3_q2_startup_retry_contract import fixture, r
    original, previous, retry = fixture(); historical = r.legacy.bind(original, previous)
    records = {}
    recovery = dict(recovery_id=Path(retry["predecessors"][0]["prepared_path"]).parent.name,
        plan_sha256=retry["original_plan_sha256"], recovery_source=dict(commit="a" * 40, tree="b" * 40,
            files={"/synthetic/recovery-tools/tools/tool.py": "c" * 64}))
    for row in retry["reservations"]:
        kind = row["kind"]
        if kind == "PREPARATION_CEILING": records[row["path"]] = original
        elif kind == "PREPARATION_SNAPSHOT": records[row["path"]] = dict(host=original["host"])
        elif kind == "RECOVERY_SNAPSHOT": records[row["path"]] = dict(plan=recovery)
        elif kind == "RETRY_SNAPSHOT": records[row["path"]] = dict(retry=previous)
        elif kind == "RECOVERY_STAGE":
            # The plan binds the actual source directory; the staged receipt is
            # independent from the installed original candidate it reserves.
            row["path"] = "/synthetic/recovery-tools/tools/stage.json"
            records[row["path"]] = dict(schema="local-hand-q2-recovery-stage/v1",
                source_commit="a" * 40, source_tree="b" * 40, recovery_id=recovery["recovery_id"],
                original_plan_sha256=retry["original_plan_sha256"], installation_future_reserved_bytes=192 * 1024**2,
                reserved_new_bytes=16384, reserved_new_inodes=7, q2_accepted=False)
        elif kind == "OWNER_COMMITMENT":
            index = [item["owner_output"] + "/reservation.json" for item in retry["predecessors"]].index(row["path"])
            amount = m.runtime_storage((original, historical)[index]["settings"])
            records[row["path"]] = dict(costs={"storage_" + key: value for key, value in amount.items()})
        elif kind == "BOOTSTRAP_COMMITMENT":
            index = [str(Path(plan["candidate"]["source"]).parent) + ".intent.json" for plan in (original, historical)].index(row["path"])
            records[row["path"]] = dict(schema="local-hand-q2-delivery/v1", status="RESERVED",
                destination=str(Path((original, historical)[index]["candidate"]["source"]).parent),
                ceiling_bytes=original["budgets"]["installation_bytes"], fixture_provisioned=False, q2_accepted=False,
                staging_bytes=32768, installation_reservation_bytes=(192 if index == 0 else 96) * 1024**2,
                retained_delivery_bytes=8 * 1024**2 if index == 0 else 0, issued_ns=1, deadline_ns=100)
    bootstrap = next(row for row in retry["reservations"] if row["kind"] == "BOOTSTRAP_ATTESTATION")
    second = records[str(Path(historical["candidate"]["source"]).parent) + ".intent.json"]
    records[bootstrap["path"]] = dict(costs=dict(installation=dict(bytes=32 * 1024**2)),
        transfer=dict(second, status="EXTRACTED", entries=10))
    return retry, [original, historical], records


class DualFailureEvidence(unittest.TestCase):
    def test_distinct_actual_boundaries_are_accepted_without_rewriting_inputs(self):
        for second, validator in ((False, m.attest_cpuquota_startup), (True, m.attest_supervisor_startup)):
            args = startup_fixture(second); before = copy.deepcopy(args)
            proof = validator(*args)
            self.assertEqual(m.KINDS[int(second)], proof["kind"])
            self.assertTrue(proof["original_owner_issued"])
            self.assertEqual("INCOMPLETE", proof["original_status"])
            self.assertFalse(proof["original_stop_proven"]); self.assertFalse(proof["original_seal_proven"])
            self.assertEqual(before, args)
            with self.assertRaises(ValueError): (m.attest_cpuquota_startup if second else m.attest_supervisor_startup)(*args)

    def test_wrong_exit_missing_eof_pipe_alias_and_unknown_diagnostic_fail(self):
        for mutation in (lambda v: v.update(returncode=1), lambda v: v.update(returncode=True),
            lambda v: v.update(eof=["stdout"]), lambda v: v["pipe_identities"].update(stderr=v["pipe_identities"]["stdout"]),
            lambda v: v.update(diagnostic={}), lambda v: v.update(close_errors=["close"])):
            args = list(startup_fixture()); value = m.c.document(args[0]["capture.json"]); mutation(value)
            args[0]["capture.json"] = m.c.encoded(value)
            with self.subTest(value=value), self.assertRaises(ValueError): m.attest_supervisor_startup(*args)

    def test_queue_observation_cannot_be_replaced_by_later_failed_or_running(self):
        for key, value in (("LoadState", "not-found"), ("Job", ""), ("MainPID", "200"), ("InvocationID", "a" * 32),
            ("ActiveState", "failed"), ("ExecMainStatus", "3")):
            args = list(startup_fixture()); controls = m.c.document(args[0]["controls.json"])
            observed = m.fields(bytes.fromhex(controls[1]["stdout_hex"])); observed[key] = value
            controls[1]["stdout_hex"] = "".join(k + "=" + v + "\n" for k, v in observed.items()).encode().hex()
            args[0]["controls.json"] = m.c.encoded(controls)
            with self.subTest(key=key), self.assertRaises(ValueError): m.attest_supervisor_startup(*args)

    def test_new_children_seal_stop_or_changed_template_are_rejected(self):
        for fault in ("child", "stop", "seal", "template", "quota-format"):
            args = list(startup_fixture())
            if fault == "child": args[0]["invocation.json"] = b"{}"
            elif fault == "stop": args[0]["stop.json"] = b'{"stopped":true}'
            elif fault == "seal":
                value = m.c.document(args[0]["result.json"]); value["sealed"] = True
                args[0]["result.json"] = m.c.encoded(value)
            elif fault == "template":
                value = m.c.document(args[1]); value["fixture"]["supervisor_envelope"]["issued_ns"] += 1
                args[1] = m.c.encoded(value)
            else:
                value = m.c.document(args[0]["delivery.json"]); value["cpu_quota_format"] = "wrong"
                args[0]["delivery.json"] = m.c.encoded(value)
            with self.subTest(fault=fault), self.assertRaises(ValueError): m.attest_supervisor_startup(*args)


class ExactHistoricalUnits(unittest.TestCase):
    def fixture(self):
        pin = dict(role="supervisor", unit="lhqold.service", invocation_id="a" * 32, exec_main_code=1, exec_main_status=3)
        observed = dict(Id=pin["unit"], LoadState="loaded", ActiveState="failed", SubState="failed", InvocationID=pin["invocation_id"],
            MainPID="0", ControlPID="0", Job="", ControlGroup="", ExecMainCode="1", ExecMainStatus="3", Result="exit-code")
        return pin, observed

    def test_exact_failed_identity_is_retained_but_not_stopped_or_reset(self):
        pin, observed = self.fixture(); before = copy.deepcopy(observed)
        self.assertEqual(observed, m.attest_failed_unit(pin, observed)["observed"])
        self.assertEqual(before, observed)

    def test_reset_restarted_unknown_failed_or_live_instances_cannot_match(self):
        for key, value in (("Id", "lhqunknown.service"), ("InvocationID", "b" * 32), ("LoadState", "not-found"),
            ("ActiveState", "inactive"), ("MainPID", "20"), ("Job", "9"), ("ControlGroup", "/busy"), ("ExecMainStatus", "0")):
            pin, observed = self.fixture(); observed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): m.attest_failed_unit(pin, observed)

    def test_unissued_template_does_not_invent_query_identity(self):
        handoff = dict(template=dict(launcher=dict(assembly=dict(phases={"preflight": dict(grant=dict(
            request=dict(execution_id="a" * 32)))}))))
        names = m.historical_child_units(handoff)
        self.assertEqual(3, len(names)); self.assertTrue(all(name.startswith("lhj-") for name in names))
        backend = m.StartupRetryBackend.__new__(m.StartupRetryBackend)
        backend.handoff_history = [handoff]
        backend.retry = dict(predecessors=[], service=next(iter(names)))
        backend.plan = backend.old = dict(settings=dict(controllers={
            "supervisor": dict(unit="lhqsupervisor.service"), "target": dict(unit="lhqtarget.service")}))
        backend.histories = [backend.old]
        with self.assertRaisesRegex(ValueError, "HISTORICAL_UNIT_REUSE"): backend.historical_units()

    def test_seven_root_bindings_must_match_both_predecessors(self):
        roots = [dict(device=10, inode=100 + i, project_id=i) for i in range(7)]
        grant = dict(roots=roots, allocation=dict(paths={"/root/" + str(i): dict(device=10, inode=100 + i) for i in range(7)}))
        handoff = dict(template=dict(launcher=dict(assembly=dict(phases={"preflight": dict(grant=grant)}))))
        backend = m.StartupRetryBackend.__new__(m.StartupRetryBackend)
        backend.handoff_history = [handoff, copy.deepcopy(handoff)]
        self.assertEqual(7, len(backend.old_root_pins()))
        backend.handoff_history[1]["template"]["launcher"]["assembly"]["phases"]["preflight"]["grant"]["roots"][0]["inode"] += 20
        with self.assertRaises(ValueError): backend.old_root_pins()


class RealRetainedFiles(unittest.TestCase):
    def test_two_real_ledgers_keep_bytes_atime_and_reject_either_consumption(self):
        from local_hand_jobs.state import StateStore
        with tempfile.TemporaryDirectory(dir=Path.home()) as td:
            ledgers = []
            for index in (0, 1):
                path = Path(td) / (str(index) + ".sqlite")
                store = StateStore(path, "authority" + str(index), "ledger" + str(index), initialize=True); store.close()
                info = path.stat(); pin = dict(path=str(path), device=info.st_dev, inode=info.st_ino, uid=info.st_uid,
                    mode=stat.S_IMODE(info.st_mode), ledger_id="ledger" + str(index), generation=[1, 1])
                raw = path.read_bytes(); os.utime(path, ns=(10**9, 2 * 10**9)); before = path.stat()
                proof = m.legacy.attest_ledger(path, pin, "authority" + str(index))
                self.assertEqual(m.p.sha(raw), proof["sha256"]); self.assertEqual(before.st_atime_ns, path.stat().st_atime_ns)
                ledgers.append((path, pin, raw, "authority" + str(index)))
            self.assertNotEqual(ledgers[0][1]["inode"], ledgers[1][1]["inode"])
            for path, pin, raw, authority in ledgers:
                with sqlite3.connect(path) as db: db.execute("INSERT INTO revocations VALUES('used',1)")
                with self.assertRaises(ValueError): m.legacy.attest_ledger(path, pin, authority)

    def test_tree_snapshot_preserves_atime_detects_change_and_rejects_aliases(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as td:
            root = Path(td); leaf = root / "payload"; leaf.write_bytes(b"one")
            for name in (root, leaf): os.utime(name, ns=(10**9, 2 * 10**9))
            before = {name: name.stat() for name in (root, leaf)}
            first = m.tree_snapshot(root, lambda: None)
            for name, value in before.items(): self.assertEqual(value.st_atime_ns, name.stat().st_atime_ns)
            leaf.write_bytes(b"two"); second = m.tree_snapshot(root, lambda: None)
            self.assertNotEqual(first["sha256"], second["sha256"])
            os.link(leaf, root / "alias")
            with self.assertRaises(ValueError): m.tree_snapshot(root, lambda: None)

    def test_leaf_noatime_denial_has_no_unprotected_retry(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as td:
            leaf = Path(td) / "payload"; leaf.write_bytes(b"retained")
            with mock.patch.object(m.p, "opened", side_effect=PermissionError("denied")) as opened:
                with self.assertRaises(PermissionError): m.tree_snapshot(leaf, lambda: None)
            opened.assert_called_once(); self.assertIs(True, opened.call_args.kwargs["noatime"])


class CumulativeReservations(unittest.TestCase):
    def test_original_and_recovery_192_are_nested_second_64_is_not_a_refund(self):
        retry, histories, records = reservation_fixture()
        before = copy.deepcopy(records)
        obligations = m.reservation_obligations(retry, histories, records)
        installed = [item for item in obligations if item["id"].endswith("#installation")]
        self.assertEqual([192 * 1024**2, 64 * 1024**2], [item["commitment"]["bytes"] for item in installed])
        self.assertEqual([8192, 4096], [item["commitment"]["inodes"] for item in installed])
        owners = [item for item in obligations if item["category"] == "capture"]
        self.assertEqual(2, len(owners)); self.assertEqual(40 * 1024**2, sum(item["commitment"]["bytes"] for item in owners))
        for item, plan in zip(owners, histories):
            self.assertEqual(["capture", "journal"], item["accounting_categories"])
            self.assertIn(plan["directories"]["journal"]["path"], item["covered_paths"])
        self.assertGreater(sum(item["commitment"]["bytes"] for item in installed) + m.INSTALL_PEAK["bytes"],
            histories[0]["budgets"]["installation_bytes"])
        self.assertEqual(before, records)

    def test_missing_or_substituted_reservation_cannot_be_omitted(self):
        retry, histories, records = reservation_fixture()
        for path in records:
            changed = copy.deepcopy(records); del changed[path]
            with self.subTest(path=path), self.assertRaises(ValueError): m.reservation_obligations(retry, histories, changed)
        for kind, key in (("RECOVERY_STAGE", "installation_future_reserved_bytes"), ("BOOTSTRAP_COMMITMENT", "ceiling_bytes")):
            changed = copy.deepcopy(records); row = next(row for row in retry["reservations"] if row["kind"] == kind)
            changed[row["path"]][key] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError): m.reservation_obligations(retry, histories, changed)

    def test_stage_admission_charges_staging_once_and_preserves_original_ceiling(self):
        backend = m.StartupRetryBackend.__new__(m.StartupRetryBackend)
        backend.plan = dict(budgets=dict(installation_bytes=100000, installation_inodes=100))
        costs = dict(installation=dict(admitted_bytes=60000, admitted_inodes=50,
            retained_unspent_bytes=10000, retained_unspent_inodes=10, new_unspent_bytes=20000, new_unspent_inodes=20))
        backend.measure_costs = lambda: costs
        backend.mounts = lambda: dict(system=dict(available_bytes=1000000, free_inodes=1000))
        result = backend.stage_admission(8192, 5)
        self.assertEqual(60000, result["installation_reservation_bytes"])
        self.assertEqual(60000 + 8192 + 8192, result["admitted_bytes"])
        self.assertEqual(58, result["admitted_inodes"])
        with self.assertRaisesRegex(ValueError, "STAGE_CAPACITY"): backend.stage_admission(40000, 5)

    def accounting_backend(self):
        # Deterministic two-filesystem observations exercise the accounting
        # boundary without creating or claiming a guest quota fixture.
        backend = m.StartupRetryBackend.__new__(m.StartupRetryBackend)
        retry, histories, records = reservation_fixture()
        backend.plan = copy.deepcopy(histories[0]); backend.guard = lambda: None
        backend.skip_candidate = True; backend.histories = histories
        backend.retry = dict(reservations=[], retained_inputs=[dict(path="/old/" + role, category=category)
            for role, category in (("capture", "capture"), ("declarations", "capture"), ("journal", "journal"))])
        backend.new_staging = lambda item: False
        backend.old_document = lambda path: records[path]
        obligation = dict(id="owner", category="capture", accounting_categories=["capture", "journal"],
            commitment=dict(bytes=100000, inodes=100), covered_paths=[item["path"] for item in backend.retry["retained_inputs"]], evidence=[])
        snapshots = {"/old/" + role: dict(device=device, bytes=size, inodes=1)
            for role, device, size in (("capture", 2, 20000), ("declarations", 1, 10000), ("journal", 1, 5000))}
        return backend, obligation, snapshots

    def test_shared_management_pool_credits_journal_once_across_devices(self):
        backend, obligation, snapshots = self.accounting_backend()
        with mock.patch.object(m, "reservation_obligations", return_value=[obligation]), \
            mock.patch.object(m.os.path, "lexists", return_value=False), \
            mock.patch.object(m, "tree_snapshot", side_effect=lambda name, *a, **kw: snapshots[name]):
            costs = backend.measure_costs()
        proof = backend.reservation_proofs[0]
        self.assertEqual([1, 2], proof["devices"])
        self.assertEqual(65000, proof["unspent"]["bytes"])
        for role in ("capture", "journal"):
            self.assertEqual(65000, costs[role]["retained_unspent_bytes"])
            self.assertEqual(m.runtime_storage(backend.plan["settings"])["bytes"], costs[role]["new_unspent_bytes"])

    def test_physical_pool_counts_once_per_possible_device_and_rejects_shortfall(self):
        backend, obligation, _ = self.accounting_backend()
        costs = {category: dict(new_unspent_bytes=0, new_unspent_inodes=0) for category in m.CATEGORIES}
        costs["capture"] = costs["journal"] = dict(new_unspent_bytes=2000, new_unspent_inodes=2)
        backend.measure_costs = lambda: costs
        backend.reservation_records = {}; backend.reservation_proofs = [dict(obligation, devices=[1, 2], unspent=dict(bytes=1000, inodes=1))]
        mounts = {"system": dict(device=1, available_bytes=3000, free_inodes=3),
            "evidence": dict(device=2, available_bytes=3000, free_inodes=3),
            "quota": dict(device=3, available_bytes=0, free_inodes=0)}
        for role, item in backend.plan["directories"].items():
            item["filesystem"] = "evidence" if role == "capture" else "system"
        result = backend.capacity(mounts, [])
        self.assertEqual([3000, 3000, 0], [result["by_device"][i]["future_bytes"] for i in (1, 2, 3)])
        aliases = dict(mounts, system_alias=dict(device=1, available_bytes=4000, free_inodes=4))
        result = backend.capacity(aliases, [])
        self.assertEqual(3000, result["by_device"][1]["available_bytes"])
        self.assertEqual(3, result["by_device"][1]["free_inodes"])
        for key, value in (("available_bytes", 2999), ("free_inodes", 2)):
            changed = copy.deepcopy(aliases); changed["system_alias"][key] = value
            with self.subTest(alias_field=key), self.assertRaisesRegex(ValueError, "DEVICE_CAPACITY"): backend.capacity(changed, [])
        for device in ("system", "evidence"):
            changed = copy.deepcopy(mounts); changed[device]["available_bytes"] -= 1
            with self.subTest(device=device), self.assertRaisesRegex(ValueError, "DEVICE_CAPACITY"): backend.capacity(changed, [])

    def test_original_320_mib_commitment_blocks_before_creation(self):
        backend, _, _ = self.accounting_backend()
        retry, histories, records = reservation_fixture()
        backend.retry = retry; backend.histories = histories; backend.old_document = lambda path: records[path]
        # Empty historical objects maximize their unspent reservation; this
        # failure is independent of staging size or current filesystem space.
        backend.retry["retained_inputs"] = [dict(path=path, category=category)
            for item in m.reservation_obligations(retry, histories, records)
            for path in item["covered_paths"]
            for category in ["journal" if path in {plan["directories"]["journal"]["path"] for plan in histories} else item["category"]]]
        with mock.patch.object(m.os.path, "lexists", return_value=False), \
            mock.patch.object(m, "tree_snapshot", return_value=dict(device=1, bytes=0, inodes=0)), \
            mock.patch.object(m.p, "create_file") as create_file, mock.patch.object(m.p, "create_directory") as create_directory:
            with self.assertRaisesRegex(ValueError, "CUMULATIVE_CAPACITY"): backend.measure_costs()
            create_file.assert_not_called(); create_directory.assert_not_called()


if __name__ == "__main__": unittest.main()

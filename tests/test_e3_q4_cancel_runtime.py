"""Finite Q4 orchestration models; no systemd service or real fixture runs."""
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import threading
import unittest
from unittest import mock

HERE = Path(__file__).parent / "e3_host"
spec = importlib.util.spec_from_file_location("_q4_launcher_test", HERE / "q2_launcher.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
if sys.platform.startswith("linux"):
    from local_hand_jobs import quota_contract as q
    from admin.local_hand_quota_observer import q2_coordinator as normal
    from q2_fixtures import make_grant, capacity, SECOND
    import test_e3_quota_q2_launcher as launcher_models
    from admin.local_hand_quota_observer import q2_assembly, q2_capture, q2_management
    from local_hand_jobs import budget, quota_bridge, runner
    spec = importlib.util.spec_from_file_location("_q4_runtime_test", HERE / "q4_cancel_runtime.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)


class LauncherBoundaryTests(unittest.TestCase):
    def declaration(self):
        return dict(schema=launcher.CANCEL_SCHEMA, purpose=launcher.CANCEL_PURPOSE, source={},
            resident={}, assembly={}, controller_envelope={}, setpriv={}, output={}, declarations={}, session="a" * 64)

    def test_q4_requires_its_exact_schema_purpose_pair(self):
        value = self.declaration()
        encoded = launcher.encoded(value, launcher.LIMIT)
        self.assertEqual(value, launcher.decode(encoded, hashlib.sha256(encoded).hexdigest()))
        for key, wrong in (("schema", launcher.SCHEMA), ("purpose", "ISOLATED_Q2_CHAIN")):
            changed = dict(value, **{key: wrong})
            encoded = launcher.encoded(changed, launcher.LIMIT)
            with self.assertRaisesRegex(ValueError, "LAUNCHER_SCHEMA"):
                launcher.decode(encoded, hashlib.sha256(encoded).hexdigest())

    def test_cancel_module_loader_is_fixed_and_checks_original_bytes(self):
        value = self.declaration()
        paths = ["tests/e3_host/q4_cancel_runtime.py", "tests/e3_host/q4_cancel_case.py"]
        blobs = {name: b"PINNED_TEST_ONLY = True\n" for name in paths}
        value["source"] = {"files": {name: hashlib.sha256(raw).hexdigest() for name, raw in blobs.items()}}
        with mock.patch.object(launcher, "protected", side_effect=lambda path, limit: blobs[str(Path(path).relative_to("/fixed"))]):
            modules = launcher.load_cancel_modules(value, Path("/fixed"))
            self.assertTrue(all(module.PINNED_TEST_ONLY for module in modules))
            value["source"]["files"][paths[1]] = "0" * 64
            with self.assertRaisesRegex(ValueError, "CANCEL_SOURCE_DIGEST"):
                launcher.load_cancel_modules(value, Path("/fixed"))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux Q4 management model")
class CancelCoordinatorTests(unittest.TestCase):
    def test_actual_sqlite_case_record_roundtrips_existing_integer_only_wire(self):
        # Existing broker fixture uses a real private SQLite ledger and a
        # modeled supervisor; no manager or ordinary process is delivered.
        import test_local_hand_jobs_broker as broker_models
        case_spec = importlib.util.spec_from_file_location("_q4_wire_case", HERE / "q4_cancel_case.py")
        case_module = importlib.util.module_from_spec(case_spec)
        case_spec.loader.exec_module(case_module)
        fixture = broker_models.BrokerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.submit()
        case = case_module.Case(fixture.broker, fixture.request["operation_id"], fixture.owner)
        fixture.cancel()
        report = case.poll()
        self.assertEqual([], case_module.validate_report(report))
        event = report["ledger"]["cancel_event"]
        self.assertIsNotNone(event)
        self.assertIsInstance(event["observed_at_hex"], str)
        raw = q._canonical(dict(schema=runtime.SNAPSHOT_SCHEMA, phase={}, case=report), 32768)
        self.assertEqual(report, q._load(raw, 32768, 20)["case"])
        changed = copy.deepcopy(report)
        changed["ledger"]["cancel_event"]["observed_at_hex"] = 1.5
        with self.assertRaises(q.QuotaError):
            q._load(q._canonical(changed, 32768), 32768, 20)

    def setup_driver(self, *, ready_after=2, management_closes=True, fault=None):
        self.now = 3 * SECOND
        self.order = []
        grant = make_grant()
        value = grant.as_dict()
        request_id = grant.request.as_dict()["request_id"]
        state = {request_id: {"status": "READY"}}
        self.case = dict(schema="modeled-case", operation_id=value["allocation"]["operation_id"],
            request_digest="d" * 64, principal_id="q4-synthetic-owner",
            target_execution_id=value["allocation"]["execution_id"],
            boot_id=value["budget"]["boot_id"], phase="preflight",
            status="PENDING", ready_for_finish=False, helper_exit_proven=False,
            chain_closed=False, leases_retained=True, phase_deadline_ns=budget.phase_deadline_ns(value["budget"])
                - value["budget"]["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS,
            record_deadline_ns=budget.phase_deadline_ns(value["budget"])
                - 2 * value["budget"]["limits"]["terminate_grace_seconds"] * budget.NANOSECONDS)
        self.phase = dict(preparation=dict(allocation=value["allocation"], budget=value["budget"], phase="preflight"),
            observation=None, pending=None, closed=None)
        owner = self

        def clock():
            owner.now += 1_000_000
            return owner.now

        class Journal:
            @contextmanager
            def locked(self):
                yield
            def scan(self):
                return state
            def close(self):
                owner.order.append("journal-close")

        class Management:
            end = 10 * SECOND
            def __init__(self, *args):
                self.runs = {}
                self.polls = 0
            def begin(self):
                owner.order.append("management-begin")
                self.launch("listener")
            def launch(self, role):
                owner.order.append(role)
                cap = SimpleNamespace(error=None, exited=False, done=False,
                    process=SimpleNamespace(returncode=0), pump=lambda: None)
                self.runs[role] = dict(invocation=None, stop_attempted=False, stop_ok=False, after=None, capture=cap)
            def poll(self):
                self.polls += 1
                for part in self.runs.values():
                    part["invocation"] = "e" * 32
                    if management_closes and self.polls >= 2:
                        part.update(stop_attempted=True, stop_ok=True, after={"LoadState": "not-found"})
                        part["capture"].done = part["capture"].exited = True
                return {"original_management": "closed"} if management_closes and self.polls >= 2 else None
            def finish(self):
                owner.order.append("management-finish")
                return {"original_management": "closed"}

        class Client:
            started = False
            polls = 0
            def call(self, action, data=None):
                owner.order.append(action)
                if action not in ("snapshot", "bind", "start"):
                    raise AssertionError("Q4 must not close the original quota phase")
                if action == "start":
                    self.started = True
                    state[request_id]["status"] = "RESULT"
                    if fault == "start_ack":
                        raise OSError("modeled lost original start acknowledgement")
                if self.started and action == "snapshot":
                    self.polls += 1
                    if ((owner.now >= owner.case["record_deadline_ns"]) if ready_after == "deadline"
                            else self.polls >= ready_after):
                        owner.case.update(ready_for_finish=True, status="INCOMPLETE")
                response = dict(schema=runtime.SNAPSHOT_SCHEMA, phase=owner.phase, case=owner.case)
                if fault == "wrapper":
                    response["schema"] = "normal-snapshot"
                if fault == "preparation":
                    response = copy.deepcopy(response)
                    response["phase"]["preparation"]["phase"] = "business"
                return copy.deepcopy(response)

        self.config = SimpleNamespace(active=lambda: grant, grants=lambda: {request_id: grant}, digest="c" * 64,
            data=lambda: dict(journal={"path": "/synthetic/journal", "pin": {}}, capacity=capacity(),
                              service={"control_path": "/synthetic/control"}))
        self.report = SimpleNamespace(validate_report=lambda case: [] if type(case) is dict and
            case.get("schema") == "modeled-case" else ["schema"],
            encode_report=lambda case: json.dumps(case, sort_keys=True).encode())
        patches = [mock.patch.object(normal.m, "Management", Management),
            mock.patch.object(runtime, "Journal", lambda *args: Journal()),
            mock.patch.object(normal, "ready", return_value=True),
            mock.patch.object(normal, "boottime_ns", side_effect=clock),
            mock.patch.object(runtime, "boottime_ns", side_effect=clock),
            mock.patch.object(runtime.time, "sleep")]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.instance = runtime.Coordinator(self.config, {"deadline_ns": 40 * SECOND}, None, Client(), report=self.report,
            request=dict(operation_id=self.case["operation_id"], request_digest="d" * 64), principal_id="q4-synthetic-owner")
        return self.instance, state[request_id]

    def test_ready_unknown_records_case_without_reader_pending_or_either_ledger_closure(self):
        instance, journal = self.setup_driver()
        result = instance.run()
        self.assertEqual("CANCEL_CASE_RECORDED", result["status"])
        self.assertEqual("INCOMPLETE", result["case"]["status"])
        self.assertTrue(result["case"]["leases_retained"])
        self.assertFalse(result["case"]["helper_exit_proven"])
        self.assertIsNone(instance.last_phase["pending"])
        self.assertEqual("RESULT", journal["status"])
        self.assertFalse(result["ordinary_phase_closed"])
        self.assertTrue(result["independent_ordinary_cleanup_required"])
        self.assertNotIn("close", self.order)
        self.assertEqual(1, self.order.count("start"))
        self.assertLess(self.order.index("management-finish"), self.order.index("journal-close"))
        with self.assertRaisesRegex(q.QuotaError, "COORDINATOR_CONSUMED"):
            instance.run()

    def test_bad_wrapper_or_original_preparation_blocks_before_delivery(self):
        for fault in ("wrapper", "preparation"):
            with self.subTest(fault=fault):
                instance, _ = self.setup_driver(fault=fault)
                with self.assertRaises(q.QuotaError):
                    instance.run()
                self.assertNotIn("management-begin", self.order)
                self.assertNotIn("start", self.order)
                self.doCleanups()

    def test_lost_start_ack_preserves_last_verified_case_and_consumption(self):
        instance, journal = self.setup_driver(fault="start_ack")
        with self.assertRaises(OSError):
            instance.run()
        self.assertEqual("RESULT", journal["status"])
        self.assertIsNotNone(instance.last_case)
        self.assertEqual(1, self.order.count("start"))
        self.assertNotIn("close", self.order)
        with self.assertRaisesRegex(q.QuotaError, "COORDINATOR_CONSUMED"):
            instance.run()

    def test_original_record_deadline_has_a_reserved_final_snapshot(self):
        instance, _ = self.setup_driver(ready_after="deadline")
        result = instance.run()
        self.assertEqual("CANCEL_CASE_RECORDED", result["status"])
        self.assertGreaterEqual(self.now, self.case["record_deadline_ns"])
        self.assertLess(self.now, self.case["phase_deadline_ns"])
        self.assertLessEqual(self.order.count("snapshot"), runtime.SNAPSHOT_POLLS + 1)

    def test_unclosed_management_cannot_be_hidden_by_ready_case(self):
        instance, _ = self.setup_driver(management_closes=False)
        with self.assertRaises(q.QuotaError):
            instance.run()
        self.assertTrue(instance.last_case["ready_for_finish"])
        self.assertNotIn("management-finish", self.order)
        self.assertNotIn("close", self.order)
        self.assertLessEqual(self.order.count("snapshot"), runtime.SNAPSHOT_POLLS + 1)

    def test_ready_case_cannot_change_and_phase_cannot_be_falsely_closed(self):
        instance, _ = self.setup_driver()
        instance.run()
        response = dict(schema=runtime.SNAPSHOT_SCHEMA, phase=copy.deepcopy(self.phase), case=copy.deepcopy(instance.last_case))
        response["case"]["helper_exit_proven"] = True
        with self.assertRaisesRegex(q.QuotaError, "CANCEL_FROZEN_CASE_CHANGED"):
            instance._accept(response)
        response["case"] = instance.last_case
        response["phase"]["closed"] = {"fabricated": True}
        with self.assertRaisesRegex(q.QuotaError, "CANCEL_UNEXPECTED_PHASE_CLOSURE"):
            instance._accept(response)

    def test_same_operation_cannot_replace_owner_request_or_original_budget(self):
        instance, _ = self.setup_driver()
        response = dict(schema=runtime.SNAPSHOT_SCHEMA, phase=self.phase, case=self.case)
        for key, wrong in (("principal_id", "other-owner"), ("request_digest", "f" * 64),
                           ("target_execution_id", "other-execution"),
                           ("boot_id", "foreign-boot"),
                           ("record_deadline_ns", self.case["record_deadline_ns"] + 1)):
            with self.subTest(key=key):
                changed = copy.deepcopy(response)
                changed["case"][key] = wrong
                with self.assertRaises(q.QuotaError):
                    instance._accept(changed)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux modeled Q4 launcher")
class CancelLauncherTests(unittest.TestCase):
    def invoke(self, *, fail=False, foreign_final=False):
        fixture = launcher_models.LauncherOrderingTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        value = fixture.value
        value.update(schema=launcher.CANCEL_SCHEMA, purpose=launcher.CANCEL_PURPOSE)
        value["resident"].update(schema="local-hand-q4-cancel-resident/v1", purpose=launcher.CANCEL_PURPOSE,
            principal={"principal_id": "q4-synthetic-owner"})
        value["resident"]["request"]["request_digest"] = "d" * 64
        case = dict(schema="modeled-case", operation_id=value["resident"]["request"]["operation_id"],
            request_digest="d" * 64, principal_id="q4-synthetic-owner", ready_for_finish=True,
            status="INCOMPLETE", chain_closed=False, helper_exit_proven=False)
        self.order = []
        finish = threading.Event()
        report = SimpleNamespace(validate_report=lambda candidate: [] if candidate.get("schema") == "modeled-case" else ["schema"],
            encode_report=lambda candidate: json.dumps(candidate, sort_keys=True).encode())
        owner = self

        class Coordinator:
            def __init__(self, *args, **kwargs):
                self.last_case = copy.deepcopy(case)
                self.events = [{"kind": "already-validated-original"}]
            def run(self):
                owner.order.append("case-coordinator")
                if fail:
                    raise OSError("modeled original case failure")
                return dict(schema=runtime.RESULT_SCHEMA, status="CANCEL_CASE_RECORDED", case=copy.deepcopy(case),
                    ordinary_phase_closed=False, independent_ordinary_cleanup_required=True,
                    q3_accepted=False, production_supported=False)

        class Channel:
            def __init__(self, *args, **kwargs):
                self.peer = kwargs["peer"]
            def _time(self):
                return fixture.clock["boottime_ns"]
            def receive(self):
                return copy.deepcopy(fixture.prepared)
            def send(self, command):
                owner.assertEqual({"action": "finish", "value": None}, command)
                owner.order.append("finish")
                finish.set()
            def close(self):
                finish.set()

        def collect(*args, **kwargs):
            self.assertTrue(finish.wait(2))
            final_case = dict(case, helper_exit_proven=True) if foreign_final else case
            summary = dict(schema="local-hand-q4-cancel-resident-result/v1", status="CANCEL_CASE_RECORDED",
                phase="preflight", operation_id=case["operation_id"], case=final_case,
                q3_accepted=False, production_supported=False)
            return dict(complete=True, returncode=0, stdout=launcher.encoded(summary, 32768), stderr=b"", error=None)

        patches = [mock.patch.object(launcher, "load_cancel_modules", return_value=(SimpleNamespace(Coordinator=Coordinator), report)),
            mock.patch.object(launcher, "controller", return_value=fixture.clock),
            mock.patch.object(launcher, "protected", return_value=b"modeled protected executable"),
            mock.patch.object(launcher, "directory", side_effect=lambda pin, mode: os.open(pin["path"], os.O_RDONLY | os.O_DIRECTORY)),
            mock.patch.object(launcher.subprocess, "Popen", return_value=SimpleNamespace(pid=os.getpid(), stdout=io.BytesIO(), stderr=io.BytesIO())),
            mock.patch.object(launcher, "start_ticks", return_value=1),
            mock.patch.object(launcher.select, "select", side_effect=lambda *args: (args[0], [], [])),
            mock.patch.object(quota_bridge, "Channel", Channel),
            mock.patch.object(q2_capture, "capture_existing", side_effect=collect),
            mock.patch.object(q2_assembly, "install", return_value={"config": object(), "management_record": {}}),
            mock.patch.object(q2_management, "controller"),
            mock.patch.object(q2_management, "RunRecord", return_value=SimpleNamespace(close=lambda: owner.order.append("record-close"))),
            mock.patch.object(normal.Coordinator, "run", side_effect=AssertionError("normal closure path must not run")),
            mock.patch.object(runner, "_quota_prepared_execution", return_value={}),
            mock.patch.object(runner, "quota_bootstrap_argv", return_value=["fixed-modeled-bootstrap"]),
            mock.patch.object(budget, "current_clock", return_value=fixture.clock)]
        from contextlib import ExitStack
        with ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            result = launcher.run(value, fixture.repository)
        self.saved = json.loads((fixture.root / "output" / "result.json").read_bytes())
        return result

    def test_launcher_records_unknown_case_and_exact_frozen_resident_report(self):
        result = self.invoke()
        self.assertEqual("CANCEL_CASE_RECORDED", result["status"])
        self.assertEqual("INCOMPLETE", result["case"]["status"])
        self.assertFalse(result["ordinary_phase_closed"])
        self.assertTrue(result["independent_ordinary_cleanup_required"])
        self.assertIn("finish", self.order)
        self.assertEqual(result, self.saved)

    def test_changed_final_case_is_not_a_successful_record(self):
        result = self.invoke(foreign_final=True)
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("CANCEL_RESIDENT_RESULT", result["reason"])
        self.assertFalse(result["case"]["helper_exit_proven"])

    def test_runtime_error_keeps_case_and_events_without_finish_or_replay(self):
        result = self.invoke(fail=True)
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("INCOMPLETE", result["case"]["status"])
        self.assertEqual([{"kind": "already-validated-original"}], result["case_events"])
        self.assertNotIn("finish", self.order)
        self.assertEqual(1, self.order.count("case-coordinator"))


if __name__ == "__main__":
    unittest.main()

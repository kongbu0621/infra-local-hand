"""One-shot runtime tests with modeled manager identity and real client pipes.

No test creates host services, accounts, mounts or quota domains. Pure static
and mutation tests distinguish original identity from declared placeholders;
the capture tests use real Popen exit, separate pipes and create-only files.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

PATH = Path(__file__).parent / "e3_host/q2_prepare_run.py"
spec = importlib.util.spec_from_file_location("_q2_prepare_run_tests", PATH)
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import controller_guard as guard, protected_inputs
    from admin.local_hand_quota_observer import q2_config, systemd_runtime
    from local_hand_jobs import budget, quota_grant as g
    from test_e3_quota_q2_supervisor import fixture, s, launcher
    from test_e3_quota_q2_chain import declaration_chain
    from q2_fixtures import BOOT, SECOND


def plan():
    value = fixture(); chain, _ = declaration_chain()
    cap = chain["installation"]["capacity"]
    cap["management"]["cpu_ns"] = 500 * SECOND
    for phase in chain["phases"].values():
        phase["grant"]["management"]["capacity_digest"] = g.digest(cap)
    value["launcher"].update(schema="local-hand-q2-launcher/v2", purpose="ISOLATED_Q2_CHAIN", assembly=chain)
    for env in (value["supervisor_envelope"], value["launcher"]["controller_envelope"]):
        env.pop("issued_ns"); env.pop("deadline_ns")
        for key in r.DYNAMIC: env["controller"].pop(key, None)
    value["supervisor_envelope"]["controller"]["runtime_max_usec"] = 100_000_000
    value["launcher"]["controller_envelope"]["controller"]["runtime_max_usec"] = 85_000_000
    return dict(schema=r.SCHEMA, purpose="ONE_ORIGINAL_Q2_HANDOFF", preparation_id="a" * 32, boot_id=BOOT,
        template=value, supervisor_parent=dict(path="/lhqsupervisor.slice", device=22, inode=900),
        output=dict(path="/owner-output", device=70, inode=910), declarations=dict(path="/owner-declarations", device=70, inode=911),
        owner_envelope=dict(issued_ns=SECOND, deadline_ns=120 * SECOND, storage_bytes=8 * 1024**2,
                            storage_inodes=32, cpu_ns=10 * SECOND, memory_bytes=64 * 1024**2,
                            pids=8, output_bytes=2 * r.PIPE_LIMIT + 4096))


class EntryTests(unittest.TestCase):
    def test_real_no_argument_entry_is_blocked_without_importing_core(self):
        run = subprocess.run([sys.executable, "-I", "-B", str(PATH)], capture_output=True, timeout=10)
        self.assertEqual(3, run.returncode); self.assertEqual(b"", run.stderr)
        value = json.loads(run.stdout)
        self.assertEqual("EXPLICIT_PRIVATE_HANDOFF_REQUIRED", value["reason"])
        self.assertFalse(value["q2_accepted"]); self.assertFalse(value["q3_accepted"])
        self.assertFalse(value["owner_self_exit_verified"])
        self.assertTrue(value["original_management_session_exit_required"])

    def test_nonlinux_rejects_before_source_and_posix_open(self):
        with mock.patch.object(r.sys, "platform", "win32"), mock.patch.object(r, "protected", side_effect=AssertionError("open")):
            with mock.patch("builtins.print") as output:
                self.assertEqual(3, r.main(["--plan", "/synthetic/plan", "--sha256", "a" * 64]))
            self.assertEqual("HANDOFF_ISOLATED_LINUX_PYTHON", json.loads(output.call_args.args[0])["reason"])

    def test_duplicate_float_nonfinite_and_wrong_digest_reject(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":1.0}', b'{"a":NaN}', b'{"a":-1}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): r.document(raw, r.sha(raw))
        with self.assertRaises(ValueError): r.document(b"{}", "0" * 64)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux declaration imports")
class OriginalDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan(); self.now = dict(boot_id=BOOT, boottime_ns=2 * SECOND)

    def issue(self):
        return r.issue(self.plan, s, self.now)

    def test_static_template_cannot_include_future_identity_or_issued_time(self):
        for location in ("own", "target"):
            for field, value in (("invocation_id", "b" * 32), ("cgroup_inode", 777), ("issued_ns", SECOND)):
                document = copy.deepcopy(self.plan)
                env = document["template"]["supervisor_envelope"] if location == "own" else document["template"]["launcher"]["controller_envelope"]
                (env if field == "issued_ns" else env["controller"])[field] = value
                raw = r.encoded(document, r.LIMIT)
                with self.subTest(location=location, field=field), self.assertRaises(ValueError): r.decode(raw, r.sha(raw))

    def test_one_clock_issues_both_deadlines_without_modifying_original_plan(self):
        before = copy.deepcopy(self.plan); issued = self.issue()
        self.assertEqual(before, self.plan)
        self.assertEqual(102 * SECOND, issued["fixture"]["supervisor_envelope"]["deadline_ns"])
        self.assertEqual(87 * SECOND, issued["fixture"]["launcher"]["controller_envelope"]["deadline_ns"])
        raw = r.encoded(issued, r.LIMIT)
        self.assertEqual(issued, r.envelope(raw, r.sha(raw), s))

    def test_bound_envelope_cannot_refresh_time_or_change_static_target(self):
        for field in ("deadline", "target"):
            issued = self.issue()
            if field == "deadline": issued["fixture"]["supervisor_envelope"]["deadline_ns"] += 1
            if field == "target": issued["fixture"]["launcher"]["controller_envelope"]["controller"]["tasks_max"] += 1
            raw = r.encoded(issued, r.LIMIT)
            with self.subTest(field=field), self.assertRaises(ValueError): r.envelope(raw, r.sha(raw), s)

    def test_expired_or_different_boot_owner_never_resets_clock(self):
        for now in (dict(boot_id=BOOT, boottime_ns=120 * SECOND), dict(boot_id="bad", boottime_ns=2 * SECOND)):
            with mock.patch.object(budget, "current_clock", return_value=now), self.assertRaises(ValueError): r.clock(self.plan)
        self.now["boottime_ns"] = 118 * SECOND
        with self.assertRaisesRegex(ValueError, "HANDOFF_ORIGINAL_CLEANUP_BUDGET"): self.issue()

    def test_independent_endpoint_is_included_in_combined_capacity(self):
        value = self.issue()
        with mock.patch.object(budget, "current_clock", return_value=self.now):
            bound = r.binding(value, s, launcher)
        self.assertEqual(bound["totals"]["cpu_ns"] + 10 * SECOND, bound["costs_with_owner"]["cpu_ns"])
        self.assertEqual(bound["totals"]["output_bytes"] + 69632, bound["costs_with_owner"]["output_bytes"])
        self.plan["owner_envelope"]["memory_bytes"] = 1024**3
        with mock.patch.object(budget, "current_clock", return_value=self.now), self.assertRaisesRegex(ValueError, "HANDOFF_COMBINED_CAPACITY"):
            r.binding(self.issue(), s, launcher)

    def test_outer_paths_cannot_alias_child_output_or_each_other(self):
        for field in ("path", "inode"):
            self.plan = plan()
            self.plan["output"][field] = self.plan["declarations"][field]
            with mock.patch.object(budget, "current_clock", return_value=self.now), self.assertRaises(ValueError):
                r.binding(self.issue(), s, launcher)

    def test_original_command_targets_only_pinned_binder(self):
        value = self.issue()
        with mock.patch.object(budget, "current_clock", return_value=self.now):
            bound = r.binding(value, s, launcher)
        command = r.command(value, s, bound, PATH.parents[2], "/owner/envelope.json", "f" * 64)
        self.assertIn("--wait", command); self.assertIn("--pipe", command)
        self.assertIn("--property=Restart=no", command)
        self.assertIn("--property=RemainAfterExit=no", command)
        self.assertIn("--unit=lhqsupervisor.service", command)
        self.assertEqual(["--bind", "--envelope", "/owner/envelope.json", "--sha256", "f" * 64], command[-5:])
        self.assertNotIn("--controller", command)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux actual descriptor identity model")
class SamePidTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan(); self.now = dict(boot_id=BOOT, boottime_ns=2 * SECOND)
        self.value = r.issue(self.plan, s, self.now)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bind(self, pid=None, invocation="c" * 32):
        actual_pid = os.getpid() if pid is None else pid
        def admission(value, ignored):
            return dict(pid=actual_pid, controller=value["supervisor_envelope"]["controller"], boot_id=BOOT)
        with mock.patch.object(budget, "current_clock", return_value=self.now), \
             mock.patch.object(systemd_runtime, "_own_cgroup", return_value=self.value["fixture"]["supervisor_envelope"]["controller"]["cgroup"]), \
             mock.patch.object(protected_inputs, "open_protected", side_effect=lambda *_a, **_k: os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)), \
             mock.patch.dict(os.environ, INVOCATION_ID=invocation), \
             mock.patch.object(s, "validate", return_value={}), mock.patch.object(s, "admit", side_effect=admission):
            return r.same_pid_bind(self.value, s, launcher)

    def test_current_pid_cgroup_inode_and_invocation_are_bound_without_time_change(self):
        bound, observed = self.bind()
        self.assertEqual(os.getpid(), observed["pid"])
        self.assertEqual(self.root.stat().st_ino, observed["cgroup_inode"])
        self.assertEqual("c" * 32, observed["invocation_id"])
        for name in ("issued_ns", "deadline_ns", "storage_bytes", "output_bytes"):
            self.assertEqual(self.value["fixture"]["supervisor_envelope"][name], bound["supervisor_envelope"][name])
        self.assertEqual(self.value["fixture"]["launcher"], bound["launcher"])
        self.assertFalse(r.DYNAMIC.intersection(self.value["fixture"]["supervisor_envelope"]["controller"]))

    def test_different_mainpid_or_missing_invocation_never_bind(self):
        with self.assertRaisesRegex(ValueError, "HANDOFF_MAINPID_CHANGED"): self.bind(pid=os.getpid() + 1)
        with self.assertRaises(Exception): self.bind(invocation="")

    def test_create_only_marker_is_atomic_and_failure_does_not_overwrite(self):
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            r.publish(fd, "result.json", b"original\n", launcher)
            self.assertEqual(b"original\n", (self.root / "result.json").read_bytes())
            with self.assertRaises(FileExistsError): r.publish(fd, "result.json", b"replacement\n", launcher)
            self.assertEqual(b"original\n", (self.root / "result.json").read_bytes())
            self.assertEqual(b"replacement\n", (self.root / "result.json.pending").read_bytes())
        finally: os.close(fd)

    def test_checker_and_supervisor_execute_in_same_original_pid_without_process_creation(self):
        original = dict(pid=os.getpid(), invocation_id="c" * 32, cgroup_device=22, cgroup_inode=77)
        checker = mock.Mock(); calls = []
        checker.check.side_effect = lambda *_a, **_k: calls.append(("check", os.getpid())) or {"status": "CHECKED"}
        bound = copy.deepcopy(self.value["fixture"])
        bound["supervisor_envelope"]["controller"].update({key: original[key] for key in r.DYNAMIC})
        result = dict(status="CONTROLLER_CLOSED", sealed=True)
        event = mock.Mock(); event.is_set.return_value = False; event.wait.return_value = True
        with mock.patch.object(r, "same_pid_bind", return_value=(bound, original)), \
             mock.patch.object(q2_config, "pinned_directory", side_effect=lambda _: os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)), \
             mock.patch.object(r, "clock", return_value=self.now), \
             mock.patch.object(r.threading, "Event", return_value=event), \
             mock.patch.object(s, "supervise", side_effect=lambda *_a: calls.append(("supervise", os.getpid())) or result), \
             mock.patch.object(r.subprocess, "Popen", side_effect=AssertionError("new process")), mock.patch("builtins.print"):
            self.assertEqual(0, r.bound_role(self.value, s, checker, launcher, PATH.parents[2]))
        self.assertEqual([("check", original["pid"]), ("supervise", original["pid"])], calls)
        self.assertEqual(bound, checker.check.call_args.kwargs["admitted"][0])
        marker = json.loads((self.root / "supervisor-result.json").read_bytes())
        self.assertEqual(original, marker["original"])

    def test_failed_same_pid_fixture_check_never_enters_supervisor_and_retains_check(self):
        original = dict(pid=os.getpid(), invocation_id="c" * 32, cgroup_device=22, cgroup_inode=77)
        checker = mock.Mock(); checker.check.return_value = {"status": "BLOCKED"}
        with mock.patch.object(r, "same_pid_bind", return_value=(self.value["fixture"], original)), \
             mock.patch.object(q2_config, "pinned_directory", side_effect=lambda _: os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)), \
             mock.patch.object(s, "supervise") as supervise:
            with self.assertRaisesRegex(ValueError, "HANDOFF_FIXTURE_NOT_CHECKED"):
                r.bound_role(self.value, s, checker, launcher, PATH.parents[2])
        supervise.assert_not_called()
        self.assertEqual({"status": "BLOCKED"}, json.loads((self.root / "fixture-check.json").read_bytes()))
        self.assertFalse((self.root / "supervisor-result.json").exists())


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux original anonymous pipes")
class OriginalClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = plan()
        now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        self.plan["owner_envelope"].update(issued_ns=now, deadline_ns=now + 119 * SECOND)
        for name in ("output", "declarations"):
            path = self.root / name; path.mkdir(mode=0o700)
            info = path.stat(); self.plan[name] = dict(path=str(path), device=info.st_dev, inode=info.st_ino)
        self.processes = []; self.original = None; self.child_marker = None; self.fault = None
        self.controls = mock.Mock()
        self.controls.empty.return_value = True
        self.controls.calls = []
        self.controls.evidence.return_value = []
        self.controls.show.return_value = dict(Id="lhqsupervisor.service", LoadState="not-found", Job="")
        self.real_popen = subprocess.Popen
        self.real_save = launcher.save

    def start(self, argv, **kwargs):
        summary = json.dumps(dict(schema=r.RESULT_SCHEMA, status="CONTROLLER_CLOSED", q3_accepted=False, production_supported=False))
        exit_code = 7 if self.fault == "nonzero" else 0
        code = "import signal,time,pathlib,os\ndef stop(*_):\n"
        if self.fault == "missing_eof":
            code += " if os.fork()==0:\n  time.sleep(.25)\n  os._exit(0)\n"
        code += " raise SystemExit(" + str(exit_code) + ")\nsignal.signal(signal.SIGTERM,stop)\nprint(" + repr(summary) + ",flush=True)\npathlib.Path(" + repr(str(self.root / "ready")) + ").write_text('ready')\nwhile True:time.sleep(.01)"
        process = self.real_popen([sys.executable, "-u", "-c", code], **kwargs)
        self.processes.append(process)
        return process

    def observe(self, controls, static, process, end):
        self.original = dict(invocation_id="c" * 32, pid=process.pid, cgroup_device=22, cgroup_inode=66)
        return self.original

    def child(self, value, original, tool):
        if not (self.root / "ready").exists(): return None
        declaration = Path(self.plan["declarations"]["path"])
        for name in ("bound-supervisor.json", "fixture-check.json", "supervisor-result.json"):
            if not (declaration / name).exists(): (declaration / name).write_bytes(b"{}\n")
        return dict(result=dict(status="CONTROLLER_CLOSED", sealed=self.fault != "unsealed"))

    def stop(self, controls, static, original, end, record):
        record.update(attempted=True, complete=True, parent_empty=True)
        if self.fault == "pending":
            record.pop("complete")
            self.processes[0].send_signal(signal.SIGTERM)
            raise ValueError("SUPERVISOR_STOP_PENDING")
        self.processes[0].send_signal(signal.SIGTERM)

    def run_model(self):
        def directory(pin, mode):
            fd = os.open(pin["path"], os.O_RDONLY | os.O_DIRECTORY)
            if os.listdir(fd):
                os.close(fd); raise ValueError("LAUNCHER_ALREADY_CONSUMED")
            return fd
        def current_clock():
            if self.fault == "missing_eof" and self.processes and self.processes[0].poll() is not None:
                return dict(boot_id=BOOT, boottime_ns=self.plan["owner_envelope"]["deadline_ns"])
            return dict(boot_id=BOOT, boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME))
        def save(fd, name, raw, mode=0o600):
            if self.fault == "reservation_race" and name == "reservation.json":
                self.real_save(fd, name, b"other-original-owner\n", mode)
                raise FileExistsError(name)
            self.real_save(fd, name, raw, mode)
        patches = [mock.patch.object(budget, "current_clock", side_effect=current_clock),
            mock.patch.object(r, "binding", return_value=dict(installation={}, costs_with_owner={})),
            mock.patch.object(r, "owner_identity", return_value=dict(pid=os.getpid(), owner_self_exit_verified=False)),
            mock.patch.object(s, "Controls", return_value=self.controls),
            mock.patch.object(launcher, "directory", side_effect=directory),
            mock.patch.object(launcher, "save", side_effect=save),
            mock.patch.object(launcher, "protected", side_effect=lambda path, limit: Path(path).read_bytes()),
            mock.patch.object(r, "command", return_value=["modeled-systemd-run"]),
            mock.patch.object(r, "subprocess", SimpleNamespace(Popen=self.start, DEVNULL=subprocess.DEVNULL, PIPE=subprocess.PIPE)),
            mock.patch.object(s, "observe_start", side_effect=self.observe),
            mock.patch.object(r, "marker", side_effect=self.child),
            mock.patch.object(s, "stop_original", side_effect=self.stop)]
        import contextlib
        with contextlib.ExitStack() as stack:
            for patch in patches: stack.enter_context(patch)
            try:
                return r.run_original(self.plan, PATH.parents[2], loaded=(s, mock.Mock(), launcher))
            finally:
                for process in self.processes:
                    if process.poll() is None: process.kill()
                    process.wait(timeout=5)

    def test_original_client_actual_exit_and_both_eof_are_retained_before_seal(self):
        result = self.run_model()
        self.assertEqual("SUPERVISOR_CLOSED", result["status"], result)
        self.assertTrue(result["sealed"]); self.assertFalse(result["owner_self_exit_verified"])
        output = Path(self.plan["output"]["path"])
        capture = json.loads((output / "capture.json").read_bytes())
        self.assertTrue(capture["complete"])
        self.assertEqual(0, capture["returncode"])
        self.assertEqual(["stderr", "stdout"], capture["eof"])
        self.assertEqual(self.processes[0].pid, capture["client_pid"])
        self.assertNotEqual(capture["pipe_identities"]["stdout"], capture["pipe_identities"]["stderr"])
        self.assertTrue((output / "seal.json").exists())
        # Same declared path cannot start a replacement or erase old records.
        before = (output / "reservation.json").read_bytes()
        again = self.run_model()
        self.assertEqual("BLOCKED", again["status"])
        self.assertEqual(1, len(self.processes))
        self.assertEqual(before, (output / "reservation.json").read_bytes())

    def test_unsealed_child_result_cannot_become_completed_handoff(self):
        self.fault = "unsealed"
        result = self.run_model()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("HANDOFF_SUPERVISOR_NOT_CLOSED", result["reason"])
        self.assertFalse((Path(self.plan["output"]["path"]) / "seal.json").exists())
        self.assertEqual(1, len(self.processes))

    def test_actual_nonzero_client_cannot_be_replaced_by_successful_marker(self):
        self.fault = "nonzero"
        result = self.run_model()
        self.assertEqual("INCOMPLETE", result["status"])
        output = Path(self.plan["output"]["path"])
        captured = json.loads((output / "capture.json").read_bytes())
        self.assertEqual(7, captured["returncode"])
        self.assertTrue(captured["complete"])
        self.assertFalse((output / "seal.json").exists())

    def test_missing_eof_at_original_deadline_retains_incomplete_with_no_seal(self):
        self.fault = "missing_eof"
        result = self.run_model()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertFalse(result["sealed"])
        self.assertFalse((Path(self.plan["output"]["path"]) / "seal.json").exists())

    def test_pending_stop_retains_actual_client_streams_without_acceptance(self):
        self.fault = "pending"
        result = self.run_model()
        self.assertEqual("INCOMPLETE", result["status"])
        output = Path(self.plan["output"]["path"])
        self.assertIn(b"CONTROLLER_CLOSED", (output / "supervisor.stdout").read_bytes())
        self.assertFalse((output / "seal.json").exists())
        stop = json.loads((output / "stop.json").read_bytes())
        self.assertNotIn("complete", stop)

    def test_concurrent_reservation_loser_cannot_write_into_original_owner_record(self):
        self.fault = "reservation_race"
        result = self.run_model()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual([], self.processes)
        output = Path(self.plan["output"]["path"])
        self.assertEqual(["reservation.json"], [path.name for path in output.iterdir()])
        self.assertEqual(b"other-original-owner\n", (output / "reservation.json").read_bytes())

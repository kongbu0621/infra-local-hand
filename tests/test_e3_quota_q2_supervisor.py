"""Modeled systemd authority with real files, anonymous pipes and client exit.

These tests never create services, cgroups, accounts or quota fixtures. Real
subprocesses test the original capture/stop ordering; host identity, manager
observations and dedicated-parent facts are explicitly modeled. No Q3 claim.
"""
import copy
import hashlib
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

PATH = Path(__file__).parent / "e3_host" / "q2_supervisor.py"
spec = importlib.util.spec_from_file_location("_q2_supervisor_tests", PATH)
s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
spec = importlib.util.spec_from_file_location("_q2_supervisor_launcher_tests", PATH.with_name("q2_launcher.py"))
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)

if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import controller_guard as guard
    from local_hand_jobs import budget, quota_grant as g
    from q2_fixtures import BOOT, SECOND
    from test_e3_quota_controller_guard import controller_value, properties
    from test_e3_quota_q2_assembly import declaration_template


def fixture():
    assembly, _ = declaration_template()
    capacity = assembly["installation"]["capacity"]
    capacity["management"]["cpu_ns"] = 500 * SECOND
    assembly["grant"]["management"]["capacity_digest"] = g.digest(capacity)
    target = controller_value()
    target.update(unit="lhqfixturecontroller.service", cgroup="/lhqoutertarget.slice/lhqfixturecontroller.service")
    static = {key: val for key, val in target.items() if key not in s.DYNAMIC}
    own = dict(target, unit="lhqsupervisor.service", cgroup="/lhqsupervisor.slice/lhqsupervisor.service",
               runtime_max_usec=120_000_000, cgroup_inode=100)
    envelope = dict(controller=static, issued_ns=SECOND, deadline_ns=80 * SECOND,
                    output_bytes=32768, storage_bytes=1024**2, storage_inodes=9)
    nested = dict(schema=launcher.SCHEMA, purpose="ISOLATED_Q2_PREFLIGHT", source={}, assembly=assembly,
        controller_envelope=envelope, session="a" * 64, setpriv=dict(path="/usr/bin/setpriv", sha256="f"*64),
        output=dict(path="/synthetic/launcher-output", device=70, inode=701),
        declarations=dict(path="/synthetic/launcher-declarations", device=70, inode=702),
        resident=dict(ordinary=dict(parent=copy.deepcopy(assembly["peer"]["parent"])),
            installation=dict(package_root="/synthetic/wheel", programs={}),
            entry=dict(path="/synthetic/source/tests/e3_host/q2_resident.py")))
    return dict(schema=s.SCHEMA, purpose="ISOLATED_Q2_SUPERVISION", launcher=nested,
        controller_parent=dict(path="/lhqoutertarget.slice", device=22, inode=400),
        supervisor_envelope=dict(envelope, controller=own, deadline_ns=101*SECOND, storage_bytes=8*1024**2, storage_inodes=16),
        output=dict(path="/supervisor-output", device=70, inode=703),
        declarations=dict(path="/supervisor-declarations", device=70, inode=704))


def running(value):
    spec = s.candidate(value["launcher"]["controller_envelope"]["controller"])
    spec = guard.decode_controller(dict(value["launcher"]["controller_envelope"]["controller"],
        invocation_id="c" * 32, cgroup_device=22, cgroup_inode=45))
    facts = properties(spec)
    facts.update(Slice=Path(spec.cgroup).parent.name, ExecStartPre="", ExecMainCode="0", ExecMainStatus="0",
                 Result="success", User="root", Group="root", NoNewPrivileges="yes",
                 CapabilityBoundingSet=s.CAPABILITIES.lower(), AmbientCapabilities="")
    return facts


class DefaultEntryTests(unittest.TestCase):
    def test_real_entry_without_explicit_fixture_is_blocked(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(PATH)], capture_output=True, timeout=10)
        self.assertEqual(3, result.returncode)
        value = json.loads(result.stdout)
        self.assertEqual("BLOCKED", value["status"])
        self.assertEqual("EXPLICIT_PRIVATE_FIXTURE_REQUIRED", value["reason"])
        self.assertFalse(value["q3_accepted"])
        self.assertFalse(value["production_supported"])
        self.assertTrue(value["independent_supervisor_stop_required"])
        self.assertEqual(b"", result.stderr)

    def test_version_determines_required_phase_closure(self):
        self.assertEqual("PREFLIGHT_CLOSED", s.expected_status(dict(schema="local-hand-q2-launcher/v1", purpose="ISOLATED_Q2_PREFLIGHT")))
        self.assertEqual("CHAIN_CLOSED", s.expected_status(dict(schema="local-hand-q2-launcher/v2", purpose="ISOLATED_Q2_CHAIN")))
        with self.assertRaises(ValueError):
            s.expected_status(dict(schema="local-hand-q2-launcher/v2", purpose="ISOLATED_Q2_PREFLIGHT"))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux supervisor fixture declarations")
class DeclarationTests(unittest.TestCase):
    def setUp(self):
        self.value = fixture()
        self.clock = dict(boot_id=BOOT, boottime_ns=2*SECOND)

    def validate(self):
        return s.validate(self.value, launcher, self.clock)

    def test_both_controllers_and_all_management_are_charged_before_host_io(self):
        with mock.patch.object(s, "admit", side_effect=AssertionError("host read")):
            binding = self.validate()
        declared = self.value["launcher"]["assembly"]["grant"]["management"]
        self.assertEqual(declared["storage_bytes"] + 9*1024**2, binding["totals"]["storage_bytes"])
        self.assertGreater(binding["totals"]["cpu_ns"], 200*SECOND)
        self.assertEqual(sum(x["output_bytes"] for x in declared["stages"].values()) + 5*32768 + 8192,
                         binding["totals"]["output_bytes"])

    def test_unfunded_outer_is_refused_before_directory_or_spawn(self):
        cap = self.value["launcher"]["assembly"]["installation"]["capacity"]
        cap["management"]["cpu_ns"] = 100*SECOND
        self.value["launcher"]["assembly"]["grant"]["management"]["capacity_digest"] = g.digest(cap)
        with mock.patch.object(launcher, "directory", side_effect=AssertionError("mutation")), \
             mock.patch.object(s.subprocess, "Popen", side_effect=AssertionError("spawn")), \
             mock.patch.object(budget, "current_clock", return_value=self.clock):
            result = s.supervise(self.value, launcher, PATH.parents[2])
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual("SUPERVISOR_COMBINED_CAPACITY", result["reason"])

    def test_clock_parent_storage_and_output_geometry_refuse(self):
        for fault in ("cleanup", "source", "slot", "alias", "own_parent", "target_parent", "storage"):
            self.value = fixture()
            if fault == "cleanup": self.value["supervisor_envelope"]["deadline_ns"] = 81*SECOND
            if fault == "source": self.value["output"]["path"] = self.value["launcher"]["resident"]["installation"]["package_root"] + "/new"
            if fault == "slot": self.value["output"]["path"] = next(iter(self.value["launcher"]["assembly"]["grant"]["allocation"]["paths"])) + "/new"
            if fault == "alias": self.value["output"]["inode"] = self.value["launcher"]["output"]["inode"]
            if fault == "own_parent": self.value["supervisor_envelope"]["controller"]["cgroup"] = "/lhqoutertarget.slice/lhqsupervisor.service"
            if fault == "target_parent": self.value["controller_parent"]["path"] = "/other.slice"
            if fault == "storage": self.value["supervisor_envelope"]["storage_bytes"] -= 1
            with self.subTest(fault=fault), self.assertRaises(ValueError): self.validate()

    def test_dynamic_target_identity_cannot_be_supplied_as_prior_authority(self):
        self.value["launcher"]["controller_envelope"]["controller"]["invocation_id"] = "c" * 32
        with self.assertRaisesRegex(ValueError, "SUPERVISOR_STATIC_CONTROLLER"): self.validate()

    def test_chain_counts_all_three_management_and_control_capture_budgets(self):
        from test_e3_quota_q2_chain import declaration_chain
        chain, _ = declaration_chain()
        cap = chain["installation"]["capacity"]
        cap["management"]["cpu_ns"] = 500*SECOND
        for item in chain["phases"].values(): item["grant"]["management"]["capacity_digest"] = g.digest(cap)
        self.value["launcher"].update(schema="local-hand-q2-launcher/v2", purpose="ISOLATED_Q2_CHAIN", assembly=chain)
        binding = self.validate()
        total_output = sum(stage["output_bytes"] for item in chain["phases"].values()
                           for stage in item["grant"]["management"]["stages"].values())
        self.assertEqual(total_output + 7*32768 + 8192, binding["totals"]["output_bytes"])
        self.value["launcher"]["controller_envelope"]["storage_inodes"] = 8
        with self.assertRaises(ValueError): self.validate()

    def test_fixed_command_has_no_shell_or_provisioning_and_no_restart(self):
        argv = s.command(self.value, self.validate(), PATH.parents[2], "/fixed/fixture.json", "a"*64)
        self.assertIn("--pipe", argv); self.assertIn("--wait", argv)
        self.assertIn("--property=Restart=no", argv)
        self.assertIn("--property=ExitType=cgroup", argv)
        self.assertIn("--property=RemainAfterExit=no", argv)
        self.assertIn("--property=NoNewPrivileges=yes", argv)
        self.assertIn("--property=CapabilityBoundingSet=" + s.CAPABILITIES, argv)
        self.assertIn("--property=Slice=lhqoutertarget.slice", argv)
        self.assertNotIn("--collect", argv)
        self.assertEqual(["--controller", "--fixture", "/fixed/fixture.json", "--sha256", "a"*64], argv[-5:])
        self.assertFalse(any("/bin/sh" in arg or "useradd" in arg or "setquota" in arg for arg in argv))

    def test_duplicate_extra_numbers_and_wrong_hash_are_rejected(self):
        original = s.encoded(self.value, s.LIMIT)
        self.assertEqual(self.value, s.decode(original, s.sha(original)))
        values = [original.rstrip()[:-1] + b',"schema":"other"}', b'{"value":NaN}', b' '*(s.LIMIT+1)]
        extra = copy.deepcopy(self.value); extra["expected_status"] = "anything"; values.append(s.encoded(extra, s.LIMIT))
        for raw in values:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError): s.decode(raw, s.sha(raw))
        with self.assertRaises(ValueError): s.decode(original, "0"*64)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux original service model")
class StopProofTests(unittest.TestCase):
    def setUp(self):
        self.value = fixture(); self.facts = running(self.value)
        self.original = dict(invocation_id="c"*32, pid=4242, cgroup_device=22, cgroup_inode=45)
        self.commands = []; self.record = {}
        self.after = dict(self.facts, ActiveState="inactive", SubState="dead", MainPID="0", ControlGroup="")
        self.empty = True
        self.controls = mock.Mock()
        self.controls.show.side_effect = lambda end: copy.deepcopy(self.after if self.commands else self.facts)
        self.controls.call.side_effect = lambda arguments, end: self.commands.append(arguments)
        self.controls.empty.side_effect = lambda: self.empty
        self.controls.clock.return_value = 3*SECOND

    def stop(self):
        with mock.patch.object(guard, "_cgroup_identity"):
            return s.stop_original(self.controls, self.value["launcher"]["controller_envelope"]["controller"],
                                   self.original, 100*SECOND, self.record)

    def test_original_instance_stop_plus_no_job_and_empty_parent_are_all_required(self):
        self.stop()
        self.assertEqual([("stop", self.facts["Id"])], self.commands)
        self.assertTrue(self.record["complete"])
        with self.assertRaises(ValueError): self.stop()
        self.assertEqual(1, len(self.commands))

    def test_foreign_invocation_or_pid_never_receives_stop(self):
        for key, value in (("InvocationID", "f"*32), ("MainPID", "123")):
            previous = self.facts[key]; self.facts[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.stop()
            self.facts[key] = previous
        self.assertEqual([], self.commands)
        self.assertNotIn("attempted", self.record)

    def test_acknowledged_stop_with_descendant_or_pending_job_is_not_a_proof(self):
        for fault in ("descendant", "job", "replacement"):
            self.setUp()
            if fault == "descendant": self.empty = False
            if fault == "job": self.after["Job"] = "777"
            if fault == "replacement": self.after["InvocationID"] = "f" * 32
            with self.subTest(fault=fault), self.assertRaises(ValueError): self.stop()
            self.assertTrue(self.record["acknowledged"])
            self.assertNotIn("complete", self.record)
            self.assertEqual(1, len(self.commands))

    def test_disappearance_is_allowed_only_after_original_stop_not_as_its_substitute(self):
        self.facts["LoadState"] = "not-found"
        with self.assertRaises(ValueError): self.stop()
        self.assertEqual([], self.commands)
        self.facts["LoadState"] = "loaded"
        self.after.update(LoadState="not-found", InvocationID="")
        self.stop(); self.assertTrue(self.record["complete"])

    def test_capability_or_hook_expansion_is_not_original_controller(self):
        for key, value in (("ExecStartPre", "/bin/other"), ("AmbientCapabilities", "cap_sys_admin"),
                           ("CapabilityBoundingSet", s.CAPABILITIES.lower() + " cap_sys_ptrace"), ("NoNewPrivileges", "no")):
            before = self.facts[key]; self.facts[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.stop()
            self.facts[key] = before
        self.assertEqual([], self.commands)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux atomic result publication")
class PublicationTests(unittest.TestCase):
    def test_complete_marker_is_atomic_and_cannot_replace_existing_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                raw = b'{"finite":"complete"}\n'
                s.publish_marker(fd, raw, launcher)
                self.assertEqual(raw, (Path(directory)/"controller-result.json").read_bytes())
                self.assertFalse((Path(directory)/"controller-result.pending").exists())
                with self.assertRaises(FileExistsError): s.publish_marker(fd, b"replacement", launcher)
                self.assertEqual(raw, (Path(directory)/"controller-result.json").read_bytes())
                self.assertEqual(b"replacement", (Path(directory)/"controller-result.pending").read_bytes())
            finally: os.close(fd)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux actual original pipe/client lifecycle")
class OriginalCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.value = fixture()
        self.binding = s.validate(self.value, launcher, dict(boot_id=BOOT, boottime_ns=2*SECOND))
        clock = budget.current_clock(); self.binding["boot_id"] = clock["boot_id"]
        for key, offset in (("controller_envelope", 4),):
            self.value["launcher"][key].update(issued_ns=clock["boottime_ns"], deadline_ns=clock["boottime_ns"]+offset*SECOND)
        self.value["supervisor_envelope"].update(issued_ns=clock["boottime_ns"], deadline_ns=clock["boottime_ns"]+8*SECOND)
        for key in ("output", "declarations"):
            path = self.root/key; path.mkdir(mode=0o700)
            info = path.stat(); self.value[key] = dict(path=str(path), device=info.st_dev, inode=info.st_ino)
        self.facts = running(self.value)
        self.foreign = False; self.overflow = False; self.fail_seal = False; self.changed_tree = False
        self.model = None

    def invoke(self):
        test = self
        original_save = launcher.save
        def save(directory, name, raw, mode=0o600):
            if name == "seal.json" and test.fail_seal: raise OSError("modeled seal fsync failure")
            return original_save(directory, name, raw, mode)
        def directory(pin, mode):
            fd = os.open(pin["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                info = os.fstat(fd)
                s.require((info.st_dev, info.st_ino, info.st_mode & 0o777) ==
                          (pin["device"], pin["inode"], mode), "MODELED_DIRECTORY_CHANGED")
                s.require(not os.listdir(fd), "LAUNCHER_ALREADY_CONSUMED")
                return fd
            except Exception: os.close(fd); raise
        def protected(path, maximum):
            raw = Path(path).read_bytes()
            s.require(len(raw) <= maximum, "MODELED_FILE_LIMIT")
            return raw
        def command(*args):
            summary = dict(schema="local-hand-q2-launcher-result/v1", status="PREFLIGHT_CLOSED", q3_accepted=False,
                           production_supported=False, independent_controller_stop_required=True)
            marker = dict(schema="local-hand-q2-controller-result/v1", fixture_sha256=s.sha(s.encoded(test.value,s.LIMIT)),
                controller=dict(invocation_id=("f" if test.foreign else "c")*32, pid=0, cgroup_device=22, cgroup_inode=45),
                result=summary, completed_ns=0)
            script = """
import json, os, pathlib, signal, sys, time
signal.signal(signal.SIGTERM, lambda *unused: sys.exit(0))
path = pathlib.Path(sys.argv[1]); marker = json.loads(sys.argv[2])
marker['controller']['pid'] = os.getpid()
marker['completed_ns'] = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
print(json.dumps(marker['result']), flush=True)
if sys.argv[3] == 'yes': print('x' * 40000, flush=True)
temporary = path.with_suffix('.pending')
temporary.write_text(json.dumps(marker))
os.rename(temporary, path)
while True: time.sleep(.01)
"""
            return [sys.executable, "-I", "-B", "-c", script,
                    test.value["declarations"]["path"] + "/controller-result.json", json.dumps(marker),
                    "yes" if test.overflow else "no"]
        class Controls:
            def __init__(self, *_):
                self.calls = []; self.shown = False; self.stopped = False; self.empties = 0; test.model = self
            def clock(self, end):
                now = budget.current_clock()["boottime_ns"]
                s.require(now < end, "SUPERVISOR_DEADLINE_OR_BOOT")
                return now
            def show(self, end):
                if not self.shown:
                    self.shown = True
                    return dict(test.facts, LoadState="not-found", InvocationID="", MainPID="0")
                marker = Path(test.value["declarations"]["path"])/"controller-result.json"
                while not marker.exists(): self.clock(end); time.sleep(.005)
                actual = json.loads(marker.read_bytes())["controller"]["pid"]
                test.facts["MainPID"] = str(actual)
                return dict(test.facts, MainPID="0", ActiveState="inactive", SubState="dead", ControlGroup="") if self.stopped else dict(test.facts)
            def call(self, arguments, end):
                self.clock(end)
                test.assertEqual(("stop", test.facts["Id"]), arguments)
                self.calls.append((arguments, SimpleNamespace(done=True)))
                os.kill(int(test.facts["MainPID"]), signal.SIGTERM)
                self.stopped = True
            def empty(self):
                self.empties += 1
                return not (test.changed_tree and self.empties >= 4)
            def evidence(self): return [dict(arguments=list(args), complete=cap.done) for args, cap in self.calls]
        patches = [mock.patch.object(s, "validate", return_value=self.binding), mock.patch.object(s, "admit", return_value={"modeled": True}),
            mock.patch.object(s, "Controls", Controls), mock.patch.object(s, "command", side_effect=command),
            mock.patch.object(s, "observe_identity", side_effect=lambda facts, static: dict(invocation_id="c"*32,
                pid=int(facts["MainPID"]), cgroup_device=22, cgroup_inode=45)),
            mock.patch.object(guard, "_cgroup_identity"), mock.patch.object(launcher, "directory", side_effect=directory),
            mock.patch.object(launcher, "protected", side_effect=protected), mock.patch.object(launcher, "save", side_effect=save)]
        for patch in patches: patch.start()
        try: return s.supervise(self.value, launcher, PATH.parents[2])
        finally:
            for patch in reversed(patches): patch.stop()

    def test_real_client_exit_both_eofs_and_independent_stop_produce_scoped_seal(self):
        result = self.invoke()
        self.assertEqual("CONTROLLER_CLOSED", result["status"], result)
        self.assertTrue(result["sealed"])
        self.assertTrue(result["independent_supervisor_stop_required"])
        capture = json.loads((self.root/"output/capture.json").read_bytes())
        self.assertTrue(capture["complete"])
        self.assertEqual(["stderr", "stdout"], capture["eof"])
        self.assertEqual(0, capture["returncode"])
        self.assertEqual(1, len(self.model.calls))
        provisional = json.loads((self.root/"output/result.json").read_bytes())
        self.assertEqual("CLOSURE_OBSERVED_SEAL_PENDING", provisional["status"])
        self.assertFalse(provisional["sealed"])
        seal = json.loads((self.root/"output/seal.json").read_bytes())
        self.assertEqual("TARGET_CONTROLLER_CLOSURE_ONLY", seal["scope"])
        self.assertFalse(seal["q3_accepted"])
        for filename, pin in seal["files"].items():
            raw = Path(filename).read_bytes()
            self.assertEqual(dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()), pin)

    def test_foreign_completion_marker_is_retained_but_never_sealed(self):
        self.foreign = True
        result = self.invoke()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("SUPERVISOR_RESULT_BINDING", result["reason"])
        self.assertEqual(1, len(self.model.calls))
        self.assertFalse((self.root/"output/seal.json").exists())
        self.assertTrue((self.root/"output/capture.json").exists())

    def test_seal_write_failure_leaves_explicit_provisional_result(self):
        self.fail_seal = True
        result = self.invoke()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertFalse(result["sealed"])
        self.assertEqual("SUPERVISOR_SEAL_UNPROVEN", result["reason"])
        self.assertFalse((self.root/"output/seal.json").exists())
        self.assertEqual("CLOSURE_OBSERVED_SEAL_PENDING", json.loads((self.root/"output/result.json").read_bytes())["status"])

    def test_parent_repopulation_before_seal_cannot_be_accepted(self):
        self.changed_tree = True
        result = self.invoke()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertFalse(result["sealed"])
        self.assertFalse((self.root/"output/seal.json").exists())

    def test_consumed_output_prevents_second_delivery_and_preserves_all_bytes(self):
        result = self.invoke()
        self.assertEqual("CONTROLLER_CLOSED", result["status"], result)
        retained = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        result = self.invoke()
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual("LAUNCHER_ALREADY_CONSUMED", result["reason"])
        self.assertEqual([], self.model.calls)
        self.assertEqual(retained, {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()})

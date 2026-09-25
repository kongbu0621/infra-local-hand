"""Offline real-file checks; system manager and host authority are modeled.

The accepted bundle is emitted by the actual supervisor with a real child,
anonymous pipes, SIGTERM and EOF. No service/cgroup/account/quota is created.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

PATH = Path(__file__).parent / "e3_host/q2_evidence_review.py"
spec = importlib.util.spec_from_file_location("_q2_evidence_review_tests", PATH)
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

if sys.platform.startswith("linux"):
    from test_e3_quota_q2_supervisor import s, launcher, fixture, running, BOOT, SECOND, guard, budget


class DefaultTests(unittest.TestCase):
    def test_actual_default_entry_is_bounded_blocked_and_does_not_claim_acceptance(self):
        completed = subprocess.run([sys.executable, "-I", "-B", str(PATH)], capture_output=True, timeout=10)
        value = json.loads(completed.stdout)
        self.assertEqual(3, completed.returncode); self.assertEqual(b"", completed.stderr)
        self.assertLess(len(completed.stdout), 4096)
        self.assertEqual("BLOCKED", value["status"])
        self.assertEqual("EXPLICIT_REVIEW_INPUTS_REQUIRED", value["reason"])
        self.assertFalse(value["q3_accepted"]); self.assertFalse(value["production_supported"])
        self.assertTrue(value["independent_supervisor_stop_required"])
        self.assertTrue(value["full_capacity_acceptance_required"])

    def test_invalid_paths_and_hash_are_sanitized_without_reading(self):
        completed = subprocess.run([sys.executable, "-I", "-B", str(PATH), "--evidence", "/secret/name",
            "--declarations", "/another/secret", "--seal-sha256", "bad"], capture_output=True, timeout=10)
        self.assertEqual(3, completed.returncode); self.assertEqual(b"", completed.stderr)
        self.assertNotIn(b"secret", completed.stdout)
        self.assertEqual("INCOMPLETE", json.loads(completed.stdout)["status"])

    def test_duplicate_keys_nonfinite_float_and_deep_structures_fail(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1.2}', b"[" * 40 + b"0" + b"]" * 40):
            with self.subTest(raw=raw), self.assertRaises(ValueError): r.decode(raw)

    def test_unrecognized_cli_arguments_do_not_echo_unbounded_private_text(self):
        completed = subprocess.run([sys.executable, "-I", "-B", str(PATH), "--unknown=" + "private" * 2000],
                                   capture_output=True, timeout=10)
        self.assertEqual(3, completed.returncode); self.assertEqual(b"", completed.stderr)
        self.assertNotIn(b"private", completed.stdout); self.assertLess(len(completed.stdout), 4096)
        self.assertEqual("REVIEW_ARGUMENTS", json.loads(completed.stdout)["reason"])


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux no-follow fd and original process fixture")
class RetainedReviewTests(unittest.TestCase):
    chain = False

    @classmethod
    def setUpClass(cls):
        cls.seed = tempfile.TemporaryDirectory()
        root = Path(cls.seed.name)
        value = fixture()
        if cls.chain:
            from test_e3_quota_q2_chain import declaration_chain
            from local_hand_jobs import quota_grant
            chain, _ = declaration_chain()
            capacity = chain["installation"]["capacity"]; capacity["management"]["cpu_ns"] = 500 * SECOND
            for phase in chain["phases"].values():
                phase["grant"]["management"]["capacity_digest"] = quota_grant.digest(capacity)
            value["launcher"].update(schema="local-hand-q2-launcher/v2", purpose="ISOLATED_Q2_CHAIN", assembly=chain)
        for name in ("output", "declarations"):
            path = root / name; path.mkdir(mode=0o700); info = path.stat()
            value[name] = dict(path=str(path), device=info.st_dev, inode=info.st_ino)
        start = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        value["launcher"]["controller_envelope"].update(issued_ns=start, deadline_ns=start + 4 * SECOND)
        value["supervisor_envelope"].update(issued_ns=start, deadline_ns=start + 8 * SECOND)
        value["supervisor_envelope"]["controller"]["invocation_id"] = "a" * 32
        value["launcher"]["resident"]["entry"]["path"] = str(PATH.with_name("q2_resident.py"))
        binding = s.validate(value, launcher, dict(boot_id=BOOT, boottime_ns=start))
        owner = dict(controller=value["supervisor_envelope"]["controller"], boot_id=BOOT, pid=4241,
                     stdout=[10, 111], stderr=[10, 112])
        initial = running(value)

        def modeled_client():
            script = """
import json, os, pathlib, signal, sys, time
signal.signal(signal.SIGTERM, lambda *unused: sys.exit(0))
directory = pathlib.Path(sys.argv[1]); value = json.loads(sys.argv[2])
identity = dict(invocation_id='c'*32, pid=os.getpid(), cgroup_device=22, cgroup_inode=45)
nested = value['launcher']
nested['controller_envelope']['controller'].update({k: identity[k] for k in ('invocation_id','cgroup_device','cgroup_inode')})
(directory/'launcher.json').write_text(json.dumps(nested,sort_keys=True,separators=(',',':'))+'\\n')
chained=nested['schema']=='local-hand-q2-launcher/v2'
summary=dict(schema='local-hand-q2-launcher-result/v2' if chained else 'local-hand-q2-launcher-result/v1',
             status='CHAIN_CLOSED' if chained else 'PREFLIGHT_CLOSED',q3_accepted=False,
             production_supported=False,independent_controller_stop_required=True)
marker=dict(schema='local-hand-q2-controller-result/v1',fixture_sha256=sys.argv[3],controller=identity,
            result=summary,completed_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME))
print(json.dumps(summary), flush=True)
pending=directory/'controller-result.pending'
pending.write_text(json.dumps(marker,sort_keys=True,separators=(',',':'))+'\\n')
os.rename(pending,directory/'controller-result.json')
while True: time.sleep(.01)
"""
            return [sys.executable, "-I", "-B", "-c", script, value["declarations"]["path"],
                    json.dumps(value), s.sha(s.encoded(value, s.LIMIT))]

        original_popen = subprocess.Popen
        class ModeledManagerClient(original_popen):
            def __init__(self, argv, *args, **kwargs):
                expected = s.command(value, binding, PATH.parents[2], value["declarations"]["path"] + "/supervisor.json",
                                     s.sha(s.encoded(value, s.LIMIT)))
                if argv != expected: raise AssertionError("unexpected fixed producer command")
                super().__init__(modeled_client(), *args, **kwargs)

        class Controls:
            def __init__(self, *_): self.calls = []; self.records = []; self.shown = False; self.stopped = False
            def clock(self, end):
                now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                s.require(now < end, "SUPERVISOR_DEADLINE_OR_BOOT"); return now
            def record(self, arguments, raw):
                self.calls.append((arguments, SimpleNamespace(done=True)))
                self.records.append(dict(arguments=list(arguments), stdout_hex=raw.hex(), stderr_hex="", returncode=0,
                                         eof=["stderr", "stdout"], error=None, complete=True))
            def show(self, end):
                if not self.shown:
                    self.shown = True; facts = dict(initial, LoadState="not-found", InvocationID="", MainPID="0")
                else:
                    marker_path = root / "declarations/controller-result.json"
                    while not marker_path.exists(): self.clock(end); time.sleep(.005)
                    pid = json.loads(marker_path.read_bytes())["controller"]["pid"]
                    initial["MainPID"] = str(pid)
                    facts = dict(initial, MainPID="0", ActiveState="inactive", SubState="dead", ControlGroup="") if self.stopped else dict(initial)
                arguments = ("show", initial["Id"], "--all", "--property=" + ",".join(sorted(facts)))
                raw = "".join(name + "=" + val + "\n" for name, val in facts.items()).encode()
                self.record(arguments, raw)
                return facts
            def call(self, arguments, end):
                self.clock(end)
                if arguments != ("stop", initial["Id"]): raise AssertionError("unexpected modeled command")
                self.record(arguments, b""); os.kill(int(initial["MainPID"]), signal.SIGTERM); self.stopped = True
            def empty(self): return True
            def evidence(self): return copy.deepcopy(self.records)

        def directory(pin, mode):
            fd = os.open(pin["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            if os.listdir(fd): os.close(fd); raise ValueError("TEST_DIRECTORY_OCCUPIED")
            return fd
        def protected(path, maximum):
            raw = Path(path).read_bytes()
            if len(raw) > maximum: raise ValueError("TEST_READ_LIMIT")
            return raw
        patches = [mock.patch.object(s, "validate", return_value=binding), mock.patch.object(s, "admit", return_value=owner),
            mock.patch.object(s, "Controls", Controls), mock.patch.object(s.subprocess, "Popen", ModeledManagerClient),
            mock.patch.object(s, "observe_identity", side_effect=lambda facts, _: dict(invocation_id="c"*32,
                pid=int(facts["MainPID"]), cgroup_device=22, cgroup_inode=45)), mock.patch.object(guard, "_cgroup_identity"),
            mock.patch.object(launcher, "directory", side_effect=directory), mock.patch.object(launcher, "protected", side_effect=protected),
            mock.patch.object(budget, "current_clock", side_effect=lambda: dict(boot_id=BOOT, boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME)))]
        for patch in patches: patch.start()
        try: result = s.supervise(value, launcher, PATH.parents[2])
        finally:
            for patch in reversed(patches): patch.stop()
        if result["status"] != "CONTROLLER_CLOSED": raise AssertionError(result)
        cls.seed_digest = r.digest((root / "output/seal.json").read_bytes())

    @classmethod
    def tearDownClass(cls): cls.seed.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(Path(self.seed.name) / "output", self.root / "output")
        shutil.copytree(Path(self.seed.name) / "declarations", self.root / "declarations")
        self.expected = self.seed_digest

    def review(self): return r.review(str(self.root / "output"), str(self.root / "declarations"), self.expected)

    def rewrite(self, name, mutate, directory="output"):
        path = self.root / directory / name
        value = json.loads(path.read_bytes()); mutate(value); path.write_bytes(r.encoded(value))

    def reseal(self):
        """Model a separately pinned dishonest/incomplete seal for semantic tests."""
        path = self.root / "output/seal.json"; seal = json.loads(path.read_bytes())
        value = json.loads((self.root / "declarations/supervisor.json").read_bytes())
        files = {}
        for directory, names in (("output", r.OUTPUT), ("declarations", r.DECLARATIONS)):
            for name in names:
                raw = (self.root / directory / name).read_bytes()
                files[value[directory]["path"] + "/" + name] = dict(bytes=len(raw), sha256=r.digest(raw))
        seal["files"] = files; raw = r.encoded(seal); path.write_bytes(raw); self.expected = r.digest(raw)

    def test_actual_producer_roundtrip_and_copied_paths_are_read_only(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("review must not launch")):
            value = self.review()
        self.assertEqual("OFFLINE_ARTIFACTS_CONSISTENT", value["status"])
        self.assertEqual(13, value["sealed_members"])
        self.assertFalse(value["host_provenance_proven"]); self.assertFalse(value["live_state_proven"])
        self.assertFalse(value["launcher_phase_evidence_reviewed"])
        self.assertFalse(value["q3_accepted"]); self.assertFalse(value["production_supported"])
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_v2_actual_producer_records_three_phase_declarations_and_scoped_chain_status(self):
        # The nested phase result is modeled; outer producer/capture/files are real.
        class ChainFixture:
            chain = True
        try:
            RetainedReviewTests.setUpClass.__func__(ChainFixture)
            root = Path(ChainFixture.seed.name)
            value = r.review(str(root / "output"), str(root / "declarations"), ChainFixture.seed_digest)
            self.assertEqual("CHAIN_CLOSED", value["recorded_launcher_status"])
            self.assertEqual("OFFLINE_ARTIFACTS_CONSISTENT", value["status"])
            self.assertFalse(value["launcher_phase_evidence_reviewed"])
            self.assertFalse(value["q3_accepted"])
        finally:
            if hasattr(ChainFixture, "seed"): ChainFixture.seed.cleanup()

    def test_real_cli_reviews_copied_bundle_without_following_recorded_paths(self):
        completed = subprocess.run([sys.executable, "-I", "-B", str(PATH), "--evidence", str(self.root / "output"),
            "--declarations", str(self.root / "declarations"), "--seal-sha256", self.expected], capture_output=True, timeout=10)
        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertEqual(b"", completed.stderr)
        self.assertEqual("OFFLINE_ARTIFACTS_CONSISTENT", json.loads(completed.stdout)["status"])

    def test_no_independent_digest_anchor_and_tampered_member_are_rejected(self):
        with self.assertRaises(ValueError): r.review(str(self.root / "output"), str(self.root / "declarations"), "")
        self.expected = "f" * 64
        with self.assertRaisesRegex(ValueError, "REVIEW_SEAL_DIGEST"): self.review()
        self.expected = self.seed_digest
        with (self.root / "output/controller.stdout").open("ab") as stream: stream.write(b" ")
        with self.assertRaisesRegex(ValueError, "REVIEW_MANIFEST_BINDING"): self.review()

    def test_absolute_and_traversal_manifest_members_never_select_files(self):
        for bad in ("/etc/passwd", "../../outside", "/fake/../controller.stdout"):
            with self.subTest(bad=bad):
                path = self.root / "output/seal.json"; seal = json.loads(path.read_bytes())
                old = next(iter(seal["files"])); seal["files"][bad] = seal["files"].pop(old)
                raw = r.encoded(seal); path.write_bytes(raw); self.expected = r.digest(raw)
                with self.assertRaisesRegex(ValueError, "REVIEW_MANIFEST_BINDING"): self.review()

    def test_unexpected_missing_and_excess_members_are_refused(self):
        path = self.root / "output/extra"; path.write_bytes(b"irrelevant")
        with self.assertRaisesRegex(ValueError, "REVIEW_DIRECTORY_MEMBERS"): self.review()
        path.unlink(); (self.root / "declarations/launcher.json").unlink()
        with self.assertRaisesRegex(ValueError, "REVIEW_DIRECTORY_MEMBERS"): self.review()

    def test_symlink_hardlink_fifo_and_directory_members_are_refused(self):
        path = self.root / "output/controller.stdout"; retained = path.read_bytes()
        outside = self.root / "outside"; outside.write_bytes(retained)
        for kind in ("symlink", "hardlink", "fifo", "directory"):
            path.unlink()
            if kind == "symlink": path.symlink_to(outside)
            elif kind == "hardlink": os.link(outside, path)
            elif kind == "fifo": os.mkfifo(path)
            else: path.mkdir()
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "REVIEW_REGULAR_SINGLE_LINK_REQUIRED"):
                self.review()
            if kind == "directory": path.rmdir()
            else: path.unlink()
            path.write_bytes(retained)

    def test_symlink_in_explicit_directory_path_is_refused(self):
        alias = self.root / "alias"; alias.symlink_to(self.root / "output", target_is_directory=True)
        with self.assertRaises(OSError): r.review(str(alias), str(self.root / "declarations"), self.expected)
        with self.assertRaises(ValueError): r.review(str(self.root / "output") + "/../output", str(self.root / "declarations"), self.expected)

    def test_file_limit_refuses_oversize_before_read(self):
        with (self.root / "output/controller.stdout").open("wb") as stream: stream.truncate(r.PIPE_LIMIT + 1)
        with self.assertRaisesRegex(ValueError, "REVIEW_FILE_LIMIT"): self.review()

    def test_missing_eof_false_completion_or_nonzero_exit_cannot_pass_even_resealed(self):
        original = (self.root / "output/capture.json").read_bytes()
        for key, value in (("eof", ["stdout"]), ("complete", False), ("returncode", -9), ("returncode", False),
                           ("error", "TIMEOUT"), ("close_errors", ["stderr"])):
            (self.root / "output/capture.json").write_bytes(original)
            self.rewrite("capture.json", lambda data: data.update({key: value})); self.reseal()
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "REVIEW_ORIGINAL_CAPTURE"):
                self.review()

    def test_success_boolean_without_valid_seal_or_provisional_contract_is_rejected(self):
        self.rewrite("result.json", lambda data: data.update(status="CONTROLLER_CLOSED", sealed=True)); self.reseal()
        with self.assertRaisesRegex(ValueError, "REVIEW_PROVISIONAL_RESULT"): self.review()
        (self.root / "output/seal.json").unlink()
        with self.assertRaisesRegex(ValueError, "REVIEW_DIRECTORY_MEMBERS"): self.review()

    def test_resealed_q3_or_production_claim_is_rejected(self):
        for name in ("q3_accepted", "production_supported"):
            path = self.root / "output/seal.json"; value = json.loads(path.read_bytes())
            value["q3_accepted"] = False; value["production_supported"] = False; value[name] = True
            raw = r.encoded(value); path.write_bytes(raw); self.expected = r.digest(raw)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "REVIEW_SCOPE"): self.review()

    def test_original_instance_stop_and_empty_tree_all_required(self):
        original = (self.root / "output/stop.json").read_bytes()
        for field in ("attempted", "acknowledged", "complete", "parent_empty"):
            (self.root / "output/stop.json").write_bytes(original)
            self.rewrite("stop.json", lambda data: data.update({field: False})); self.reseal()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "REVIEW_STOP_INCOMPLETE"): self.review()

    def test_foreign_invocation_pending_job_and_capability_expansion_rejected(self):
        original = (self.root / "output/stop.json").read_bytes()
        for which, key, value in (("after", "InvocationID", "f"*32), ("after", "Job", "1"),
                                  ("before", "MainPID", "999999"), ("before", "AmbientCapabilities", "cap_sys_admin")):
            (self.root / "output/stop.json").write_bytes(original)
            self.rewrite("stop.json", lambda data: data[which].update({key: value})); self.reseal()
            with self.subTest(which=which, key=key), self.assertRaises(ValueError): self.review()

    def test_control_pipe_records_cannot_be_replaced_by_stop_boolean(self):
        original = (self.root / "output/controls.json").read_bytes()
        for mode in ("empty", "missing_eof", "wrong_command", "changed_output"):
            records = json.loads(original)
            if mode == "empty": records = []
            elif mode == "missing_eof": records[-2]["eof"] = ["stdout"]
            elif mode == "wrong_command": records[-2]["arguments"] = ["stop", "other.service"]
            else: records[-1]["stdout_hex"] = b"arbitrary".hex()
            (self.root / "output/controls.json").write_bytes(r.encoded(records)); self.reseal()
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.review()

    def test_identity_marker_and_nested_launcher_must_match(self):
        self.rewrite("launcher.json", lambda data: data["controller_envelope"]["controller"].update(invocation_id="f"*32),
                     "declarations")
        self.reseal()
        with self.assertRaisesRegex(ValueError, "REVIEW_LAUNCHER_BINDING"): self.review()

    def test_declared_capacity_costs_cannot_be_lowered_by_result(self):
        self.rewrite("reservation.json", lambda data: data["capacity_costs"].update(storage_bytes=1)); self.reseal()
        with self.assertRaisesRegex(ValueError, "REVIEW_CAPACITY_COSTS"): self.review()

    def test_delivery_hash_is_recomputed_from_fixed_fixture_command(self):
        self.rewrite("delivery.json", lambda data: data.update(argv_sha256="f"*64)); self.reseal()
        with self.assertRaisesRegex(ValueError, "REVIEW_DELIVERY_BINDING"): self.review()

    def test_manifest_integer_cannot_be_a_boolean(self):
        path = self.root / "output/seal.json"; seal = json.loads(path.read_bytes())
        name = next(name for name in seal["files"] if name.endswith("/controller.stderr"))
        seal["files"][name]["bytes"] = False
        raw = r.encoded(seal); path.write_bytes(raw); self.expected = r.digest(raw)
        with self.assertRaisesRegex(ValueError, "REVIEW_INTEGER"): self.review()

    def test_seal_bytes_are_included_in_retained_storage_check(self):
        actual = r.facts
        expected = sum(p.stat().st_size for folder in ("output", "declarations")
                       for p in (self.root / folder).iterdir())
        def checked(*args):
            self.assertEqual(expected, args[-1])
            return actual(*args)
        with mock.patch.object(r, "facts", side_effect=checked): self.review()

    def test_original_deadline_and_pipe_identity_cannot_be_replaced(self):
        original = (self.root / "output/capture.json").read_bytes()
        for mode in ("deadline", "pipe", "digest"):
            (self.root / "output/capture.json").write_bytes(original)
            def mutate(data):
                if mode == "deadline": data["deadline_ns"] += 1000000000
                elif mode == "pipe": data["pipe_identities"]["stderr"] = data["pipe_identities"]["stdout"]
                else: data["stdout_sha256"] = "f"*64
            self.rewrite("capture.json", mutate); self.reseal()
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.review()

    def test_mutation_after_read_is_detected(self):
        original = r.facts
        def changed(*args):
            value = original(*args)
            with (self.root / "output/controller.stdout").open("ab") as stream: stream.write(b" ")
            return value
        with mock.patch.object(r, "facts", side_effect=changed), self.assertRaisesRegex(ValueError, "REVIEW_MEMBER_CHANGED"):
            self.review()


if __name__ == "__main__": unittest.main()

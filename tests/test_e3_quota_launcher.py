"""LOGIC_ONLY host doubles and real LOCAL_FILE durability/exec checks.

No systemd process, quota operation, journal, account, mount or host fixture.
Temporary-directory ownership/ancestor checks are explicitly replaced for CI;
the actual write/fsync/exclusive creation and exec syscalls remain real.
"""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from admin.local_hand_quota_observer import admission as a, launcher as l, protected_inputs as p
from test_e3_quota_experiment import experiment_fixture
from test_e3_quota_fixture import make_inputs, second_slot
from test_e3_quota_monitor import binding, encoded, NOW
from test_e3_quota_worker import runtime_value


LAUNCH_PATH = "/synthetic/launch/input.json"
TOOLS_PATH = "/synthetic/install"


def fixture():
    runtime = runtime_value()
    runtime["worker_path"] = TOOLS_PATH + "/" + l.PACKAGE + "worker.py"
    inputs = make_inputs(runtime=runtime)
    config = p.decode_runtime(inputs["runtime_bytes"], inputs["runtime_digest"])
    manifest = a.decode_manifest(inputs["manifest_bytes"], inputs["manifest_digest"])
    original = experiment_fixture()[4]
    controller = {name: original["controller"][name] for name in l.STATIC_FIELDS}
    digests = dict.fromkeys(l.SOURCE_FILES, "f" * 64)
    digests[l.PACKAGE + "worker.py"] = config.worker_sha256
    for name, digest in config.package_files:
        digests[l.PACKAGE + name] = digest
    value = {"schema": "local-hand-quota-q1-launch-input/v1", "operation": "run",
             "source_commit": manifest.source_commit, "runtime_path": inputs["runtime_path"],
             "runtime_digest": inputs["runtime_digest"], "journal": original["journal"],
             "ticket": p.encode_ticket(binding(manifest)), "controller": controller,
             "output": {"path": "/synthetic/delivery/experiment.json",
                        "parent": {"path": "/synthetic/delivery", "owner_uid": 0,
                                   "device": 81, "inode": 82}},
             "installation": {"tools_path": TOOLS_PATH, "files": digests}}
    return inputs, config, manifest, value


def decode(value):
    raw = encoded(value)
    return l.decode_launch_input(raw, hashlib.sha256(raw).hexdigest(), "c" * 40)


class LaunchDecodeTests(unittest.TestCase):
    def test_immutable_external_root_and_original_ticket_without_dynamic_identity(self):
        inputs, config, manifest, value = fixture()
        spec = decode(value)
        self.assertEqual(p.decode_ticket(spec.ticket, manifest), binding(manifest))
        self.assertEqual(spec.runtime_digest, inputs["runtime_digest"])
        self.assertNotIn("invocation_id", dict(spec.controller))
        with self.assertRaises(AttributeError):
            spec.operation = "retry"
        l._geometry(spec, config, manifest, LAUNCH_PATH)
        with self.assertRaisesRegex(a.Rejected, "LAUNCH_DIGEST"):
            l.decode_launch_input(encoded(value) + b" ", spec.digest, "c" * 40)
        with self.assertRaisesRegex(a.Rejected, "SOURCE_COMMIT_CHANGED"):
            l.decode_launch_input(encoded(value), spec.digest, "d" * 40)

    def test_schema_missing_extra_duplicate_fields_and_unbounded_values(self):
        original = fixture()[3]
        cases = []
        for key in original:
            value = deepcopy(original); del value[key]; cases.append(value)
        for field, bad in (("operation", "retry"), ("schema", "unknown"), ("source_commit", "HEAD")):
            value = deepcopy(original); value[field] = bad; cases.append(value)
        for field, bad in (("invocation_id", "d" * 32), ("cgroup_inode", 123), ("prepared", True),
                           ("tasks_max", True), ("runtime_max_usec", 120_000_001)):
            value = deepcopy(original); value["controller"][field] = bad; cases.append(value)
        value = deepcopy(original); value["installation"]["files"].pop(l.SOURCE_FILES[-1]); cases.append(value)
        value = deepcopy(original); value["output"]["parent"]["owner_uid"] = 1000; cases.append(value)
        value = deepcopy(original); value["output"]["path"] = "/different/x"; cases.append(value)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(a.Rejected):
                decode(value)
        for raw in (b'{"schema":"duplicate",' + encoded(original)[1:],
                    encoded(original) + b" " * l.MAX_LAUNCH_BYTES):
            with self.assertRaises(a.Rejected):
                l.decode_launch_input(raw, hashlib.sha256(raw).hexdigest(), "c" * 40)

    def test_every_installation_member_and_all_slots_are_checked_for_overlap(self):
        inputs, config, manifest, value = fixture()
        for root in (value["journal"]["path"], config.manifest_path, LAUNCH_PATH,
                     config.python_path, TOOLS_PATH, manifest.slots[0].path):
            changed = deepcopy(value)
            changed["output"]["parent"]["path"] = root
            changed["output"]["path"] = root + "/generated.json"
            with self.subTest(root=root), self.assertRaises(a.Rejected):
                l._geometry(decode(changed), config, manifest, LAUNCH_PATH)
        mf = json.loads(inputs["manifest_bytes"])
        second_slot(mf, "/synthetic/delivery/other-root")
        raw = encoded(mf)
        other = a.decode_manifest(raw, hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(a.Rejected, "OUTPUT_ROOT_OVERLAP"):
            l._geometry(decode(value), config, other, LAUNCH_PATH)
        changed = deepcopy(value)
        changed["installation"]["files"][l.PACKAGE + "admission.py"] = "0" * 64
        with self.assertRaisesRegex(a.Rejected, "LAUNCH_INSTALLATION_BINDING"):
            l._geometry(decode(changed), config, manifest, LAUNCH_PATH)

    def test_run_preserves_and_checks_deadline_but_expired_recovery_remains_observational(self):
        _, _, manifest, value = fixture()
        bound = binding(manifest)
        with patch.object(l, "boottime_ns", return_value=bound.deadline_ns):
            with self.assertRaisesRegex(a.Rejected, "DEADLINE_EXPIRED"):
                l._check_time(decode(value), bound)
            value["operation"] = "recover_original"
            l._check_time(decode(value), bound)
        self.assertEqual(p.decode_ticket(value["ticket"], manifest).deadline_ns, bound.deadline_ns)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux local filesystem contract")
class LaunchFileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.target = Path(self.directory.name) / "experiment.json"
        self.inputs, self.config, self.manifest, self.value = fixture()
        info = os.stat(self.directory.name)
        self.value["output"] = {"path": str(self.target), "parent": {
            "path": self.directory.name, "owner_uid": 0, "device": info.st_dev, "inode": info.st_ino}}
        self.spec = decode(self.value)
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.real_fstat = os.fstat
        # Only ownership and ancestor protection are doubles; identity, modes,
        # link count, nofollow/exclusive flags and all actual file bytes are real.
        def fake_owner(fd):
            metadata = self.real_fstat(fd)
            attrs = {name: getattr(metadata, name) for name in dir(metadata) if name.startswith("st_")}
            attrs["st_uid"] = 0
            return SimpleNamespace(**attrs)
        self.stack.enter_context(patch.object(l.os, "fstat", side_effect=fake_owner))
        def local_open(filename, *, directory=False):
            flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
            return os.open(filename, flags | (os.O_DIRECTORY if directory else 0))
        self.stack.enter_context(patch.object(l, "open_protected", side_effect=local_open))

    def test_real_short_writes_preserve_every_byte_and_sync_file_before_parent(self):
        raw = b"partial-write-test\x00" * 100
        real_write, real_sync = os.write, os.fsync
        syncs = []
        def sync(fd):
            syncs.append(stat.S_ISDIR(self.real_fstat(fd).st_mode)); return real_sync(fd)
        with patch.object(l.os, "write", side_effect=lambda fd, data: real_write(fd, data[:7])) as writes, \
                patch.object(l.os, "fsync", side_effect=sync):
            identity = l._write_experiment(self.spec, raw)
        self.assertGreater(writes.call_count, 2)
        self.assertEqual(self.target.read_bytes(), raw)
        self.assertEqual(syncs, [False, True])
        self.assertEqual(identity[0:2], (self.target.stat().st_dev, self.target.stat().st_ino))
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)

    def test_existing_file_and_symlink_are_retained_and_never_overwritten(self):
        self.target.write_bytes(b"original evidence")
        with self.assertRaises(FileExistsError):
            l._write_experiment(self.spec, b"replacement")
        self.assertEqual(self.target.read_bytes(), b"original evidence")
        self.target.unlink()
        other = Path(self.directory.name) / "other"; other.write_bytes(b"other")
        self.target.symlink_to(other)
        with self.assertRaises(FileExistsError):
            l._write_experiment(self.spec, b"replacement")
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(other.read_bytes(), b"other")

    def test_failed_write_retains_prefix_without_cleanup(self):
        real_write = os.write
        calls = 0
        def interrupted(fd, raw):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise OSError("simulated full disk")
            return real_write(fd, raw[:3])
        with patch.object(l.os, "write", side_effect=interrupted), self.assertRaises(OSError):
            l._write_experiment(self.spec, b"preserve original prefix")
        self.assertEqual(self.target.read_bytes(), b"pre")
        with self.assertRaises(FileExistsError):
            l._write_experiment(self.spec, b"retry forbidden")

    def test_zero_write_and_fsync_failures_leave_original_output(self):
        with patch.object(l.os, "write", return_value=0), self.assertRaisesRegex(a.Rejected, "OUTPUT_WRITE_FAILED"):
            l._write_experiment(self.spec, b"content")
        self.assertEqual(self.target.read_bytes(), b"")
        self.target.unlink()
        real_sync = os.fsync
        for fail_call in (1, 2):
            calls = 0
            def failing_sync(fd):
                nonlocal calls
                calls += 1
                if calls == fail_call:
                    raise OSError("synthetic fsync failure")
                return real_sync(fd)
            with patch.object(l.os, "fsync", side_effect=failing_sync), self.assertRaises(OSError):
                l._write_experiment(self.spec, b"original")
            self.assertEqual(self.target.read_bytes(), b"original")
            self.target.unlink()

    def test_wrong_parent_identity_or_public_directory_reject_before_creation(self):
        for spec in (replace(self.spec, parent_inode=self.spec.parent_inode + 1),
                     replace(self.spec, parent_device=self.spec.parent_device + 1)):
            with self.assertRaisesRegex(a.Rejected, "OUTPUT_PARENT_IDENTITY"):
                l._write_experiment(spec, b"not written")
        os.chmod(self.directory.name, 0o755)
        with self.assertRaisesRegex(a.Rejected, "OUTPUT_PARENT_IDENTITY"):
            l._write_experiment(self.spec, b"not written")
        self.assertFalse(self.target.exists())

    def wire(self):
        self.calls = []
        self.original = encoded(self.value)
        self.controller = l.decode_controller({**dict(self.spec.controller), "invocation_id": "d" * 32,
                                              "cgroup_device": 91, "cgroup_inode": 92})
        def read(filename, maximum):
            return self.original if filename == LAUNCH_PATH else self.inputs["manifest_bytes"]
        self.stack.enter_context(patch.object(l, "read_protected", side_effect=read))
        self.stack.enter_context(patch.object(l, "load_runtime", return_value=self.config))
        self.stack.enter_context(patch.object(l, "_input_identities", return_value=(("input", 1),)))
        self.stack.enter_context(patch.object(l, "_verify_sources", return_value=(("fixed", 1),)))
        self.stack.enter_context(patch.object(l, "_current_controller", return_value=self.controller))
        self.stack.enter_context(patch.object(l.os, "getuid", return_value=0))
        self.stack.enter_context(patch.object(l.os, "geteuid", return_value=0))
        self.stack.enter_context(patch.object(l, "boottime_ns", return_value=NOW))
        self.guard = self.stack.enter_context(patch.object(l, "admit_controller", side_effect=lambda *args:
                                              self.calls.append("guard")))
        self.execute = self.stack.enter_context(patch.object(l, "_exec_entry", side_effect=lambda *args:
                                                self.calls.append("exec")))

    def invoke(self):
        return l.launch_experiment(LAUNCH_PATH, self.spec.digest, "c" * 40,
                                   launcher_path=TOOLS_PATH + "/launch_q1_experiment.py")

    def test_admission_before_delivery_and_exact_original_identity_reaches_exec(self):
        self.wire()
        real_writer = l._write_experiment
        def write(*args):
            self.assertEqual(self.calls, ["guard"])
            self.calls.append("write")
            return real_writer(*args)
        with patch.object(l, "_write_experiment", side_effect=write):
            self.invoke()
        self.assertEqual(self.calls, ["guard", "write", "exec"])
        document = json.loads(self.target.read_bytes())
        self.assertEqual(document["ticket"], self.value["ticket"])
        self.assertEqual(document["runtime_digest"], self.value["runtime_digest"])
        self.assertEqual(document["journal"], self.value["journal"])
        self.assertEqual(document["controller"]["invocation_id"], "d" * 32)
        self.assertEqual(document["controller"]["cgroup_inode"], 92)
        self.assertEqual(document["operation"], "run")
        self.execute.assert_called_once_with(self.config, self.spec,
                                            hashlib.sha256(self.target.read_bytes()).hexdigest())

    def test_guard_fsync_and_existing_file_failures_never_exec(self):
        self.wire()
        self.guard.side_effect = a.Rejected("CONTROLLER_UNIT_CHANGED")
        with self.assertRaises(a.Rejected): self.invoke()
        self.assertFalse(self.target.exists()); self.execute.assert_not_called()
        self.guard.side_effect = None
        with patch.object(l.os, "fsync", side_effect=OSError("disk error")), self.assertRaises(OSError):
            self.invoke()
        raw = self.target.read_bytes(); self.assertTrue(raw)
        self.execute.assert_not_called()
        with self.assertRaises(FileExistsError): self.invoke()
        self.assertEqual(self.target.read_bytes(), raw); self.execute.assert_not_called()

    def test_changed_source_input_or_controller_after_delivery_never_exec(self):
        self.wire()
        for name, kwargs in (("_verify_sources", {"side_effect": [(("fixed", 1),), (("changed", 2),)]}),
                             ("_input_identities", {"side_effect": [(("input", 1),), (("input", 2),)]}),
                             ("_current_controller", {"side_effect": [self.controller,
                                replace(self.controller, invocation_id="e" * 32)]})):
            with self.subTest(name=name), patch.object(l, name, **kwargs), self.assertRaises(a.Rejected):
                self.invoke()
            self.assertTrue(self.target.exists()); self.execute.assert_not_called()
            self.target.unlink()

    def test_expired_recovery_passes_same_original_ticket_to_entry(self):
        self.value["operation"] = "recover_original"; self.spec = decode(self.value)
        self.wire()
        with patch.object(l, "boottime_ns", return_value=NOW + 999_000_000_000):
            self.invoke()
        document = json.loads(self.target.read_bytes())
        self.assertEqual((document["operation"], document["ticket"]),
                         ("recover_original", self.value["ticket"]))

    def test_stale_bytecode_and_extension_shadow_are_refused_with_real_paths(self):
        tools = Path(self.directory.name) / "tools"
        package = tools / "admin" / "local_hand_quota_observer"
        package.mkdir(parents=True)
        l._no_implicit_code(str(tools))
        paths = [tools / "__pycache__", tools / "admin" / "__init__.py",
                 package / "__init__.pyc", package / "__pycache__"]
        for suffix in l.EXTENSION_SUFFIXES:
            paths.extend((tools / ("admin" + suffix), tools / "admin" / ("__init__" + suffix),
                          tools / "admin" / ("local_hand_quota_observer" + suffix),
                          package / ("__init__" + suffix), package / ("launcher" + suffix),
                          package / ("experiment" + suffix)))
        for target in paths:
            target.write_bytes(b"not loaded")
            try:
                with self.subTest(path=target.name), self.assertRaisesRegex(a.Rejected, "LAUNCH_IMPLICIT_CODE"):
                    l._no_implicit_code(str(tools))
            finally:
                target.unlink()
        for name in ("experiment", "admission"):
            target = package / name
            target.mkdir()
            (target / "__init__.py").write_text("raise AssertionError('must never import')")
            try:
                with self.subTest(package=name), self.assertRaisesRegex(a.Rejected, "LAUNCH_IMPLICIT_CODE"):
                    l._no_implicit_code(str(tools))
            finally:
                (target / "__init__.py").unlink()
                target.rmdir()

    def test_candidate_controller_reads_current_cgroup_and_environment_only_as_candidate(self):
        target = Path(self.directory.name)
        with patch.object(l, "_own_cgroup", return_value=dict(self.spec.controller)["cgroup"]), \
                patch.dict(os.environ, {"INVOCATION_ID": "d" * 32}), \
                patch.object(l, "open_protected", side_effect=lambda *args, **kwargs:
                             os.open(target, os.O_RDONLY | os.O_DIRECTORY)):
            observed = l._current_controller(self.spec)
            self.assertEqual(observed.invocation_id, "d" * 32)
            self.assertEqual((observed.cgroup_device, observed.cgroup_inode),
                             (target.stat().st_dev, target.stat().st_ino))
            with patch.object(l, "_own_cgroup", return_value="/other.slice/other.service"), \
                    self.assertRaisesRegex(a.Rejected, "CONTROLLER_CGROUP_CHANGED"):
                l._current_controller(self.spec)
            with patch.dict(os.environ, {"INVOCATION_ID": "invalid"}), self.assertRaisesRegex(a.Rejected, "TOKEN"):
                l._current_controller(self.spec)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux local exec PID and pipe continuity")
class ExecContinuityTests(unittest.TestCase):
    def test_real_exec_keeps_pid_pipe_identity_and_cpu_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "run_q1_experiment.py"
            target.write_text("""import json, os, resource, sys
print(json.dumps({'pid': os.getpid(), 'out': list(os.fstat(1)[:3]),
                  'err': list(os.fstat(2)[:3]), 'cpu': resource.getrlimit(resource.RLIMIT_CPU),
                  'argv': sys.argv[1:], 'isolated': sys.flags.isolated,
                  'bytecode': sys.flags.dont_write_bytecode}), flush=True)
""")
            runner = """import json, os, resource, sys
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from admin.local_hand_quota_observer.launcher import _exec_entry
resource.setrlimit(resource.RLIMIT_CPU, (9, 9))
print(json.dumps({'pid': os.getpid(), 'out': list(os.fstat(1)[:3]),
                  'err': list(os.fstat(2)[:3]), 'cpu': resource.getrlimit(resource.RLIMIT_CPU)}), flush=True)
_exec_entry(SimpleNamespace(python_path=sys.executable),
            SimpleNamespace(tools_path=sys.argv[2], output_path='/synthetic/original.json',
                            source_commit='c'*40), 'd'*64)
"""
            completed = subprocess.run([sys.executable, "-I", "-B", "-c", runner,
                                        str(Path(l.__file__).resolve().parents[2]), folder],
                                       capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            before, after = map(json.loads, completed.stdout.splitlines())
            for key in ("pid", "out", "err", "cpu"):
                self.assertEqual(before[key], after[key])
            self.assertEqual(after["cpu"], [9, 9])
            self.assertEqual(after["argv"], ["--input", "/synthetic/original.json", "--sha256", "d" * 64,
                                              "--source-commit", "c" * 40])
            self.assertEqual((after["isolated"], after["bytecode"]), (1, 1))


if __name__ == "__main__":
    unittest.main()

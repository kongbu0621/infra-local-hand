"""Launcher protocol/order models plus actual finite files and default entry.

No test here invokes setpriv/systemd, admits a real fixture or claims Q3. The
orchestration checks explicitly model protected host qualification and child
supervision; create-only I/O, anonymous sockets and collection thread are real.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

PATH = Path(__file__).parent / "e3_host" / "q2_launcher.py"
spec = importlib.util.spec_from_file_location("_q2_launcher_tests", PATH)
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)
if sys.platform.startswith("linux"):
    from local_hand_jobs import budget, quota_bridge as bridge, quota_closure, runner
    from admin.local_hand_quota_observer import q2_assembly as assembly, q2_capture, q2_coordinator, q2_management
    from test_e3_quota_q2_assembly import declaration_template, snapshot, SESSION
    from q2_fixtures import BOOT, SECOND


def raw(value):
    return launcher.encoded(value, launcher.LIMIT)


def header():
    return dict(schema=launcher.SCHEMA, purpose="ISOLATED_Q2_PREFLIGHT", source={}, resident={}, assembly={},
                controller_envelope={}, setpriv={}, output={}, declarations={}, session="a"*64)


class UnexpectedFailure(Exception):
    """A direct Exception subclass, like the production JobError boundary."""


class EntryAndDeclarationTests(unittest.TestCase):
    def test_real_isolated_default_entry_blocks_without_any_fixture(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(PATH)], capture_output=True, timeout=10)
        self.assertEqual(3, result.returncode)
        value = json.loads(result.stdout)
        self.assertEqual("BLOCKED", value["status"])
        self.assertEqual("EXPLICIT_PRIVATE_FIXTURE_REQUIRED", value["reason"])
        self.assertFalse(value["q3_accepted"])
        self.assertFalse(value["production_supported"])
        self.assertEqual(b"", result.stderr)

    def test_duplicate_unknown_schema_digest_and_oversize_are_rejected(self):
        valid = raw(header())
        self.assertEqual(header(), launcher.decode(valid, hashlib.sha256(valid).hexdigest()))
        duplicate = valid.rstrip()[:-1] + b',"purpose":"ISOLATED_Q2_PREFLIGHT"}'
        extra = header(); extra["shell"] = "/bin/sh"
        invalid = header(); invalid["schema"] = "local-hand-q2-launcher/v2"
        for candidate in (duplicate, raw(extra), raw(invalid), b" " * (launcher.LIMIT + 1), b'{"x":NaN}'):
            with self.subTest(size=len(candidate)), self.assertRaises(ValueError):
                launcher.decode(candidate, hashlib.sha256(candidate).hexdigest())
        with self.assertRaises(ValueError): launcher.decode(valid, "0"*64)

    def test_float_oversized_integer_and_deep_tree_are_rejected(self):
        for forbidden in (1.5, 2**63, -1):
            value = header(); value["source"] = {"value": forbidden}
            candidate = raw(value)
            with self.subTest(forbidden=forbidden), self.assertRaises(ValueError):
                launcher.decode(candidate, hashlib.sha256(candidate).hexdigest())
        value = header(); nested = {}
        for unused in range(25): nested = {"nested": nested}
        value["source"] = nested; candidate = raw(value)
        with self.assertRaisesRegex(ValueError, "LAUNCHER_DEPTH"):
            launcher.decode(candidate, hashlib.sha256(candidate).hexdigest())

    def test_privilege_drop_is_an_argv_vector_with_cleared_groups_and_capabilities(self):
        value = dict(setpriv={"path": "/usr/bin/setpriv"}, resident={"ordinary": {"uid": 1234, "gid": 2345},
            "installation": {"programs": {"python": {"path": "/protected/python"}}}, "entry": {"path": "/protected/resident.py"}})
        command = launcher.command(value, "/protected/fixture.json", "d"*64)
        self.assertEqual(["/usr/bin/setpriv", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all",
            "--no-new-privs", "--reuid=1234", "--regid=2345", "--clear-groups", "--", "/protected/python",
            "-I", "-B", "/protected/resident.py", "--fixture", "/protected/fixture.json", "--sha256", "d"*64], command)
        self.assertFalse(any(item in ("/bin/sh", "-c", "sudo") for item in command))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux protected fixture/files")
class FileEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.home()); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        self.addCleanup(os.close, self.fd)

    def test_real_createonce_file_and_symlink_cannot_overwrite_existing_evidence(self):
        launcher.save(self.fd, "record.json", b"original\n")
        with self.assertRaises(FileExistsError): launcher.save(self.fd, "record.json", b"replacement")
        self.assertEqual(b"original\n", (self.root/"record.json").read_bytes())
        (self.root/"alias.json").symlink_to(self.root/"record.json")
        with self.assertRaises(FileExistsError): launcher.save(self.fd, "alias.json", b"replacement")
        self.assertEqual(b"original\n", (self.root/"record.json").read_bytes())
        self.assertEqual(0o600, stat.S_IMODE((self.root/"record.json").stat().st_mode))

    def test_failed_fsync_retains_original_file_and_cannot_be_retried(self):
        with mock.patch.object(launcher.os, "fsync", side_effect=OSError("modeled fsync fault")), self.assertRaises(OSError):
            launcher.save(self.fd, "reservation.json", b"reserved")
        self.assertEqual(b"reserved", (self.root/"reservation.json").read_bytes())
        with self.assertRaises(FileExistsError): launcher.save(self.fd, "reservation.json", b"retry")

    def test_protected_read_checks_real_nofollow_links_mode_and_size(self):
        path = self.root/"fixture"; path.write_bytes(b"finite"); path.chmod(0o600)
        original = launcher.os.fstat
        def modeled_root(fd):
            info = original(fd)
            # Root ownership only is modeled for unprivileged Linux CI.
            return SimpleNamespace(**{name: 0 if name == "st_uid" else getattr(info, name) for name in
                ("st_uid", "st_mode", "st_nlink", "st_size", "st_dev", "st_ino", "st_mtime_ns", "st_ctime_ns")})
        with mock.patch.object(launcher.os, "fstat", side_effect=modeled_root):
            self.assertEqual(b"finite", launcher.protected(str(path), 6))
            with self.assertRaises(ValueError): launcher.protected(str(path), 5)
            path.chmod(0o622)
            with self.assertRaises(ValueError): launcher.protected(str(path), 6)
            path.chmod(0o600)
            link = self.root/"hard"; os.link(path, link)
            with self.assertRaises(ValueError): launcher.protected(str(path), 6)
            link.unlink(); link.symlink_to(path)
            with self.assertRaises(OSError): launcher.protected(str(link), 6)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux explicitly modeled launcher orchestration")
class LauncherOrderingTests(unittest.TestCase):
    def setUp(self):
        try:
            left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET); left.close(); right.close()
        except PermissionError: self.skipTest("Anonymous Unix sockets unavailable")
        self.tmp = tempfile.TemporaryDirectory(dir=Path.home()); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.value = header(); declared, self.original = declaration_template()
        declared["peer"]["runner"]["path"] = "/synthetic/installed/local_hand_jobs/runner.py"
        self.value["assembly"] = declared
        self.clock = dict(boot_id=BOOT, boottime_ns=2*SECOND)
        checksum = hashlib.sha256(b"modeled protected executable").hexdigest()
        for pin in declared["installation"]["programs"].values(): pin["sha256"] = checksum
        for name, mode in (("output", 0o700), ("declarations", 0o755)):
            path = self.root/name; path.mkdir(mode=mode); info = path.stat()
            self.value[name] = dict(path=str(path), device=info.st_dev, inode=info.st_ino)
        self.value["setpriv"] = dict(path="/usr/bin/setpriv", sha256=checksum)
        self.repository = PATH.resolve().parents[2]
        installed_files = {"local_hand_jobs/runner.py": declared["peer"]["runner"]["sha256"]}
        self.value["source"] = dict(commit=declared["installation"]["source_commit"],
            files={"tools/"+key: val for key, val in installed_files.items()} | {"tests/e3_host/q2_resident.py": "e"*64})
        self.value["controller_envelope"] = dict(controller={"cgroup": "/synthetic-launch.slice/launcher.service"},
            issued_ns=SECOND, deadline_ns=50*SECOND, output_bytes=32768, storage_bytes=2**20, storage_inodes=32)
        self.value["resident"] = dict(phases=["preflight"],
            installation=dict(source_commit=self.value["source"]["commit"], files=installed_files,
                package_root="/synthetic/installed", programs={"python": dict(path=declared["peer"]["executable"]["path"], sha256=checksum)}),
            ordinary=dict(uid=1234, gid=1234, parent=declared["peer"]["parent"], broker_cgroup=self.value["controller_envelope"]["controller"]["cgroup"]),
            entry=dict(path=str(self.repository/"tests/e3_host/q2_resident.py"), sha256="e"*64),
            request=dict(operation_id=declared["grant"]["allocation"]["operation_id"]), plan={})
        self.prepared = dict(event="prepared", namespace="job", identity=self.value["resident"]["request"]["operation_id"],
            phase="preflight", snapshot=snapshot(declared, self.original))
        self.events = []; self.finish = threading.Event(); self.popen_calls = []
        self.capture_complete = True; self.coordinator_failure = False; self.foreign_summary = False; self.cleanup_failure = False
        self.build_failure = False; self.capture_failure = False; self.process_streams = []
        self.fence = {"schema": "explicitly-modeled-closure"}

    def invoke(self):
        events = self.events; finished = self.finish
        def open_directory(pin, mode):
            fd = os.open(pin["path"], os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_CLOEXEC)
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode)) != (pin["device"], pin["inode"], mode):
                os.close(fd); raise ValueError("MODELED_DIRECTORY_PIN")
            with os.scandir(fd) as entries:
                if next(entries, None) is not None:
                    os.close(fd); raise ValueError("LAUNCHER_ALREADY_CONSUMED")
            return fd
        def popen(argv, **kwargs):
            events.append("spawn"); self.popen_calls.append((argv, kwargs))
            self.assertEqual(1, len(kwargs["pass_fds"]))
            with socket.socket(fileno=os.dup(kwargs["pass_fds"][0])) as inherited:
                self.assertEqual(socket.SOCK_SEQPACKET, inherited.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE))
            stdout, stderr = io.BytesIO(), io.BytesIO()
            self.process_streams.extend((stdout, stderr))
            return SimpleNamespace(pid=os.getpid(), stdout=stdout, stderr=stderr)
        class Channel:
            def __init__(inner, sock, **kwargs): events.append("channel")
            def _time(inner): return 2*SECOND
            def receive(inner): events.append("prepared"); return copy.deepcopy(self.prepared)
            def send(inner, command):
                self.assertEqual(dict(action="finish", value=None), command)
                events.append("finish"); finished.set()
            def close(inner): events.append("channel_close"); finished.set()
        def collect(process, **kwargs):
            self.assertTrue(finished.wait(2), "modeled child never received finish/disconnect")
            events.append("capture")
            if self.capture_failure: raise UnexpectedFailure("private capture detail must not escape")
            summary = dict(schema="local-hand-q2-resident-result/v1", status="PHASE_CLOSED",
                operation_id=self.value["resident"]["request"]["operation_id"], phase="preflight",
                closure_digest="f"*64 if self.foreign_summary else quota_closure.digest({"phase": "preflight", "fence": self.fence}),
                q3_accepted=False, production_supported=False)
            return dict(complete=self.capture_complete, returncode=0, stdout=raw(summary), stderr=b"", error=None)
        def install(template, grant, **kwargs):
            events.append("install")
            self.assertEqual(self.prepared["snapshot"]["preparation"]["budget"], grant.as_dict()["budget"])
            self.assertEqual(SESSION, kwargs["session"])
            return dict(config=SimpleNamespace(), management_record={})
        def execute(plan, **kwargs):
            events.append("execution")
            self.assertEqual(self.original, plan["budget_grant"])
            return {}
        def bootstrap_argv(*args, **kwargs): events.append("argv"); return ["modeled-exact-argv"]
        class Record:
            def __init__(inner, pin): events.append("record")
            def close(inner):
                events.append("record_close")
                if self.cleanup_failure: raise OSError("modeled close error")
        class Coordinator:
            def __init__(inner, *args): events.append("coordinator")
            def run(inner):
                events.append("phase")
                if self.coordinator_failure: raise ValueError("MODELED_PHASE_UNKNOWN")
                return dict(status="PHASE_CLOSED", fence=self.fence, q3_accepted=False, production_supported=False)
        real_build = assembly.build_grant
        def build(*args, **kwargs):
            events.append("grant")
            if self.build_failure: raise UnexpectedFailure("private build detail must not escape")
            return real_build(*args, **kwargs)
        patches = [mock.patch.object(launcher, "protected", return_value=b"modeled protected executable"),
            mock.patch.object(launcher, "controller", side_effect=lambda *_: events.append("controller") or self.clock),
            mock.patch.object(launcher, "directory", side_effect=open_directory),
            mock.patch.object(launcher, "start_ticks", return_value=77),
            mock.patch.object(launcher.os, "readlink", return_value="mnt:[123]"),
            mock.patch.object(launcher.subprocess, "Popen", side_effect=popen),
            mock.patch.object(launcher.select, "select", return_value=([True], [], [])),
            mock.patch.object(budget, "current_clock", return_value=self.clock),
            mock.patch.object(bridge, "Channel", Channel), mock.patch.object(bridge, "Client", side_effect=lambda channel: channel),
            mock.patch.object(assembly, "build_grant", side_effect=build), mock.patch.object(assembly, "install", side_effect=install),
            mock.patch.object(runner, "_quota_prepared_execution", side_effect=execute),
            mock.patch.object(runner, "quota_bootstrap_argv", side_effect=bootstrap_argv),
            mock.patch.object(q2_management, "controller", side_effect=lambda *_: events.append("installed_controller")),
            mock.patch.object(q2_management, "RunRecord", Record), mock.patch.object(q2_coordinator, "Coordinator", Coordinator),
            mock.patch.object(q2_capture, "capture_existing", side_effect=collect)]
        for patch in patches: patch.start()
        try: return launcher.run(self.value, self.repository)
        finally:
            for patch in reversed(patches): patch.stop()

    def test_handshake_original_budget_assembly_phase_close_finish_and_capture_order(self):
        result = self.invoke()
        self.assertEqual("PREFLIGHT_CLOSED", result["status"])
        order = ["controller", "spawn", "channel", "prepared", "grant", "execution", "argv", "install",
                 "installed_controller", "record", "coordinator", "phase", "finish", "capture"]
        indexes = [self.events.index(event) for event in order]
        self.assertEqual(sorted(indexes), indexes)
        command, options = self.popen_calls[0]
        self.assertEqual("/usr/bin/setpriv", command[0])
        self.assertTrue(options["close_fds"])
        self.assertNotIn("shell", options)
        self.assertEqual(subprocess.DEVNULL, options["stdin"])
        self.assertEqual({"PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": "/run/user/1234"}, options["env"])
        self.assertFalse(result["q3_accepted"])
        self.assertTrue(result["independent_controller_stop_required"])
        self.assertEqual("PHASE_CLOSED", json.loads((self.root/"output"/"resident.stdout").read_bytes())["status"])

    def test_phase_failure_retains_capture_and_never_sends_finish_or_replays(self):
        self.coordinator_failure = True
        result = self.invoke()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("MODELED_PHASE_UNKNOWN", result["reason"])
        self.assertNotIn("finish", self.events)
        self.assertTrue((self.root/"output"/"reservation.json").exists())
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = self.invoke()
        self.assertEqual("LAUNCHER_ALREADY_CONSUMED", result["reason"])
        self.assertEqual(1, len(self.popen_calls))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_complete_phase_cannot_mask_incomplete_resident_capture(self):
        self.capture_complete = False
        result = self.invoke()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("LAUNCHER_RESIDENT_CAPTURE", result["reason"])
        self.assertEqual("PHASE_CLOSED", json.loads((self.root/"output"/"phase.json").read_bytes())["status"])
        self.assertFalse(json.loads((self.root/"output"/"capture.json").read_bytes())["complete"])

    def test_foreign_prepared_operation_never_assembles_or_delivers(self):
        self.prepared["identity"] = "different-operation"
        result = self.invoke()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("LAUNCHER_PREPARED", result["reason"])
        self.assertNotIn("grant", self.events)
        self.assertNotIn("coordinator", self.events)
        self.assertNotIn("finish", self.events)

    def test_successful_process_with_foreign_closure_cannot_close_fixture(self):
        self.foreign_summary = True
        result = self.invoke()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("LAUNCHER_RESIDENT_RESULT", result["reason"])
        self.assertFalse(result["q3_accepted"])

    def test_root_or_foreign_account_rejected_before_any_reservation_or_spawn(self):
        for key, value in (("uid", 0), ("gid", 999)):
            previous = self.value["resident"]["ordinary"][key]
            self.value["resident"]["ordinary"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.invoke()
            self.value["resident"]["ordinary"][key] = previous
        self.assertEqual([], self.popen_calls)
        self.assertEqual([], list((self.root/"output").iterdir()))

    def test_close_error_after_complete_phase_keeps_overall_result_incomplete(self):
        self.cleanup_failure = True
        result = self.invoke()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("LAUNCHER_RECORD_CLOSE", result["reason"])
        self.assertIn("LAUNCHER_RECORD_CLOSE", result["cleanup_errors"])
        self.assertEqual("PHASE_CLOSED", json.loads((self.root/"output"/"phase.json").read_bytes())["status"])
        self.assertTrue((self.root/"output"/"resident.stdout").is_file())

    def test_unexpected_exception_after_spawn_retains_incomplete_result_without_traceback(self):
        self.build_failure = True
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr): result = self.invoke()
        self.assertEqual("", stderr.getvalue())
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("UnexpectedFailure", result["reason"])
        self.assertEqual(1, len(self.popen_calls))
        self.assertIn("grant", self.events)
        self.assertIn("capture", self.events)
        for event in ("install", "coordinator", "finish"): self.assertNotIn(event, self.events)
        self.assertTrue((self.root/"output"/"reservation.json").is_file())
        self.assertTrue((self.root/"output"/"capture.json").is_file())
        retained = json.loads((self.root/"output"/"result.json").read_bytes())
        self.assertEqual(result, retained)
        self.assertNotIn("private build detail", json.dumps(retained))

    def test_unexpected_capture_thread_exception_retains_finite_incomplete_evidence(self):
        self.capture_failure = True
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr): result = self.invoke()
        self.assertEqual("", stderr.getvalue())
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("LAUNCHER_RESIDENT_CAPTURE", result["reason"])
        capture = json.loads((self.root/"output"/"capture.json").read_bytes())
        self.assertFalse(capture["complete"])
        self.assertIsNone(capture["returncode"])
        self.assertEqual([], capture["eof"])
        self.assertEqual("UnexpectedFailure", capture["error"])
        self.assertEqual([], capture["close_errors"])
        self.assertEqual(self.clock["boottime_ns"], capture["started_ns"])
        self.assertEqual(self.value["controller_envelope"]["deadline_ns"], capture["deadline_ns"])
        self.assertTrue(all(stream.closed for stream in self.process_streams))
        self.assertEqual(b"", (self.root/"output"/"resident.stdout").read_bytes())
        self.assertEqual(b"", (self.root/"output"/"resident.stderr").read_bytes())
        self.assertEqual("PHASE_CLOSED", json.loads((self.root/"output"/"phase.json").read_bytes())["status"])
        self.assertEqual(result, json.loads((self.root/"output"/"result.json").read_bytes()))
        self.assertFalse(result["q3_accepted"])

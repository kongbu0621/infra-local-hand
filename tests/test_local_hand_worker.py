from __future__ import annotations

import hashlib
import copy
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from local_hand import act, mailbox_safety, observe, validate, worker
from local_hand.paths import load_profile
from config_fixtures import profile_v2
from local_hand.protocol import LocalHandError, task_digest

MAILBOX_BRANCH = "fixture/mailbox-v1"


class LocalHandCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        admission = mock.patch.object(worker, "validate_worker_mailbox")
        admission.start(); self.addCleanup(admission.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.projects = self.root / "projects"
        self.repo = self.projects / "scratch-local-hand"
        self.repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        # The product intentionally ignores ambient system/global Git config.
        # Make the fixture equally deterministic so Windows runner autocrlf does
        # not manufacture a dirty worktree that Local Hand itself never asked for.
        subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "core.eol", "lf"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Local Hand Test"], cwd=self.repo, check=True)
        (self.repo / "sample.txt").write_bytes(b"before\n")
        (self.repo / "nested").mkdir()
        (self.repo / "nested" / "a.txt").write_bytes(b"a\n")
        (self.repo / "heartbeat_child.py").write_text(
            "from pathlib import Path\n"
            "import time\n"
            "with Path('heartbeat.txt').open('a', encoding='utf-8') as handle:\n"
            "    while True:\n"
            "        handle.write('x')\n"
            "        handle.flush()\n"
            "        time.sleep(0.05)\n",
            encoding="utf-8",
        )
        (self.repo / "spawn_tree.py").write_text(
            "from pathlib import Path\n"
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, 'heartbeat_child.py'])\n"
            "Path('child.pid').write_text(str(child.pid), encoding='utf-8')\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.repo, check=True)

        profile_data = self._profile_data(single_writer=True)
        self.profile_path = self.root / "profile.json"
        self.profile_path.write_text(json.dumps(profile_data), encoding="utf-8")
        self.profile = load_profile(self.profile_path)
        self.runtime = self.root / "runtime"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _profile_data(self, *, single_writer: bool) -> dict:
        return profile_v2({
            "node_id": "test-node",
            "projects_root": str(self.projects),
            "repositories": {
                "scratch-local-hand": {
                    "path": "scratch-local-hand",
                    "single_writer": single_writer,
                    "validations": {
                        "pass": {
                            "argv": [sys.executable, "-c", "print('PASS_MARKER')"],
                            "timeout_seconds": 5,
                            "replay_safe": True,
                        },
                        "fail": {
                            "argv": [sys.executable, "-c", "import sys; print('FAIL_MARKER', file=sys.stderr); sys.exit(3)"],
                            "timeout_seconds": 5,
                            "replay_safe": True,
                        },
                        "timeout": {
                            "argv": [sys.executable, "spawn_tree.py"],
                            "timeout_seconds": 2.0,
                            "replay_safe": True,
                        },
                        "env-probe": {
                            "argv": [
                                sys.executable,
                                "-c",
                                "import os; print('PYTHONPATH='+str(os.environ.get('PYTHONPATH'))); print('VIRTUAL_ENV='+str(os.environ.get('VIRTUAL_ENV'))); print('PYTHONDONTWRITEBYTECODE='+str(os.environ.get('PYTHONDONTWRITEBYTECODE'))); print('LOCAL_HAND_IMPLEMENTATION_COMMIT='+str(os.environ.get('LOCAL_HAND_IMPLEMENTATION_COMMIT')))",
                            ],
                            "timeout_seconds": 5,
                            "replay_safe": True,
                        },
                    },
                }
            },
        })

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    def _init_mailbox(self) -> tuple[Path, Path]:
        origin = self.root / "mailbox-origin.git"
        seed = self.root / "mailbox-seed"
        mailbox = self.root / "mailbox-worker"
        self._git(self.root, "init", "--bare", "-q", str(origin))
        seed.mkdir()
        self._git(seed, "init", "-q")
        self._git(seed, "config", "user.email", "mailbox@example.invalid")
        self._git(seed, "config", "user.name", "Mailbox Test")
        for name in ("tasks", "results", "conflicts"):
            d = seed / "_executor_spike" / name
            d.mkdir(parents=True, exist_ok=True)
            (d / ".keep").write_text("keep\n", encoding="utf-8")
        self._git(seed, "add", ".")
        self._git(seed, "commit", "-qm", "mailbox baseline")
        self._git(seed, "branch", "-M", MAILBOX_BRANCH)
        self._git(seed, "remote", "add", "origin", str(origin))
        self._git(seed, "push", "-q", "-u", "origin", MAILBOX_BRANCH)
        self._git(self.root, "clone", "-q", "--branch", MAILBOX_BRANCH, str(origin), str(mailbox))
        return seed, mailbox

    def _mailbox_commit(self, seed: Path, files: dict[str, dict], message: str) -> None:
        for relative, value in files.items():
            path = seed / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        self._git(seed, "add", ".")
        self._git(seed, "commit", "-qm", message)
        self._git(seed, "push", "-q", "origin", MAILBOX_BRANCH)

    def task(self, action: str, params: dict, *, target: str = "test-node", task_id: str = "LH0001") -> dict:
        return {
            "schema_version": "local-hand-task/v1",
            "task_id": task_id,
            "target_node": target,
            "action": action,
            "params": params,
        }

    def test_node_status_and_repo_audit(self) -> None:
        status = observe.node_status(self.profile)
        self.assertEqual(status["node_id"], "test-node")
        self.assertIn("fs.read_text", status["capabilities"])
        self.assertEqual(status["repository_write_policy"]["scratch-local-hand"], "single-writer")
        audit = observe.repo_audit(self.profile, "scratch-local-hand")
        self.assertFalse(audit["dirty"])
        self.assertTrue(audit["head"])

    def test_read_list_and_git_diff(self) -> None:
        listing = observe.fs_list(self.profile, "scratch-local-hand", ".")
        self.assertIn("sample.txt", [x["name"] for x in listing["entries"]])
        read = observe.fs_read_text(self.profile, "scratch-local-hand", "sample.txt")
        self.assertEqual(read["content"], "before\n")
        self.assertEqual(read["sha256"], hashlib.sha256(b"before\n").hexdigest())
        act.fs_write_text_cas(
            self.profile, "scratch-local-hand", "sample.txt", read["sha256"], "after\n",
            lease_root=self.runtime / "leases",
        )
        diff = observe.git_diff(self.profile, "scratch-local-hand")
        self.assertIn("-before", diff["diff"])
        self.assertIn("+after", diff["diff"])

    def test_cas_write_readback_and_idempotent_retry(self) -> None:
        read = observe.fs_read_text(self.profile, "scratch-local-hand", "sample.txt")
        first = act.fs_write_text_cas(
            self.profile, "scratch-local-hand", "sample.txt", read["sha256"], "after\n",
            lease_root=self.runtime / "leases",
        )
        self.assertFalse(first["already_applied"])
        self.assertTrue(first["read_back_verified"])
        self.assertEqual(first["cas_model"], "single-writer-optimistic")
        second = act.fs_write_text_cas(
            self.profile, "scratch-local-hand", "sample.txt", read["sha256"], "after\n",
            lease_root=self.runtime / "leases",
        )
        self.assertTrue(second["already_applied"])
        self.assertEqual((self.repo / "sample.txt").read_bytes(), b"after\n")

    def test_single_writer_gate_fail_closed(self) -> None:
        path = self.root / "read-only-profile.json"
        path.write_text(json.dumps(self._profile_data(single_writer=False)), encoding="utf-8")
        profile = load_profile(path)
        read = observe.fs_read_text(profile, "scratch-local-hand", "sample.txt")
        with self.assertRaises(LocalHandError) as ctx:
            act.fs_write_text_cas(
                profile, "scratch-local-hand", "sample.txt", read["sha256"], "after\n",
                lease_root=self.runtime / "leases",
            )
        self.assertEqual(ctx.exception.code, "workspace_not_single_writer")
        self.assertEqual((self.repo / "sample.txt").read_bytes(), b"before\n")

    def test_stale_write_has_zero_side_effect(self) -> None:
        before = (self.repo / "sample.txt").read_bytes()
        with self.assertRaises(LocalHandError) as ctx:
            act.fs_write_text_cas(
                self.profile, "scratch-local-hand", "sample.txt", "0" * 64, "should-not-write\n",
                lease_root=self.runtime / "leases",
            )
        self.assertEqual(ctx.exception.code, "stale_write")
        self.assertEqual(ctx.exception.status, "stale")
        self.assertEqual((self.repo / "sample.txt").read_bytes(), before)

    def test_cas_detects_change_before_replace(self) -> None:
        read = observe.fs_read_text(self.profile, "scratch-local-hand", "sample.txt")
        real_safe = act.safe_existing_path
        calls = 0

        def racing_safe(repo: Path, relative_path: str, *, expect: str | None = None) -> Path:
            nonlocal calls
            calls += 1
            if calls == 2:
                (self.repo / "sample.txt").write_bytes(b"external-writer\n")
            return real_safe(repo, relative_path, expect=expect)

        with mock.patch("local_hand.act.safe_existing_path", side_effect=racing_safe):
            with self.assertRaises(LocalHandError) as ctx:
                act.fs_write_text_cas(
                    self.profile, "scratch-local-hand", "sample.txt", read["sha256"], "local-hand\n",
                    lease_root=self.runtime / "leases",
                )
        self.assertEqual(ctx.exception.code, "stale_write")
        self.assertEqual((self.repo / "sample.txt").read_bytes(), b"external-writer\n")

    def test_repository_path_and_git_metadata_boundaries(self) -> None:
        with self.assertRaises(LocalHandError) as ctx:
            observe.fs_read_text(self.profile, "missing-repo", "x")
        self.assertEqual(ctx.exception.code, "repository_not_allowlisted")
        for bad in ("../outside.txt", "/etc/passwd"):
            with self.assertRaises(LocalHandError) as ctx:
                observe.fs_read_text(self.profile, "scratch-local-hand", bad)
            self.assertEqual(ctx.exception.code, "path_escape")
        for git_path in (".git/config", ".GIT/config"):
            with self.assertRaises(LocalHandError) as ctx:
                observe.fs_read_text(self.profile, "scratch-local-hand", git_path)
            self.assertEqual(ctx.exception.code, "git_metadata_rejected")
            with self.assertRaises(LocalHandError) as ctx:
                act.fs_write_text_cas(
                    self.profile, "scratch-local-hand", git_path, "0" * 64, "blocked\n",
                    lease_root=self.runtime / "leases",
                )
            self.assertEqual(ctx.exception.code, "git_metadata_rejected")

        with self.assertRaises(LocalHandError) as ctx:
            observe.fs_read_text(self.profile, "scratch-local-hand", "bad\x7fname.txt")
        self.assertEqual(ctx.exception.code, "path_syntax_rejected")

    def test_symlink_rejected(self) -> None:
        outside = self.root / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        link = self.repo / "escape.txt"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable in this environment")
        with self.assertRaises(LocalHandError) as ctx:
            observe.fs_read_text(self.profile, "scratch-local-hand", "escape.txt")
        self.assertEqual(ctx.exception.code, "symlink_rejected")

    def test_non_utf8_and_oversized_rejected(self) -> None:
        binary = self.repo / "binary.dat"
        binary.write_bytes(b"\xff\xfe")
        with self.assertRaises(LocalHandError) as ctx:
            observe.fs_read_text(self.profile, "scratch-local-hand", "binary.dat")
        self.assertEqual(ctx.exception.code, "not_utf8")
        large = self.repo / "large.txt"
        large.write_bytes(b"abcdef")
        old = observe.MAX_TEXT_BYTES
        observe.MAX_TEXT_BYTES = 3
        try:
            with self.assertRaises(LocalHandError) as ctx:
                observe.fs_read_text(self.profile, "scratch-local-hand", "large.txt")
            self.assertEqual(ctx.exception.code, "read_too_large")
        finally:
            observe.MAX_TEXT_BYTES = old

    def test_validation_profiles_pass_fail_timeout_tree_and_shell_false(self) -> None:
        with mock.patch("local_hand.validate.subprocess.Popen", wraps=subprocess.Popen) as popen:
            passed = validate.run_profile(self.profile, "scratch-local-hand", "pass")
            self.assertEqual(passed["exit_code"], 0)
            self.assertIn("PASS_MARKER", passed["stdout"])
            self.assertFalse(popen.call_args.kwargs["shell"])
        with self.assertRaises(validate.ValidationFailed) as ctx:
            validate.run_profile(self.profile, "scratch-local-hand", "fail")
        self.assertEqual(ctx.exception.code, "validation_failed")
        self.assertEqual(ctx.exception.details["exit_code"], 3)
        self.assertIn("FAIL_MARKER", ctx.exception.details["stderr"])

        with self.assertRaises(validate.ValidationFailed) as ctx:
            validate.run_profile(self.profile, "scratch-local-hand", "timeout")
        self.assertEqual(ctx.exception.code, "validation_timeout")
        self.assertTrue(ctx.exception.details["timed_out"])
        self.assertTrue(ctx.exception.details["termination_confirmed"])
        self.assertEqual(ctx.exception.details["termination_scope"], "process_tree")
        heartbeat = self.repo / "heartbeat.txt"
        self.assertTrue(heartbeat.exists(), "child heartbeat should start before timeout")
        size_before = heartbeat.stat().st_size
        time.sleep(0.25)
        size_after = heartbeat.stat().st_size
        self.assertEqual(size_before, size_after, "descendant process survived validation timeout")

        with self.assertRaises(LocalHandError) as ctx:
            validate.run_profile(self.profile, "scratch-local-hand", "unknown")
        self.assertEqual(ctx.exception.code, "validation_profile_not_allowlisted")

    def test_windows_taskkill_output_is_never_text_decoded(self) -> None:
        proc = mock.Mock()
        proc.pid = 12345
        proc.wait.return_value = 1
        killer = subprocess.CompletedProcess(["taskkill"], 0)

        with (
            mock.patch.object(validate.os, "name", "nt"),
            mock.patch("local_hand.validate.subprocess.run", return_value=killer) as run,
        ):
            exit_code, confirmed, method = validate._terminate_tree(proc)

        self.assertEqual(exit_code, 1)
        self.assertTrue(confirmed)
        self.assertEqual(method, "windows-taskkill-tree")
        kwargs = run.call_args.kwargs
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)
        self.assertNotIn("text", kwargs)
        self.assertNotIn("encoding", kwargs)
        self.assertNotIn("errors", kwargs)

    def test_validation_does_not_inherit_worker_python_env(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "PYTHONPATH": "SHOULD_NOT_LEAK",
                "VIRTUAL_ENV": "SHOULD_NOT_LEAK",
                "PYTHONDONTWRITEBYTECODE": "SHOULD_BE_NORMALIZED",
                "LOCAL_HAND_IMPLEMENTATION_COMMIT": worker._implementation_commit(),
            },
            clear=False,
        ):
            details = validate.run_profile(self.profile, "scratch-local-hand", "env-probe")
        self.assertIn("PYTHONPATH=None", details["stdout"])
        self.assertIn("VIRTUAL_ENV=None", details["stdout"])
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", details["stdout"])
        self.assertIn("LOCAL_HAND_IMPLEMENTATION_COMMIT=" + worker._implementation_commit(), details["stdout"])
        self.assertTrue(details["bytecode_writes_disabled"])
        self.assertFalse(details["inherited_pythonpath"])
        self.assertFalse(details["inherited_virtual_env"])
        with mock.patch.dict(
            os.environ,
            {"LOCAL_HAND_IMPLEMENTATION_COMMIT": "INVALID"},
            clear=False,
        ):
            self.assertNotIn("LOCAL_HAND_IMPLEMENTATION_COMMIT", validate._filtered_env())

    def test_validation_profile_must_explicitly_be_replay_safe(self) -> None:
        missing = copy.deepcopy(self._profile_data(single_writer=True))
        del missing["repositories"]["scratch-local-hand"]["validations"]["pass"]["replay_safe"]
        missing_path = self.root / "missing-replay-safe.json"
        missing_path.write_text(json.dumps(missing), encoding="utf-8")
        with self.assertRaises(LocalHandError) as ctx:
            load_profile(missing_path)
        self.assertEqual(ctx.exception.code, "invalid_profile")

        unsafe = copy.deepcopy(self._profile_data(single_writer=True))
        unsafe["repositories"]["scratch-local-hand"]["validations"]["pass"]["replay_safe"] = False
        unsafe_path = self.root / "unsafe-replay.json"
        unsafe_path.write_text(json.dumps(unsafe), encoding="utf-8")
        unsafe_profile = load_profile(unsafe_path)
        with mock.patch("local_hand.validate.subprocess.Popen") as popen:
            with self.assertRaises(LocalHandError) as ctx:
                validate.run_profile(unsafe_profile, "scratch-local-hand", "pass")
            popen.assert_not_called()
        self.assertEqual(ctx.exception.code, "validation_profile_not_replay_safe")

    def test_result_provenance_is_bound(self) -> None:
        instance_id = "11111111-2222-4333-8444-555555555555"
        with mock.patch.dict(os.environ, {
            "LOCAL_HAND_IMPLEMENTATION_COMMIT": worker._implementation_commit(),
            "LOCAL_HAND_INSTALL_INSTANCE_ID": instance_id,
            "USER": "environment-impostor",
            "USERNAME": "environment-impostor",
        }, clear=False):
            result = worker.execute_task(self.task("node.status", {}), self.profile, self.runtime)
        assert result is not None
        self.assertEqual(result["implementation_commit"], worker._implementation_commit())
        self.assertRegex(result["package_digest"], r"^[0-9a-f]{64}$")
        expected_profile = hashlib.sha256(self.profile_path.read_bytes()).hexdigest()
        self.assertEqual(result["profile_digest"], expected_profile)
        self.assertEqual(result["node_id"], "test-node")
        identity = result["details"]
        self.assertEqual(identity["worker_pid"], os.getpid())
        self.assertTrue(identity["effective_os_user"])
        self.assertNotEqual(identity["effective_os_user"], "environment-impostor")
        self.assertEqual(identity["service_account"], identity["effective_os_user"])
        self.assertEqual(identity["install_instance_id"], instance_id)
        self.assertEqual(identity["runtime_identity"]["implementation_commit"], result["implementation_commit"])
        self.assertEqual(identity["runtime_identity"]["package_digest"], result["package_digest"])
        self.assertEqual(identity["runtime_identity"]["profile_digest"], result["profile_digest"])

    def test_worker_target_action_and_structured_failure(self) -> None:
        wrong = worker.execute_task(self.task("node.status", {}, target="other-node"), self.profile, self.runtime)
        self.assertIsNone(wrong)
        with self.assertRaises(LocalHandError) as ctx:
            worker.validate_task(self.task("shell.exec", {}))
        self.assertEqual(ctx.exception.code, "action_not_allowlisted")
        task = self.task("fs.write_text_cas", {
            "repository": "scratch-local-hand",
            "relative_path": "sample.txt",
            "expected_sha256": "0" * 64,
            "content": "nope\n",
        })
        try:
            worker.execute_task(task, self.profile, self.runtime)
        except Exception as exc:
            result = worker.result_error(task, self.profile.node_id, exc, worker.build_provenance(self.profile))
        else:
            self.fail("expected stale write")
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["error_code"], "stale_write")

    def test_crash_after_effect_does_not_replay_before_result_persistence(self) -> None:
        class SimulatedCrash(BaseException):
            pass
        mailbox=self.root/'crash-mailbox'
        for name in ('tasks','results','conflicts'):
            (mailbox/'_executor_spike'/name).mkdir(parents=True)
        task=self.task('validation.run_profile',{'repository':'scratch-local-hand','profile':'pass'},task_id='LH8801')
        (mailbox/'_executor_spike/tasks/LH8801.json').write_text(json.dumps(task))
        effect=self.root/'effect.txt'
        def interrupted(*args):
            effect.write_text('executed once')
            raise SimulatedCrash()
        with mock.patch.object(worker,'publish_outbox'),mock.patch.object(worker,'sync_mailbox'):
            with mock.patch.object(worker,'execute_task',side_effect=interrupted):
                with self.assertRaises(SimulatedCrash):worker.process_once(mailbox,MAILBOX_BRANCH,self.profile,self.runtime)
            self.assertTrue((self.runtime/'receipts/LH8801.json').exists())
            with mock.patch.object(worker,'execute_task') as execute:
                worker.process_once(mailbox,MAILBOX_BRANCH,self.profile,self.runtime)
                execute.assert_not_called()
        result=json.loads((self.runtime/'outbox/LH8801.json').read_text())
        self.assertEqual(result['status'],'indeterminate')
        self.assertEqual(result['error_code'],'outcome_unknown')
        self.assertEqual(effect.read_text(),'executed once')

    def test_receipt_write_failure_prevents_execution(self) -> None:
        mailbox=self.root/'receipt-failure'
        for name in ('tasks','results','conflicts'):
            (mailbox/'_executor_spike'/name).mkdir(parents=True)
        task=self.task('node.status',{},task_id='LH8802')
        (mailbox/'_executor_spike/tasks/LH8802.json').write_text(json.dumps(task))
        with mock.patch.object(worker,'publish_outbox'),mock.patch.object(worker,'sync_mailbox'),mock.patch.object(worker,'write_json_atomic',side_effect=OSError('fixture: receipt disk unavailable')),mock.patch.object(worker,'execute_task',wraps=worker.execute_task) as execute:
            with self.assertRaises(OSError):worker.process_once(mailbox,MAILBOX_BRANCH,self.profile,self.runtime)
            execute.assert_not_called()

    @unittest.skipIf(os.name == 'nt', 'POSIX directory fsync semantics')
    def test_receipt_directory_fsync_failure_prevents_execution(self) -> None:
        import stat
        mailbox = self.root / 'receipt-directory-failure'
        for name in ('tasks', 'results', 'conflicts'):
            (mailbox / '_executor_spike' / name).mkdir(parents=True)
        task = self.task('node.status', {}, task_id='LH8803')
        (mailbox / '_executor_spike/tasks/LH8803.json').write_text(json.dumps(task))
        real_fsync = os.fsync
        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError('fixture: directory persistence unavailable')
            return real_fsync(fd)
        with mock.patch.object(worker, 'publish_outbox'), mock.patch.object(worker, 'sync_mailbox'), mock.patch.object(worker.os, 'fsync', side_effect=fail_directory), mock.patch.object(worker, 'execute_task') as execute:
            with self.assertRaises(LocalHandError) as raised:
                worker.process_once(mailbox, MAILBOX_BRANCH, self.profile, self.runtime)
            execute.assert_not_called()
        self.assertEqual(raised.exception.code, 'local_state_durability_unconfirmed')
        self.assertEqual(raised.exception.status, 'indeterminate')
        self.assertEqual(json.loads((self.runtime/'receipts/LH8803.json').read_text())['source'], 'local_execution_started')

    def test_worker_startup_rejects_invalid_absolute_runtime_binding_before_lock(self) -> None:
        state = self.root / "startup-state"
        with mock.patch.dict(os.environ, {"LOCAL_HAND_GIT_EXECUTABLE": "git"}, clear=False):
            with mock.patch("local_hand.worker.worker_instance_lock") as lock:
                result = worker.main([
                    "--profile", str(self.profile_path),
                    "--mailbox-repo", str(self.root / "mailbox"),
                    "--state-root", str(state),
                    "--once",
                ])
                lock.assert_not_called()
        self.assertEqual(result, 3)
        self.assertFalse(state.exists())

    def test_action_parameter_schemas_are_exact_and_fail_closed(self) -> None:
        valid = {
            "node.status": {},
            "repo.audit": {"repository": "scratch-local-hand"},
            "fs.list": {"repository": "scratch-local-hand"},
            "fs.read_text": {"repository": "scratch-local-hand", "relative_path": "sample.txt"},
            "fs.write_text_cas": {
                "repository": "scratch-local-hand",
                "relative_path": "sample.txt",
                "expected_sha256": "0" * 64,
                "content": "",
            },
            "git.status": {"repository": "scratch-local-hand"},
            "git.diff": {"repository": "scratch-local-hand"},
            "validation.run_profile": {"repository": "scratch-local-hand", "profile": "pass"},
        }
        for action, params in valid.items():
            with self.subTest(action=action, case="valid"):
                worker.validate_task(self.task(action, params))
            with self.subTest(action=action, case="unknown"):
                invalid = dict(params)
                invalid["typo"] = "x"
                with self.assertRaises(LocalHandError) as ctx:
                    worker.validate_task(self.task(action, invalid))
                self.assertEqual(ctx.exception.code, "invalid_params")

        required = {
            "repo.audit": {"repository"},
            "fs.list": {"repository"},
            "fs.read_text": {"repository", "relative_path"},
            "fs.write_text_cas": {"repository", "relative_path", "expected_sha256", "content"},
            "git.status": {"repository"},
            "git.diff": {"repository"},
            "validation.run_profile": {"repository", "profile"},
        }
        for action, names in required.items():
            for name in names:
                for replacement in ("missing", None):
                    with self.subTest(action=action, name=name, replacement=replacement):
                        params = dict(valid[action])
                        if replacement == "missing":
                            params.pop(name)
                        else:
                            params[name] = None
                        with self.assertRaises(LocalHandError) as ctx:
                            worker.validate_task(self.task(action, params))
                        self.assertEqual(ctx.exception.code, "invalid_params")

        missing_params = self.task("node.status", {})
        del missing_params["params"]
        for params_value in (missing_params, {**self.task("node.status", {}), "params": None}):
            with self.assertRaises(LocalHandError) as ctx:
                worker.validate_task(params_value)
            self.assertEqual(ctx.exception.code, "invalid_params")

        null_optional = self.task("fs.list", {"repository": "scratch-local-hand", "relative_path": None})
        with self.assertRaises(LocalHandError) as ctx:
            worker.validate_task(null_optional)
        self.assertEqual(ctx.exception.code, "invalid_params")

    def test_wrong_target_is_ignored_before_action_contract_interpretation(self) -> None:
        cases = [
            self.task("shell.exec", {"command": "must-not-run"}, target="other-node"),
            {**self.task("node.status", {}, target="other-node"), "params": None},
            {key: value for key, value in self.task("node.status", {}, target="other-node").items() if key != "params"},
        ]
        for task in cases:
            with self.subTest(task=task):
                self.assertIsNone(worker.execute_task(task, self.profile, self.runtime))

    def test_process_once_returns_structured_rejection_for_unknown_action(self) -> None:
        seed, mailbox = self._init_mailbox()
        task = self.task("shell.exec", {}, task_id="LH0101")
        self._mailbox_commit(seed, {"_executor_spike/tasks/LH0101.json": task}, "invalid action")
        worker.process_once(mailbox, MAILBOX_BRANCH, self.profile, self.runtime / "worker-state")
        worker.sync_mailbox(mailbox, MAILBOX_BRANCH)
        result = json.loads((mailbox / "_executor_spike/results/LH0101.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error_code"], "action_not_allowlisted")

    def test_process_once_rejects_missing_cas_content_with_zero_side_effect(self) -> None:
        seed, mailbox = self._init_mailbox()
        before = (self.repo / "sample.txt").read_bytes()
        task = self.task(
            "fs.write_text_cas",
            {
                "repository": "scratch-local-hand",
                "relative_path": "sample.txt",
                "expected_sha256": hashlib.sha256(before).hexdigest(),
            },
            task_id="LH0105",
        )
        self._mailbox_commit(seed, {"_executor_spike/tasks/LH0105.json": task}, "missing CAS content")
        worker.process_once(mailbox, MAILBOX_BRANCH, self.profile, self.runtime / "worker-state")
        worker.sync_mailbox(mailbox, MAILBOX_BRANCH)
        result = json.loads((mailbox / "_executor_spike/results/LH0105.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error_code"], "invalid_params")
        self.assertEqual((self.repo / "sample.txt").read_bytes(), before)

    def test_digest_conflict_is_quarantined_without_wedging_later_task(self) -> None:
        seed, mailbox = self._init_mailbox()
        original = self.task("node.status", {}, task_id="LH0102")
        conflicting = self.task("node.status", {"collision": True}, task_id="LH0102")
        later = self.task("node.status", {}, task_id="LH0103")
        provenance = worker.build_provenance(self.profile)
        remote_result = {
            "schema_version": "local-hand-result/v1",
            "task_id": "LH0102",
            "task_digest": task_digest(original),
            "target_node": "test-node",
            "node_id": "test-node",
            "action": "node.status",
            "status": "succeeded",
            "worker_version": "historical",
            "implementation_commit": provenance["implementation_commit"],
            "package_digest": provenance["package_digest"],
            "profile_digest": provenance["profile_digest"],
            "details": {},
            "error_code": None,
            "error": None,
        }
        self._mailbox_commit(seed, {
            "_executor_spike/results/LH0102.json": remote_result,
            "_executor_spike/tasks/LH0102.json": conflicting,
            "_executor_spike/tasks/LH0103.json": later,
        }, "conflict and later task")

        state = self.runtime / "conflict-state"
        worker.process_once(mailbox, MAILBOX_BRANCH, self.profile, state)
        worker.sync_mailbox(mailbox, MAILBOX_BRANCH)

        later_result = json.loads((mailbox / "_executor_spike/results/LH0103.json").read_text(encoding="utf-8"))
        self.assertEqual(later_result["status"], "succeeded")
        incoming_digest = task_digest(conflicting)
        conflict_name = worker._conflict_filename("LH0102", incoming_digest, task_digest(original))
        conflict_path = mailbox / "_executor_spike" / "conflicts" / conflict_name
        self.assertTrue(conflict_path.exists())
        conflict = json.loads(conflict_path.read_text(encoding="utf-8"))
        self.assertEqual(conflict["status"], "rejected")
        self.assertEqual(conflict["error_code"], "remote_task_id_digest_conflict")
        self.assertTrue((state / "conflicts" / conflict_name).exists())

    def test_publish_outbox_digest_collision_quarantines_without_wedge(self) -> None:
        seed, mailbox = self._init_mailbox()
        original = self.task("node.status", {}, task_id="LH0104")
        incoming = self.task("node.status", {"new": True}, task_id="LH0104")
        provenance = worker.build_provenance(self.profile)
        remote_result = {
            "schema_version": "local-hand-result/v1",
            "task_id": "LH0104",
            "task_digest": task_digest(original),
            "target_node": "test-node",
            "node_id": "test-node",
            "action": "node.status",
            "status": "succeeded",
            "worker_version": "historical",
            "implementation_commit": provenance["implementation_commit"],
            "package_digest": provenance["package_digest"],
            "profile_digest": provenance["profile_digest"],
            "details": {},
            "error_code": None,
            "error": None,
        }
        self._mailbox_commit(seed, {"_executor_spike/results/LH0104.json": remote_result}, "remote result")
        worker.sync_mailbox(mailbox, MAILBOX_BRANCH)

        outbox = self.runtime / "publish-collision-outbox"
        incoming_result = worker.result_success(
            incoming, "test-node", {}, worker.build_provenance(self.profile)
        )
        worker.write_json_atomic(outbox / "LH0104.json", incoming_result)
        worker.publish_outbox(mailbox, MAILBOX_BRANCH, outbox)
        self.assertFalse(mailbox_safety.target_lexists(outbox / "LH0104.json"))
        conflict_name = worker._conflict_filename(
            "LH0104", task_digest(incoming), task_digest(original)
        )
        self.assertTrue((outbox / conflict_name).exists())

        worker.publish_outbox(mailbox, MAILBOX_BRANCH, outbox)
        worker.sync_mailbox(mailbox, MAILBOX_BRANCH)
        conflict_path = mailbox / "_executor_spike" / "conflicts" / conflict_name
        self.assertTrue(conflict_path.exists())
        conflict = json.loads(conflict_path.read_text(encoding="utf-8"))
        self.assertEqual(conflict["status"], "indeterminate")
        self.assertEqual(conflict["error_code"], "remote_result_digest_conflict")

    def test_publish_outbox_same_digest_content_conflict_preserves_local_result(self) -> None:
        seed, mailbox = self._init_mailbox()
        task = self.task("node.status", {}, task_id="LH0105")
        remote_result = worker.result_success(task,"test-node",{"source":"remote"},worker.build_provenance(self.profile))
        self._mailbox_commit(seed,{"_executor_spike/results/LH0105.json":remote_result},"remote result")
        worker.sync_mailbox(mailbox,MAILBOX_BRANCH)
        outbox=self.runtime/"publish-content-collision-outbox"
        local_result=worker.result_success(task,"test-node",{"source":"local"},worker.build_provenance(self.profile))
        worker.write_json_atomic(outbox/"LH0105.json",local_result)
        worker.publish_outbox(mailbox,MAILBOX_BRANCH,outbox)
        self.assertFalse(mailbox_safety.target_lexists(outbox/"LH0105.json"))
        quarantined=list((outbox.parent/"quarantine").glob("LH0105.json.*.conflict"))
        self.assertEqual(len(quarantined),1)
        self.assertEqual(json.loads(quarantined[0].read_text()),local_result)
        conflict_path=outbox/worker._conflict_filename("LH0105",task_digest(task),task_digest(task))
        conflict=json.loads(conflict_path.read_text())
        self.assertEqual(conflict["error_code"],"remote_result_content_conflict")
        self.assertNotEqual(conflict["details"]["local_result_sha256"],conflict["details"]["remote_result_sha256"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from local_hand import act, bounded_io, git_safety, mailbox_safety, observe, worker
from local_hand.paths import load_profile
from config_fixtures import profile_v2
from local_hand.protocol import LocalHandError, task_digest


class LocalHandHardeningDTests(unittest.TestCase):
    def setUp(self) -> None:
        admission = mock.patch.object(worker, "validate_worker_mailbox")
        admission.start(); self.addCleanup(admission.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.projects = self.root / "projects"
        self.repo = self.projects / "scratch"
        self.repo.mkdir(parents=True)
        self._git(self.repo, "init", "-q")
        self._git(self.repo, "config", "user.name", "D test")
        self._git(self.repo, "config", "user.email", "d@example.invalid")
        (self.repo / "sample.txt").write_text("before\n", encoding="utf-8")
        self._git(self.repo, "add", ".")
        self._git(self.repo, "commit", "-qm", "base")
        data = {
            "node_id": "d-node",
            "projects_root": str(self.projects),
            "repositories": {
                "scratch": {
                    "path": "scratch",
                    "single_writer": True,
                    "validations": {
                        "pass": {"argv": [sys.executable, "-c", "print('ok')"], "timeout_seconds": 5, "replay_safe": True}
                    },
                }
            },
        }
        self.profile_path = self.root / "profile.json"
        self.profile_path.write_text(json.dumps(profile_v2(data)), encoding="utf-8")
        self.profile = load_profile(self.profile_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def _task(self, tid: str = "LH9001") -> dict:
        return {"schema_version": "local-hand-task/v1", "task_id": tid, "target_node": "d-node", "action": "node.status", "params": {}}

    def _mailbox_dirs(self) -> Path:
        mailbox = self.root / "mailbox"
        (mailbox / ".git").mkdir(parents=True)
        (mailbox / "_executor_spike").mkdir()
        for name in ("tasks", "results", "conflicts"):
            (mailbox / "_executor_spike" / name).mkdir()
        return mailbox

    @unittest.skipIf(os.name == "nt", "symlink privilege varies on Windows")
    def test_dangling_mailbox_result_symlink_cannot_write_outside(self) -> None:
        mailbox = self._mailbox_dirs()
        outside = self.root / "outside-created.json"
        target = mailbox / "_executor_spike" / "results" / "LH9001.json"
        target.symlink_to(outside)
        with self.assertRaises(LocalHandError):
            mailbox_safety.atomic_create_control_file(mailbox, target, b"{}\n")
        self.assertFalse(outside.exists())

    @unittest.skipIf(os.name == "nt", "symlink privilege varies on Windows")
    def test_task_json_symlink_is_not_followed(self) -> None:
        real = self.root / "real.json"
        real.write_text("{}", encoding="utf-8")
        link = self.root / "LH9002.json"
        link.symlink_to(real)
        with self.assertRaises(LocalHandError) as ctx:
            worker.load_json_bounded(link, 1024, "task_file_invalid")
        self.assertEqual(ctx.exception.code, "task_file_invalid")

    def test_remote_tree_rejects_exact_control_root_and_control_children_links(self) -> None:
        cases = [
            b"120000 blob " + b"a" * 40 + b" 12\t_executor_spike\0",
            b"120000 blob " + b"a" * 40 + b" 12\t_executor_spike/results/LH9001.json\0",
            b"160000 commit " + b"b" * 40 + b" -\t_executor_spike/tasks/submodule\0",
        ]
        for records in cases:
            with self.subTest(records=records):
                with self.assertRaises(LocalHandError) as ctx:
                    mailbox_safety.validate_ls_tree_records(records)
                self.assertEqual(ctx.exception.code, "mailbox_symlink_rejected")
        # The transport repository legitimately contains sibling README/worker files;
        # they are not control payload and must not be confused with tasks/results/conflicts.
        mailbox_safety.validate_ls_tree_records(
            b"100644 blob " + b"c" * 40 + b" 12\t_executor_spike/README.md\0"
        )

    def test_missing_optional_conflicts_directory_is_created_safely(self) -> None:
        mailbox = self.root / "mailbox-missing-conflicts"
        (mailbox / ".git").mkdir(parents=True)
        for name in ("tasks", "results"):
            (mailbox / "_executor_spike" / name).mkdir(parents=True, exist_ok=True)
        mailbox_safety.validate_checkout_control_dirs(mailbox)
        self.assertTrue((mailbox / "_executor_spike" / "conflicts").is_dir())

    def test_windows_control_directory_creation_inherits_service_acl(self) -> None:
        path = self.root / "windows-control-directory"
        with (
            mock.patch.object(mailbox_safety.os, "name", "nt"),
            mock.patch.object(mailbox_safety.os, "mkdir") as mkdir,
        ):
            mailbox_safety._create_control_directory(path)
        mkdir.assert_called_once_with(path)

    def test_posix_control_directory_creation_remains_private(self) -> None:
        path = self.root / "posix-control-directory"
        with (
            mock.patch.object(mailbox_safety.os, "name", "posix"),
            mock.patch.object(mailbox_safety.os, "mkdir") as mkdir,
        ):
            mailbox_safety._create_control_directory(path)
        mkdir.assert_called_once_with(path, 0o700)

    def test_mailbox_tree_file_byte_missing_blob_and_disk_ceilings(self) -> None:
        with mock.patch.object(mailbox_safety, "MAX_MAILBOX_TRACKED_FILES", 2):
            records = b"".join(
                f"100644 blob {'a'*40} 1\t_executor_spike/tasks/LH{i:04d}.json\0".encode()
                for i in range(3)
            )
            with self.assertRaises(LocalHandError) as ctx:
                mailbox_safety.validate_ls_tree_records(records)
            self.assertEqual(ctx.exception.code, "mailbox_tree_too_large")
        with mock.patch.object(mailbox_safety, "MAX_MAILBOX_TRACKED_BYTES", 2):
            records = f"100644 blob {'a'*40} 3\t_executor_spike/tasks/LH9001.json\0".encode()
            with self.assertRaises(LocalHandError) as ctx:
                mailbox_safety.validate_ls_tree_records(records)
            self.assertEqual(ctx.exception.code, "mailbox_tree_too_large")
        missing = f"100644 blob {'a'*40} -\t_executor_spike/tasks/LH9001.json\0".encode()
        with self.assertRaises(LocalHandError) as ctx:
            mailbox_safety.validate_ls_tree_records(missing)
        self.assertEqual(ctx.exception.code, "mailbox_blob_unavailable")
        mailbox = self._mailbox_dirs()
        (mailbox / ".git" / "large").write_bytes(b"x" * 32)
        with mock.patch.object(mailbox_safety, "MAX_MAILBOX_DISK_BYTES", 8):
            with self.assertRaises(LocalHandError) as ctx:
                mailbox_safety.enforce_mailbox_disk_quota(mailbox)
            self.assertEqual(ctx.exception.code, "mailbox_disk_quota_exceeded")

    def test_fs_list_fails_at_limit_plus_one(self) -> None:
        for i in range(5):
            (self.repo / f"x{i}.txt").write_text("x", encoding="utf-8")
        old = observe.MAX_LIST_ENTRIES
        observe.MAX_LIST_ENTRIES = 3
        try:
            with self.assertRaises(LocalHandError) as ctx:
                observe.fs_list(self.profile, "scratch", ".")
            self.assertEqual(ctx.exception.code, "directory_too_large")
        finally:
            observe.MAX_LIST_ENTRIES = old

    def test_project_git_output_is_bounded_while_drained(self) -> None:
        (self.repo / "sample.txt").write_text("x" * 20000, encoding="utf-8")
        old = observe.MAX_GIT_OUTPUT_BYTES
        observe.MAX_GIT_OUTPUT_BYTES = 512
        try:
            with self.assertRaises(LocalHandError) as ctx:
                observe.git_diff(self.profile, "scratch")
            self.assertEqual(ctx.exception.code, "git_output_too_large")
        finally:
            observe.MAX_GIT_OUTPUT_BYTES = old

    def test_cas_existing_file_reads_use_same_size_ceiling(self) -> None:
        path = self.repo / "sample.txt"
        before = path.read_bytes()
        old = act.MAX_TEXT_BYTES
        act.MAX_TEXT_BYTES = 3
        try:
            with self.assertRaises(LocalHandError) as ctx:
                act.fs_write_text_cas(
                    self.profile,
                    "scratch",
                    "sample.txt",
                    "0" * 64,
                    "x",
                    lease_root=self.root / "leases",
                )
            self.assertEqual(ctx.exception.code, "write_source_too_large")
            self.assertEqual(path.read_bytes(), before)
        finally:
            act.MAX_TEXT_BYTES = old

    def test_generic_bounded_subprocess_never_retains_excess_output(self) -> None:
        with self.assertRaises(LocalHandError) as ctx:
            bounded_io.run_process_bounded(
                [sys.executable, "-c", "import sys;sys.stdout.write('x'*10000)"],
                cwd=self.root,
                env=dict(os.environ),
                timeout=5,
                max_stdout=128,
                max_stderr=128,
                code_prefix="probe",
                text=False,
            )
        self.assertEqual(ctx.exception.code, "probe_output_too_large")

    def test_generic_bounded_subprocess_timeout_kills_descendant_tree(self) -> None:
        child = self.root / "child.py"
        parent = self.root / "parent.py"
        child.write_text(
            "from pathlib import Path\nimport time\np=Path('heartbeat.txt')\n"
            "while True:\n p.write_text(p.read_text()+'x' if p.exists() else 'x')\n time.sleep(.03)\n",
            encoding="utf-8",
        )
        parent.write_text(
            "import subprocess,sys,time\nsubprocess.Popen([sys.executable,'child.py'])\ntime.sleep(30)\n",
            encoding="utf-8",
        )
        with self.assertRaises(LocalHandError) as ctx:
            bounded_io.run_process_bounded(
                [sys.executable, "parent.py"],
                cwd=self.root,
                env=dict(os.environ),
                timeout=0.5,
                max_stdout=1024,
                max_stderr=1024,
                code_prefix="tree",
                text=False,
            )
        self.assertEqual(ctx.exception.code, "tree_timeout")
        heartbeat = self.root / "heartbeat.txt"
        self.assertTrue(heartbeat.exists())
        size_before = heartbeat.stat().st_size
        time.sleep(0.2)
        self.assertEqual(heartbeat.stat().st_size, size_before)

    def test_remote_result_requires_digest_node_and_provenance(self) -> None:
        task = self._task()
        with mock.patch.dict(os.environ, {"LOCAL_HAND_IMPLEMENTATION_COMMIT": worker._implementation_commit()}, clear=False):
            result = worker.result_success(task, "d-node", {}, worker.build_provenance(self.profile))
        worker.validate_remote_result(result, task["task_id"], task["action"], "d-node", task_digest(task))
        for field, value in (("task_digest", "b" * 64), ("package_digest", None), ("node_id", "other")):
            forged = dict(result)
            forged[field] = value
            with self.assertRaises(LocalHandError):
                worker.validate_remote_result(forged, task["task_id"], task["action"], "d-node", task_digest(task))

    def test_windows_ssh_command_uses_git_shell_paths(self) -> None:
        windows_paths = {
            "LOCAL_HAND_MAILBOX_SSH_KEY": r"D:\Local Hand\mailbox_id",
            "LOCAL_HAND_KNOWN_HOSTS": r"C:\ProgramData\Local Hand\known_hosts",
        }
        with (
            mock.patch.dict(os.environ, windows_paths, clear=False),
            mock.patch.object(git_safety.os, "name", "nt"),
            mock.patch.object(git_safety.os, "devnull", "NUL"),
            mock.patch.object(
                git_safety,
                "_bound_executable",
                return_value=r"C:\Windows\System32\OpenSSH\ssh.exe",
            ),
        ):
            command = git_safety._ssh_command()

        self.assertNotIn("\\", command)
        self.assertIn("C:/Windows/System32/OpenSSH/ssh.exe", command)
        self.assertIn("D:/Local Hand/mailbox_id", command)
        self.assertIn("UserKnownHostsFile=C:/ProgramData/Local Hand/known_hosts", command)

    def test_receipt_nested_result_digest_must_match_top_level(self) -> None:
        task = self._task("LH9003")
        with mock.patch.dict(os.environ, {"LOCAL_HAND_IMPLEMENTATION_COMMIT": worker._implementation_commit()}, clear=False):
            result = worker.result_success(task, "d-node", {}, worker.build_provenance(self.profile))
        forged = dict(result)
        forged["task_digest"] = "d" * 64
        receipt = {"task_id": task["task_id"], "task_digest": task_digest(task), "status": "succeeded", "result": forged}
        with self.assertRaises(LocalHandError):
            worker._validate_receipt(receipt, task, self.profile)

    def test_result_envelope_limit_before_write(self) -> None:
        with self.assertRaises(LocalHandError) as ctx:
            worker._json_bytes({"x": "y" * 1024}, 32, "result_too_large")
        self.assertEqual(ctx.exception.code, "result_too_large")

    def test_git_environment_drops_agent_and_user_ssh_config(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "SSH_AUTH_SOCK": "evil-agent",
                "SSH_AGENT_PID": "42",
                "GIT_SSH_COMMAND": "evil",
                "LOCAL_HAND_MAILBOX_SSH_KEY": str(self.root / "key"),
                "LOCAL_HAND_KNOWN_HOSTS": str(self.root / "known"),
            },
            clear=False,
        ):
            env = git_safety.sanitized_git_env(allow_ssh=True)
        self.assertNotIn("SSH_AUTH_SOCK", env)
        self.assertNotIn("SSH_AGENT_PID", env)
        command = env["GIT_SSH_COMMAND"]
        expected_key = git_safety._ssh_shell_path(str(self.root / "key"))
        for token in ("IdentityAgent=none", "IdentitiesOnly=yes", "PermitLocalCommand=no", "ClearAllForwardings=yes", expected_key):
            self.assertIn(token, command)
        self.assertNotIn("evil-agent", command)

    def test_hardened_git_trust_is_command_scoped_to_exact_repository(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"LOCAL_HAND_GIT_EXECUTABLE": sys.executable},
            clear=False,
        ):
            prefix = git_safety.hardened_git_prefix(self.repo)
        config_values = [
            prefix[index + 1]
            for index, token in enumerate(prefix[:-1])
            if token == "-c"
        ]
        safe_values = [
            value for value in config_values
            if value.startswith("safe.directory=")
        ]
        expected_path = str(self.repo.resolve())
        if os.name == "nt":
            expected_path = expected_path.replace("\\", "/")
        self.assertEqual(
            safe_values,
            [f"safe.directory={expected_path}"],
        )
        self.assertNotIn("safe.directory=*", config_values)

    def test_windows_git_environment_preserves_only_required_machine_storage(self) -> None:
        ambient = {
            "PATH": r"C:\\Windows\\System32",
            "PROGRAMDATA": r"C:\\ProgramData",
            "ALLUSERSPROFILE": r"C:\\ProgramData",
            "SYSTEMDRIVE": "C:",
            "APPDATA": r"C:\\Users\\worker\\AppData\\Roaming",
            "LOCALAPPDATA": r"C:\\Users\\worker\\AppData\\Local",
            "GIT_SSH_VARIANT": "ssh",
            "SSH_AUTH_SOCK": "evil-agent",
        }
        with (
            mock.patch.dict(os.environ, ambient, clear=True),
            mock.patch.object(git_safety.os, "name", "nt"),
        ):
            env = git_safety.sanitized_git_env()

        self.assertEqual(env["PROGRAMDATA"], ambient["PROGRAMDATA"])
        for name in (
            "ALLUSERSPROFILE",
            "SYSTEMDRIVE",
            "APPDATA",
            "LOCALAPPDATA",
            "GIT_SSH_VARIANT",
            "SSH_AUTH_SOCK",
        ):
            self.assertNotIn(name, env)

    def test_non_windows_git_environment_drops_programdata(self) -> None:
        with (
            mock.patch.dict(
                os.environ,
                {"PATH": "/usr/bin", "PROGRAMDATA": r"C:\\ProgramData"},
                clear=True,
            ),
            mock.patch.object(git_safety.os, "name", "posix"),
        ):
            env = git_safety.sanitized_git_env()

        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertNotIn("PROGRAMDATA", env)

    def test_bootstrap_contract_is_retryable_immutable_and_low_privilege(self) -> None:
        root = Path(__file__).resolve().parents[1]
        linux = (root / "tools/local_hand/bootstrap_linux.sh").read_text(encoding="utf-8")
        windows = (root / "tools/local_hand/bootstrap_windows.ps1").read_text(encoding="utf-8")
        paths = (root / "tools/local_hand/paths.py").read_text(encoding="utf-8")
        for text in (linux, windows):
            for marker in (
                "INDEPENDENT_MAILBOX=true",
                "DEDICATED_OS_IDENTITY=true",
                "IMMUTABLE_DEPLOYMENT=true",
                "VALIDATION_PROFILE_ADMITTED=true",
                "bounded_io.py",
                "mailbox_safety.py",
                "bootstrap_safety.py",
                "windows_runner.py",
                "--depth=1",
                "blob:limit=8388608",
                "sparse-checkout",
                "existing immutable deployment mismatch",
            ):
                self.assertIn(marker, text)
        self.assertIn('--run-user) RUN_USER="$2"', linux)
        self.assertIn('[[ -n "$PROFILE_SOURCE"', linux)
        self.assertIn("ProtectSystem=strict", linux)
        self.assertIn("ProtectHome=yes", linux)
        self.assertIn('sudo chgrp -R "$RUN_GROUP" "$STAGE_ROOT"', linux)
        self.assertIn('sudo chmod -R u=rwX,g=rX,o= "$STAGE_ROOT"', linux)
        smoke_identity = (
            'sudo -u "$RUN_USER" env -i HOME="$RUN_HOME" PATH="$PATH" '
            'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$STAGE_WORKER_ROOT"'
        )
        self.assertIn(smoke_identity, linux)
        self.assertLess(
            linux.index('python3 -m compileall -q "$STAGE_PACKAGE_ROOT"'),
            linux.index('sudo chgrp -R "$RUN_GROUP" "$STAGE_ROOT"'),
        )
        self.assertLess(
            linux.index('sudo chmod -R u=rwX,g=rX,o= "$STAGE_ROOT"'),
            linux.index(smoke_identity),
        )
        self.assertIn("CapabilityBoundingSet=", linux)
        self.assertIn("ReadOnlyPaths=$DEPLOYMENT_ROOT $CREDENTIALS_ROOT", linux)
        self.assertIn("ReadWritePaths=$RUNTIME_STATE $PROJECTS_ROOT $MAILBOX_ROOT", linux)
        self.assertNotIn("ReadWritePaths=$STATE_ROOT", linux)
        self.assertIn("cleanup_uncommitted", linux)
        self.assertIn("old Local Hand service did not stop before upgrade", linux)
        self.assertIn("Local Hand service did not stop during rollback", linux)
        self.assertIn('[[ "$UNSAFE_LIVE_PROCESS" == true ]] && return 0', linux)
        self.assertIn('[[ "$ROLLBACK_FAILED" == true ]] && return 0', linux)
        self.assertIn("Local Hand rollback could not be verified", linux)
        self.assertIn('sudo cmp -s "$OLD_UNIT_BACKUP" "$UNIT_PATH"', linux)
        self.assertIn("restored_active_state", linux)
        self.assertIn("restored_unit_file_state", linux)
        self.assertIn("old Local Hand active state is transitional/indeterminate", linux)
        self.assertIn("old Local Hand enable state is unsupported/indeterminate", linux)
        self.assertLess(
            linux.index('sudo systemctl disable "${SERVICE_NAME}.service"', linux.index("rollback_switch")),
            linux.index('sudo rm -f "$UNIT_PATH"', linux.index("rollback_switch")),
        )
        self.assertIn("validate-repository-target", linux)
        self.assertIn("repository target escapes projects_root", paths)
        self.assertIn("NT AUTHORITY\\LOCAL SERVICE", windows)
        self.assertIn("Set-ReadOnlyAcl $DeploymentRoot", windows)
        self.assertIn("Set-WritableAcl $MailboxRoot", windows)
        self.assertIn("mailbox control directory missing before ACL normalization", windows)
        for relative in (
            "_executor_spike",
            "_executor_spike\\tasks",
            "_executor_spike\\results",
            "_executor_spike\\conflicts",
        ):
            self.assertIn(relative, windows)
        self.assertIn("validate-repository-target", windows)
        self.assertIn("new Local Hand task did not stop during rollback", windows)
        self.assertIn("previous-task.xml", windows)
        self.assertIn("previous Local Hand task identity was not restored", windows)
        self.assertIn("rollback could not be verified", windows)
        self.assertIn("-not $RollbackFailed", windows)
        for marker in (
            ".local-hand-root-owner.json",
            "validate-roots",
            "ensure-root-marker",
            "service-owner-token",
            "ownership is not proven; refusing stop/replace",
        ):
            self.assertIn(marker, linux)
            self.assertIn(marker, windows)
        self.assertIn("# X-Local-Hand-Owner=$SERVICE_OWNER_TOKEN", linux)
        self.assertIn("--property=LoadState", linux)
        self.assertIn("--property=FragmentPath", linux)
        self.assertIn("--property=DropInPaths", linux)
        self.assertIn("unowned drop-in configuration", linux)
        self.assertIn("fragment is not the Local Hand unit path", linux)
        self.assertGreaterEqual(linux.count("assert_owned_existing_unit"), 4)
        self.assertLess(linux.index("assert_owned_existing_unit", linux.index("SOURCE_DIRTY")), linux.index("ensure-root-marker"))
        self.assertGreater(linux.index("assert_owned_existing_unit", linux.index("sudo systemctl daemon-reload")), linux.index("sudo systemctl daemon-reload"))
        self.assertLess(linux.index("ensure-root-marker"), linux.index('sudo chown root:root "$STATE_ROOT"'))
        self.assertLess(windows.index("ensure-root-marker"), windows.index("Set-RootAcl $StateRoot"))
        self.assertGreaterEqual(windows.count("Get-OwnedScheduledTask"), 3)
        self.assertLess(windows.index("$null=Get-OwnedScheduledTask"), windows.index("ensure-root-marker"))
        self.assertLess(windows.index("$old=Get-OwnedScheduledTask"), windows.index("Stop-ScheduledTask"))
        self.assertIn("windows_acl.ps1", windows)
        self.assertIn("-Description $TaskDescription", windows)
        self.assertIn("local_hand.windows_runner", windows)
        self.assertIn("--state-root $ProjectsRoot --projects-root $TargetRepo", windows)
        self.assertIn('--state-root "$PROJECTS_ROOT" --projects-root "$TARGET_REPO"', linux)

        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/local-hand-v0-1-validation.yml").read_text(encoding="utf-8")
        self.assertIn("python -m local_hand.windows_runner", workflow)
        self.assertIn("LINUX_REPEAT_BOOTSTRAP_SMOKE_IDENTITY=PASS", workflow)
        self.assertIn("New-Item -ItemType Junction", workflow)
        self.assertIn("bootstrap_root_reparse_rejected", workflow)
        self.assertIn("Validate Windows exact ACL replacement", workflow)
        self.assertIn("Register-ScheduledTask", workflow)
        self.assertIn("Get-ScheduledTaskInfo", workflow)
        self.assertIn("LocalHand-Git-Trust-CI-", workflow)
        self.assertIn("safe.directory=", workflow)
        self.assertIn("detected dubious ownership", workflow)

    def test_hosted_matrix_classifier_is_fail_safe_and_concurrency_is_event_scoped(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/local-hand-v0-1-validation.yml").read_text(encoding="utf-8")
        for marker in (
            "classify-change:",
            'event.get("before")',
            "classifier uncertainty -> runtime_changed=true",
            "runtime_changed",
            "needs: classify-change",
            "needs.classify-change.outputs.runtime_changed == 'true'",
            'if event_name in {"push", "workflow_dispatch"}:',
            "EXACT_REF: ${{ github.ref }}",
            'if exact_ref != "refs/heads/main":',
            "must target refs/heads/main",
            "exact-commit:{os.environ['EXACT_SHA']}",
            'out.write("runtime_changed=true\\n")',
            "local-hand-v0-1-${{ github.event_name }}-${{ github.event.pull_request.number || github.sha }}",
        ):
            self.assertIn(marker, workflow)
        top = workflow.split("jobs:", 1)[0]
        self.assertIn("push:", top)
        self.assertIn('branches:\n      - "main"', top)
        self.assertIn("workflow_dispatch:", top)
        self.assertIn("concurrency:", top)
        self.assertIn("cancel-in-progress: true", top)
        self.assertIn(
            "if: runner.os == 'Linux' && github.event_name == 'pull_request'",
            workflow,
        )
        pull_request_trigger = top.split("pull_request:", 1)[1].split("  push:", 1)[0]
        push_trigger = top.split("  push:", 1)[1].split("  workflow_dispatch:", 1)[0]
        pull_request_paths = [
            line.strip()
            for line in pull_request_trigger.splitlines()
            if line.strip().startswith("- ")
        ]
        push_paths = [
            line.strip()
            for line in push_trigger.splitlines()
            if line.strip().startswith("- ") and line.strip() != '- "main"'
        ]
        self.assertEqual(push_paths, pull_request_paths)

        classifier_start = workflow.index('event_name = os.environ["EVENT_NAME"]')
        pr_classifier_start = workflow.index(
            'event = json.loads(Path(os.environ["EVENT_PATH"])',
            classifier_start,
        )
        exact_commit_block = workflow[classifier_start:pr_classifier_start]
        self.assertLess(
            exact_commit_block.index('if exact_ref != "refs/heads/main":'),
            exact_commit_block.index('out.write("runtime_changed=true\\n")'),
        )

        identity_start = workflow.index("Validate exact checked-out commit identity")
        compile_start = workflow.index("Compile Local Hand shared core and tests")
        identity_block = workflow[identity_start:compile_start]
        for marker in (
            "if: github.event_name != 'pull_request'",
            "shell: python",
            "EXPECTED_SHA: ${{ github.sha }}",
            '["git", "rev-parse", "HEAD"]',
            "checkout mismatch:",
        ):
            self.assertIn(marker, identity_block)
        self.assertLess(identity_start, compile_start)

    def test_mailbox_fetch_contract_shallow_filtered_sparse_and_no_lazy_admission(self) -> None:
        root = Path(__file__).resolve().parents[1]
        linux = (root / "tools/local_hand/bootstrap_linux.sh").read_text(encoding="utf-8")
        windows = (root / "tools/local_hand/bootstrap_windows.ps1").read_text(encoding="utf-8")
        worker_text = (root / "tools/local_hand/worker.py").read_text(encoding="utf-8")
        safety = (root / "tools/local_hand/mailbox_safety.py").read_text(encoding="utf-8")
        for text in (linux, windows, worker_text):
            self.assertIn("--depth=1", text)
            self.assertIn("blob:limit=", text)
        for text in (linux, windows):
            for path in ("/_executor_spike/tasks/", "/_executor_spike/results/", "/_executor_spike/conflicts/"):
                self.assertIn(path, text)
        self.assertIn("GIT_NO_LAZY_FETCH", safety)
        self.assertIn("mailbox_blob_unavailable", safety)
        self.assertIn("mailbox_disk_quota_exceeded", safety)


if __name__ == "__main__":
    unittest.main()

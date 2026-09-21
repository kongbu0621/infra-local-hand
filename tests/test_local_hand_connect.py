from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from local_hand.config import parse_transport
from config_fixtures import transport
from local_hand.protocol import LocalHandError, result_success, task_digest
from local_hand_connect import controller
from local_hand_connect.cli import main as connect_main


@unittest.skipUnless(shutil.which("git") and shutil.which("ssh"), "Git and SSH executables required")
class LocalHandConnectTests(unittest.TestCase):
    branch = "fixture/mailbox-v1"
    expected_provenance = {
        "implementation_commit": "a" * 40,
        "package_digest": "b" * 64,
        "profile_digest": "c" * 64,
    }

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = self.root / "mailbox.git"
        self.remote_url = self.remote.resolve().as_uri()
        self.seed = self.root / "seed"
        self.mailbox = self.root / "controller"
        self.key = self.root / "controller_key"
        self.known_hosts = self.root / "known_hosts"
        self.key.write_text("test-only-key", encoding="utf-8")
        self.known_hosts.write_text("test-only-known-host", encoding="utf-8")
        self.git = str(Path(shutil.which("git") or "").resolve())
        self.ssh = str(Path(shutil.which("ssh") or "").resolve())
        self.env = {
            "LOCAL_HAND_GIT_EXECUTABLE": self.git,
            "LOCAL_HAND_SSH_EXECUTABLE": self.ssh,
            "LOCAL_HAND_MAILBOX_SSH_KEY": str(self.key.resolve()),
            "LOCAL_HAND_KNOWN_HOSTS": str(self.known_hosts.resolve()),
        }
        # Local file Git transport isolates inherited publish/recovery tests.
        # SSH syntax/admission is tested separately without this parser injection.
        self.remote_allowlist = mock.patch("local_hand.config.ssh_identity", return_value=("fixture", "example.invalid", 22, "mailbox.git"))
        self.remote_allowlist.start()
        self.policy = parse_transport(transport(self.branch, self.remote_url))
        self._git(self.root, "init", "--bare", str(self.remote))
        self._git(self.root, "clone", self.remote_url, str(self.seed))
        self._git(self.seed, "config", "user.name", "fixture")
        self._git(self.seed, "config", "user.email", "fixture@example.invalid")
        for name in ("tasks", "results", "conflicts"):
            path = self.seed / "_executor_spike" / name
            path.mkdir(parents=True, exist_ok=True)
            (path / ".keep").write_text("", encoding="utf-8")
        self._git(self.seed, "add", "_executor_spike")
        self._git(self.seed, "commit", "-m", "mailbox fixture")
        self._git(self.seed, "branch", "-M", self.branch)
        self._git(self.seed, "push", "origin", self.branch)
        self._git(self.root, "clone", "--branch", self.branch, self.remote_url, str(self.mailbox))
        with mock.patch.dict(os.environ, self.env, clear=False):
            controller.initialize_controller_mailbox(
                self.mailbox,
                self.branch,
                policy=self.policy,
            )

    def tearDown(self) -> None:
        self.remote_allowlist.stop()
        self.temp.cleanup()

    @staticmethod
    def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [shutil.which("git") or "git", *args],
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _task(self, *, task_id: str = "LH9001", action: str = "node.status", params=None):
        return controller.build_task(
            "fixture-windows-node",
            action,
            {} if params is None else params,
            task_id=task_id,
        )

    def _publish_result(
        self,
        task: dict,
        *,
        digest_override: str | None = None,
        remove_field: str | None = None,
    ) -> None:
        publisher = self.root / f"publisher-{task['task_id']}"
        self._git(self.root, "clone", "--branch", self.branch, self.remote_url, str(publisher))
        result = result_success(
            task,
            task["target_node"],
            {"connected": True},
            {
                "implementation_commit": "a" * 40,
                "package_digest": "b" * 64,
                "profile_digest": "c" * 64,
            },
        )
        if digest_override is not None:
            result["task_digest"] = digest_override
        if remove_field is not None:
            result.pop(remove_field)
        path = publisher / "_executor_spike" / "results" / f"{task['task_id']}.json"
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        self._git(publisher, "config", "user.name", "fixture")
        self._git(publisher, "config", "user.email", "fixture@example.invalid")
        self._git(publisher, "add", str(path.relative_to(publisher)))
        self._git(publisher, "commit", "-m", f"result {task['task_id']}")
        self._git(publisher, "push", "origin", self.branch)

    def test_build_is_bounded_typed_and_controller_neutral(self) -> None:
        task = self._task()
        self.assertEqual(task["schema_version"], "local-hand-task/v1")
        self.assertEqual(task["target_node"], "fixture-windows-node")
        self.assertRegex(controller.new_task_id(), r"^LH[0-9]{26}$")
        with self.assertRaises(LocalHandError) as ctx:
            self._task(action="shell.exec", params={"command": "whoami"})
        self.assertEqual(ctx.exception.code, "action_not_allowlisted")
        with self.assertRaises(LocalHandError) as ctx:
            self._task(action="node.status", params={"model": "chatgpt"})
        self.assertEqual(ctx.exception.code, "invalid_params")

    def test_external_task_requires_exact_runtime_neutral_envelope(self) -> None:
        task = self._task(task_id="LH9011")
        task["model"] = "chatgpt"
        task["authority"] = "root"
        with mock.patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(LocalHandError) as ctx:
                controller.submit_task(self.mailbox, self.branch, task)
        self.assertEqual(ctx.exception.code, "controller_task_shape_invalid")
        self.assertFalse((self.mailbox / "_executor_spike" / "tasks" / "LH9011.json").exists())

    def test_controller_task_id_is_bounded_for_derived_filenames(self) -> None:
        maximum = "LH" + "1" * controller.MAX_TASK_ID_DIGITS
        self.assertEqual(self._task(task_id=maximum)["task_id"], maximum)
        largest_conflict_name = controller.conflict_filename("a" * 64)
        self.assertEqual(len(largest_conflict_name.encode("ascii")), 78)
        with self.assertRaises(LocalHandError) as ctx:
            self._task(task_id=maximum + "1")
        self.assertEqual(ctx.exception.code, "controller_task_id_invalid")

    def test_controller_finds_exact_digest_bound_conflict(self) -> None:
        task = self._task(task_id="LH9017")
        result = result_success(
            task,
            task["target_node"],
            {"quarantined": True},
            {
                "implementation_commit": "a" * 40,
                "package_digest": "b" * 64,
                "profile_digest": "c" * 64,
            },
        )
        path = self.mailbox / "_executor_spike" / "conflicts" / controller.conflict_filename(task_digest(task))
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(controller._matching_conflict(self.mailbox, task), result)

    def test_controller_git_timeout_binding_must_be_finite_and_positive(self) -> None:
        for value in ("nan", "inf", "0", "-1", "not-a-number"):
            with self.subTest(value=value):
                env = dict(self.env, LOCAL_HAND_GIT_TIMEOUT_SECONDS=value)
                with mock.patch.dict(os.environ, env, clear=False):
                    with self.assertRaises(LocalHandError) as ctx:
                        controller.validate_controller_bindings()
                self.assertEqual(ctx.exception.code, "controller_binding_invalid")
                self.assertEqual(ctx.exception.status, "indeterminate")

    def test_extreme_poll_interval_is_sliced_to_platform_safe_sleep(self) -> None:
        task = self._task(task_id="LH9015")
        stop = LocalHandError("test_stop", "stop after one sleep")
        with (
            mock.patch.object(controller, "validate_controller_mailbox"),
            mock.patch.object(controller, "sync_mailbox", side_effect=[None, stop]),
            mock.patch.object(controller, "target_lexists", return_value=False),
            mock.patch.object(controller, "_matching_conflict", return_value=None),
            mock.patch.object(controller.time, "monotonic", side_effect=[0.0, 1.0]),
            mock.patch.object(controller.time, "sleep") as sleep,
        ):
            with self.assertRaises(LocalHandError) as ctx:
                controller._wait_for_result_locked(
                    self.mailbox,
                    self.branch,
                    task,
                    timeout_seconds=1e300,
                    poll_seconds=1e300,
                    expected_provenance=self.expected_provenance,
                )
        self.assertEqual(ctx.exception.code, "test_stop")
        sleep.assert_called_once_with(controller.MAX_SLEEP_SLICE_SECONDS)

    def test_p0_branch_is_exact_and_rejects_git_option_like_input(self) -> None:
        with mock.patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(LocalHandError) as ctx:
                controller.initialize_controller_mailbox(
                    self.mailbox,
                    "--upload-pack=false",
                    policy=self.policy,
                )
        self.assertEqual(ctx.exception.code, "controller_branch_rejected")

    def test_mailbox_requires_explicit_clean_admission_marker(self) -> None:
        fresh = self.root / "fresh"
        self._git(self.root, "clone", "--branch", self.branch, self.remote_url, str(fresh))
        task = self._task()
        with mock.patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(LocalHandError) as ctx:
                controller.submit_task(fresh, self.branch, task)
        self.assertEqual(ctx.exception.code, "controller_marker_invalid")
        (fresh / "untracked.txt").write_text("do not reset", encoding="utf-8")
        with mock.patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(LocalHandError) as ctx:
                controller.initialize_controller_mailbox(
                    fresh,
                    self.branch,
                    policy=self.policy,
                )
        self.assertEqual(ctx.exception.code, "controller_mailbox_dirty")
        self.assertEqual((fresh / "untracked.txt").read_text(encoding="utf-8"), "do not reset")

    def test_mailbox_admission_rejects_wrong_remote_and_non_root_path(self) -> None:
        fresh = self.root / "wrong-remote"
        self._git(self.root, "clone", "--branch", self.branch, self.remote_url, str(fresh))
        with mock.patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(LocalHandError) as ctx:
                controller.initialize_controller_mailbox(
                    fresh,
                    self.branch,
                    policy=parse_transport(transport(self.branch, "git@example.invalid:owner/not-the-mailbox.git")),
                )
            self.assertEqual(ctx.exception.code, "controller_remote_rejected")
            with self.assertRaises(LocalHandError) as ctx:
                controller.initialize_controller_mailbox(
                    fresh / "_executor_spike",
                    self.branch,
                    policy=self.policy,
                )
        self.assertEqual(ctx.exception.code, "controller_mailbox_not_dedicated")

    def test_origin_change_after_admission_fails_before_task_mutation(self) -> None:
        task = self._task(task_id="LH9000")
        self._git(self.mailbox, "remote", "set-url", "--push", "origin", str(self.root / "other.git"))
        with mock.patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(LocalHandError) as ctx:
                controller.submit_task(self.mailbox, self.branch, task)
        self.assertEqual(ctx.exception.code, "controller_remote_rejected")
        self.assertFalse((self.mailbox / "_executor_spike" / "tasks" / "LH9000.json").exists())

    def test_second_controller_process_is_rejected_before_git_mutation(self) -> None:
        ready = self.root / "controller-lock-ready"
        code = (
            "from pathlib import Path; import sys,time; "
            "from local_hand_connect.controller import _controller_mailbox_lock; "
            "c=_controller_mailbox_lock(Path(sys.argv[1])); c.__enter__(); "
            "Path(sys.argv[2]).write_text('ready'); time.sleep(5)"
        )
        child_env = dict(os.environ)
        child_env["PYTHONPATH"] = str(TOOLS_ROOT)
        process = subprocess.Popen(
            [sys.executable, "-c", code, str(self.mailbox), str(ready)],
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 3
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists(), process.stderr.read() if process.poll() is not None else "lock holder did not start")
            task = self._task(task_id="LH9005")
            with mock.patch.dict(os.environ, self.env, clear=False):
                with self.assertRaises(LocalHandError) as ctx:
                    controller.submit_task(self.mailbox, self.branch, task)
            self.assertEqual(ctx.exception.code, "controller_mailbox_busy")
            self.assertFalse((self.mailbox / "_executor_spike" / "tasks" / "LH9005.json").exists())
        finally:
            process.terminate()
            process.communicate(timeout=5)

    def test_submit_is_idempotent_and_digest_conflict_fails_closed(self) -> None:
        task = self._task()
        with mock.patch.dict(os.environ, self.env, clear=False):
            first = controller.submit_task(self.mailbox, self.branch, task)
            second = controller.submit_task(self.mailbox, self.branch, task)
            self.assertEqual(first["status"], "submitted")
            self.assertEqual(second["status"], "already_present")
            conflicting = self._task(task_id=task["task_id"], action="repo.audit", params={"repository": "scratch"})
            with self.assertRaises(LocalHandError) as ctx:
                controller.submit_task(self.mailbox, self.branch, conflicting)
        self.assertEqual(ctx.exception.code, "controller_task_id_conflict")

    def test_wait_accepts_only_exact_result_identity_and_provenance(self) -> None:
        task = self._task(task_id="LH9002")
        with mock.patch.dict(os.environ, self.env, clear=False):
            controller.submit_task(self.mailbox, self.branch, task)
        self._publish_result(task)
        expected = self.expected_provenance
        with mock.patch.dict(os.environ, self.env, clear=False):
            result = controller.wait_for_result(
                self.mailbox,
                self.branch,
                task,
                timeout_seconds=1,
                poll_seconds=0.01,
                expected_provenance=expected,
            )
        self.assertEqual(result["task_digest"], task_digest(task))
        self.assertEqual(result["target_node"], task["target_node"])
        self.assertEqual(result["implementation_commit"], "a" * 40)

    def test_expected_provenance_mismatch_is_indeterminate(self) -> None:
        task = self._task(task_id="LH9006")
        with mock.patch.dict(os.environ, self.env, clear=False):
            controller.submit_task(self.mailbox, self.branch, task)
        self._publish_result(task)
        expected = {
            "implementation_commit": "a" * 40,
            "package_digest": "e" * 64,
            "profile_digest": "c" * 64,
        }
        with mock.patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(LocalHandError) as ctx:
                controller.wait_for_result(
                    self.mailbox,
                    self.branch,
                    task,
                    timeout_seconds=1,
                    poll_seconds=0.01,
                    expected_provenance=expected,
                )
        self.assertEqual(ctx.exception.code, "controller_provenance_mismatch")
        self.assertEqual(ctx.exception.status, "indeterminate")

        with self.assertRaises(LocalHandError) as ctx:
            controller.validate_expected_provenance({"implementation_commit": "a" * 40})
        self.assertEqual(ctx.exception.code, "controller_provenance_policy_invalid")
        with self.assertRaises(LocalHandError) as ctx:
            controller.validate_expected_provenance(
                {
                    "implementation_commit": "A" * 40,
                    "package_digest": "b" * 64,
                    "profile_digest": "c" * 64,
                }
            )
        self.assertEqual(ctx.exception.code, "controller_provenance_policy_invalid")

    def test_wait_rejects_wrong_digest_instead_of_accepting_foreign_result(self) -> None:
        task = self._task(task_id="LH9003")
        with mock.patch.dict(os.environ, self.env, clear=False):
            controller.submit_task(self.mailbox, self.branch, task)
        self._publish_result(task, digest_override="d" * 64)
        with mock.patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(LocalHandError) as ctx:
                controller.wait_for_result(
                    self.mailbox,
                    self.branch,
                    task,
                    timeout_seconds=1,
                    poll_seconds=0.01,
                    expected_provenance=self.expected_provenance,
                )
        self.assertEqual(ctx.exception.code, "remote_result_invalid")

    def test_wait_rejects_incomplete_result_envelope(self) -> None:
        task = self._task(task_id="LH9012")
        with mock.patch.dict(os.environ, self.env, clear=False):
            controller.submit_task(self.mailbox, self.branch, task)
        self._publish_result(task, remove_field="details")
        with mock.patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(LocalHandError) as ctx:
                controller.wait_for_result(
                    self.mailbox,
                    self.branch,
                    task,
                    timeout_seconds=1,
                    poll_seconds=0.01,
                    expected_provenance=self.expected_provenance,
                )
        self.assertEqual(ctx.exception.code, "controller_result_shape_invalid")
        self.assertEqual(ctx.exception.status, "indeterminate")

    def test_wait_timeout_is_indeterminate_and_does_not_reexecute(self) -> None:
        task = self._task(task_id="LH9004")
        with mock.patch.dict(os.environ, self.env, clear=False):
            controller.submit_task(self.mailbox, self.branch, task)
            with self.assertRaises(LocalHandError) as ctx:
                controller.wait_for_result(
                    self.mailbox,
                    self.branch,
                    task,
                    timeout_seconds=0,
                    poll_seconds=0.01,
                    expected_provenance=self.expected_provenance,
                )
        self.assertEqual(ctx.exception.code, "controller_wait_timeout")
        self.assertEqual(ctx.exception.status, "indeterminate")

    def test_wait_rejects_non_finite_timing(self) -> None:
        task = self._task(task_id="LH9014")
        for timeout, poll in (
            (float("nan"), 0.01),
            (float("inf"), 0.01),
            (1, float("nan")),
            (1, float("inf")),
            (1, 0),
        ):
            with self.subTest(timeout=timeout, poll=poll):
                with mock.patch.dict(os.environ, self.env, clear=False):
                    with self.assertRaises(LocalHandError) as ctx:
                        controller.wait_for_result(
                            self.mailbox,
                            self.branch,
                            task,
                            timeout_seconds=timeout,
                            poll_seconds=poll,
                            expected_provenance=self.expected_provenance,
                        )
                self.assertEqual(ctx.exception.code, "controller_wait_invalid")

    def test_cli_build_refuses_output_overwrite(self) -> None:
        params = self.root / "params.json"
        params.write_text("{}", encoding="utf-8")
        output = self.root / "task.json"
        args = [
            "build",
            "--target-node", "fixture-windows-node",
            "--action", "node.status",
            "--params-file", str(params),
            "--task-id", "LH9010",
            "--output", str(output),
        ]
        self.assertEqual(connect_main(args), 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["task_id"], "LH9010")
        self.assertEqual(connect_main(args), 2)

    def test_call_without_expected_provenance_rejects_before_submit(self) -> None:
        task = self._task(task_id="LH9018")
        with mock.patch.object(controller, "_submit_task_locked") as submit:
            with self.assertRaises(LocalHandError) as ctx:
                controller.call_task(self.mailbox, self.branch, task)
        self.assertEqual(ctx.exception.code, "controller_provenance_policy_invalid")
        submit.assert_not_called()

    def test_runtime_neutral_port_has_git_mailbox_implementation(self) -> None:
        adapter = controller.GitMailboxControllerAdapter(
            self.mailbox,
            expected_provenance={
                "implementation_commit": "a" * 40,
                "package_digest": "b" * 64,
                "profile_digest": "c" * 64,
            },
        )
        self.assertIsInstance(adapter, controller.LocalHandControllerAdapter)
        task = adapter.build("fixture-windows-node", "node.status", {}, task_id="LH9013")
        with mock.patch.dict(os.environ, self.env, clear=False):
            self.assertEqual(adapter.submit(task)["status"], "submitted")
        self._publish_result(task)
        with mock.patch.dict(os.environ, self.env, clear=False):
            result = adapter.wait(task, timeout_seconds=1, poll_seconds=0.01)
        self.assertEqual(result["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()

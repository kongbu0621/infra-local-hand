from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from local_hand import bootstrap_safety, git_safety, windows_runner
from local_hand.protocol import LocalHandError


class LocalHandHardeningDClosureTests(unittest.TestCase):
    def test_git_ext_remote_helper_protocol_is_forced_off(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            prefix = git_safety.hardened_git_prefix(Path(td))
        rendered = " ".join(prefix)
        self.assertIn("protocol.ext.allow=never", rendered)

    def test_linux_runtime_identity_has_a_dedicated_primary_group(self) -> None:
        script = (Path(__file__).resolve().parents[1] / "tools/local_hand/bootstrap_linux.sh").read_text(encoding="utf-8")
        for marker in (
            'groupadd --system "$RUN_USER"',
            'useradd --system --gid "$RUN_USER"',
            '[[ "$RUN_GROUP" == "$RUN_USER" ]]',
            "DEDICATED_OS_GROUP=true",
        ):
            self.assertIn(marker, script)

    def test_privileged_bootstrap_restricts_mailbox_and_seed_sources(self) -> None:
        script = (Path(__file__).resolve().parents[1] / "tools/local_hand/bootstrap_linux.sh").read_text(encoding="utf-8")
        self.assertIn("local_hand.config --profile", script)
        self.assertIn('--match-remote-url "$MAILBOX_URL"', script)
        self.assertLess(script.index("local_hand.config --profile"), script.index('DISABLED_HOOKS="$(mktemp'))
        self.assertNotIn("https://github.com/example-owner/example-mailbox.git", script)
        self.assertIn("--seed-repository-from must name a trusted root-owned standalone local Git working copy", script)
        self.assertIn("protocol.ext.allow=never", script)

    def test_bootstrap_roots_require_a_strict_non_broad_descendant(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / "state"
            projects = state / "projects"
            self.assertEqual(
                bootstrap_safety.validate_install_roots(state, projects, reserved_roots=(root,)),
                (state, projects),
            )
            for bad_state, bad_projects in (
                (root, root / "projects"),
                (state, state),
                (state, root / "outside"),
            ):
                with self.subTest(state=bad_state, projects=bad_projects):
                    with self.assertRaises(LocalHandError):
                        bootstrap_safety.validate_install_roots(
                            bad_state,
                            bad_projects,
                            reserved_roots=(root,),
                        )
            file_root = root / "file-root"
            file_root.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(LocalHandError) as ctx:
                bootstrap_safety.validate_install_roots(file_root, file_root / "projects")
            self.assertEqual(ctx.exception.code, "bootstrap_root_invalid")

    @unittest.skipIf(os.name == "nt", "creating symlinks is privilege-dependent on Windows")
    def test_bootstrap_root_chain_rejects_symlink_ancestors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real = root / "real"
            real.mkdir()
            link = root / "linked"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(LocalHandError) as ctx:
                bootstrap_safety.validate_install_roots(link / "state", link / "state/projects")
            self.assertEqual(ctx.exception.code, "bootstrap_root_reparse_rejected")

    def test_root_owner_marker_is_create_once_and_identity_bound(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            with self.assertRaises(LocalHandError) as ctx:
                bootstrap_safety.ensure_root_owner_marker(state, "node-a", "service-a")
            self.assertEqual(ctx.exception.code, "bootstrap_state_root_invalid")
            marker = bootstrap_safety.ensure_root_owner_marker(
                state,
                "node-a",
                "service-a",
                allow_create=True,
            )
            first = marker.read_bytes()
            parsed = json.loads(first.decode("utf-8"))
            self.assertEqual(parsed["schema_version"], bootstrap_safety.ROOT_MARKER_SCHEMA)
            self.assertEqual(parsed["node_id"], "node-a")
            self.assertEqual(parsed["service_id"], "service-a")
            bootstrap_safety.ensure_root_owner_marker(state, "node-a", "service-a")
            self.assertEqual(marker.read_bytes(), first)
            with self.assertRaises(LocalHandError) as ctx:
                bootstrap_safety.ensure_root_owner_marker(state, "node-b", "service-a")
            self.assertEqual(ctx.exception.code, "bootstrap_root_owner_mismatch")
            unmarked = Path(td) / "unmarked"
            unmarked.mkdir()
            with self.assertRaises(LocalHandError) as ctx:
                bootstrap_safety.ensure_root_owner_marker(
                    unmarked,
                    "node-a",
                    "service-a",
                    allow_create=True,
                )
            self.assertEqual(ctx.exception.code, "bootstrap_root_owner_missing")
            self.assertEqual(list(unmarked.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "creating symlinks is privilege-dependent on Windows")
    def test_root_owner_marker_symlink_is_rejected_without_following(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state"
            state.mkdir()
            outside = Path(td) / "outside"
            outside.write_text("unchanged", encoding="utf-8")
            (state / bootstrap_safety.ROOT_MARKER_NAME).symlink_to(outside)
            with self.assertRaises(LocalHandError) as ctx:
                bootstrap_safety.ensure_root_owner_marker(state, "node-a", "service-a")
            self.assertEqual(ctx.exception.code, "bootstrap_root_owner_mismatch")
            self.assertEqual(outside.read_text(encoding="utf-8"), "unchanged")

    def test_service_owner_token_binds_root_node_and_service(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            token = bootstrap_safety.service_owner_token(root / "state", "node-a", "service-a")
            self.assertTrue(token.startswith(bootstrap_safety.SERVICE_OWNER_SCHEMA + ":"))
            self.assertNotEqual(token, bootstrap_safety.service_owner_token(root / "other", "node-a", "service-a"))
            self.assertNotEqual(token, bootstrap_safety.service_owner_token(root / "state", "node-b", "service-a"))
            self.assertNotEqual(token, bootstrap_safety.service_owner_token(root / "state", "node-a", "service-b"))

    def test_install_instance_identity_is_unique_canonical_uuid(self) -> None:
        first = bootstrap_safety.new_install_instance_id()
        second = bootstrap_safety.new_install_instance_id()
        self.assertEqual(str(uuid.UUID(first)), first)
        self.assertEqual(str(uuid.UUID(second)), second)
        self.assertNotEqual(first, second)

    def test_deployed_runtime_bindings_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            git = root / "git"
            ssh = root / "ssh"
            key = root / "key"
            known = root / "known_hosts"
            for path in (git, ssh, key, known):
                path.write_text("fixture", encoding="utf-8")
            git.chmod(0o755)
            ssh.chmod(0o755)
            valid = {
                "LOCAL_HAND_GIT_EXECUTABLE": str(git),
                "LOCAL_HAND_SSH_EXECUTABLE": str(ssh),
                "LOCAL_HAND_MAILBOX_USES_SSH": "1",
                "LOCAL_HAND_MAILBOX_SSH_KEY": str(key),
                "LOCAL_HAND_KNOWN_HOSTS": str(known),
                "LOCAL_HAND_INSTALL_INSTANCE_ID": str(uuid.uuid4()),
                "LOCAL_HAND_IMPLEMENTATION_COMMIT": "a" * 40,
            }
            with mock.patch.dict(os.environ, valid, clear=True):
                git_safety.validate_runtime_bindings()
            https_mode = dict(valid)
            https_mode["LOCAL_HAND_MAILBOX_USES_SSH"] = "0"
            with mock.patch.dict(os.environ, https_mode, clear=True):
                with self.assertRaises(LocalHandError) as ctx:
                    git_safety.validate_runtime_bindings()
            self.assertEqual(ctx.exception.code, "runtime_binding_invalid")
            for field, value in (
                ("LOCAL_HAND_GIT_EXECUTABLE", "git"),
                ("LOCAL_HAND_INSTALL_INSTANCE_ID", "not-a-uuid"),
                ("LOCAL_HAND_MAILBOX_SSH_KEY", str(root / "missing")),
            ):
                with self.subTest(field=field):
                    broken = dict(valid)
                    broken[field] = value
                    with mock.patch.dict(os.environ, broken, clear=False):
                        with self.assertRaises(LocalHandError) as ctx:
                            git_safety.validate_runtime_bindings()
                    self.assertEqual(ctx.exception.code, "runtime_binding_invalid")
            for missing in (
                "LOCAL_HAND_GIT_EXECUTABLE",
                "LOCAL_HAND_SSH_EXECUTABLE",
                "LOCAL_HAND_INSTALL_INSTANCE_ID",
                "LOCAL_HAND_IMPLEMENTATION_COMMIT",
                "LOCAL_HAND_MAILBOX_USES_SSH",
            ):
                with self.subTest(missing=missing):
                    broken = dict(valid)
                    del broken[missing]
                    with mock.patch.dict(os.environ, broken, clear=True):
                        with self.assertRaises(LocalHandError) as ctx:
                            git_safety.validate_runtime_bindings()
                    self.assertEqual(ctx.exception.code, "runtime_binding_invalid")

    def test_windows_runner_is_create_only_escaped_and_propagates_native_exit(self) -> None:
        values = {
            "home": r"C:\Local Hand\owner's home",
            "worker_root": r"C:\Local Hand\worker",
            "profile": r"C:\Local Hand\node-profile.json",
            "mailbox": r"C:\Local Hand\mailbox",
            "branch": "fixture/mailbox-v1",
            "runtime": r"C:\Local Hand\runtime",
            "python": r"C:\Program Files\Python\python.exe",
            "git": r"C:\Program Files\Git\cmd\git.exe",
            "ssh": r"C:\Windows\System32\OpenSSH\ssh.exe",
            "commit": "0" * 40,
            "install_instance_id": "11111111-2222-4333-8444-555555555555",
            "mailbox_uses_ssh": True,
            "mailbox_key": r"C:\Local Hand\credentials\mailbox_id",
            "known_hosts": r"C:\Local Hand\credentials\known_hosts",
            "install_record": r"C:\Local Hand\credentials\install-record.json",
        }
        expected = windows_runner.render_windows_runner(**values)
        self.assertIn("'C:\\Local Hand\\owner''s home'", expected)
        self.assertIn("$workerExitCode=$LASTEXITCODE", expected)
        self.assertIn("LOCAL_HAND_INSTALL_INSTANCE_ID", expected)
        self.assertIn("LOCAL_HAND_GIT_EXECUTABLE", expected)
        self.assertIn("LOCAL_HAND_MAILBOX_USES_SSH='1'", expected)
        self.assertIn("if($null -eq $workerExitCode){exit 1}", expected)
        self.assertTrue(expected.endswith("exit [int]$workerExitCode\n"))
        with self.assertRaises(ValueError):
            windows_runner.render_windows_runner(**{**values, "mailbox_uses_ssh": False})

        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "runner.ps1"
            args = ["--output", str(output)]
            for name, value in values.items():
                args.extend(("--" + name.replace("_", "-"), "1" if value is True else str(value)))
            self.assertEqual(windows_runner.main(args), 0)
            self.assertEqual(output.read_text(encoding="utf-8"), expected)
            with self.assertRaises(FileExistsError):
                windows_runner.main(args)

    def test_windows_acl_helper_replaces_and_read_back_verifies_exact_dacl(self) -> None:
        helper = (Path(__file__).resolve().parents[1] / "tools/local_hand/windows_acl.ps1").read_text(encoding="utf-8")
        for marker in (
            "SetAccessRuleProtection($true,$false)",
            "RemoveAccessRuleSpecific",
            "Set-Acl -LiteralPath $Path -AclObject $acl",
            "Get-Acl -LiteralPath $Path",
            "Compare-Object $expected $actual",
            "AreAccessRulesProtected",
            "S-1-5-18",
            "S-1-5-32-544",
            "S-1-5-19",
            "Set-LocalHandRuntimePrivateKeyAcl",
            "SetOwner($administrators)",
            "exact Local Hand private-key owner/DACL verification failed",
        ):
            self.assertIn(marker, helper)
        self.assertNotIn("icacls", helper.lower())

    def test_windows_bootstrap_uses_two_phase_ssh_key_handoff(self) -> None:
        windows = (Path(__file__).resolve().parents[1] / "tools/local_hand/bootstrap_windows.ps1").read_text(encoding="utf-8")
        clone = windows.index('Invoke-SafeGit "clone" "--depth=1"')
        provisioning_command = windows.index('-i `"$ProvisioningMailboxKey`"')
        copy_runtime_key = windows.index("Copy-Item $ProvisioningMailboxKey $MailboxKey -Force")
        runtime_acl = windows.index("Set-RuntimePrivateKeyAcl $MailboxKey")
        runtime_command = windows.index('-i `"$MailboxKey`"', provisioning_command + 1)
        runner = windows.index("$RunnerPath=Join-Path")
        self.assertIn("$TaskPrincipalUser='LOCALSERVICE'", windows)
        self.assertIn("New-ScheduledTaskPrincipal -UserId $TaskPrincipalUser -LogonType ServiceAccount", windows)
        self.assertLess(provisioning_command, clone)
        self.assertLess(clone, copy_runtime_key)
        self.assertLess(copy_runtime_key, runtime_acl)
        self.assertLess(runtime_acl, runtime_command)
        self.assertLess(runtime_command, runner)

    def test_bootstrap_source_python_calls_cannot_dirty_the_source_tree(self) -> None:
        root = Path(__file__).resolve().parents[1]
        windows = (root / "tools/local_hand/bootstrap_windows.ps1").read_text(encoding="utf-8")
        linux = (root / "tools/local_hand/bootstrap_linux.sh").read_text(encoding="utf-8")

        windows_source_calls = [
            line for line in windows.splitlines() if "$env:PYTHONPATH=$SourceTools" in line
        ]
        self.assertGreater(len(windows_source_calls), 0)
        for line in windows_source_calls:
            self.assertIn("& $Python -B", line)

        linux_source_calls = [
            line for line in linux.splitlines() if 'PYTHONPATH="$SOURCE_REPO_ROOT/tools"' in line
        ]
        self.assertGreater(len(linux_source_calls), 0)
        for line in linux_source_calls:
            self.assertIn("PYTHONDONTWRITEBYTECODE=1", line)
            self.assertIn("python3 -B", line)

        self.assertIn("$sourceDirtyAfterPreparation", windows)
        self.assertIn("SOURCE_DIRTY_AFTER_PREPARATION", linux)
        message = "tools/local_hand source tree became dirty during bootstrap preparation"
        self.assertIn(message, windows)
        self.assertIn(message, linux)
        self.assertLess(windows.index("$sourceDirtyAfterPreparation"), windows.index("$action=New-ScheduledTaskAction"))
        self.assertLess(linux.index("SOURCE_DIRTY_AFTER_PREPARATION"), linux.index("SWITCH_STARTED=true"))

    def test_b4_b5_b6_bootstrap_contract_markers(self) -> None:
        root = Path(__file__).resolve().parents[1]
        linux = (root / "tools/local_hand/bootstrap_linux.sh").read_text(encoding="utf-8")
        windows = (root / "tools/local_hand/bootstrap_windows.ps1").read_text(encoding="utf-8")
        workflow = (root / ".github/workflows/local-hand-v0-1-validation.yml").read_text(encoding="utf-8")
        for text in (linux, windows):
            self.assertIn("INSTALL_INSTANCE_ID", text.upper())
            self.assertIn("new-install-instance-id", text)
            self.assertIn("replay_safe", text)
            self.assertIn("local_hand.config", text)
            self.assertIn("local_hand.provenance", text)
            self.assertIn("local_hand.installation", text)
            self.assertNotIn("pytest-smoke", text)
            self.assertNotIn("timeout-child-probe", text)
            self.assertNotIn("https://github.com/example-owner/example-mailbox.git", text)
        self.assertIn("Copy-Item -LiteralPath $ProfileSource -Destination $StageProfile", windows)
        self.assertIn('cp -- "$PROFILE_SOURCE" "$STAGE_PROFILE"', linux)
        self.assertIn("profile changed after admission", windows)
        self.assertIn("profile changed after admission", linux)
        for marker in (
            "allowed_remote_urls",
            "protocol.ext.allow=never",
            'Resolve-Executable "ssh"',
            "@($PowerShell,$Python,$Git,$Ssh)",
            '"local-hand-disabled-hooks-bootstrap-"+[guid]::NewGuid().ToString("N")',
            "bootstrap disabled-hooks directory is not empty",
            "seed repository path must be the exact working-copy root",
            "requires PowerShell 7 or newer",
            "$MailboxesRoot $InstallInstanceId",
            '$RunnersRoot ("$InstallInstanceId.ps1")',
        ):
            self.assertIn(marker, windows)
        self.assertIn('$CREDENTIALS_BASE/$INSTALL_INSTANCE_ID', linux)
        self.assertIn('$MAILBOXES_ROOT/$INSTALL_INSTANCE_ID', linux)
        self.assertGreaterEqual(linux.count("core.hooksPath=/dev/null"), 5)
        self.assertIn("mailbox-branch contains a systemd specifier marker", linux)
        self.assertIn("systemd unit values must not contain '%'", linux)
        self.assertIn("systemd unit paths must use safe absolute ASCII syntax", linux)
        self.assertLess(windows.index("local_hand.config"), windows.index("New-Item -ItemType Directory -Path $DisabledHooks"))
        self.assertLess(windows.index("seed repository path must be the exact working-copy root"), windows.index("ensure-root-marker"))
        self.assertLess(linux.index("seed repository path must be the exact working-copy root"), linux.index("ensure-root-marker"))
        self.assertIn("Prove Windows PowerShell 5.1 is rejected explicitly", workflow)
        self.assertIn("Execute PowerShell 7 startup contract without mutation", workflow)
        self.assertIn("shell: powershell", workflow)
        runner_probe = workflow.split("& python -m local_hand.windows_runner", 1)[1].split(
            "if ($LASTEXITCODE -ne 0)", 1
        )[0]
        required_runner_args = {
            action.option_strings[0]
            for action in windows_runner._build_parser()._actions
            if action.required
        }
        for required_arg in required_runner_args:
            self.assertIn(required_arg, runner_probe)
        self.assertLess(windows.index("$SwitchStarted=$true"), windows.index("Stop-ScheduledTask"))
        self.assertIn("-not $SwitchCommitted", windows)


if __name__ == "__main__":
    unittest.main()

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "tools" / "local_hand" / "bootstrap_linux.sh"


class BootstrapInheritedWorkingDirectoryTests(unittest.TestCase):
    def test_source_repository_access_uses_exact_worktree_trust(self) -> None:
        script = BOOTSTRAP.read_text(encoding="utf-8")
        trusted_source_access = (
            'git_safe -c "safe.directory=$SOURCE_REPO_ROOT" '
            '-C "$SOURCE_REPO_ROOT"'
        )

        self.assertEqual(script.count(trusted_source_access), 4)
        executable_trusted_lines = [
            line
            for line in script.splitlines()
            if trusted_source_access in line
            and not line.lstrip().startswith("#")
        ]
        self.assertEqual(len(executable_trusted_lines), 4)
        self.assertNotIn(
            r"Trust only\n# the exact worktree",
            script,
        )
        self.assertNotIn('git_safe -C "$SOURCE_REPO_ROOT"', script)
        self.assertNotIn('safe.directory=$SOURCE_REPO_ROOT/.git', script)
        self.assertNotIn("safe.directory=*", script)

    def test_safe_cwd_precedes_every_service_account_subprocess(self) -> None:
        script = BOOTSTRAP.read_text(encoding="utf-8")
        marker = (
            "# Service-account subprocesses must not inherit a caller-owned "
            "or inaccessible working directory.\n"
            "cd /\n"
        )

        self.assertEqual(script.count(marker), 1)
        self.assertIn('sudo -u "$RUN_USER"', script)

        marker_offset = script.index(marker)
        first_run_user_offset = script.index('sudo -u "$RUN_USER"')
        seed_gate = 'if [[ "$TARGET_NEEDS_SEED" == true ]]; then'
        self.assertEqual(script.count(seed_gate), 1)
        seed_gate_offset = script.index(seed_gate)
        self.assertLess(marker_offset, seed_gate_offset)
        self.assertLess(marker_offset, first_run_user_offset)
        self.assertNotIn('sudo -u "$RUN_USER"', script[:marker_offset])

    def test_safe_cwd_is_after_cli_path_resolution(self) -> None:
        script = BOOTSTRAP.read_text(encoding="utf-8")

        cwd_offset = script.index(
            "# Service-account subprocesses must not inherit a caller-owned "
            "or inaccessible working directory.\n"
            "cd /\n"
        )

        for required_predecessor in (
            'STATE_ROOT="$(python3 -c',
            'PROJECTS_ROOT="$(python3 -c',
            'SEED_REPOSITORY_FROM="$(python3 -c',
            'sudo install -m0440 -o root -g "$RUN_GROUP" '
            '"$MAILBOX_SSH_KEY" "$CREDENTIALS_ROOT/mailbox_id"',
            'sudo install -m0440 -o root -g "$RUN_GROUP" '
            '"$KNOWN_HOSTS_FILE" "$CREDENTIALS_ROOT/known_hosts"',
        ):
            with self.subTest(required_predecessor=required_predecessor):
                self.assertIn(required_predecessor, script)
                self.assertLess(script.index(required_predecessor), cwd_offset)


    def test_seed_clone_uses_ephemeral_protected_config(self) -> None:
        script = BOOTSTRAP.read_text(encoding="utf-8")

        temporary_config = (
            'SEED_GIT_CONFIG="$(sudo mktemp '
            '"$STATE_ROOT/.local-hand-seed-git-config.XXXXXX")"'
        )
        exact_safe_directory = (
            'sudo "$GIT_BIN" config --file "$SEED_GIT_CONFIG" '
            '--add safe.directory "$SEED_REPOSITORY_FROM"'
        )
        protected_clone_environment = (
            'GIT_CONFIG_GLOBAL="$SEED_GIT_CONFIG"'
        )
        cleanup = (
            'trap \'sudo rm -f -- "$SEED_GIT_CONFIG" || true\' EXIT'
        )
        clone = (
            'clone --no-local "$SEED_REPOSITORY_FROM" "$TARGET_REPO"'
        )

        self.assertEqual(script.count(temporary_config), 1)
        self.assertEqual(script.count(exact_safe_directory), 1)
        self.assertEqual(script.count(protected_clone_environment), 1)
        self.assertEqual(script.count(cleanup), 1)
        self.assertEqual(script.count(clone), 1)
        self.assertIn('sudo chmod 0444 "$SEED_GIT_CONFIG"', script)
        self.assertIn(
            '"$(sudo stat -c \'%u:%g:%a\' -- "$SEED_GIT_CONFIG")" '
            '== 0:0:444',
            script,
        )
        self.assertIn(
            'sudo -u "$RUN_USER" test -r "$SEED_GIT_CONFIG"',
            script,
        )
        self.assertNotIn("safe.directory=*", script)

        config_offset = script.index(temporary_config)
        exact_safe_offset = script.index(exact_safe_directory)
        clone_environment_offset = script.index(protected_clone_environment)
        clone_offset = script.index(clone)
        cleanup_offset = script.index(cleanup)

        self.assertLess(config_offset, cleanup_offset)
        self.assertLess(cleanup_offset, exact_safe_offset)
        self.assertLess(exact_safe_offset, clone_environment_offset)
        self.assertLess(clone_environment_offset, clone_offset)


    @unittest.skipUnless(
        os.name == "posix" and shutil.which("git"),
        "POSIX Git behavior test",
    )
    def test_safe_directory_uses_worktree_root_for_repository_access(self) -> None:
        git = shutil.which("git")
        assert git is not None

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root / "seed"
            bad_config = root / "bad.gitconfig"
            good_config = root / "good.gitconfig"

            subprocess.run([git, "init", "-q", str(seed)], check=True)
            subprocess.run(
                [
                    git,
                    "-C",
                    str(seed),
                    "-c",
                    "user.name=Local Hand test",
                    "-c",
                    "user.email=local-hand@example.invalid",
                    "commit",
                    "--allow-empty",
                    "-q",
                    "-m",
                    "seed",
                ],
                check=True,
            )
            subprocess.run(
                [
                    git,
                    "config",
                    "--file",
                    str(bad_config),
                    "--add",
                    "safe.directory",
                    str(seed / ".git"),
                ],
                check=True,
            )
            subprocess.run(
                [
                    git,
                    "config",
                    "--file",
                    str(good_config),
                    "--add",
                    "safe.directory",
                    str(seed),
                ],
                check=True,
            )

            base_environment = os.environ.copy()
            base_environment.update(
                {
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
                    "HOME": str(root),
                }
            )

            bad_environment = base_environment | {
                "GIT_CONFIG_GLOBAL": str(bad_config)
            }
            bad = subprocess.run(
                [git, "-C", str(seed), "rev-parse", "--is-inside-work-tree"],
                env=bad_environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("dubious ownership", bad.stderr.lower())

            good_environment = base_environment | {
                "GIT_CONFIG_GLOBAL": str(good_config)
            }
            good = subprocess.run(
                [git, "-C", str(seed), "rev-parse", "--is-inside-work-tree"],
                env=good_environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(good.stdout.strip(), "true")

            command_scoped_environment = base_environment | {
                "GIT_CONFIG_GLOBAL": os.devnull
            }
            bad_command_scoped = subprocess.run(
                [
                    git,
                    "-c",
                    f"safe.directory={seed / '.git'}",
                    "-C",
                    str(seed),
                    "rev-parse",
                    "--is-inside-work-tree",
                ],
                env=command_scoped_environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(bad_command_scoped.returncode, 0)
            self.assertIn(
                "dubious ownership",
                bad_command_scoped.stderr.lower(),
            )

            good_command_scoped = subprocess.run(
                [
                    git,
                    "-c",
                    f"safe.directory={seed}",
                    "-C",
                    str(seed),
                    "rev-parse",
                    "--is-inside-work-tree",
                ],
                env=command_scoped_environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                good_command_scoped.returncode,
                0,
                good_command_scoped.stderr,
            )
            self.assertEqual(good_command_scoped.stdout.strip(), "true")


if __name__ == "__main__":
    unittest.main()

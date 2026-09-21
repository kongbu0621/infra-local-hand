from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from local_hand import git_safety


ROOT = Path(__file__).resolve().parents[1]


class PosixHookBoundaryTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX-only hook boundary")
    def test_hardened_git_uses_devnull_without_temp_hooks(self) -> None:
        with mock.patch.object(
            git_safety.tempfile,
            "gettempdir",
            side_effect=AssertionError("POSIX must not create a temporary hooks directory"),
        ) as gettempdir:
            prefix = git_safety.hardened_git_prefix(ROOT)

        gettempdir.assert_not_called()
        self.assertIn(f"core.hooksPath={os.devnull}", prefix)


class LinuxSeedBoundaryContractTests(unittest.TestCase):
    def test_seed_is_verified_before_local_clone(self) -> None:
        script = (ROOT / "tools/local_hand/bootstrap_linux.sh").read_text(
            encoding="utf-8"
        )
        required = (
            "seed repository must be a standalone Git working copy "
            "with a real .git directory",
            "seed repository must not use external Git object alternates",
            "seed repository Git metadata must contain only regular files and directories",
            "seed repository ancestors must be root-owned",
            "seed repository ancestors must not be writable by run user",
            "seed repository must be root-owned across its filesystem tree",
            "seed repository must not be writable by run user",
            "seed repository must be clean",
            "seed repository HEAD must equal implementation commit",
            'sudo find "$SEED_REPOSITORY_FROM" ! -user root '
            "-print -quit",
            'sudo find "$SEED_REPOSITORY_FROM/.git" '
            "! -type d ! -type f -print -quit",
            'sudo -u "$RUN_USER" find "$SEED_REPOSITORY_FROM" '
            "-writable -print -quit",
            "GIT_OPTIONAL_LOCKS=0 git_safe",
            '-c "safe.directory=$SEED_REPOSITORY_FROM"',
            'sudo -u "$RUN_USER" test -w "$SEED_ANCESTOR"',
            "reject_execution_config",
            "config --no-includes --name-only --get-regexp '.*'",
            "includeif.*.path",
            "uploadpack.packobjectshook",
            "core.alternaterefscommand",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

        self.assertNotIn("safe.directory=*", script)

        clone = script.index(
            'clone --no-local "$SEED_REPOSITORY_FROM" "$TARGET_REPO"'
        )
        for gate in (
            "seed repository must be a standalone Git working copy",
            "seed repository must not use external Git object alternates",
            "seed repository Git metadata must contain only regular files and directories",
            "seed repository ancestors must be root-owned",
            "seed repository ancestors must not be writable by run user",
            "seed repository must be root-owned across its filesystem tree",
            "seed repository must not be writable by run user",
            "seed repository must be clean",
            "seed repository HEAD must equal implementation commit",
            'reject_execution_config "$SEED_REPOSITORY_FROM"',
        ):
            with self.subTest(gate=gate):
                self.assertLess(script.index(gate), clone)


if __name__ == "__main__":
    unittest.main()

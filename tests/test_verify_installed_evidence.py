"""The installed verifier must prove directory-entry absence fail-closed."""
from __future__ import annotations

import errno
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


VERIFY_INSTALLED = Path(__file__).resolve().parents[1] / "tools" / "verify_installed.py"
SPEC = importlib.util.spec_from_file_location("verify_installed_evidence", VERIFY_INSTALLED)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class VerifyInstalledEvidenceTests(unittest.TestCase):
    def test_strict_entry_presence_distinguishes_dangling_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = root / "missing-result.json"
            pending = root / "pending.json"

            self.assertFalse(verifier._entry_exists_strict(missing))
            pending.symlink_to(missing)
            self.assertFalse(pending.exists())
            self.assertTrue(verifier._entry_exists_strict(pending))

    def test_strict_entry_presence_rejects_unknown_metadata_state(self):
        target = Path("unreadable-pending.json")
        with mock.patch.object(
            Path,
            "lstat",
            side_effect=OSError(errno.EIO, "synthetic metadata lookup failure"),
        ):
            with self.assertRaisesRegex(
                AssertionError, "cannot determine directory-entry state.*errno=5"
            ):
                verifier._entry_exists_strict(target)


if __name__ == "__main__":
    unittest.main()

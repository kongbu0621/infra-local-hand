from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest import mock

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from local_hand import mailbox_safety, worker
from local_hand.protocol import (
    MAX_TASK_ID_DIGITS,
    TASK_ID_RE,
    LocalHandError,
    TASK_SCHEMA,
    conflict_filename,
)


class LocalHandWindowsPathBudgetTests(unittest.TestCase):
    def _mailbox(self, root: Path) -> Path:
        mailbox = root / "mailbox"
        for relative in mailbox_safety.CONTROL_DIRS:
            (mailbox / relative).mkdir(parents=True, exist_ok=True)
        return mailbox

    def test_conflict_filename_is_digest_bound_and_component_bounded(self) -> None:
        task_id = "LH" + "9" * MAX_TASK_ID_DIGITS
        incoming = "a" * 64
        observed = "b" * 64
        name = conflict_filename(incoming)
        self.assertEqual(worker._conflict_filename(task_id, incoming, observed), name)
        self.assertEqual(len(name), 78)
        self.assertEqual(worker._conflict_filename(task_id, incoming, "malformed"), name)

    def test_full_windows_conflict_path_stays_below_legacy_max_path(self) -> None:
        parent = PureWindowsPath(
            "C:/ProgramData/LocalHand/mailboxes/"
            "12345678-1234-1234-1234-123456789abc/_executor_spike/conflicts"
        )
        target = parent / conflict_filename("a" * 64)
        temp = mailbox_safety._temporary_control_path(parent, target)
        self.assertLess(len(str(target)), 260)
        self.assertLess(len(str(temp)), 260)
        self.assertLessEqual(len(temp.name), 48)
        self.assertNotIn(target.name, temp.name)

    def test_worker_rejects_task_ids_beyond_controller_bound(self) -> None:
        task = {
            "schema_version": TASK_SCHEMA,
            "task_id": "LH" + "1" * (MAX_TASK_ID_DIGITS + 1),
            "target_node": "test-node",
            "action": "node.status",
            "params": {},
        }
        with self.assertRaises(LocalHandError) as ctx:
            worker.validate_task(task)
        self.assertEqual(ctx.exception.code, "invalid_task_id")
        self.assertIs(worker.TASK_ID_RE, TASK_ID_RE)

    def test_atomic_create_succeeds_and_removes_bounded_temp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mailbox = self._mailbox(Path(td))
            target = mailbox / "_executor_spike" / "conflicts" / f"CONFLICT-{'a' * 64}.json"
            mailbox_safety.atomic_create_control_file(mailbox, target, b"payload")
            self.assertEqual(target.read_bytes(), b"payload")
            self.assertEqual(list(target.parent.glob(".lh-*.tmp")), [])

    def test_atomic_publish_race_never_overwrites_winner(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mailbox = self._mailbox(Path(td))
            target = mailbox / "_executor_spike" / "results" / "LH0001.json"
            real_link = os.link

            def competing_publish(src: os.PathLike[str], dst: os.PathLike[str]) -> None:
                Path(dst).write_bytes(b"winner")
                real_link(src, dst)

            with mock.patch.object(mailbox_safety.os, "link", side_effect=competing_publish):
                with self.assertRaises(LocalHandError) as ctx:
                    mailbox_safety.atomic_create_control_file(mailbox, target, b"loser")
            self.assertEqual(ctx.exception.code, "mailbox_target_occupied")
            self.assertEqual(target.read_bytes(), b"winner")
            self.assertEqual(list(target.parent.glob(".lh-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()

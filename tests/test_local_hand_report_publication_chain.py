"""Evidence reports publish complete bytes and retain unrelated concurrent output."""
import errno
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from local_hand.protocol import LocalHandError
from local_hand_connect import controller, live_acceptance


@unittest.skipIf(os.name == 'nt', 'POSIX directory durability; Windows deferred')
class ReportPublicationChainTests(unittest.TestCase):
    def test_final_report_is_invisible_until_all_bytes_are_written(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'report.json'
            original = os.write
            observations = []
            def short_write(fd, data):
                count = original(fd, data[:3])
                observations.append(target.read_bytes() if target.exists() else None)
                return count
            value = {'status': 'partial', 'message': '完整证据'}
            with mock.patch.object(os, 'write', side_effect=short_write):
                live_acceptance._write_report(target, value)
            self.assertGreater(len(observations), 1)
            self.assertTrue(all(item is None for item in observations), observations)
            self.assertEqual(json.loads(target.read_bytes()), value)
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_write_failure_preserves_concurrent_final_path(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'report.json'
            original = os.write
            winner = b'{"owner":"concurrent publisher"}\n'
            def fail_after_replacement(fd, data):
                original(fd, data[:3])
                if target.exists():
                    target.unlink()
                target.write_bytes(winner)
                raise OSError(errno.ENOSPC, 'synthetic report disk full')
            with mock.patch.object(os, 'write', side_effect=fail_after_replacement):
                with self.assertRaises(LocalHandError) as raised:
                    live_acceptance._write_report(target, {'status': 'partial'})
            self.assertEqual(raised.exception.code, 'acceptance_report_write_failed')
            self.assertEqual(raised.exception.status, 'indeterminate')
            self.assertTrue(target.exists(), 'cleanup removed a different publisher output')
            self.assertEqual(target.read_bytes(), winner)
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_directory_sync_failure_retains_complete_report_as_uncertain(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'report.json'
            value = {'status': 'partial', 'message': 'complete before publication'}
            with mock.patch.object(controller, '_sync_publication_directory', side_effect=OSError(errno.EIO, 'synthetic directory sync failure')):
                with self.assertRaises(LocalHandError) as raised:
                    live_acceptance._write_report(target, value)
            self.assertEqual(raised.exception.code, 'acceptance_report_durability_unconfirmed')
            self.assertEqual(raised.exception.status, 'indeterminate')
            self.assertEqual(json.loads(target.read_bytes()), value)
            with self.assertRaises(LocalHandError):
                live_acceptance._write_report(target, {'status': 'failed'})
            self.assertEqual(json.loads(target.read_bytes()), value)

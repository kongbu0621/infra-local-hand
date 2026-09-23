from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from local_hand.bounded_io import FileReadUnavailable, read_regular_file_bounded
from local_hand.config import read_config
from local_hand.worker import load_json_bounded
from local_hand.protocol import LocalHandError


class ReadCompletenessTests(unittest.TestCase):
    def test_premature_eof_cannot_hide_config_or_worker_json_suffix(self):
        for reader in (read_config, lambda p: load_json_bounded(p, 1024, 'synthetic-invalid')):
            with self.subTest(reader=reader), tempfile.TemporaryDirectory() as folder:
                target = Path(folder) / 'fixture.json'
                prefix = b'{"valid_prefix":true}'
                target.write_bytes(prefix + b' invalid trailing bytes')
                original, reads = os.read, []
                def premature(fd, count):
                    reads.append(count)
                    return original(fd, min(count, len(prefix))) if len(reads) == 1 else b''
                with mock.patch('local_hand.bounded_io.os.read', side_effect=premature):
                    with self.assertRaises(FileReadUnavailable) as raised:
                        reader(target)
                self.assertEqual('indeterminate', raised.exception.status)
                self.assertTrue(target.read_bytes().endswith(b' invalid trailing bytes'))

    def test_same_size_mutation_during_read_is_uncertain(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'mutable.bin'
            target.write_bytes(b'original')
            before = target.stat()
            original, reads = os.read, []
            def changed(fd, count):
                result = original(fd, count)
                reads.append(count)
                if len(reads) == 1:
                    target.write_bytes(b'replaced')
                    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
                return result
            with mock.patch('local_hand.bounded_io.os.read', side_effect=changed):
                with self.assertRaises(FileReadUnavailable):
                    read_regular_file_bounded(target, 1024, 'synthetic-invalid')
            self.assertEqual(b'replaced', target.read_bytes())

    def test_empty_short_chunk_and_size_boundary_behavior(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'stable.bin'
            target.write_bytes(b'')
            self.assertEqual(b'', read_regular_file_bounded(target, 8, 'synthetic-invalid'))
            target.write_bytes(b'12345678')
            original = os.read
            with mock.patch('local_hand.bounded_io.os.read', side_effect=lambda fd, n: original(fd, min(n, 2))):
                self.assertEqual(b'12345678', read_regular_file_bounded(target, 8, 'synthetic-invalid'))
            with self.assertRaises(LocalHandError) as oversized:
                read_regular_file_bounded(target, 7, 'synthetic-invalid')
            self.assertNotIsInstance(oversized.exception, FileReadUnavailable)


if __name__ == '__main__':
    unittest.main(verbosity=2)

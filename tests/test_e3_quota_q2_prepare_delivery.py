"""Real tar and process/pipe transport checks, without SSH or a host fixture."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch

from e3_host import q2_prepare_delivery as d


def archive(entries=None):
    entries = entries or [("source", None, tarfile.DIRTYPE), ("source/payload.py", b"pass\n", tarfile.REGTYPE)]
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, raw, kind in entries:
            info = tarfile.TarInfo(name); info.type = kind
            info.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
            info.size = 0 if raw is None else len(raw)
            tar.addfile(info, None if raw is None else io.BytesIO(raw))
    return stream.getvalue()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


@unittest.skipUnless(os.name == "posix", "Linux host transport")
class Archives(unittest.TestCase):
    def test_tar_and_gzip_are_bound_before_extract(self):
        for raw in (archive(), gzip.compress(archive())):
            result = d.archive_members(raw, digest(raw), maximum_bytes=65536)
            self.assertEqual([m["name"] for m in result["members"]], ["source", "source/payload.py"])
            self.assertEqual(result["staging_bytes"], 12288)

    def test_duplicate_traversal_links_and_missing_parents_rejected(self):
        variants = [
            [("../escape", b"x", tarfile.REGTYPE)],
            [("/absolute", b"x", tarfile.REGTYPE)],
            [("link", None, tarfile.SYMTYPE)],
            [("link", None, tarfile.LNKTYPE)],
            [("fifo", None, tarfile.FIFOTYPE)],
            [("same", b"x", tarfile.REGTYPE), ("same", b"y", tarfile.REGTYPE)],
            [("missing/file", b"x", tarfile.REGTYPE)],
            [("source/.git/objects/info/alternates", b"/external\n", tarfile.REGTYPE)],
        ]
        for entries in variants:
            with self.subTest(entries=entries):
                raw = archive(entries)
                with self.assertRaises(ValueError):
                    d.archive_members(raw, digest(raw), maximum_bytes=65536)

    def test_compressed_expansion_and_wrong_hash_rejected(self):
        raw = gzip.compress(archive([("large", b"x" * 131072, tarfile.REGTYPE)]))
        with self.assertRaisesRegex(ValueError, "DELIVERY_DECOMPRESSION_LIMIT"):
            d.archive_members(raw, digest(raw), maximum_bytes=65536)
        raw = archive()
        with self.assertRaisesRegex(ValueError, "DELIVERY_ARCHIVE_DIGEST"):
            d.archive_members(raw, "0" * 64, maximum_bytes=65536)

    def extraction(self, folder, **changes):
        now = time.monotonic_ns()
        args = dict(destination=Path(folder) / "stage", reservation_path=Path(folder) / "intent.json", guest_pin={},
                    installation_reservation_bytes=4096, retained_delivery_bytes=10240, ceiling_bytes=65536,
                    issued_ns=now, deadline_ns=now + 3*10**9)
        args.update(changes)
        return args

    def test_create_only_extraction_and_second_attempt_refused(self):
        raw = archive()
        with tempfile.TemporaryDirectory() as folder, patch.object(d, "protected_parent", side_effect=Path), \
                patch.object(d, "verify_guest", return_value={}):
            args = self.extraction(folder)
            result = d.reserve_and_extract(raw, digest(raw), **args)
            self.assertEqual(result["status"], "EXTRACTED")
            self.assertEqual((Path(folder) / "stage/source/payload.py").read_bytes(), b"pass\n")
            with self.assertRaisesRegex(ValueError, "DELIVERY_ALREADY_RESERVED"):
                d.reserve_and_extract(raw, digest(raw), **args)
            self.assertEqual(json.loads((Path(folder) / "intent.json").read_bytes())["status"], "RESERVED")

    def test_partial_file_failure_retains_intent_and_blocks_replay(self):
        raw = archive(); actual = d.write
        def fail(path, content, mode=0o600):
            if Path(path).name == "payload.py":
                raise OSError("injected disk error")
            return actual(path, content, mode)
        with tempfile.TemporaryDirectory() as folder, patch.object(d, "protected_parent", side_effect=Path), \
                patch.object(d, "verify_guest", return_value={}):
            args = self.extraction(folder)
            with patch.object(d, "write", side_effect=fail), self.assertRaises(OSError):
                d.reserve_and_extract(raw, digest(raw), **args)
            self.assertTrue(args["reservation_path"].exists())
            self.assertTrue(args["destination"].exists())
            with self.assertRaisesRegex(ValueError, "DELIVERY_ALREADY_RESERVED"):
                d.reserve_and_extract(raw, digest(raw), **args)

    def test_aggregate_budget_and_wrong_guest_fail_before_intent(self):
        raw = archive()
        with tempfile.TemporaryDirectory() as folder, patch.object(d, "protected_parent", side_effect=Path), \
                patch.object(d, "verify_guest", return_value={}):
            args = self.extraction(folder, installation_reservation_bytes=65536)
            with self.assertRaisesRegex(ValueError, "DELIVERY_TOTAL_BUDGET"):
                d.reserve_and_extract(raw, digest(raw), **args)
            self.assertFalse(args["reservation_path"].exists())
        with tempfile.TemporaryDirectory() as folder, patch.object(d, "verify_guest", side_effect=ValueError("WRONG_GUEST")):
            args = self.extraction(folder)
            with self.assertRaisesRegex(ValueError, "WRONG_GUEST"):
                d.reserve_and_extract(raw, digest(raw), **args)
            self.assertFalse(args["reservation_path"].exists())


@unittest.skipUnless(os.name == "posix", "Linux process-group transport")
class Capture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_capture(self, code, *, seconds=3, **changes):
        issued = time.monotonic_ns()
        args = dict(issued_ns=issued, deadline_ns=issued+int(seconds*1e9), output_limit=4096,
                    stdout_path=self.root/"stdout", stderr_path=self.root/"stderr")
        args.update(changes)
        return d.capture([sys.executable, "-I", "-B", "-c", code], **args)

    def test_large_file_stdin_and_both_stream_eof_with_actual_exit(self):
        stdin = self.root / "input"; stdin.write_bytes(b"x" * 2*1024*1024)
        result = self.run_capture("import sys; print(len(sys.stdin.buffer.read())); print('done',file=sys.stderr)", stdin_path=stdin)
        self.assertTrue(result["complete"]); self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["eof"], ["stderr", "stdout"])
        self.assertEqual((self.root/"stdout").read_bytes(), b"2097152\n")
        self.assertFalse(result["remote_stop_proven"])

    def test_nonzero_exit_preserved_despite_eof(self):
        result = self.run_capture("raise SystemExit(7)")
        self.assertFalse(result["complete"]); self.assertEqual(result["returncode"], 7)
        self.assertEqual(result["eof"], ["stderr", "stdout"])

    def test_output_limit_truncates_and_stays_incomplete(self):
        result = self.run_capture("import os; os.write(1,b'x'*20000)")
        self.assertFalse(result["complete"]); self.assertEqual(result["error"], "DELIVERY_CAPTURE_LIMIT")
        self.assertEqual(result["captured_bytes"], 4096)

    @unittest.skipUnless(hasattr(os, "fork"), "fork preserves pipe ownership")
    def test_exited_client_with_live_pipe_holder_is_not_complete(self):
        code = "import os,time; child=os.fork(); time.sleep(5) if child==0 else None; os._exit(0)"
        result = self.run_capture(code, seconds=0.4)
        self.assertFalse(result["complete"]); self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["error"], "DELIVERY_CAPTURE_TIMEOUT")
        self.assertTrue(result["within_original_deadline"])

    def test_expired_original_budget_has_no_output_or_spawn(self):
        now = time.monotonic_ns()
        with self.assertRaisesRegex(ValueError, "DELIVERY_DEADLINE"):
            d.capture([sys.executable,"-c","pass"],issued_ns=now-2*10**9, deadline_ns=now-10**9,
                output_limit=4096,stdout_path=self.root/"stdout",stderr_path=self.root/"stderr")
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

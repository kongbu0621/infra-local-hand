"""Actual Git/archive/compiler checks for the explicit preparation installer."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from e3_host import q2_prepare_build as b


def command(argv):
    result = subprocess.run(argv, capture_output=True, check=True, timeout=10,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if len(result.stdout) > 32768 or len(result.stderr) > 32768:
        raise ValueError("TEST_COMMAND_CAPTURE_LIMIT")
    return result.stdout


def fixture_wheel(path, files, *, commit="a" * 40, transform=None):
    content = {name: raw for name, raw in files.items()}
    metadata = dict(schema_version="infra-local-hand-build/v1", product_version="0.2.0a1",
                    source_commit=commit, artifact_kind="wheel", files={k: b.sha(v) for k, v in files.items()})
    content[b.METADATA] = json.dumps(metadata).encode()
    root = "infra_local_hand-0.2.0a1.dist-info/"
    content[root + "METADATA"] = b"Metadata-Version: 2.4\nName: infra-local-hand\nVersion: 0.2.0a1\n"
    content[root + "WHEEL"] = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    if transform:
        transform(content)
    stream = io.StringIO(); writer = csv.writer(stream, lineterminator="\n")
    for name, raw in content.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()
        writer.writerow((name, "sha256=" + digest, str(len(raw))))
    writer.writerow((root + "RECORD", "", ""))
    content[root + "RECORD"] = stream.getvalue().encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in content.items():
            archive.writestr(name, raw)
    return b.sha(path.read_bytes())


@unittest.skipUnless(os.name == "posix", "Linux preparation file admission")
class BuildArchives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.wheel = self.root / "candidate.whl"
        self.files = {name + "/__init__.py": b"\"\"\"Bound package.\"\"\"\n" for name in b.PACKAGES}
        self.files["local_hand/worker.py"] = b"pass\n"
        self.source = {"tools/" + k: b.sha(v) for k, v in self.files.items()}

    def test_complete_record_metadata_payload_matches_source(self):
        digest = fixture_wheel(self.wheel, self.files)
        result = b.verify_wheel(self.wheel, digest, "a" * 40, self.source)
        self.assertEqual(result["files"], {k: b.sha(v) for k, v in self.files.items()})
        self.assertEqual(len(result["payload_digest"]), 64)

    def test_changed_record_even_with_new_whole_archive_hash_is_rejected(self):
        fixture_wheel(self.wheel, self.files)
        with zipfile.ZipFile(self.wheel) as archive:
            content = {name: archive.read(name) for name in archive.namelist()}
        metadata = "infra_local_hand-0.2.0a1.dist-info/METADATA"
        content[metadata] += b"Summary: tampered after RECORD\n"
        with zipfile.ZipFile(self.wheel, "w") as archive:
            for name, raw in content.items():
                archive.writestr(name, raw)
        with self.assertRaisesRegex(ValueError, "BUILD_RECORD_BYTES"):
            b.verify_wheel(self.wheel, b.sha(self.wheel.read_bytes()), "a" * 40, self.source)

    def test_foreign_commit_rejected(self):
        digest = fixture_wheel(self.wheel, self.files, commit="b" * 40)
        with self.assertRaisesRegex(ValueError, "BUILD_WHEEL_METADATA"):
            b.verify_wheel(self.wheel, digest, "a" * 40, self.source)

    def test_extra_import_tree_or_path_escape_rejected(self):
        for name in ("foreign/__init__.py", "local_hand/extra.py", "../escape"):
            with self.subTest(name=name):
                digest = fixture_wheel(self.wheel, self.files, transform=lambda v: v.update({name: b"pass\n"}))
                with self.assertRaisesRegex(ValueError, "BUILD_WHEEL_(EXTRAS|ENTRY)"):
                    b.verify_wheel(self.wheel, digest, "a" * 40, self.source)

    def test_self_consistent_wrong_payload_rejected_against_git(self):
        self.files["local_hand/worker.py"] = b"raise RuntimeError('changed')\n"
        digest = fixture_wheel(self.wheel, self.files)
        with self.assertRaisesRegex(ValueError, "BUILD_WHEEL_SOURCE"):
            b.verify_wheel(self.wheel, digest, "a" * 40, self.source)

    def test_pinned_artifact_digest_rejected_before_archive(self):
        fixture_wheel(self.wheel, self.files)
        with self.assertRaisesRegex(ValueError, "BUILD_WHEEL_DIGEST"):
            b.verify_wheel(self.wheel, "0" * 64, "a" * 40, self.source)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires no-follow open")
    def test_symlink_and_hardlink_input_rejected(self):
        digest = fixture_wheel(self.wheel, self.files)
        link = self.root / "link.whl"; link.symlink_to(self.wheel)
        with self.assertRaises(OSError):
            b.verify_wheel(link, digest, "a" * 40, self.source)
        link.unlink(); os.link(self.wheel, link)
        with self.assertRaisesRegex(ValueError, "BUILD_FILE"):
            b.verify_wheel(self.wheel, digest, "a" * 40, self.source)

    def test_create_only_write_preserves_partial_attempt(self):
        target = self.root / "receipt.json"
        b.write_new(target, b"original\n")
        with self.assertRaises(FileExistsError):
            b.write_new(target, b"replacement\n")
        self.assertEqual(target.read_bytes(), b"original\n")


@unittest.skipUnless(shutil.which("git") and os.name == "posix", "actual Git source admission")
class BuildGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"; self.root.mkdir()
        command(["git", "init", "--quiet", str(self.root)])
        command(["git", "-C", str(self.root), "config", "user.name", "Fixture"])
        command(["git", "-C", str(self.root), "config", "user.email", "fixture@example.invalid"])
        (self.root / "tracked.py").write_text("pass\n")
        (self.root / ".gitignore").write_text("ignored/\n")
        command(["git", "-C", str(self.root), "add", "."])
        command(["git", "-C", str(self.root), "commit", "--quiet", "-m", "fixture"])
        self.commit, self.tree = command(["git", "-C", str(self.root), "rev-parse", "HEAD", "HEAD^{tree}"]).decode().split()

    def test_clean_exact_source(self):
        self.assertEqual(b.verify_source(self.root, self.commit, self.tree, command)["tracked.py"], b.sha(b"pass\n"))

    def test_skip_worktree_drift_is_not_clean_source(self):
        command(["git", "-C", str(self.root), "update-index", "--skip-worktree", "tracked.py"])
        (self.root / "tracked.py").write_text("untrusted = True\n")
        self.assertEqual(command(["git", "-C", str(self.root), "status", "--porcelain"]), b"")
        with self.assertRaisesRegex(ValueError, "BUILD_SOURCE_BYTES"):
            b.verify_source(self.root, self.commit, self.tree, command)

    def test_ignored_executable_is_not_clean_source(self):
        (self.root / "ignored").mkdir(); (self.root / "ignored/poison.py").write_text("pass\n")
        with self.assertRaisesRegex(ValueError, "BUILD_IGNORED_INPUT"):
            b.verify_source(self.root, self.commit, self.tree, command)

    def test_large_full_tree_uses_bounded_directory_queries(self):
        for folder in range(8):
            path = self.root / ("group" + str(folder)); path.mkdir()
            for index in range(80):
                (path / ("payload_" + str(index) + ".py")).write_text("pass\n")
        command(["git", "-C", str(self.root), "add", "."])
        command(["git", "-C", str(self.root), "commit", "--quiet", "-m", "larger tree"])
        commit, tree = command(["git", "-C", str(self.root), "rev-parse", "HEAD", "HEAD^{tree}"]).decode().split()
        actual = b.verify_source(self.root, commit, tree, command)
        self.assertEqual(len(actual), 642)


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("cc"), "Linux headers and C compiler")
class BuildNative(unittest.TestCase):
    def test_real_native_compile_and_real_abi_sizes(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            # Pin protection is separately enforced in production; a temporary
            # test directory deliberately cannot satisfy root immutable ancestry.
            with patch.object(b, "pin", side_effect=lambda p: {"path": str(p), "sha256": b.sha(b.regular(p))}):
                result = b.compile_native(source, out, Path(shutil.which("cc")).resolve(), command)
            self.assertEqual(result["abi"]["fsxattr_bytes"], 28)
            self.assertGreater(result["abi"]["dqblk_bytes"], 0)
            self.assertIn(str(source / "tools/admin/local_hand_quota_observer/quota_fd_query.c"), result["inputs"])
            self.assertIn(str(source / "tools/admin/local_hand_quota_observer/quota_syscall_filter.h"), result["inputs"])
            self.assertEqual(b.regular(out / "quota_fd_query")[:4], b"\x7fELF")

    def test_no_argument_is_blocked_and_does_not_create_objects(self):
        with patch("sys.stdout", new_callable=io.StringIO) as stream:
            self.assertEqual(b.main([]), 3)
        self.assertFalse(json.loads(stream.getvalue())["fixture_provisioned"])


if __name__ == "__main__":
    unittest.main()

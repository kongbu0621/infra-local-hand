"""Exercise real setuptools builds while source/distribution identities move."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


_SOURCE = Path(__file__).resolve().parents[1]
_PACKAGES = ("local_hand", "local_hand_connect", "local_hand_jobs", "local_hand_mcp")
_DRIVER = r'''
from pathlib import Path
import os
import runpy
import subprocess
import sys
from unittest.mock import patch
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.command.build_py import build_py
from setuptools.dist import Distribution

stage, target, destination = sys.argv[1:]
switched = False
def switch():
    global switched
    if not switched:
        subprocess.run(['git', 'checkout', '--quiet', '--detach', target], check=True)
        switched = True
        print('SOURCE_SWITCHED=' + target, flush=True)

if stage == 'after_parse':
    owner, attribute = Distribution, 'parse_config_files'
elif stage == 'after_copy':
    owner, attribute = build_py, 'run'
elif stage == 'after_archive':
    owner, attribute = bdist_wheel, 'run'
else:
    owner, attribute = os, 'fsync'
original = getattr(owner, attribute)
def boundary(*args, **kwargs):
    result = original(*args, **kwargs)
    switch()
    return result
sys.argv = ['setup.py', 'bdist_wheel', '--dist-dir', destination]
with patch.object(owner, attribute, boundary):
    runpy.run_path('setup.py', run_name='__main__')
'''


class BuildIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lh-build-identity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        # Copy only the actual build inputs. Every case commits its own isolated
        # fixture; the caller's dirty checkout and other tests remain untouched.
        for name in ("setup.py", "pyproject.toml", ".gitattributes", ".gitignore"):
            shutil.copyfile(_SOURCE / name, self.repo / name)
        (self.repo / "README.md").write_bytes(b"# Fixture release A\n\nREADME_FROM_A\n")
        for package in _PACKAGES:
            target = self.repo / "tools" / package
            target.mkdir(parents=True)
            for source in (_SOURCE / "tools" / package).iterdir():
                if source.suffix in (".py", ".sh", ".ps1"):
                    shutil.copyfile(source, target / source.name)
        self.environment = os.environ.copy()
        for key in tuple(self.environment):
            if key.startswith("GIT_") or key in ("PYTHONPATH", "PYTHONHOME"):
                self.environment.pop(key)
        self.environment["GIT_CONFIG_SYSTEM"] = os.devnull
        self.environment["GIT_CONFIG_GLOBAL"] = os.devnull
        self.environment["PYTHONDONTWRITEBYTECODE"] = "1"
        self.git("init", "--quiet")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "user.name", "build-fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Fixture source A")
        self.commit_a = self.git("rev-parse", "HEAD").strip()
        self.output = self.root / "wheel-output"
        self.output.mkdir()

    def command(self, args, *, succeeds=True):
        result = subprocess.run([str(value) for value in args], cwd=self.repo,
                                env=self.environment, capture_output=True,
                                text=True, timeout=120)
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def git(self, *args):
        return self.command(["git", *args]).stdout

    def changed_commit(self, kind="readme"):
        if kind == "readme":
            (self.repo / "README.md").write_bytes(b"# Fixture release B\n\nREADME_FROM_B\n")
        else:
            path = self.repo / "pyproject.toml"
            text = path.read_text(encoding="utf-8").replace(
                'local-hand-worker = "local_hand.worker:main"',
                'local-hand-worker = "local_hand.controller:main"')
            path.write_bytes(text.encode("utf-8"))
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Fixture metadata-only source B")
        return self.git("rev-parse", "HEAD").strip()

    def build(self, *, metadata=None, succeeds=True):
        if metadata is not None:
            script = ("import setuptools.build_meta as b; "
                      "b.build_wheel(%r, metadata_directory=%r)" % (str(self.output), str(metadata)))
            args = [sys.executable, "-I", "-c", script]
        else:
            args = [sys.executable, "-I", "setup.py", "bdist_wheel", "--dist-dir", self.output]
        return self.command(args, succeeds=succeeds)

    def wheel_identity(self):
        wheels = list(self.output.glob("*.whl"))
        self.assertEqual(len(wheels), 1)
        with zipfile.ZipFile(wheels[0]) as archive:
            identity = json.loads(archive.read("local_hand/_build_metadata.json"))
            name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            metadata = archive.read(name).decode("utf-8")
            return identity, metadata

    def assert_switch_rejected(self, stage, kind="readme"):
        commit_b = self.changed_commit(kind)
        self.git("checkout", "--quiet", "--detach", self.commit_a)
        driver = self.root / "driver.py"
        driver.write_text(_DRIVER, encoding="utf-8")
        result = self.command([sys.executable, "-I", driver, stage, commit_b, self.output], succeeds=False)
        self.assertIn("SOURCE_SWITCHED=" + commit_b, result.stdout)
        self.assertIn("source commit changed", result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), commit_b)
        if stage != "after_archive":
            self.assertEqual(list(self.output.glob("*.whl")), [])
        else:
            # Failed late output is retained, never reported as a verified build.
            identity, metadata = self.wheel_identity()
            self.assertEqual(identity["source_commit"], self.commit_a)
            self.assertIn("README_FROM_A", metadata)

    def prepare_metadata(self):
        output = self.root / "prepared-metadata"
        output.mkdir()
        # The real PEP 517 hook executes setup before the later build hook.
        script = "import setuptools.build_meta as b; b.prepare_metadata_for_build_wheel(%r)" % str(output)
        self.command([sys.executable, "-I", "-c", script])
        matches = list(output.glob("*.dist-info"))
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_clean_wheel_preserves_source_and_distribution_identity(self):
        self.build()
        identity, metadata = self.wheel_identity()
        self.assertEqual(identity["source_commit"], self.commit_a)
        self.assertIn("README_FROM_A", metadata)
        self.assertNotIn("README_FROM_B", metadata)

    def test_readme_checkout_after_distribution_parse_is_rejected(self):
        self.assert_switch_rejected("after_parse")

    def test_entrypoint_checkout_after_distribution_parse_is_rejected(self):
        self.assert_switch_rejected("after_parse", "entrypoint")

    def test_readme_checkout_after_payload_copy_is_rejected(self):
        self.assert_switch_rejected("after_copy")

    def test_entrypoint_checkout_after_payload_copy_is_rejected(self):
        self.assert_switch_rejected("after_copy", "entrypoint")

    def test_checkout_while_sealing_payload_identity_is_rejected(self):
        self.assert_switch_rejected("after_fsync")

    def test_checkout_after_archive_creation_cannot_report_success(self):
        self.assert_switch_rejected("after_archive")

    def test_clean_prepared_metadata_can_be_reused(self):
        self.build(metadata=self.prepare_metadata())
        identity, metadata = self.wheel_identity()
        self.assertEqual(identity["source_commit"], self.commit_a)
        self.assertIn("README_FROM_A", metadata)

    def test_prepared_metadata_from_previous_commit_is_rejected(self):
        metadata = self.prepare_metadata()
        self.changed_commit()
        result = self.build(metadata=metadata, succeeds=False)
        self.assertIn("prepared metadata differs", result.stderr)
        self.assertEqual(list(self.output.glob("*.whl")), [])

    def test_changed_prepared_metadata_bytes_are_rejected(self):
        metadata = self.prepare_metadata()
        with (metadata / "METADATA").open("a", encoding="utf-8") as stream:
            stream.write("\nUNBOUND_PREPARED_METADATA\n")
        result = self.build(metadata=metadata, succeeds=False)
        self.assertIn("prepared metadata differs", result.stderr)
        self.assertEqual(list(self.output.glob("*.whl")), [])

    def test_skip_build_cannot_bypass_payload_verification(self):
        result = self.command([sys.executable, "-I", "setup.py", "bdist_wheel", "--skip-build",
                               "--dist-dir", self.output], succeeds=False)
        self.assertIn("wheel must verify its source build", result.stderr)
        self.assertEqual(list(self.output.glob("*.whl")), [])


if __name__ == "__main__":
    unittest.main()

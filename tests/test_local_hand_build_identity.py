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


class BuildFixture(unittest.TestCase):
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
        shutil.copytree(_SOURCE / "plugins", self.repo / "plugins", ignore=shutil.ignore_patterns("__pycache__"))
        (self.repo / "README.md").write_bytes(b"# Fixture release A\n\nREADME_FROM_A\n")
        for package in _PACKAGES:
            target = self.repo / "tools" / package
            target.mkdir(parents=True)
            for source in (_SOURCE / "tools" / package).iterdir():
                if source.suffix in (".py", ".sh", ".ps1"):
                    shutil.copyfile(source, target / source.name)
        shutil.copyfile(_SOURCE / "tools/build_plugin.py", self.repo / "tools/build_plugin.py")
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


class BuildIdentityTests(BuildFixture):
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

    def test_prepared_metadata_changed_during_wheel_assembly_is_rejected(self):
        metadata = self.prepare_metadata()
        script = r'''
from pathlib import Path
import sys
from unittest.mock import patch
import setuptools.build_meta as backend
from setuptools.command.build_py import build_py
original = build_py.run
metadata_root, wheel_output = Path(sys.argv[1]), sys.argv[2]
def mutate(self):
    result = original(self)
    with (metadata_root / 'METADATA').open('a', encoding='utf-8') as stream:
        stream.write('\nUNBOUND_DURING_BUILD\n')
    print('PREPARED_METADATA_CHANGED', flush=True)
    return result
with patch.object(build_py, 'run', mutate):
    backend.build_wheel(wheel_output, metadata_directory=str(metadata_root))
'''
        result = self.command([sys.executable, "-I", "-c", script, metadata, self.output], succeeds=False)
        self.assertIn("PREPARED_METADATA_CHANGED", result.stdout)
        self.assertIn("wheel distribution metadata differs", result.stderr)

    def test_installed_copy_changed_after_payload_verification_is_rejected(self):
        script = r'''
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
from setuptools.command.install_lib import install_lib
original = install_lib.run
def mutate(self):
    result = original(self)
    with (Path(self.install_dir) / 'local_hand/worker.py').open('a', encoding='utf-8') as stream:
        stream.write('\nUNBOUND_AFTER_COPY = True\n')
    print('INSTALLED_COPY_CHANGED', flush=True)
    return result
sys.argv = ['setup.py', 'bdist_wheel', '--dist-dir', sys.argv[1]]
with patch.object(install_lib, 'run', mutate):
    runpy.run_path('setup.py', run_name='__main__')
'''
        result = self.command([sys.executable, "-I", "-c", script, self.output], succeeds=False)
        self.assertIn("INSTALLED_COPY_CHANGED", result.stdout)
        self.assertIn("wheel payload differs", result.stderr)

    def assert_distribution_copy_rejected(self, member):
        script = r'''
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
from wheel.wheelfile import WheelFile
original = WheelFile.write_files
member, destination = sys.argv[1:]
def mutate(self, base_dir):
    target = next(Path(base_dir).glob('*.dist-info/' + member))
    with target.open('a', encoding='utf-8') as stream:
        stream.write('\nUNBOUND_DISTRIBUTION_METADATA\n')
    print('DISTRIBUTION_COPY_CHANGED', flush=True)
    return original(self, base_dir)
sys.argv = ['setup.py', 'bdist_wheel', '--dist-dir', destination]
with patch.object(WheelFile, 'write_files', mutate):
    runpy.run_path('setup.py', run_name='__main__')
'''
        result = self.command([sys.executable, "-I", "-c", script, member, self.output], succeeds=False)
        self.assertIn("DISTRIBUTION_COPY_CHANGED", result.stdout)
        self.assertIn("wheel distribution metadata differs", result.stderr)

    def test_generated_metadata_changed_during_archive_creation_is_rejected(self):
        self.assert_distribution_copy_rejected("METADATA")

    def test_generated_entrypoints_changed_during_archive_creation_are_rejected(self):
        self.assert_distribution_copy_rejected("entry_points.txt")

    def test_retained_wheel_cannot_add_unbound_import_package(self):
        self.build()
        wheel = next(self.output.glob("*.whl"))
        installed = self.root / "installed" / "local_hand"
        installed.mkdir(parents=True)
        with zipfile.ZipFile(wheel) as archive:
            (installed / "_build_metadata.json").write_bytes(archive.read("local_hand/_build_metadata.json"))
        with zipfile.ZipFile(wheel, "a") as archive:
            archive.writestr("local_hand/worker/__init__.py", "UNBOUND_IMPORT_PACKAGE = True\n")
        script = r'''
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path.cwd() / 'tools'))
from local_hand import installation
from local_hand.protocol import LocalHandError
installation.__file__ = sys.argv[1]
metadata = json.loads((Path(sys.argv[1]).parent / '_build_metadata.json').read_bytes())
try:
    installation.verify_wheel(Path(sys.argv[2]), metadata)
except LocalHandError as exc:
    assert exc.code == 'installation_mismatch', exc.code
    assert 'unbound' in str(exc), str(exc)
else:
    raise AssertionError('retained wheel accepted an unbound import package')
'''
        self.command([sys.executable, "-I", "-c", script, installed / "installation.py", wheel])

    def test_skip_build_cannot_bypass_payload_verification(self):
        result = self.command([sys.executable, "-I", "setup.py", "bdist_wheel", "--skip-build",
                               "--dist-dir", self.output], succeeds=False)
        self.assertIn("wheel must verify its source build", result.stderr)
        self.assertEqual(list(self.output.glob("*.whl")), [])


@unittest.skipUnless(sys.platform == "linux", "Plugin publication is Linux-only; wheel identity remains cross-platform")
class PluginBuildIdentityTests(BuildFixture):
    def plugin_probe(self, boundary):
        script = r'''
from pathlib import Path
import json
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path.cwd() / 'tools'))
import build_plugin
output = Path(sys.argv[1]) / 'plugin.zip'
boundary = sys.argv[2]
replacements = []
name = '_publish_create_only' if hasattr(build_plugin, '_publish_create_only') else None
owner = build_plugin if name else build_plugin.os
name = name or 'link'
original = getattr(owner, name)
def publish(source, target, **kwargs):
    result = original(source, target, **kwargs)
    path = Path(sys.argv[1]) / Path(source if boundary == 'staging' else target).name
    if path.exists():
        path.unlink()
    path.write_bytes(b'CONCURRENT_REPLACEMENT')
    replacements.append(path)
    return result
with patch.object(owner, name, publish):
    try:
        result = build_plugin.build(output)
    except (ValueError, OSError) as exc:
        if boundary != 'output':
            raise
        print('PUBLICATION_REJECTED=' + str(exc))
    else:
        if boundary == 'output':
            raise AssertionError('build accepted a replaced output: ' + json.dumps(result))
assert len(replacements) == 1
assert replacements[0].exists(), 'build deleted a concurrent staging replacement'
assert replacements[0].read_bytes() == b'CONCURRENT_REPLACEMENT'
'''
        return self.command([sys.executable, "-I", "-c", script, self.output, boundary])

    def test_plugin_publication_preserves_replaced_staging_entry(self):
        self.plugin_probe("staging")

    def test_plugin_publication_rejects_replaced_output(self):
        self.plugin_probe("output")

    def test_plugin_final_readback_rejects_in_place_rewrite_with_restored_mtime(self):
        script = r'''
from pathlib import Path
import os
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path.cwd() / 'tools'))
import build_plugin
output = Path(sys.argv[1]) / 'plugin.zip'
original = build_plugin.hashlib.file_digest
calls = 0
changed = None
def mutate(stream, digest):
    global calls, changed
    result = original(stream, digest)
    calls += 1
    if calls == 2:
        before = output.stat()
        changed = b'!' + output.read_bytes()[1:]
        output.write_bytes(changed)
        os.utime(output, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = output.stat()
        assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        assert before.st_ctime_ns != after.st_ctime_ns
    return result
with patch.object(build_plugin.hashlib, 'file_digest', mutate):
    try:
        build_plugin.build(output)
    except ValueError as exc:
        assert 'changed' in str(exc), str(exc)
    else:
        raise AssertionError('build accepted an output rewritten after final hashing')
assert changed is not None and output.read_bytes() == changed
'''
        self.command([sys.executable, "-I", "-c", script, self.output])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_plugin_output_cannot_enter_source_through_linked_parent(self):
        linked = self.root / "linked-output"
        linked.symlink_to(self.repo, target_is_directory=True)
        script = r'''
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd() / 'tools'))
import build_plugin
try:
    build_plugin.build(Path(sys.argv[1]))
except ValueError:
    pass
else:
    raise AssertionError('build published inside its source tree through a symlink')
assert not (Path.cwd() / 'plugin.zip').exists()
'''
        self.command([sys.executable, "-I", "-c", script, linked / "plugin.zip"])


if __name__ == "__main__":
    unittest.main()

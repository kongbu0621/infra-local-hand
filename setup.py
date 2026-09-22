"""Build a wheel whose payload is bound to the exact clean source commit."""
from pathlib import Path
import hashlib
import json
import os
import sys

from setuptools import setup
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.command.build_py import build_py
from setuptools.command.dist_info import dist_info

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
from local_hand.provenance import source_commit, write_build_metadata
from local_hand.protocol import LocalHandError

# setuptools parses README and project metadata before build_py.run. Freeze the
# identity before setup() so a later clean checkout cannot relabel older inputs.
BUILD_SOURCE_COMMIT = source_commit(require_clean=True)
DIST_IDENTITY = "local_hand_build_identity.json"


def _check_source(*, require_clean=False):
    if source_commit(require_clean=require_clean) != BUILD_SOURCE_COMMIT:
        raise LocalHandError("provenance_mismatch", "source commit changed during build", "indeterminate")


def _metadata_files(root):
    files = {}
    for path in sorted(Path(root).iterdir()):
        if path.name == DIST_IDENTITY:
            continue
        if path.is_symlink() or not path.is_file():
            raise LocalHandError("provenance_mismatch", "prepared metadata must use regular files", "indeterminate")
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


class VerifiedDistInfo(dist_info):
    def run(self):
        _check_source(require_clean=True)
        super().run()
        _check_source(require_clean=True)
        identity = {"source_commit": BUILD_SOURCE_COMMIT, "files": _metadata_files(self.dist_info_dir)}
        with (Path(self.dist_info_dir) / DIST_IDENTITY).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(identity, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _check_source(require_clean=True)


class VerifiedWheel(bdist_wheel):
    def run(self):
        _check_source(require_clean=True)
        if self.skip_build:
            raise LocalHandError("provenance_mismatch", "wheel must verify its source build", "indeterminate")
        if self.dist_info_dir:
            path = Path(self.dist_info_dir) / DIST_IDENTITY
            try:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("missing metadata identity")
                identity = json.loads(path.read_text(encoding="utf-8"))
                expected = {"source_commit": BUILD_SOURCE_COMMIT, "files": _metadata_files(self.dist_info_dir)}
                if identity != expected:
                    raise ValueError("prepared metadata identity differs")
            except (OSError, ValueError) as exc:
                raise LocalHandError("provenance_mismatch", "prepared metadata differs from frozen build identity", "indeterminate") from exc
        super().run()
        # At this point dist/ contains an output artifact, so check HEAD without
        # treating the newly written wheel as an unadmitted source input.
        _check_source()


class VerifiedBuild(build_py):
    def run(self):
        _check_source(require_clean=True)
        super().run()
        write_build_metadata(Path(self.build_lib).resolve(), artifact_kind="wheel",
                             expected_source_commit=BUILD_SOURCE_COMMIT)


setup(cmdclass={"build_py": VerifiedBuild, "dist_info": VerifiedDistInfo, "bdist_wheel": VerifiedWheel})

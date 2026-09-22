"""Build a wheel whose payload is bound to the exact clean source commit."""
from pathlib import Path
import hashlib
import json
import os
import sys
import zipfile

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
    def write_wheelfile(self, wheelfile_base, *args, **kwargs):
        super().write_wheelfile(wheelfile_base, *args, **kwargs)
        # Freeze setuptools' finished distribution output before WheelFile
        # consumes it, for normal builds as well as prepared-metadata hooks.
        folder = Path(wheelfile_base)
        files = _metadata_files(folder)
        identity = folder / DIST_IDENTITY
        if identity.exists():
            if identity.is_symlink() or not identity.is_file():
                raise LocalHandError("provenance_mismatch", "wheel metadata identity is not regular", "indeterminate")
            files[DIST_IDENTITY] = hashlib.sha256(identity.read_bytes()).hexdigest()
        self.verified_distribution = {"prefix": folder.name + "/", "files": files}

    def _verify_output(self, path, prepared_identity):
        """Bind the actual archive, after setuptools copied its verified inputs."""
        built = self.get_finalized_command("build_py").verified_metadata
        metadata_name = "local_hand/_build_metadata.json"
        metadata_bytes = (json.dumps(built, sort_keys=True, indent=2) + "\n").encode("utf-8")
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                payload_names = set(built["files"]) | {metadata_name}
                if len(names) != len(set(names)) or archive.read(metadata_name) != metadata_bytes:
                    raise ValueError("wheel payload differs from its verified build")
                metadata_root = self.verified_distribution["prefix"]
                metadata_names = {metadata_root + name for name in self.verified_distribution["files"]}
                if set(names) != payload_names | metadata_names | {metadata_root + "RECORD"}:
                    raise ValueError("wheel payload differs from its verified build")
                for name, digest in built["files"].items():
                    if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                        raise ValueError("wheel payload differs from its verified build")
                for name, digest in self.verified_distribution["files"].items():
                    if hashlib.sha256(archive.read(metadata_root + name)).hexdigest() != digest:
                        raise ValueError("wheel distribution metadata differs from its verified build")
                if prepared_identity is not None:
                    for name, digest in prepared_identity["files"].items():
                        if hashlib.sha256(archive.read(metadata_root + name)).hexdigest() != digest:
                            raise ValueError("wheel distribution metadata differs from its verified build")
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
            raise LocalHandError("provenance_mismatch", str(exc), "indeterminate") from exc

    def run(self):
        _check_source(require_clean=True)
        if self.skip_build:
            raise LocalHandError("provenance_mismatch", "wheel must verify its source build", "indeterminate")
        prepared_identity = None
        if self.dist_info_dir:
            path = Path(self.dist_info_dir) / DIST_IDENTITY
            try:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("missing metadata identity")
                identity = json.loads(path.read_text(encoding="utf-8"))
                expected = {"source_commit": BUILD_SOURCE_COMMIT, "files": _metadata_files(self.dist_info_dir)}
                if identity != expected:
                    raise ValueError("prepared metadata identity differs")
                prepared_identity = identity
            except (OSError, ValueError) as exc:
                raise LocalHandError("provenance_mismatch", "prepared metadata differs from frozen build identity", "indeterminate") from exc
        previous = len(self.distribution.dist_files)
        super().run()
        # At this point dist/ contains an output artifact, so check HEAD without
        # treating the newly written wheel as an unadmitted source input.
        _check_source()
        outputs = [path for kind, _, path in self.distribution.dist_files[previous:] if kind == "bdist_wheel"]
        if len(outputs) != 1:
            raise LocalHandError("provenance_mismatch", "wheel output identity is unresolved", "indeterminate")
        self._verify_output(outputs[0], prepared_identity)


class VerifiedBuild(build_py):
    def run(self):
        _check_source(require_clean=True)
        super().run()
        self.verified_metadata = write_build_metadata(
            Path(self.build_lib).resolve(), artifact_kind="wheel",
            expected_source_commit=BUILD_SOURCE_COMMIT)


setup(cmdclass={"build_py": VerifiedBuild, "dist_info": VerifiedDistInfo, "bdist_wheel": VerifiedWheel})

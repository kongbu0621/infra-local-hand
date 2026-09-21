"""Build a wheel whose payload is bound to the exact clean source commit."""
from pathlib import Path
import sys

from setuptools import setup
from setuptools.command.build_py import build_py


class VerifiedBuild(build_py):
    def run(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
        from local_hand.provenance import source_commit, write_build_metadata

        source_commit(require_clean=True)
        super().run()
        write_build_metadata(Path(self.build_lib).resolve(), artifact_kind="wheel")


setup(cmdclass={"build_py": VerifiedBuild})

import base64
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from e3_host import q2_core_delivery_loader as loader


def test_loader_decodes_only_canonical_base64_with_exact_digest():
    raw = b"VALUE = 1\n"
    encoded = base64.b64encode(raw).decode("ascii")
    digest = hashlib.sha256(raw).hexdigest()
    assert loader.decode_bootstrap(encoded, digest) == raw
    with pytest.raises(ValueError, match="CORE_LOADER_BASE64"):
        loader.decode_bootstrap(encoded + "\n", digest)
    with pytest.raises(ValueError, match="CORE_LOADER_BASE64"):
        loader.decode_bootstrap(encoded.rstrip("="), digest)
    with pytest.raises(ValueError, match="CORE_LOADER_DIGEST"):
        loader.decode_bootstrap(encoded, "0" * 64)


def test_loader_limit_is_checked_after_decode():
    raw = b"x" * (loader.BOOTSTRAP_LIMIT + 1)
    # The encoded argv ceiling is reached before a decoded blob can exceed the
    # 49152-byte bootstrap ceiling; both bounds are independently retained.
    with pytest.raises(ValueError, match="CORE_LOADER_ARGUMENT"):
        loader.decode_bootstrap(base64.b64encode(raw).decode("ascii"), hashlib.sha256(raw).hexdigest())


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Loader runtime is Linux only")
def test_exact_loader_blob_executes_bootstrap_under_isolated_python():
    source = Path(loader.__file__).read_bytes()
    bootstrap = b'import sys;sys.stdout.write("BOOTSTRAP_EXECUTED")\n'
    result = subprocess.run([
        sys.executable, "-I", "-B", "-c", source.decode("utf-8"),
        base64.b64encode(bootstrap).decode("ascii"), hashlib.sha256(bootstrap).hexdigest()],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        check=False, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b"BOOTSTRAP_EXECUTED"
    assert result.stderr == b""


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Loader runtime is Linux only")
def test_loader_rejects_extra_argument_before_bootstrap_execution():
    source = Path(loader.__file__).read_bytes()
    bootstrap = b'raise AssertionError("must not execute")\n'
    encoded = base64.b64encode(bootstrap).decode("ascii")
    result = subprocess.run([
        sys.executable, "-I", "-B", "-c", source.decode("utf-8"), encoded,
        hashlib.sha256(bootstrap).hexdigest(), "extra"], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        check=False, timeout=10)
    assert result.returncode != 0
    assert b"CORE_LOADER_ARGUMENTS" in result.stderr
    assert b"must not execute" not in result.stderr


def test_loader_blob_stays_inside_approved_argument_limit():
    raw = Path(loader.__file__).read_bytes()
    assert 0 < len(raw) <= 16384
    assert hashlib.sha256(raw).hexdigest() == "9315d0a804df07eab74fd6b1272cf108e81a143c3e535458aa80f403b0b81a36"

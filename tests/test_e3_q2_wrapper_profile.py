"""Finite wrapper compatibility, with synthetic local recorders only.

No private raw is embedded or executed. The real-process comparison deliberately
uses one shared synthetic PATH with a recording ssh stub; it cannot attest the
field environment and never calls capture or a network client.
"""
import builtins
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
import sys

import pytest

from e3_host import q2_host_window_contract as contract
from e3_host import q2_host_window_delivery as d


SOURCE = rb'''#!/usr/bin/env bash
set -euo pipefail
q1_vm=/synthetic/control
exec ssh -F /dev/null \
  -i "$q1_vm/id_ed25519" -p 22022 \
  -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="$q1_vm/known_hosts" \
  -o ConnectTimeout=10 \
  fixture@fixture.invalid "$@"
'''
PROFILE = d.ENV_BASH_LITERAL_SSH_PROFILE
WRAPPER = "/synthetic/wrapper.sh"


@pytest.fixture(autouse=True)
def posix_path_model(monkeypatch):
    # Pure argv construction models the Linux target, including on Windows.
    monkeypatch.setattr(d, "Path", PurePosixPath)


def analyze(raw=SOURCE, **changes):
    values = dict(expected_sha256=hashlib.sha256(raw).hexdigest(),
        wrapper_path=WRAPPER, profile_id=PROFILE)
    values.update(changes)
    return d.analyze_wrapper_profile(raw, **values)


def argv(raw=SOURCE, remote_argv=None, **changes):
    values = dict(expected_sha256=hashlib.sha256(raw).hexdigest(),
        wrapper_path=WRAPPER, remote_argv=["fixed-command"] if remote_argv is None else remote_argv,
        profile_id=PROFILE)
    values.update(changes)
    return d.memory_wrapper_argv(raw, **values)


def test_analysis_is_ram_only_and_does_not_adopt_source(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("no I/O or process creation in profile analysis")
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(os, "stat", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    result = analyze()
    assert result["supported_syntax"] is True
    assert result["source_execution_admitted"] is False
    assert result["source_sha256"] == hashlib.sha256(SOURCE).hexdigest()
    assert result["source_bytes"] == len(SOURCE)
    assert result["local_variables"] == ["q1_vm"]
    assert result["dependency_roles"] == ["env", "bash", "ssh", "identity_file", "known_hosts"]
    assert "/synthetic" not in json.dumps(result)
    constructed = argv()
    assert constructed[:3] == ["/usr/bin/env", "bash", "-c"]
    assert constructed[3].encode() == SOURCE
    assert constructed[4:] == [WRAPPER, "fixed-command"]


def test_default_api_still_rejects_env_bash_and_existing_api_is_unchanged():
    with pytest.raises(ValueError, match="WRAPPER_INTERPRETER_UNSUPPORTED"):
        argv(profile_id=None)
    old = b'#!/bin/sh\nprintf "%s\\n" "$1"\n'
    before = d.memory_wrapper_argv(old, expected_sha256=hashlib.sha256(old).hexdigest(),
        wrapper_path=WRAPPER, remote_argv=["fixed", "two words"])
    assert before == ["/bin/sh", "-c", old.decode(), WRAPPER, "fixed 'two words'"]


@pytest.mark.parametrize("profile", ["", "env-bash", "env-bash-literal-ssh-v2", False, [], {}])
def test_profile_is_explicit_and_cannot_select_an_unknown_language(profile):
    with pytest.raises(ValueError, match="WRAPPER_PROFILE_UNSUPPORTED"):
        argv(profile_id=profile)


@pytest.mark.parametrize("old,new", [
    (b"#!/usr/bin/env bash", b"#!/usr/bin/env -S bash -e"),
    (b"set -euo pipefail", b"set -eu"),
    (b"q1_vm=/synthetic/control", b"PATH=/synthetic/control"),
    (b"q1_vm=/synthetic/control", b"BASH_ENV=/synthetic/control"),
    (b"q1_vm=/synthetic/control", b"q1_vm=$(touch /synthetic/injected)"),
    (b"q1_vm=/synthetic/control", b"q1_vm=/synthetic/`id`"),
    (b"q1_vm=/synthetic/control", b"q1_vm=/synthetic/$((1+1))"),
    (b"q1_vm=/synthetic/control", b"q1_vm=<(id)"),
    (b"q1_vm=/synthetic/control", b"q1_vm=$HOME/control"),
    (b"q1_vm=/synthetic/control", b"q1_vm='/synthetic/control'"),
    (b"q1_vm=/synthetic/control", b"q1_vm=/synthetic/control\nq1_vm=/other"),
    (b"exec ssh", b"echo prelude\nexec ssh"),
    (b"exec ssh", b"exec /usr/bin/ssh"),
    (b"-F /dev/null", b"-F /synthetic/config"),
    (b"StrictHostKeyChecking=accept-new", b"StrictHostKeyChecking=no"),
    (b'"$q1_vm/id_ed25519"', b'$q1_vm/id_ed25519'),
    (b'"$q1_vm/id_ed25519"', b'"${!q1_vm}"'),
    (b'"$q1_vm/id_ed25519"', b'"$0"'),
    (b'"$q1_vm/id_ed25519"', b'"${BASH_SOURCE[0]}"'),
    (b'"$@"', b'"$*"'),
    (b'"$@"', b'$@'),
    (b'"$@"', b'"$@" </synthetic/input'),
    (b'"$@"', b'"$@"; id'),
    (b'"$@"', b'"$@" &'),
    (b"fixture@fixture.invalid", b"fixture@$(id)"),
    (b"fixture@fixture.invalid", b"-oProxyCommand=bad@fixture.invalid"),
    (b"\n", b"\r\n"),
])
def test_full_language_rejects_injection_or_semantic_changes(old, new):
    changed = SOURCE.replace(old, new)
    assert changed != SOURCE
    with pytest.raises(ValueError, match="WRAPPER_PROFILE_(SOURCE|LITERAL)_UNSUPPORTED"):
        argv(changed)


@pytest.mark.parametrize("suffix", [b"\n", b"# comment\n", b"id\n", b"\0"])
def test_no_unexamined_tail(suffix):
    with pytest.raises(ValueError, match="WRAPPER_PROFILE_SOURCE_UNSUPPORTED"):
        analyze(SOURCE + suffix)


@pytest.mark.parametrize("value", [b"//synthetic/control", b"/synthetic//control",
    b"/synthetic/./control", b"/synthetic/../control", b"/synthetic/control/", b"/"])
def test_literal_directory_is_canonical(value):
    with pytest.raises(ValueError, match="WRAPPER_PROFILE_(SOURCE|LITERAL)_UNSUPPORTED"):
        analyze(SOURCE.replace(b"/synthetic/control", value))


@pytest.mark.parametrize("value", [b"0", b"022022", b"65536", b"999999", b"-1"])
def test_port_range_is_not_silently_reinterpreted(value):
    with pytest.raises(ValueError, match="WRAPPER_PROFILE_(SOURCE|LITERAL)_UNSUPPORTED"):
        analyze(SOURCE.replace(b"22022", value))


@pytest.mark.parametrize("value", [b"1", b"65535"])
def test_literal_port_boundaries_are_supported_without_rewriting(value):
    source = SOURCE.replace(b"22022", value)
    assert argv(source)[3].encode() == source


@pytest.mark.parametrize("remote", [[], [""], ["x"] * 65, ["x" * 65537], ["a\0b"], [b"x"], "command"])
def test_existing_remote_argument_bounds_remain(remote):
    with pytest.raises(ValueError, match="HOST_WINDOW_REMOTE_ARGV"):
        argv(remote_argv=remote)


def test_source_integrity_encoding_and_limits_still_apply():
    with pytest.raises(ValueError, match="WRAPPER_DIGEST"):
        analyze(expected_sha256="0" * 64)
    with pytest.raises(ValueError, match="WRAPPER_DIGEST"):
        analyze(b"x" * (1024**2 + 1))
    with pytest.raises(ValueError, match="WRAPPER_ENCODING"):
        analyze(SOURCE + b"\xff")
    with pytest.raises(ValueError, match="WRAPPER_REMOTE_ENCODING"):
        argv(remote_argv=["bad\ud800"])


@pytest.mark.parametrize("path", ["relative", "/", "//synthetic/wrapper", "/a/../b", "/a/./b", "/a\0b"])
def test_profile_wrapper_identity_is_lexical_and_canonical(path):
    with pytest.raises(ValueError, match="WRAPPER_PATH"):
        analyze(wrapper_path=path)


def test_profile_success_cannot_clear_field_or_remote_deadline_gates(monkeypatch):
    result = analyze()
    with pytest.raises(ValueError, match="FIELD_READINESS_UNPROVEN"):
        contract.require_field_readiness(result)
    def forbidden(*args, **kwargs):
        raise AssertionError("syntax support cannot spawn")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    boot = "12345678-1234-1234-1234-123456789abc"
    window = d.base.Window(monotonic=lambda: 100 * d.NS, boottime=lambda: 100 * d.NS)
    with pytest.raises(ValueError, match="EXISTING_REMOTE_HARD_DEADLINE_UNPROVEN"):
        d.dispatch_original(argv(), b"pass", retained_anchors=[], host_boot_id=boot,
            guest_boot_id=boot, window=window, until_ns=window.deadline_ns, on_stdout_line=forbidden)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux synthetic env/Bash process comparison")
def test_synthetic_script_and_memory_argv_match_without_reopening_source(tmp_path):
    bash = shutil.which("bash", path="/usr/bin:/bin")
    if bash is None or not Path("/usr/bin/env").is_file():
        pytest.skip("requires existing env and Bash; no tool installation")
    stub_dir = tmp_path / "tools"
    stub_dir.mkdir()
    # Both program names used by the wrapper resolve into this isolated fixture.
    (stub_dir / "bash").symlink_to(bash)
    stub = stub_dir / "ssh"
    stub.write_text(f"#!{sys.executable}\n" +
        "import json,os,sys\n" +
        "print(json.dumps({'argv':sys.argv[1:],'stdin':sys.stdin.buffer.read().hex(),"
        "'cwd':os.getcwd(),'HOME':os.environ.get('HOME'),'local_exported':os.environ.get('q1_vm')}))\n")
    stub.chmod(0o700)
    script = tmp_path / "synthetic-wrapper.sh"
    script.write_bytes(SOURCE)
    script.chmod(0o700)
    env = d.controlled_environment({"HOME": "/synthetic/home", "BASH_ENV": "/bad", "PATH": "/bad"})
    env["PATH"] = str(stub_dir)  # Shared synthetic environment, never field proof.
    remote = ["fixed-command", "two words", "'quoted'", "$(touch should-not-exist)", ";false", "line\nnext"]
    command = shlex.join(remote)
    stdin = b"unchanged transport input\x00\n"
    direct = subprocess.run([str(script), command], input=stdin, capture_output=True,
        env=env, cwd=tmp_path, timeout=5, check=True)
    constructed = argv(wrapper_path=str(script), remote_argv=remote)
    # Replace the original name with a failing script; it must not be reopened.
    script.write_bytes(b"#!/bin/sh\nexit 99\n")
    before = script.stat()
    adapted = subprocess.run(constructed, input=stdin, capture_output=True,
        env=env, cwd=tmp_path, timeout=5, check=True)
    after = script.stat()
    assert after == before
    assert direct.stderr == adapted.stderr == b""
    assert direct.stdout == adapted.stdout
    recorded = json.loads(adapted.stdout)
    assert recorded["argv"] == ["-F", "/dev/null", "-i", "/synthetic/control/id_ed25519", "-p", "22022",
        "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "UserKnownHostsFile=/synthetic/control/known_hosts", "-o", "ConnectTimeout=10",
        "fixture@fixture.invalid", command]
    assert shlex.split(recorded["argv"][-1]) == remote
    assert recorded["stdin"] == stdin.hex()
    assert recorded["cwd"] == str(tmp_path)
    assert recorded["HOME"] == "/synthetic/home"
    assert recorded["local_exported"] is None
    assert not (tmp_path / "should-not-exist").exists()

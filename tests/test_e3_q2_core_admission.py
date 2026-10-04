"""Policy component tests using temporary files and real bounded child processes.

These do not contact the guest or stand in for live admission/capacity evidence.
"""
from __future__ import annotations

import base64
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux held-fd and wait4 policy collectors", allow_module_level=True)

PATH = Path(__file__).parent / "e3_host" / "q2_core_delivery_dispatcher.py"
spec = importlib.util.spec_from_file_location("_core_admit_test", PATH)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
GRANT = dict(commands=["ALL"], host="ALL", runas_groups=[], runas_users=["ALL"], tags=["NOPASSWD"])
SUDO = b'''Matching Defaults entries for q1admin on local-hand-q1:
    env_reset, mail_badpass

User q1admin may run the following commands on local-hand-q1:

Sudoers entry:
    RunAsUsers: ALL
    RunAsGroups: ALL
    Commands:
        ALL

Sudoers entry:
    RunAsUsers: ALL
    Options: !authenticate
    Commands:
        ALL
'''


def test_sudo_requires_exact_nopasswd_without_explicit_groups():
    grants = d._admit_sudo_output(SUDO, GRANT)
    assert grants[1] == GRANT
    assert grants[0]["runas_groups"] == ["ALL"]
    with pytest.raises(d.DispatchError, match="SUDO_GRANT"):
        d._admit_sudo_output(SUDO.replace(b"    Options: !authenticate", b"    RunAsGroups: ALL\n    Options: !authenticate"), GRANT)


@pytest.mark.parametrize("change", [
    (b"!authenticate", b"authenticate"),
    (b"    Options: !authenticate", b"    Unknown: !authenticate"),
    (b"        ALL", b"        /bin/true"),
    (b"q1admin on", b"other on"),
])
def test_sudo_unknown_or_restricted_output_stops(change):
    with pytest.raises(d.DispatchError):
        d._admit_sudo_output(SUDO.replace(*change), GRANT)


def test_sudo_source_host_relation_and_plugin_are_not_guessed():
    source = {"/etc/sudo.conf": b"# system defaults\n", "/etc/sudoers": b"Defaults env_reset\nroot ALL=(ALL:ALL) ALL\n@includedir /etc/sudoers.d\n",
              "/etc/sudoers.d/90-cloud-init-users": b"q1admin ALL=(ALL) NOPASSWD:ALL\n"}
    assert d._admit_sudo_source(source, "q1admin ALL=(ALL) NOPASSWD:ALL") == 1
    with pytest.raises(d.DispatchError, match="PLUGIN"):
        d._admit_sudo_source({**source, "/etc/sudo.conf": b"Plugin custom /tmp/plugin.so\n"}, "q1admin ALL=(ALL) NOPASSWD:ALL")
    with pytest.raises(d.DispatchError, match="INCLUDE"):
        d._admit_sudo_source({**source, "/etc/sudoers.d/90-cloud-init-users": b"@include /other\n"}, "q1admin ALL=(ALL) NOPASSWD:ALL")


def test_sshd_source_effective_both_required():
    d._admit_sshd_source({"/etc/ssh/sshd_config": b"Include /etc/ssh/sshd_config.d/*.conf\nPubkeyAuthentication yes\n"})
    required = dict(authorizedkeyscommand="none", authorizedkeysfile=[".ssh/authorized_keys", ".ssh/authorized_keys2"],
                    forcecommand="none", permituserenvironment="no", pubkeyauthentication="yes")
    raw = b"\n".join((key + " " + (" ".join(value) if type(value) is list else value)).encode() for key, value in required.items())
    assert d._admit_sshd_output(raw, required) == required
    with pytest.raises(d.DispatchError, match="PREDICATE"):
        d._admit_sshd_output(raw.replace(b"forcecommand none", b"forcecommand /bin/x"), required)
    with pytest.raises(d.DispatchError, match="MATCH"):
        d._admit_sshd_source({"/etc/ssh/sshd_config": b"Match User q1admin\n"})
    with pytest.raises(d.DispatchError, match="INCLUDE"):
        d._admit_sshd_source({"/etc/ssh/sshd_config": b"Include /tmp/*.conf\n"})


def test_single_key_exact_bytes_and_no_options():
    key = base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0 " + b"x" * 32).decode()
    approved = dict(type="ssh-ed25519", key_base64=key)
    raw = ("# comment\n\nssh-ed25519 " + key + " label\n").encode()
    result = d._admit_authorized(raw, "/home/q1admin/.ssh/authorized_keys", approved)
    assert result[0]["line_number"] == 3 and result[0]["options"] == []
    for bad in (b'command="/bin/true" ' + raw.splitlines()[-1], raw + raw,
                raw.replace(b"ssh-ed25519", b"ssh-rsa")):
        with pytest.raises(d.DispatchError):
            d._admit_authorized(bad, "/home/q1admin/.ssh/authorized_keys", approved)


@pytest.mark.parametrize("prefix", [b"X=1\n", b"echo hello\n", b"trap true EXIT\n", b"source /tmp/x\n", b"\\\n"])
def test_bashrc_only_accepts_first_executable_guard(prefix):
    guard = b"# Ubuntu default\ncase $- in\n    *i*) ;;\n      *) return;;\nesac\nexport AFTER=yes\n"
    assert d._admit_bashrc(guard)
    with pytest.raises(d.DispatchError, match="BASHRC_GUARD"):
        d._admit_bashrc(prefix + guard)


@pytest.fixture
def held_reader(tmp_path, monkeypatch):
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    reader = d._admit_reader(lambda: None, "/unit", os.getuid())
    monkeypatch.setattr(reader, "parent", lambda path: (fd, Path(path).name))
    try:
        yield reader, tmp_path
    finally:
        reader.close()
        os.close(fd)


def test_held_reader_real_inode_replacement_and_appearing_absence(held_reader):
    reader, root = held_reader
    file = root / "policy"
    file.write_bytes(b"source\n"); file.chmod(0o600)
    assert reader.read("/unit/policy") == b"source\n"
    file.rename(root / "old")
    file.write_bytes(b"source\n"); file.chmod(0o600)
    with pytest.raises(d.DispatchError, match="DRIFT"):
        reader.recheck()


def test_held_reader_absence_rechecked(held_reader):
    reader, root = held_reader
    assert reader.read("/unit/missing", required=False) is None
    (root / "missing").write_bytes(b"new")
    with pytest.raises(d.DispatchError, match="DRIFT"):
        reader.recheck()


@pytest.mark.parametrize("kind", ["symlink", "fifo", "hardlink", "world-write"])
def test_held_reader_rejects_unsafe_before_open(held_reader, kind):
    reader, root = held_reader
    path = root / "policy"
    if kind == "fifo":
        os.mkfifo(path)
    else:
        path.write_bytes(b"policy"); path.chmod(0o600)
        if kind == "symlink":
            path.rename(root / "original"); path.symlink_to(root / "original")
        elif kind == "hardlink":
            os.link(path, root / "other")
        else:
            path.chmod(0o666)
    with pytest.raises(d.DispatchError, match="PROTECTION"):
        reader.read("/unit/policy")


def test_parent_walk_rejects_real_world_writable_ancestor(tmp_path):
    if os.geteuid() != 0:
        pytest.skip("field root-directory O_NOATIME requires root")
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(); unsafe.chmod(0o777)
    reader = d._admit_reader(lambda: None, str(tmp_path), os.getuid())
    try:
        with pytest.raises(d.DispatchError, match="PROTECTION"):
            reader.read(str(unsafe / "missing"), required=False)
    finally:
        reader.close()


def helper_fixture(monkeypatch, script, *, seconds=5, output=65536):
    real_popen = subprocess.Popen
    calls = []
    def launch(argv, **kwargs):
        calls.append((argv, kwargs.copy()))
        # Substitute only the component-test executable; child I/O and wait4
        # are real, while the production fixed sudo command is never run.
        return real_popen([sys.executable, "-I", "-c", script], **kwargs)
    monkeypatch.setattr(d.subprocess, "Popen", launch)
    end = time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 10 * d.NS
    effects = SimpleNamespace(_effect_guard=lambda: None,
        context={"guest_deadlines": {}}, _admit_helper_usage=[])
    def stop_guard(*args):
        if time.clock_gettime_ns(time.CLOCK_BOOTTIME) >= end:
            raise d.DispatchError("TEST_STOP_LIMIT")
    monkeypatch.setattr(d, "_clock", stop_guard)
    policy = dict(argv=["/usr/bin/sudo", "-n", "-ll", "-U", "q1admin"],
        environment={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"},
        limits=dict(command_seconds=seconds, command_cpu_seconds=2,
                    stdout_bytes=output, stderr_bytes=output, combined_output_bytes=output))
    return effects, policy, calls


def test_real_helper_wait4_two_eof_fixed_invocation_and_no_retry(monkeypatch):
    effects, policy, calls = helper_fixture(monkeypatch, "import os; os.write(1,b'ok'); os.write(2,b'note')")
    checks = []
    stdout, stderr, facts = d._admit_helper(effects, policy, lambda: checks.append(True))
    assert (stdout, stderr) == (b"ok", b"note")
    assert facts["stdout_eof"] and facts["stderr_eof"] and facts["exit_status"] == 0
    assert facts["combined_bytes"] == 6 and facts["finished_boottime_ns"] >= facts["started_boottime_ns"]
    usage = effects._admit_helper_usage[0]
    assert usage["wait4"]["max_rss_bytes"] > 0 and usage["eof"] == ["stderr", "stdout"]
    assert calls[0][1]["shell"] is False and calls[0][1]["cwd"] == "/" and len(checks) == 2
    with pytest.raises(d.DispatchError, match="REPLAY"):
        d._admit_helper(effects, policy, lambda: None)
    assert len(calls) == 1


@pytest.mark.parametrize("script,seconds,output,reason", [
    ("import os; os.write(1,b'x'*65536); os.write(2,b'y'*65536)", 5, 128, "OUTPUT_LIMIT"),
    ("import time; time.sleep(5)", 0.04, 65536, "TIMEOUT"),
    ("raise SystemExit(7)", 5, 65536, "EXIT"),
])
def test_real_helper_failure_kills_reaps_and_keeps_no_success(monkeypatch, script, seconds, output, reason):
    effects, policy, _ = helper_fixture(monkeypatch, script, seconds=seconds, output=output)
    with pytest.raises(d.DispatchError, match=reason):
        d._admit_helper(effects, policy, lambda: None)
    usage = effects._admit_helper_usage[0]
    assert usage["wait4"] is not None and usage["eof"] == ["stderr", "stdout"]
    assert usage["failure"] and usage["cleanup_failure"] is None


@pytest.mark.parametrize("key,value", [
    ("stage", "PRE_ENTRY"), ("pre_entry_containment", True), ("matched", False),
    ("policy_basis_sha256", "0" * 64), ("predicate_sha256", "0" * 64),
    ("snapshot_sha256", "0" * 64), ("facts_sha256", "not-a-digest"),
])
def test_public_admission_requires_exact_policy_binding(key, value):
    import test_e3_q2_core_delivery_dispatcher as fixture
    context = fixture.context()
    admission = fixture.FakeEffects(context).admit({})
    admission["policies"]["sudo"]["relation"][key] = value
    with pytest.raises(fixture.d.DispatchError, match="POLICY_RELATION"):
        fixture.d._validate_admission(admission, context)


def test_real_program_identity_cannot_adopt_another_digest():
    if os.geteuid() != 0:
        pytest.skip("O_NOATIME current root-owned executable requires root")
    reader = d._admit_reader(lambda: None, "/home/q1admin", 1000)
    try:
        value = d._admit_program(reader, "/usr/bin/true")
        assert value["resolved_path"] == "/usr/bin/true" and value["bytes"] > 0
    finally:
        reader.close()
    other = d._admit_reader(lambda: None, "/home/q1admin", 1000)
    try:
        with pytest.raises(d.DispatchError, match="PROGRAM_BINDING"):
            d._admit_program(other, "/usr/bin/true", {**value, "sha256": "0" * 64})
    finally:
        other.close()

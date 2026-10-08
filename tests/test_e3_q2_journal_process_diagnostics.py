"""Process failures identify the captured observation without disclosing its values."""
from __future__ import annotations

import hashlib
import os
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux guest inventory helper", allow_module_level=True)

from e3_host import q2_journal_growth_guest as g


PID = 712
START = 845621
ROOT = "/fixture/private-business"
SAFE = "/fixture/unrelated"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def stat_bytes(start=START):
    return f"{PID} (synthetic ) name) S ".encode() + b"0 " * 18 + f"{start} 0\n".encode()


@pytest.fixture
def proc_inventory(monkeypatch):
    """Run the original loop against bounded in-memory procfs observations only."""
    def make(*, cmdline=b"/usr/bin/fixture\0", exe=SAFE + "/bin", cwd=SAFE,
             self_pid=1, fd_target=None, fd_flags=b"0100000", maps=b"",
             missing=None, roots=None):
        calls = []
        values = {"stat": stat_bytes(), "cmdline": cmdline,
                  "cgroup": b"0::/fixture.slice\n", "maps": maps,
                  "fdinfo/8": b"flags:\t" + fd_flags + b"\n"}
        prefix = f"/proc/{PID}"

        def check():
            pass

        def read_kernel(path, cap, guard, *, expected_fs):
            assert guard is check and expected_fs == 0x9FA0
            assert path.startswith(prefix + "/")
            key = path[len(prefix) + 1:]
            calls.append(("read", key, cap))
            if key == missing:
                raise FileNotFoundError(path)
            raw = values[key]
            assert len(raw) <= cap
            return raw

        def listdir(path):
            assert path == "/proc"
            calls.append(("list", path))
            return ["not-a-pid", str(PID)]

        def readlink(path, *, dir_fd=None):
            if dir_fd is not None:
                assert dir_fd == 900 and path == "8" and fd_target is not None
                calls.append(("link", "fd/8"))
                return fd_target
            assert path in (prefix + "/exe", prefix + "/cwd")
            key = path.rsplit("/", 1)[1]
            calls.append(("link", key))
            if key == missing:
                raise FileNotFoundError(path)
            return exe if key == "exe" else cwd

        def open_fd(path, flags):
            assert path == prefix + "/fd"
            assert flags == os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
            calls.append(("open", "fd"))
            return 900

        class Entries:
            def __enter__(self):
                return iter([SimpleNamespace(name="8")] if fd_target is not None else [])

            def __exit__(self, *_):
                return False

        def scandir(fd):
            assert fd == 900
            calls.append(("scan", "fd"))
            return Entries()

        def close(fd):
            assert fd == 900
            calls.append(("close", "fd"))

        synthetic_os = SimpleNamespace(**{key: getattr(os, key) for key in
            ("O_RDONLY", "O_DIRECTORY", "O_CLOEXEC", "O_NOFOLLOW", "O_ACCMODE", "fsdecode", "fsencode")})
        synthetic_os.listdir = listdir
        synthetic_os.getpid = lambda: self_pid
        synthetic_os.readlink = readlink
        synthetic_os.open = open_fd
        synthetic_os.scandir = scandir
        synthetic_os.close = close
        monkeypatch.setattr(g, "os", synthetic_os)
        monkeypatch.setattr(g, "read_kernel", read_kernel)
        monkeypatch.setattr(g.r, "filesystem_type", lambda fd: 0x9FA0 if fd == 900 else None)
        inventory = object.__new__(g.GuestInventory)
        inventory.roots = roots or ["/fixture/a-unused", ROOT]
        inventory.check = check
        inventory.context = dict(manager="user_1100", unit="previous-private.slice")
        return inventory, calls, values

    return make


@pytest.mark.parametrize("field,value", [
    ("cmdline", b"/usr/bin/fixture\0--source=" + ROOT.encode() + b"/secret\0"),
    ("exe", (ROOT + "/private-bin").encode()),
    ("exe", (ROOT + "/private-bin (deleted)").encode()),
    ("cwd", ROOT.encode()),
])
def test_failure_binds_current_process_and_field_without_more_reads(proc_inventory, field, value):
    args = {field: value if field == "cmdline" else os.fsdecode(value)}
    inventory, calls, _ = proc_inventory(**args)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_BUSINESS_PROCESS$"):
        inventory.processes()
    context = inventory.context
    assert context["operation"] == "process_inventory"
    assert context["pid"] == PID and context["observer_pid"] == 1
    assert context["start_ticks"] == START and context["identity_rechecked"] is False
    assert context["field"] == field
    assert context["cgroup_sha256"] == sha(b"0::/fixture.slice\n")
    assert not {"manager", "unit", "command_index", "arguments_sha256"} & context.keys()
    diagnostic = context["process_reference_diagnostic"]
    assert diagnostic["field"] == field
    assert diagnostic["comparison"] == ("byte_substring" if field == "cmdline" else "path_under_root")
    assert diagnostic["root_index"] == 2
    assert diagnostic["root_bytes"] == len(ROOT.encode())
    assert diagnostic["root_sha256"] == sha(ROOT.encode())
    assert diagnostic["value_bytes"] == len(value) and diagnostic["value_sha256"] == sha(value)
    assert diagnostic["byte_offset"] == value.index(ROOT.encode())
    assert diagnostic["deleted_suffix_removed"] is (field != "cmdline" and value.endswith(b" (deleted)"))
    if field == "cmdline":
        argument = value.split(b"\0")[1]
        assert diagnostic["argument_index"] == 1
        assert diagnostic["argument_byte_offset"] == len(b"--source=")
        assert diagnostic["argument_bytes"] == len(argument)
        assert diagnostic["argument_sha256"] == sha(argument)
        assert diagnostic["match_at_argument_start"] is False
        assert diagnostic["match_followed_by"] == "slash"
    else:
        assert all(diagnostic[key] is None for key in (
            "argument_index", "argument_byte_offset", "argument_bytes", "argument_sha256",
            "match_at_argument_start", "match_followed_by"))
    encoded = g.canonical(context)
    for private in (ROOT.encode(), value, b"private-bin", b"--source=", b"secret", b"previous-private"):
        assert private not in encoded
    expected = [("list", "/proc"), ("read", "stat", 4096),
                ("read", "cmdline", 65536), ("read", "cgroup", 4096)]
    if field != "cmdline":
        expected.append(("link", "exe"))
    if field == "cwd":
        expected.append(("link", "cwd"))
    assert calls == expected


@pytest.mark.parametrize("argument,suffix,start", [
    (ROOT.encode(), "argument_end", True),
    (ROOT.encode() + b"/item", "slash", True),
    (ROOT.encode() + b"-other", "other", True),
    (b"--root=" + ROOT.encode() + b"-other", "other", False),
])
def test_cmdline_boundary_diagnostic_keeps_substring_rejection(proc_inventory, argument, suffix, start):
    inventory, calls, _ = proc_inventory(cmdline=b"/usr/bin/fixture\0" + argument + b"\0")
    with pytest.raises(g.r.ObservationError, match="^GROWTH_BUSINESS_PROCESS$"):
        inventory.processes()
    diagnostic = inventory.context["process_reference_diagnostic"]
    assert diagnostic["argument_index"] == 1
    assert diagnostic["argument_sha256"] == sha(argument)
    assert diagnostic["argument_byte_offset"] == argument.index(ROOT.encode())
    assert diagnostic["match_at_argument_start"] is start
    assert diagnostic["match_followed_by"] == suffix
    assert len(calls) == 4


def test_diagnostic_error_cannot_replace_original_rejection(proc_inventory):
    inventory, calls, _ = proc_inventory(cmdline=ROOT.encode() + b"\0")

    def unavailable(*_):
        raise ValueError("synthetic diagnostic failure")

    inventory._process_reference_diagnostic = unavailable
    with pytest.raises(g.r.ObservationError, match="^GROWTH_BUSINESS_PROCESS$"):
        inventory.processes()
    assert inventory.context["process_reference_diagnostic"] == {"status": "UNAVAILABLE"}
    assert len(calls) == 4


def test_proc_listing_failure_clears_previous_domain_context(proc_inventory):
    inventory, _, _ = proc_inventory()
    error = PermissionError("synthetic proc listing failure")

    def unavailable(_):
        raise error

    g.os.listdir = unavailable
    with pytest.raises(PermissionError) as observed:
        inventory.processes()
    assert observed.value is error
    assert inventory.context["operation"] == "process_inventory"
    assert "manager" not in inventory.context and "unit" not in inventory.context
    assert "process_reference_diagnostic" not in inventory.context


@pytest.mark.parametrize("cmdline,exe,cwd", [
    (b"/usr/bin/fixture\0", ROOT + "-other/bin", ROOT + "-other"),
    (b"/usr/bin/fixture\0/fixture/private-\0business\0", SAFE + "/bin", SAFE),
])
def test_nonmatching_observations_keep_original_success_and_reads(proc_inventory, cmdline, exe, cwd):
    inventory, calls, _ = proc_inventory(cmdline=cmdline, exe=exe, cwd=cwd)
    result = inventory.processes()
    rows = [dict(pid=PID, start=START, cgroup_sha256=sha(b"0::/fixture.slice\n"))]
    assert result == dict(processes=1, fd_count=0, sha256=sha(g.canonical(rows)))
    assert inventory.context == {}
    assert calls == [
        ("list", "/proc"), ("read", "stat", 4096), ("read", "cmdline", 65536),
        ("read", "cgroup", 4096), ("link", "exe"), ("link", "cwd"),
        ("open", "fd"), ("scan", "fd"), ("close", "fd"),
        ("read", "maps", 1048576), ("read", "stat", 4096), ("list", "/proc"),
    ]


@pytest.mark.parametrize("missing,reason", [
    ("stat", "GROWTH_PROCESS_INVENTORY_DRIFT"),
    ("exe", "GROWTH_PROCESS_LINK_UNKNOWN"),
    ("cwd", "GROWTH_PROCESS_LINK_UNKNOWN"),
])
def test_missing_observation_keeps_original_failure(proc_inventory, missing, reason):
    inventory, _, _ = proc_inventory(missing=missing)
    with pytest.raises(g.r.ObservationError, match="^" + reason + "$"):
        inventory.processes()
    assert inventory.context["operation"] == "process_inventory"
    assert inventory.context["pid"] == PID and inventory.context["field"] == missing
    assert inventory.context["start_ticks"] == (None if missing == "stat" else START)
    assert "manager" not in inventory.context and "unit" not in inventory.context
    assert "process_reference_diagnostic" not in inventory.context


def test_self_exemption_still_checks_and_rejects_writable_protected_fd(proc_inventory):
    inventory, calls, _ = proc_inventory(self_pid=PID, cmdline=ROOT.encode() + b"\0",
                                       fd_target=ROOT + "/private-output", fd_flags=b"0100002")
    with pytest.raises(g.r.ObservationError, match="^GROWTH_UNKNOWN_WRITER$"):
        inventory.processes()
    assert ("link", "exe") not in calls and ("link", "cwd") not in calls
    assert calls[-2:] == [("read", "fdinfo/8", 4096), ("close", "fd")]


def test_shared_writable_mapping_remains_rejected(proc_inventory):
    line = b"1000-2000 rw-s 00000000 00:00 1 " + ROOT.encode() + b"/private-map\n"
    inventory, calls, _ = proc_inventory(maps=line)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_MAPPED_WRITER$"):
        inventory.processes()
    assert calls[-1] == ("read", "maps", 1048576)

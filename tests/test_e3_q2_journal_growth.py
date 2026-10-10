"""J2 synthetic fixtures only. Never reads or modifies the original VM."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import time

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only fd, process and image maintenance", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g


@pytest.fixture
def store(tmp_path):
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOATIME)
    value = h.Store(fd, lambda: None)
    yield value
    value.close()
    os.close(fd)


@pytest.mark.parametrize("failed", h.STATES[1:])
def test_every_step_failure_is_terminal(failed):
    events = []
    sequence = h.Sequence(lambda: None, events.append)
    for state in h.STATES[1:]:
        if state == failed:
            with pytest.raises(RuntimeError, match="injected"):
                sequence.step(state, lambda: (_ for _ in ()).throw(RuntimeError("injected")))
            assert sequence.state == "STOP_AND_RETAIN"
            with pytest.raises(h.prior.r.ObservationError):
                sequence.step(state, lambda: pytest.fail("replay"))
            break
        sequence.step(state, lambda: {"test_only": True})
    assert events[-1] == {"step": failed, "state": "STARTED"}


def test_state_order_and_event_failure():
    sequence = h.Sequence(lambda: None, lambda _: (_ for _ in ()).throw(OSError("fsync")))
    with pytest.raises(h.prior.r.ObservationError):
        sequence.step("IMAGE_GROWN", lambda: pytest.fail("skipped backup"))
    with pytest.raises(OSError):
        sequence.step("CONSUMED", lambda: pytest.fail("event failed"))
    assert sequence.state == "STOP_AND_RETAIN"


def test_window_dual_clocks_and_mutation_cutoff():
    now = [0]
    w = h.Window(clock=lambda _: now[0])
    assert w.remaining() == 1800
    now[0] = 1560 * 10**9
    with pytest.raises(h.local.CaptureError, match="DEADLINE"):
        w.change()
    assert w.remaining() == 240
    now[0] = 1800 * 10**9
    with pytest.raises(h.local.CaptureError, match="DEADLINE"):
        w.check()


def test_preflight_and_execute_share_original_clock_and_host_boot(monkeypatch):
    now = [20 * 10**9]
    monkeypatch.setattr(g, "host_boot_id", lambda check, report: "11111111-2222-3333-4444-555555555555")
    first = h.Window(clock=lambda _: now[0])
    saved = g.bind_window(first)
    now[0] += 100 * 10**9
    second = h.Window(clock=lambda _: now[0])
    assert g.bind_window(second, h.canonical(saved)) == saved
    assert second.remaining() == 1700 and second.origins == first.origins
    now[0] += 1700 * 10**9
    with pytest.raises(h.local.CaptureError, match="DEADLINE"):
        g.bind_window(h.Window(clock=lambda _: now[0]), h.canonical(saved))


def test_boot_permission_error_is_precise_without_weaker_retry(monkeypatch):
    calls = []
    def denied(path, flags):
        calls.append((path, flags))
        raise PermissionError(1, "private text must not be disclosed", path)
    monkeypatch.setattr(g.os, "open", denied)
    with pytest.raises(g.r.ObservationError, match="^GROWTH_KERNEL_OPEN$") as caught:
        g.boot_id(lambda: None)
    assert caught.value.diagnostic == dict(operation="open_kernel", target="boot", errno=1)
    assert len(calls) == 1
    assert calls[0][0] == "/proc/sys/kernel/random/boot_id"
    assert calls[0][1] & os.O_NOATIME and calls[0][1] & os.O_NOFOLLOW


@pytest.mark.parametrize("kind", ["future", "reboot", "malformed"])
def test_invalid_window_binding_never_starts_a_new_window(monkeypatch, kind):
    current = "11111111-2222-3333-4444-555555555555"
    monkeypatch.setattr(g, "host_boot_id", lambda check, report: current)
    value = {"boot_id": current, "origins": [100, 100]}
    if kind == "future": value["origins"] = [101, 101]
    elif kind == "reboot": value["boot_id"] = "22222222-3333-4444-5555-666666666666"
    else: value["origins"] = [True, 100]
    with pytest.raises((h.local.CaptureError, g.r.ObservationError)):
        g.bind_window(h.Window(clock=lambda _: 100), h.canonical(value))


@pytest.mark.parametrize("suffix", h.SUFFIXES)
def test_existing_any_output_blocks(store, suffix):
    store.create(suffix)
    with pytest.raises(h.prior.r.ObservationError, match="OUTPUT_EXISTS"):
        store.absent()


def test_create_only_and_partial_consumption(store):
    store.put("consumed.json", b'{"partial":')
    another = h.Store(store.fd, lambda: None)
    try:
        with pytest.raises(FileExistsError):
            another.create("consumed.json")
    finally:
        another.close()
    assert os.fstat(store.opened["consumed.json"]).st_size == 11


def test_fsync_failure_does_not_delete_marker(store, monkeypatch):
    monkeypatch.setattr(os, "fsync", lambda _: (_ for _ in ()).throw(OSError("injected fsync")))
    with pytest.raises(OSError):
        store.put("consumed.json", b"{}")
    assert os.stat(h.NAMES["consumed.json"], dir_fd=store.fd).st_size == 0


def test_capture_limit_and_alias(store, tmp_path):
    with pytest.raises(h.prior.r.ObservationError, match="OUTPUT_LIMIT"):
        store.put("pre.stdout", b"a" * (2 * h.MIB + 1))
    with pytest.raises(h.prior.r.ObservationError, match="OUTPUT_NAME"):
        store.create("../elsewhere")
    other = tmp_path / "other"
    other.write_bytes(b"untouched")
    (tmp_path / h.NAMES["consumed.json"]).symlink_to(other)
    with pytest.raises(FileExistsError):
        store.create("consumed.json")
    assert other.read_bytes() == b"untouched"


def test_full_copy_and_reread_hash(store, tmp_path):
    source = tmp_path / "synthetic.qcow2"
    source.write_bytes(b"synthetic-original" * 10000)
    source.chmod(0o600)
    fd = os.open(source, os.O_RDONLY | os.O_NOATIME)
    try:
        result = h.full_backup(store, fd)
    finally:
        os.close(fd)
    assert result["sha256"] == h.digest(source.read_bytes())
    assert (tmp_path / h.NAMES["journal.backup.qcow2"]).read_bytes() == source.read_bytes()


@pytest.mark.parametrize("kind", ["hardlink", "permissions", "size", "allocation"])
def test_backup_bad_source_rejected(store, tmp_path, kind):
    path = tmp_path / "original"
    path.write_bytes(b"x")
    path.chmod(0o600)
    if kind == "hardlink": os.link(path, tmp_path / "alias")
    if kind == "permissions": path.chmod(0o644)
    if kind in ("size", "allocation"):
        info = os.stat(path)
        from types import SimpleNamespace
        values = {name: getattr(info, name) for name in ("st_mode", "st_nlink", "st_uid", "st_size", "st_blocks")}
        values["st_size" if kind == "size" else "st_blocks"] = h.BACKUP_CAP + 1
        with pytest.raises(h.prior.r.ObservationError):
            h.validate_file(SimpleNamespace(**values), h.BACKUP_CAP, os.geteuid())
        return
    fd = os.open(path, os.O_RDONLY | os.O_NOATIME)
    try:
        with pytest.raises(h.prior.r.ObservationError): h.full_backup(store, fd)
    finally:
        os.close(fd)


def test_tool_argv_and_no_force():
    c = h.image_commands("/fixture/journal.qcow2", "/fixture/backup.qcow2")
    assert c["resize"] == ["resize", "-f", "qcow2", "/fixture/journal.qcow2", "536870912"]
    assert c["compare"] == ["compare", "-f", "qcow2", "-F", "qcow2", "/fixture/backup.qcow2", "/fixture/journal.qcow2"]
    assert not ({"-U", "-r", "--shrink", "--force"} & {word for args in c.values() for word in args})


def test_pinned_launcher_utf8_notice_only_two_argument_changes(monkeypatch):
    raw = ('#!/bin/bash\nq1_vm=/fixture\n\nqemu-system-x86_64 \\\n'
           ' -name local-hand-q1 -smp 4 -m 8192 -monitor none '
           '-serial "file:$q1_log" -daemonize -pidfile "$q1_vm/vm.pid" \\\n'
           ' -drive if=none,id=journal,format=qcow2,file="$q1_vm/journal.qcow2"\n\n'
           "printf 'QEMU 已启动\\n'\n").encode()
    monkeypatch.setitem(h.local.PINS, "start.sh", (0o700, h.digest(raw)))
    old, new = h.qemu_argv(raw, "/fixture", "/fixture/old-console.log")
    changes = [(old[index - 1], a, b) for index, (a, b) in enumerate(zip(old, new)) if a != b]
    assert changes == [("-serial", "file:/fixture/old-console.log", "null"),
                       ("-pidfile", "/fixture/vm.pid", "/fixture/" + h.NAMES["vm.pid"])]
    assert new[new.index("-m") + 1] == "8192" and new[new.index("-smp") + 1] == "4"
    with pytest.raises(h.prior.r.ObservationError, match="START_PIN"):
        h.qemu_argv(raw + b"x", "/fixture", "/fixture/old-console.log")
    with pytest.raises(h.prior.r.ObservationError, match="START_ANCHOR"):
        h.qemu_argv(raw, "/elsewhere", "/fixture/old-console.log")


@pytest.mark.parametrize("change", [dict(format="raw"), {"virtual-size": h.OLD_SIZE},
    {"encrypted": True}, {"snapshots": ["old"]}, {"backing-filename": "other"},
    {"full-backing-filename": "/other"}, {"format-specific": {"data": {"compat": "0.10", "corrupt": False}}},
    {"format-specific": {"data": {"compat": "1.1", "corrupt": True}}}])
def test_image_info_refuses_aliases_or_unsupported_format(change):
    value = dict(format="qcow2", **{"virtual-size": h.NEW_SIZE,
                "format-specific": {"data": {"compat": "1.1", "corrupt": False}}})
    h.validate_image_info(h.canonical(value), h.NEW_SIZE)
    value.update(change)
    with pytest.raises(h.prior.r.ObservationError):
        h.validate_image_info(h.canonical(value), h.NEW_SIZE)


def test_source_ceiling_and_approved_documents_unchanged():
    root = Path(__file__).resolve().parents[1]
    for name in ("q2_journal_growth.py", "q2_journal_growth_guest.py"):
        assert (root / "tests/e3_host" / name).stat().st_size <= 196608
    for name, sha in h.DOC_PINS.items():
        assert h.digest((root / "docs/a2-execution/q2-core-journal-growth" / name).read_bytes()) == sha


def test_real_pidfd_identity_and_exit():
    import subprocess
    argv = [sys.executable, "-I", "-B", "-c",
            "import sys; print('ready', flush=True); sys.stdin.buffer.read()"]
    child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    exe = os.open(sys.executable, os.O_PATH | os.O_CLOEXEC)
    observer = None
    try:
        assert child.stdout.readline() == b"ready\n"
        expected = b"\0".join(os.fsencode(word) for word in argv) + b"\0"
        try:
            observed = h.proc_bytes(child.pid, "cmdline", 65536, lambda: None)
        except (FileNotFoundError, PermissionError):
            assert child.poll() is None
            pytest.skip("native child is live but /proc PID mapping is unavailable")
        if observed != expected:
            pytest.skip("native PID/proc identity unavailable: ready child has different proc argv")
        observer = h.ProcessIdentity(child.pid, argv, exe, lambda: None)
        assert observer.start > 0
        with pytest.raises(h.prior.r.ObservationError, match="ARGV"):
            h.ProcessIdentity(child.pid, [*argv, "different"], exe, lambda: None)
        child.stdin.close()
        child.wait(timeout=3)
        assert observer.exited()
        with pytest.raises(h.prior.r.ObservationError, match="EXITED"):
            observer.recheck()
    finally:
        child.stdin.close()
        child.wait(timeout=3)
        child.stdout.close()
        if observer is not None: observer.close()
        os.close(exe)


def test_timeout_never_signals_mutator():
    until = time.monotonic() + 0.1
    def check():
        if time.monotonic() > until:
            raise TimeoutError("observation ended")
    command = h.Command([sys.executable, "-I", "-B", "-c", "import time; time.sleep(.4)"], check)
    try:
        with pytest.raises(TimeoutError): command.collect()
        assert command.process.poll() is None
    finally:
        # Synthetic child completes naturally; no signal even in test cleanup.
        command.process.wait(timeout=3)


def test_stream_limit_bounded_and_failure_not_success():
    command = h.Command([sys.executable, "-I", "-B", "-c", "import os; os.write(1,b'x'*1000)"], lambda: None, limit=10)
    try:
        with pytest.raises(h.prior.r.ObservationError, match="STREAM_LIMIT"): command.collect()
        assert len(command.output["stdout"]) <= 11
    finally:
        command.process.wait(timeout=3)


def test_tool_return_and_eof():
    output = h.run_tool([sys.executable, "-I", "-B", "-c", "print('fixture')"], lambda: None)
    assert output["stdout"] == b"fixture\n" and all(output["eof"].values())
    with pytest.raises(h.prior.r.ObservationError, match="TOOL_FAILED"):
        h.run_tool([sys.executable, "-I", "-B", "-c", "raise SystemExit(3)"], lambda: None)


def tree(path, **kwargs):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOATIME)
    try:
        return g.tree_digest(fd, lambda: None, mount_id=lambda _: 1, **kwargs)
    finally:
        os.close(fd)


def test_tree_preserves_hardlink_relationship_and_atime(tmp_path):
    (tmp_path / "dir").mkdir()
    file = tmp_path / "dir/a"
    file.write_bytes(b"fixture")
    os.link(file, tmp_path / "b")
    before_atime = file.stat().st_atime_ns
    before = tree(tmp_path)
    assert before["content_bytes"] == 14 and before["entries"] == 4
    g.verify_preservation(before, tree(tmp_path))
    assert file.stat().st_atime_ns == before_atime
    file.write_bytes(b"changed")
    with pytest.raises(g.r.ObservationError, match="CHANGED"):
        g.verify_preservation(before, tree(tmp_path))


def test_tree_requires_noatime_root(tmp_path):
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(g.r.ObservationError, match="NOATIME"):
            g.tree_digest(fd, lambda: None, mount_id=lambda _: 1)
    finally:
        os.close(fd)


def test_two_simultaneous_marker_claims_have_one_winner(store):
    import concurrent.futures
    import threading
    barrier = threading.Barrier(2)
    def claim():
        other = h.Store(store.fd, lambda: None)
        barrier.wait(timeout=3)
        try:
            other.create("consumed.json")
            return "winner"
        except FileExistsError:
            return "blocked"
        finally:
            other.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(claim) for _ in range(2)]
        assert sorted(f.result(timeout=5) for f in futures) == ["blocked", "winner"]


@pytest.mark.parametrize("kind", ["symlink", "fifo", "bytes", "entries", "mount"])
def test_tree_refuses_unsafe_or_unbounded_objects(tmp_path, kind):
    (tmp_path / "file").write_bytes(b"content")
    if kind == "symlink": (tmp_path / "alias").symlink_to(tmp_path / "file")
    if kind == "fifo": os.mkfifo(tmp_path / "fifo")
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOATIME)
    try:
        with pytest.raises(g.r.ObservationError):
            g.tree_digest(fd, lambda: None, max_bytes=1 if kind == "bytes" else g.MAX_BYTES,
                          max_entries=1 if kind == "entries" else g.MAX_ENTRIES,
                          mount_id=lambda child: 1 if kind != "mount" or child == fd else 2)
    finally:
        os.close(fd)


def quiet_unit():
    return dict(Id="synthetic.service", ActiveState="inactive", SubState="dead", MainPID="0", ControlPID="0",
                Restart="no", UnitFileState="disabled", Triggers="", TriggeredBy="", WantedBy="", RequiredBy="",
                UpheldBy="", OnSuccess="", OnFailure="", Job="", Transient="no", FragmentPath="/fixture", DropInPaths="")


@pytest.mark.parametrize("key,value", [("MainPID", "2"), ("ControlPID", "3"), ("ActiveState", "active"),
    ("Restart", "always"), ("UnitFileState", "enabled"), ("Triggers", "x"), ("TriggeredBy", "x.timer"),
    ("WantedBy", "multi-user.target"), ("RequiredBy", "other.service"), ("UpheldBy", "other.service"),
    ("OnSuccess", "business.service"), ("OnFailure", "business.service"), ("Job", "1")])
def test_quiet_rejects_active_or_startup_edges(key, value):
    unit = quiet_unit()
    assert g.validate_quiet_unit(unit) == unit
    unit[key] = value
    with pytest.raises(g.r.ObservationError): g.validate_quiet_unit(unit)


def test_volatile_evidence_not_durable():
    with pytest.raises(g.r.ObservationError, match="VOLATILE"):
        g.validate_durable_filesystem(dict(uuid="", mount=dict(fstype="tmpfs", root="/", options=["rw"])))


def test_field_entry_is_closed_without_complete_j2(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["growth", "--execute"])
    monkeypatch.setattr(h.history.c,"VM_ADOPTION_CLOSURE",dict(commit="c"*40))
    assert h.main() == 3
    value = json.loads(capsys.readouterr().out)
    assert value["marker_created"] is False and value["ssh_requests"] == value["business_cases"] == 0


def test_native_qcow2_ext4_growth_and_full_backup(tmp_path, store):
    """Real local tools, offline synthetic filesystem; NOT online/field PASS."""
    names = ("qemu-img", "mke2fs", "resize2fs", "debugfs", "dumpe2fs")
    programs = {name: shutil.which(name, path="/usr/sbin:/usr/bin:/sbin:/bin") for name in names}
    if not all(programs.values()):
        pytest.skip("native synthetic qcow2/ext4 tools unavailable")
    def run(name, args):
        return h.run_tool([programs[name], *map(str, args)], lambda: None)
    raw, image, expanded = (tmp_path / name for name in ("old.raw", "journal.qcow2", "expanded.raw"))
    with raw.open("xb") as stream: stream.truncate(h.OLD_SIZE)
    run("mke2fs", ["-t", "ext4", "-F", "-q", raw])  # ONLY the fresh synthetic file.
    payload = tmp_path / "payload"
    payload.write_bytes(b"journal-growth-synthetic-sentinel\n")
    run("debugfs", ["-w", "-R", "write " + str(payload) + " /sentinel", raw])
    old_meta = run("dumpe2fs", ["-h", raw])["stdout"]
    run("qemu-img", ["convert", "-f", "raw", "-O", "qcow2", raw, image])
    image.chmod(0o600)
    commands = h.image_commands(str(image), str(tmp_path / h.NAMES["journal.backup.qcow2"]))
    h.validate_image_info(run("qemu-img", commands["info"])["stdout"], h.OLD_SIZE)
    run("qemu-img", commands["check"])
    fd = os.open(image, os.O_RDONLY | os.O_NOATIME)
    try: h.full_backup(store, fd)
    finally: os.close(fd)
    run("qemu-img", commands["resize"])
    h.validate_image_info(run("qemu-img", commands["info"])["stdout"], h.NEW_SIZE)
    run("qemu-img", commands["check"])
    run("qemu-img", commands["compare"])  # Old logical bytes + zero extension, actual tool.
    run("qemu-img", ["convert", "-f", "qcow2", "-O", "raw", image, expanded])
    assert expanded.stat().st_size == h.NEW_SIZE
    run("resize2fs", [expanded])  # No -f, and no real guest/device involved.
    new_meta = run("dumpe2fs", ["-h", expanded])["stdout"]
    def field(data, name):
        return next(line.split(b":", 1)[1].strip() for line in data.splitlines() if line.startswith(name + b":"))
    assert field(old_meta, b"Filesystem UUID") == field(new_meta, b"Filesystem UUID")
    assert field(old_meta, b"Filesystem features") == field(new_meta, b"Filesystem features")
    assert int(field(new_meta, b"Block count")) * int(field(new_meta, b"Block size")) == h.NEW_SIZE
    assert run("debugfs", ["-R", "cat /sentinel", expanded])["stdout"] == payload.read_bytes()

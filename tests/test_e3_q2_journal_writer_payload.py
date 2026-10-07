"""Generated writer behavior against isolated fixtures, without sudo or live procfs."""
from __future__ import annotations

import ast
import base64
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only journal writer contract", allow_module_level=True)

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g


BOOT = "11111111-2222-3333-4444-555555555555"
NOW = 100_000_000_000
PRIVATE_PATH = "/private/fixture/SENSITIVE_WRITER_PATH"
PRIVATE_MESSAGE = "SENSITIVE_WRITER_RAW_MESSAGE"


@pytest.fixture
def payload():
    source = Path(h.__file__).parent
    raw = g.writer_payload(*(source.joinpath(name).read_bytes() for name in (
        "q2_journal_growth.py", "q2_journal_growth_guest.py", "q2_host_kernel_facts.py")), "d" * 40)
    tree = ast.parse(raw)
    invocation = tree.body.pop()
    assert isinstance(invocation, ast.Expr)
    assert ast.unparse(invocation) == "sys.exit(writer_entry())"
    namespace = {"__name__": "isolated_writer_payload"}
    exec(compile(tree, "<isolated-writer-payload>", "exec"), namespace)
    return namespace


@pytest.fixture
def proc_fixture(tmp_path):
    root = tmp_path / "synthetic-proc"
    process = root / "27"
    task = process / "task" / "27"
    (task / "fd").mkdir(parents=True)
    (task / "fdinfo").mkdir()
    raw_stat = ("27 (fixture worker) " + " ".join(["S", *(["0"] * 18), "17"])).encode()
    (process / "stat").write_bytes(raw_stat)
    (task / "stat").write_bytes(raw_stat)
    (task / "maps").write_bytes(b"")
    return root, task


@pytest.mark.parametrize("failure,expected", [
    ("maps", "GROWTH_PROC_MAPS"),
    ("visibility", "GROWTH_WRITERS_VISIBILITY"),
    ("drift", "GROWTH_PROC_DRIFT_FD_SNAPSHOT"),
    ("deadline", "GROWTH_WRITER_DEADLINE"),
])
def test_generated_scanner_retains_source_rejection_codes(payload, proc_fixture, monkeypatch,
                                                          failure, expected):
    root, task = proc_fixture
    if failure == "maps":
        (task / "maps").write_bytes(b"invalid map\n")
    codes = []
    for namespace, error_type in ((vars(h), h.prior.r.ObservationError),
                                  (payload, payload["WriterError"])):
        with monkeypatch.context() as isolated:
            options = dict(proc_root=str(root))
            if failure == "visibility":
                # Reject the synthetic mount record before any process enumeration.
                options = dict(proc_root="/proc", mount_reader=lambda:
                               b"36 25 0:23 / /proc rw - proc proc rw,hidepid=1\n")
                isolated.setitem(namespace, "_bounded_names", lambda *args, **kwargs:
                                 pytest.fail("visibility rejection must precede proc enumeration"))
            if failure == "drift":
                snapshots = iter(({}, {"8": SimpleNamespace(
                    st_dev=42, st_ino=7, st_mode=0, st_uid=0, st_gid=0, st_nlink=1)}))
                isolated.setitem(namespace, "_fd_snapshot", lambda *args, **kwargs: next(snapshots))

            def guard():
                if failure == "deadline":
                    raise error_type("GROWTH_WRITER_DEADLINE")

            with pytest.raises(error_type) as caught:
                namespace["collect_image_writers"]({"journal": (42, 1)}, guard, **options)
            codes.append(str(caught.value))
    assert codes == [expected, expected]


def run_entry(namespace):
    request = dict(schema="lhq-journal-writer/v1", scope="LH-Q2-CORE-JOURNAL-HOST-READ-v1",
        session=h.SESSION, D="d" * 40, nonce="a" * 64,
        images={name: [42, index] for index, name in enumerate(
            ("system", "quota", "journal", "evidence", "seed"), 1)},
        origins=[NOW - 1] * 2, boot_id=BOOT, started=[NOW] * 2, checkpoint=1)
    output = io.BytesIO()
    # Copy module attributes so no process identity, limits or clock is modified.
    namespace["os"] = SimpleNamespace(**(vars(namespace["os"]) | {"geteuid": lambda: 0}))
    namespace["resource"] = SimpleNamespace(**(vars(namespace["resource"]) |
                                              {"setrlimit": lambda *args: None}))
    namespace["time"] = SimpleNamespace(**(vars(namespace["time"]) |
                                          {"clock_gettime_ns": lambda clock: NOW}))
    namespace["sys"] = SimpleNamespace(argv=["fixed", "unused", "unused",
        base64.b64encode(h.canonical(request)).decode()], stdout=SimpleNamespace(buffer=output))
    assert namespace["writer_entry"]() == 3
    raw = output.getvalue()
    result = json.loads(raw)
    assert set(result) == {"schema", "request", "complete", "reason", "errno", "progress"}
    assert result["schema"] == "lhq-journal-writer-result/v2"
    assert result["request"] == request and result["complete"] is False
    assert 0 < len(raw) <= 65536 and raw.endswith(b"\n")
    assert PRIVATE_PATH.encode() not in raw and PRIVATE_MESSAGE.encode() not in raw
    return result


def test_generated_entry_retains_wrapped_permission_errno(payload, proc_fixture):
    root, _task = proc_fixture
    original_scan = payload["collect_image_writers"]
    original_read = payload["_proc_read"]

    def denied(path, cap, check, *context, **options):
        if path.endswith("/maps"):
            raise PermissionError(13, PRIVATE_MESSAGE, PRIVATE_PATH)
        return original_read(path, cap, check, *context, **options)

    payload["_proc_read"] = denied
    payload["read_fact"] = lambda kind, check, report: (BOOT + "\n").encode()
    payload["collect_image_writers"] = lambda images, check, **kwargs: original_scan(
        images, check, proc_root=str(root), progress=kwargs["progress"])
    result = run_entry(payload)
    assert result["reason"] == "GROWTH_WRITERS_UNKNOWN"
    assert result["errno"] == 13
    assert result["progress"]["phase"] == "MAPS_READ"
    assert result["progress"]["maps_files_read"] == result["progress"]["maps_bytes_read"] == 0
    assert result["progress"]["tasks_started"] == 1 and not result["progress"]["scan_complete"]


@pytest.mark.parametrize("target,reason,error_number", [
    ("boot", "HOST_LOCAL_KERNEL_STATX_MASK", None),
    ("boot", "HOST_LOCAL_KERNEL_SYSCALL", 13),
    ("mountinfo", "HOST_LOCAL_KERNEL_SYSCALL", 13),
])
def test_generated_entry_retains_kernel_reason_and_errno(payload, target, reason, error_number):
    calls = []

    def read(kind, check, report):
        calls.append(kind)
        if kind == target:
            error = payload["KernelFactError"](reason, "open_read", kind, errno=error_number)
            if error_number is not None:
                error.__cause__ = PermissionError(error_number, PRIVATE_MESSAGE, PRIVATE_PATH)
            raise error
        assert kind == "boot"
        return (BOOT + "\n").encode()

    payload["read_fact"] = read
    payload["_bounded_names"] = lambda *args, **kwargs: pytest.fail(
        "kernel qualification failure must precede proc enumeration")
    result = run_entry(payload)
    assert result["reason"] == reason and result["errno"] == error_number
    assert calls == (["boot"] if target == "boot" else ["boot", "mountinfo"])

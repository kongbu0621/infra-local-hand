"""Real SQLite snapshots and the pinned checker; only host ancestry is modeled."""
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux held ledger descriptors", allow_module_level=True)

from test_e3_q2_core_delivery_dispatcher import d


@pytest.fixture
def ledger_gate(tmp_path, monkeypatch):
    state = tmp_path / "state"; state.mkdir(mode=0o700)
    reservation = tmp_path / "reservation"; reservation.mkdir(mode=0o700)
    path = state / "jobs.sqlite"
    db = sqlite3.connect(path)
    db.executescript("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);"
        "INSERT INTO metadata VALUES('schema','1'),('authority_id','fixture'),('ledger_id','ledger');"
        "CREATE TABLE operations(id INTEGER); CREATE TABLE events(id INTEGER); CREATE TABLE leases(id INTEGER);"
        "CREATE TABLE counters(key TEXT,value INTEGER); INSERT INTO counters VALUES('generation',1);"
        "CREATE TABLE revocations(id INTEGER);")
    db.execute("PRAGMA journal_mode=WAL"); db.close(); path.chmod(0o600)
    spec = importlib.util.spec_from_file_location("_empty_gate_checker",
        Path(__file__).parent / "e3_host/q2_fixture_check.py")
    checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)
    monkeypatch.setattr(checker, "opened", lambda path, **kw: os.open(
        path, os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if kw.get("directory") else 0)))
    policy = SimpleNamespace(broker_root=str(state), authority_id="fixture", generation=2)
    effects = d.FieldEffects({"guest_deadlines": {"boot_id": "fixture", "boottime_deadline_ns": 750,
                                                "monotonic_deadline_ns": 760}})
    effects.now = lambda: {"boot_id": "fixture", "boottime_ns": 100, "monotonic_ns": 110}
    effects._active_case_deadlines = {"owner_deadline_ns": 200, "owner_monotonic_deadline_ns": 210}
    effects._exec_guard = lambda plan: d._prep_guard(effects, plan["deadlines"]["owner_deadline_ns"])
    effects._candidate_modules = lambda names: {"q2_fixture_check": checker,
        "local_hand_jobs.policy": SimpleNamespace(Policy=lambda config: policy)}
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW); info = os.fstat(fd)
    prepared = {"_exec_ledger_fd": fd,
        "_exec_ledger_identity": {"path": str(path), "dev": info.st_dev, "ino": info.st_ino},
        "assembled": {"policy": {}, "chain": {"broker_generation": [2, 1]}},
        "facts": {"ordinary": {"uid": os.getuid(), "gid": os.getgid()}},
        "paths": {"reservation": str(reservation)}}
    plan = {"ledger_path": str(path), "identity": {"authority_id": "fixture", "ledger_id": "ledger"},
            "deadlines": {"owner_deadline_ns": 200}}
    try:
        yield effects, prepared, plan, path, reservation, checker
    finally:
        os.close(fd); effects.close()


def test_gate_hashes_original_wal_header_without_modifying_ledger(ledger_gate, monkeypatch):
    effects, prepared, plan, path, reservation, checker = ledger_gate
    original = path.read_bytes()
    connect = sqlite3.connect
    def only_memory(name, *args, **kwargs):
        assert name == ":memory:"
        return connect(name, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", only_memory)
    source = effects._exec_empty_ledger_gate(d.CASES[0], prepared, plan)
    value = d.document(source["raw"], newline=True, limit=65536)
    assert original[18:20] == b"\2\2" and value["snapshot_sha256"] == d._sha(original)
    assert value["operations"] == value["events"] == value["leases"] == 0
    assert value["before_submit"] is True and value["stage"] == "fixture"
    assert path.read_bytes() == original
    assert (reservation / "empty-ledger-gate.json").read_bytes() == source["raw"]
    with pytest.raises(FileExistsError):
        effects._exec_empty_ledger_gate(d.CASES[0], prepared, plan)


@pytest.mark.parametrize("fault", ["used", "ledger_id", "authority", "generation", "sidecar"])
def test_gate_never_records_failed_direct_check(ledger_gate, fault):
    effects, prepared, plan, path, reservation, checker = ledger_gate
    if fault == "sidecar":
        Path(str(path) + "-wal").write_bytes(b"retained")
    elif fault == "generation":
        prepared["assembled"]["chain"]["broker_generation"] = [2, 3]
    else:
        db = sqlite3.connect(path)
        if fault == "used": db.execute("INSERT INTO events VALUES(1)")
        else: db.execute("UPDATE metadata SET value='other' WHERE key=?",
                         ("authority_id" if fault == "authority" else "ledger_id",))
        db.commit(); db.close()
    with pytest.raises((ValueError, d.DispatchError)):
        effects._exec_empty_ledger_gate(d.CASES[0], prepared, plan)
    assert not list(reservation.iterdir())


def test_name_substitution_after_direct_checker_is_rejected(ledger_gate):
    effects, prepared, plan, path, reservation, checker = ledger_gate
    original = checker.empty_ledger
    def checked_then_replaced(*args):
        original(*args)
        raw = path.read_bytes(); path.rename(path.with_name("retained.sqlite"))
        path.write_bytes(raw); path.chmod(0o600)
    checker.empty_ledger = checked_then_replaced
    with pytest.raises(d.DispatchError, match="EMPTY_LEDGER_CHANGED"):
        effects._exec_empty_ledger_gate(d.CASES[0], prepared, plan)
    assert not list(reservation.iterdir())


def test_expired_owner_window_performs_no_candidate_check(ledger_gate):
    effects, prepared, plan, path, reservation, checker = ledger_gate
    effects.now = lambda: {"boot_id": "fixture", "boottime_ns": 201, "monotonic_ns": 211}
    checker.empty_ledger = lambda *args: pytest.fail("expired gate called checker")
    with pytest.raises(d.DispatchError, match="DEADLINE"):
        effects._exec_empty_ledger_gate(d.CASES[0], prepared, plan)
    assert not list(reservation.iterdir())

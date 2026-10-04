"""Real SQLite export checks; these do not establish field acceptance."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Held descriptor export requires Linux", allow_module_level=True)

SPEC = importlib.util.spec_from_file_location("core_ledger_export", Path(__file__).parent / "e3_host/q2_core_delivery_dispatcher.py")
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    case = copy.deepcopy(d.CASES[0])
    state = tmp_path / d.SESSION / case["case_id"] / "state"
    state.mkdir(parents=True)
    reservation = state.parent / "reservation"
    reservation.mkdir()
    path = state / "jobs.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE operations(namespace TEXT,id TEXT,parent TEXT,principal TEXT,digest TEXT,
            reserved_bytes INTEGER,request_json TEXT,plan_json TEXT,record_json TEXT);
        CREATE TABLE events(seq INTEGER PRIMARY KEY,namespace TEXT,id TEXT,kind TEXT,
            observed_at REAL,data_json TEXT);
    """)
    connection.executemany("INSERT INTO metadata VALUES (?,?)", [
        ("schema", "1"), ("authority_id", "authority"), ("ledger_id", "ledger")])
    original_text = '{ "b" : 1.25, "a": {"x":true} }'
    connection.execute("INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?)",
        ("job", case["operation_id"], None, "principal", "a" * 64, 8388608,
         original_text, "{}", '{"seals":{}}'))
    connection.executemany("INSERT INTO events VALUES (?,?,?,?,?,?)", [
        (2, "job", case["operation_id"], "DONE", 1.2345678901234567, '{ "ok": true }'),
        (1, "job", case["operation_id"], "ACCEPTED", 1.0, "{}")])
    observed = connection.execute("SELECT printf('%.17g',observed_at) FROM events WHERE seq=2").fetchone()[0]
    connection.commit()
    connection.close()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    effects = d.FieldEffects({"manifest": {"locators": {"state_parent": str(tmp_path)}},
        "guest_deadlines": {"boottime_deadline_ns": 10**20}})
    effects._effect_guard = lambda: None
    effects.now = lambda: {"boottime_ns": 123, "monotonic_ns": 123}
    effects._active_case_deadlines = {"owner_deadline_ns": 10**19,
                                     "owner_monotonic_deadline_ns": 10**19}
    monkeypatch.setattr(d, "_prep_guard", lambda *_args: None)
    # Persistence owns files as the current test account; production uses root.
    real_file = d._prep_file
    monkeypatch.setattr(d, "_prep_file", lambda *args, **kwargs:
        real_file(*args, uid=os.getuid(), gid=os.getgid(), **kwargs))
    prepared = {"_exec_ledger_fd": fd, "_exec_ledger_identity": {
        "path": str(path), "dev": info.st_dev, "ino": info.st_ino}}
    plan = {"ledger_path": str(path), "identity": {"authority_id": "authority",
        "ledger_id": "ledger", "principal_id": "principal"}, "request": {"request_digest": "a" * 64}, "deadlines": {"owner_deadline_ns": 10**19}}
    yield effects, case, prepared, plan, path, reservation, original_text, observed
    effects.close()
    os.close(fd)


def export(row):
    return row[0]._exec_ledger_export(*row[1:4])


def mutate(row, sql, parameters=()):
    with sqlite3.connect(row[4]) as connection:
        connection.execute(sql, parameters)
    connection.close()


def test_export_preserves_sqlite_text_and_held_bytes(ledger):
    original = ledger[4].read_bytes()
    source = export(ledger)
    value = json.loads(source["raw"])
    assert source["path"].endswith("/records/ledger-export.json")
    assert source["role"] == "ledger" and source["mode"] == 384
    assert value["operation"]["request_json"] == ledger[6]
    assert [event["seq"] for event in value["events"]] == [1, 2]
    assert value["events"][1]["observed_at"] == ledger[7]
    assert value["events"][1]["data_json"] == '{ "ok": true }'
    assert value["ledger_identity"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert ledger[4].read_bytes() == original
    assert sorted(item.name for item in ledger[4].parent.iterdir()) == ["jobs.sqlite"]
    output = ledger[5] / "ledger-export.json"
    assert output.read_bytes() == source["raw"]
    assert output.stat().st_mode & 0o777 == 0o600
    assert not (ledger[4].parent.parent / "records").exists()
    with pytest.raises(FileExistsError):
        export(ledger)


@pytest.mark.parametrize("bad", ['{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}',
    '{"x":NaN}', '{"x":Infinity}', '{"x":1e9999}', '[]'])
@pytest.mark.parametrize("target", ["request_json", "plan_json", "record_json", "data_json"])
def test_export_rejects_invalid_original_text(ledger, bad, target):
    table = "events" if target == "data_json" else "operations"
    mutate(ledger, "UPDATE " + table + " SET " + target + "=?", (bad,))
    with pytest.raises(d.DispatchError, match="EXPORT_TEXT"):
        export(ledger)
    assert not (ledger[5] / "ledger-export.json").exists()


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_export_rejects_every_sidecar(ledger, suffix):
    Path(str(ledger[4]) + suffix).touch()
    with pytest.raises(d.DispatchError, match="EXPORT_SIDECAR"):
        export(ledger)


def test_export_rejects_replaced_ledger(ledger):
    ledger[4].rename(ledger[4].with_name("retained.sqlite"))
    ledger[4].write_bytes(b"different")
    with pytest.raises(d.DispatchError, match="EXPORT_IDENTITY"):
        export(ledger)


@pytest.mark.parametrize("sql", [
    "UPDATE metadata SET value='other' WHERE key='ledger_id'",
    "INSERT INTO metadata VALUES ('extra','not-allowed')",
    "INSERT INTO operations SELECT * FROM operations",
    "UPDATE operations SET principal='another'",
    "UPDATE events SET id='another'",
])
def test_export_rejects_unbound_rows(ledger, sql):
    mutate(ledger, sql)
    with pytest.raises(d.DispatchError):
        export(ledger)


def test_h11_cannot_export_even_if_caller_has_descriptor(ledger):
    with pytest.raises(d.DispatchError, match="EXPORT_CASE"):
        ledger[0]._exec_ledger_export(d.CASES[2], ledger[2], ledger[3])


@pytest.mark.skipif(os.geteuid() != 0, reason="Carrier directory creation requires root ownership")
def test_only_session_container_allows_ordinary_traversal(tmp_path):
    info = tmp_path.stat()
    effects = d.FieldEffects({"manifest": {"locators": {"state_parent": str(tmp_path)}}})
    effects._effect_guard = lambda: None
    effects._admission = {"parents": {"state": {"dev": info.st_dev, "ino": info.st_ino,
        "mode": info.st_mode & 0o777, "uid": info.st_uid, "gid": info.st_gid}}}
    effects._prepare_carrier_storage()
    base = tmp_path / d.SESSION
    assert base.stat().st_mode & 0o777 == 0o755
    assert (base / "carrier").stat().st_mode & 0o777 == 0o700
    assert (base / "carrier/intents").stat().st_mode & 0o777 == 0o700

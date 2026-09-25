"""Original-budget assembly with real create-only files and journal cells.

Protected ownership/program bytes are explicitly modeled for unprivileged CI;
no systemd, quota, namespace or Q3 host success is claimed by these tests.
"""
import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from local_hand_jobs import bootstrap, quota_binding, quota_contract as q, quota_grant as g
from q2_fixtures import BOOT, SECOND
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import q2_assembly as a, q2_config as c
    from admin.local_hand_quota_observer.q2_journal import Journal
    from test_e3_quota_q2_runtime import declaration, fixture_open

SESSION = "a" * 64


def declaration_template():
    cfg = declaration(); original = next(iter(cfg["grants"].values()))
    original["management"]["storage_inodes"] = 11
    original_budget = dict(original["budget"]["limits"])
    for key in ("wall_seconds", "cpu_seconds", "log_bytes"): original_budget[key] *= 3
    grant = {key: value for key, value in original.items() if key not in ("budget", "predecessors")}
    grant["request"].pop("deadline_ns")
    grant["management"].pop("issued_ns")
    peer = next(iter(cfg["peers"].values()))
    return {"schema": a.SCHEMA, "purpose": "ISOLATED_Q2_PREFLIGHT", "id": "1" * 32,
        "installation": {k: cfg[k] for k in a._STATIC}, "grant": grant,
        "original_budgets": original_budget, "broker_generation": [1, 1],
        "output": {"path": "/synthetic/output", "device": 7, "inode": 321},
        "journal": dict(cfg["journal"]["pin"]["directory"], path=cfg["journal"]["path"]),
        "service": {k: v for k, v in cfg["service"].items() if k not in ("request_id", "end_ns")},
        "peer": {"parent": peer["parent"], "executable": peer["executable"],
            "runner": {"path": "/synthetic/installed/runner.py", "sha256": "e" * 64}}}, original["budget"]


def template(value):
    raw = q._canonical(value, c.LIMIT)
    return a.decode(raw, hashlib.sha256(raw).hexdigest())


def snapshot(value, original_budget):
    return dict(preparation=dict(phase="preflight", session=SESSION, budget=copy.deepcopy(original_budget),
        allocation=copy.deepcopy(value["grant"]["allocation"]), generation=value["broker_generation"]),
        observation=None, pending=None, closed=None)


def argv(value, grant):
    execution = quota_binding.execution(grant)
    payload = dict(version=2, execution=execution, allocation=grant.as_dict()["allocation"], observation=grant.as_dict())
    return [value["peer"]["executable"]["path"], "-I", value["peer"]["runner"]["path"], "--bootstrap", bootstrap.encode_payload(payload)]


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux administrative assembly")
class OriginalBudgetTests(unittest.TestCase):
    def setUp(self):
        self.value, self.original = declaration_template()
        self.snapshot = snapshot(self.value, self.original)
        self.clock = dict(boot_id=BOOT, boottime_ns=2*SECOND)

    def build(self, value=None, snap=None, clock=None):
        return a.build_grant(template(self.value if value is None else value),
            self.snapshot if snap is None else snap, session=SESSION, clock=self.clock if clock is None else clock)

    def test_exact_budget_and_allocation_retained_with_original_deadline(self):
        grant = self.build(); data = grant.as_dict()
        self.assertEqual(self.original, data["budget"])
        self.assertEqual(self.value["grant"]["allocation"], data["allocation"])
        self.assertEqual(30*SECOND, data["request"]["deadline_ns"])
        self.assertEqual(2*SECOND, data["management"]["issued_ns"])
        self.assertEqual([], data["predecessors"])
        later = self.build(clock=dict(self.clock, boottime_ns=3*SECOND))
        self.assertEqual(data["request"]["deadline_ns"], later.as_dict()["request"]["deadline_ns"])

    def test_false_original_budget_session_generation_or_identity_cannot_be_substituted(self):
        for fault in ("budget", "limits", "operation", "root", "session", "generation", "started", "boot"):
            snap = copy.deepcopy(self.snapshot)
            prep = snap["preparation"]
            if fault == "budget": prep["budget"]["budget_digest"] = "f"*64
            if fault == "limits": prep["budget"]["limits"]["cpu_seconds"] += 1
            if fault == "operation": prep["budget"]["operation_id"] = "other"
            if fault == "root": next(iter(prep["allocation"]["paths"].values()))["inode"] += 1
            if fault == "session": prep["session"] = "b"*64
            if fault == "generation": prep["generation"] = [1, 2]
            if fault == "started": prep["budget"]["started_boottime_ns"] += 1
            if fault == "boot": prep["budget"]["boot_id"] = "99999999-2222-3333-4444-555555555555"
            with self.subTest(fault=fault), self.assertRaises((ValueError, RuntimeError)):
                self.build(snap=snap)

    def test_late_or_previous_boot_assembly_never_extends_budget(self):
        for clock in (dict(self.clock, boottime_ns=29*SECOND), dict(self.clock, boottime_ns=0),
                      dict(self.clock, boot_id="99999999-2222-3333-4444-555555555555")):
            with self.subTest(clock=clock), self.assertRaises(ValueError): self.build(clock=clock)

    def test_observed_pending_closed_or_extra_snapshot_fields_rejected(self):
        for field in ("observation", "pending", "closed", "untrusted_path"):
            snap = copy.deepcopy(self.snapshot); snap[field] = {}
            with self.subTest(field=field), self.assertRaises(ValueError): self.build(snap=snap)

    def test_later_phase_and_untrusted_override_fields_are_rejected(self):
        for field in ("phase", "deadline", "predecessors", "root"):
            candidate = copy.deepcopy(self.value)
            if field == "phase": candidate["grant"]["request"]["phase"] = "business"
            if field == "deadline": candidate["grant"]["request"]["deadline_ns"] = 999*SECOND
            if field == "predecessors": candidate["grant"]["predecessors"] = []
            if field == "root": candidate["ordinary_path"] = "/other"
            with self.subTest(field=field), self.assertRaises(ValueError): template(candidate)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux real create-only journal assembly")
class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.home()); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.value, self.original = declaration_template()
        def pin(path):
            info = path.stat()
            return dict(path=str(path), device=info.st_dev, inode=info.st_ino)
        for name in ("output", "journal", "evidence"):
            path = self.root/name; path.mkdir(mode=0o700)
            target = self.value["installation"] if name == "evidence" else self.value
            target[name] = pin(path)
        executable = self.root/"python"; executable.write_bytes(b"synthetic executable"); executable.chmod(0o755)
        self.value["peer"]["executable"] = pin(executable)
        runner = self.root/"runner.py"; runner.write_bytes(b"# synthetic pinned runner\n")
        self.value["peer"]["runner"] = dict(path=str(runner), sha256=hashlib.sha256(runner.read_bytes()).hexdigest())
        self.clock = dict(boot_id=BOOT, boottime_ns=2*SECOND)
        self.grant = a.build_grant(template(self.value), snapshot(self.value, self.original), session=SESSION, clock=self.clock)
        self.commands = argv(self.value, self.grant)
        # Actual root ownership/ELF admission is modeled; fd identity, contents,
        # journal validation, nofollow, O_EXCL and fsync are exercised for real.
        patches = [mock.patch.object(a, "_administrator"),
            mock.patch.object(c, "open_protected", side_effect=fixture_open),
            mock.patch.object(a, "verify_file", side_effect=lambda p, h: self.assertEqual(h, hashlib.sha256(Path(p).read_bytes()).hexdigest())),
            mock.patch.object(c, "load", side_effect=lambda p, h: c.decode(Path(p).read_bytes(), p, h))]
        for patch in patches: patch.start(); self.addCleanup(patch.stop)

    def install(self, **kwargs):
        options = dict(bootstrap_argv=self.commands, session=SESSION, clock=self.clock); options.update(kwargs)
        return a.install(template(self.value), self.grant, **options)

    def test_config_and_real_journal_pin_written_once_and_replay_retained(self):
        result = self.install(); cfg = result["config"]
        self.assertEqual(self.grant, cfg.active())
        self.assertEqual({"observer.json", "reservation.json", "session", "management.jsonl"},
                         {p.name for p in (self.root/"output").iterdir()})
        journal = Journal(cfg.data()["journal"]["path"], cfg.data()["journal"]["pin"], cfg.data()["capacity"], list(cfg.grants().values()))
        try:
            with journal.locked(): self.assertEqual("READY", journal.scan()[self.grant.request.as_dict()["request_id"]]["status"])
        finally: journal.close()
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        expected = hashlib.sha256(b"\0".join(x.encode() for x in self.commands)+b"\0").hexdigest()
        self.assertEqual(expected, next(iter(cfg.data()["peers"].values()))["command_sha256"])

    def test_wrong_command_or_payload_rejected_before_reservation(self):
        for fault in ("program", "script", "role", "grant", "budget"):
            command = list(self.commands)
            if fault == "program": command[0] = "/bin/sh"
            if fault == "script": command[2] = "/other.py"
            if fault == "role": command[3] = "--helper"
            if fault in ("grant", "budget"):
                payload = bootstrap.decode_payload(command[4])
                if fault == "grant": payload["observation"]["request"]["request_id"] = "f"*32
                else: payload["execution"]["budgets"]["cpu_seconds"] += 1
                command[4] = bootstrap.encode_payload(payload)
            with self.subTest(fault=fault), self.assertRaises(ValueError): self.install(bootstrap_argv=command)
            self.assertEqual([], list((self.root/"output").iterdir()))

    def test_fsync_failure_leaves_permanent_reservation_and_no_replay(self):
        real = a.os.fsync; calls = []
        def fail(fd):
            calls.append(fd)
            if len(calls) == 1: raise OSError("synthetic fsync failure")
            return real(fd)
        with mock.patch.object(a.os, "fsync", side_effect=fail), self.assertRaises(OSError): self.install()
        self.assertTrue((self.root/"output"/"reservation.json").exists())
        with self.assertRaises(ValueError): self.install()
        self.assertEqual([], list((self.root/"journal").iterdir()))

    def test_partial_journal_failure_never_finishes_or_replaces_existing_state(self):
        def partial(path, cap, grants):
            (Path(path)/"lock").touch(mode=0o600)
            raise OSError("synthetic partial journal")
        with mock.patch.object(Journal, "provision", side_effect=partial), self.assertRaises(OSError): self.install()
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_changed_directory_pin_symlink_or_occupied_evidence_rejected(self):
        self.value["output"]["inode"] += 1
        with self.assertRaises(ValueError): self.install()
        self.value["output"]["inode"] -= 1
        (self.root/"evidence"/"old").write_bytes(b"retained")
        with self.assertRaises(ValueError): self.install()
        self.assertEqual([], list((self.root/"output").iterdir()))
        (self.root/"evidence"/"old").unlink()
        output = self.root/"output"; output.rmdir(); output.symlink_to(self.root/"journal", target_is_directory=True)
        with self.assertRaises(OSError): self.install()

    def test_assembly_artifacts_are_charged_to_original_management_budget(self):
        self.value["grant"]["management"]["storage_inodes"] = 10
        self.grant = a.build_grant(template(self.value), snapshot(self.value, self.original), session=SESSION, clock=self.clock)
        self.commands = argv(self.value, self.grant)
        with self.assertRaisesRegex(ValueError, "ASSEMBLY_STORAGE"): self.install()
        self.assertEqual([], list((self.root/"output").iterdir()))

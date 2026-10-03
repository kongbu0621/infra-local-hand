"""Strict contract tests for the self-contained core field dispatcher.

The fake below is an injected effect transcript.  It does not establish field
acceptance; it exists only to prove that the dispatcher rejects altered facts
and never manufactures H01/Q4/H11 evidence.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import struct

import pytest


PATH = Path(__file__).parent / "e3_host/q2_core_delivery_dispatcher.py"
SPEC = importlib.util.spec_from_file_location("_q2_core_delivery_dispatcher_test", PATH)
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _field_member(path, raw):
    return {"path": path, "role": "field-code", "mode": 420, "bytes": len(raw),
            "sha256": _sha(raw),
            "origin": {"kind": "implementation-blob", "commit": "9" * 40,
                       "path": "tests/e3_host/" + Path(path).name, "blob": "8" * 40}}


def context(*, guest_duration_ns=750 * d.NS):
    dispatcher = PATH.read_bytes()
    blobs = {"field/loader.py": b"loader", "field/bootstrap.py": b"bootstrap",
             "field/dispatcher.py": dispatcher}
    rows = [_field_member(path, raw) for path, raw in blobs.items()]
    rows.sort(key=lambda row: row["path"].encode("ascii"))
    entry = {
        "loader_path": "field/loader.py", "loader_bytes": len(blobs["field/loader.py"]),
        "loader_sha256": _sha(blobs["field/loader.py"]),
        "bootstrap_path": "field/bootstrap.py", "bootstrap_bytes": len(blobs["field/bootstrap.py"]),
        "bootstrap_sha256": _sha(blobs["field/bootstrap.py"]),
        "dispatcher_path": "field/dispatcher.py", "dispatcher_bytes": len(dispatcher),
        "dispatcher_sha256": _sha(dispatcher), "carrier_argv_sha256": "a" * 64,
        "management_entry_binding_sha256": "b" * 64,
    }
    manifest = {
        "schema": "local-hand-q2-core-field-package/v1", "scope": d.SCOPE,
        "rule": copy.deepcopy(d.RULE), "baseline": copy.deepcopy(d.BASELINE),
        "owner_decision": copy.deepcopy(d.OWNER_DECISION), "closure": copy.deepcopy(d.CLOSURE),
        "implementation": {"commit": "9" * 40, "tree": "7" * 40},
        "candidate": copy.deepcopy(d.CANDIDATE), "wheel": copy.deepcopy(d.WHEEL),
        "projection": copy.deepcopy(d.PROJECTION), "entry": entry,
        "locators": {"schema": "local-hand-q2-core-private-locators/v1",
                     "state_parent": "/state", "quota_parent": "/quota",
                     "install_parent": "/install", "journal_parent": "/journal",
                     "evidence_parent": "/evidence"},
        "members": rows, "limits": copy.deepcopy(d.PACKAGE_LIMITS),
    }
    manifest_raw = d.canonical(manifest, newline=True)
    package = b"LHCFP1\n" + struct.pack(">Q", len(manifest_raw)) + manifest_raw + b"".join(
        blobs[row["path"]] for row in rows)
    guest_origin = 1_000_000_000_000
    hello = {
        "schema": "local-hand-q2-core-carrier-hello/v1", "scope": d.SCOPE,
        "loader_sha256": entry["loader_sha256"], "bootstrap_sha256": entry["bootstrap_sha256"],
        "guest_boot_id": "11111111-2222-3333-4444-555555555555",
        "guest_boottime_origin_ns": guest_origin, "guest_monotonic_origin_ns": guest_origin + d.NS,
        "pid": 123, "uid": 0, "gid": 0, "euid": 0, "egid": 0,
        "python": {}, "carrier_unit": {}, "process_limits": {},
    }
    host_origin = 2_000_000_000_000
    # mapped = remaining - 17s.  Values below are exact millisecond multiples.
    remaining = guest_duration_ns + 17 * d.NS
    host_boot_deadline = host_origin + d.LIMITS["carrier_seconds"] * d.NS
    host_mono_origin = host_origin + d.NS
    host_mono_deadline = host_mono_origin + d.LIMITS["carrier_seconds"] * d.NS
    bind = {
        "schema": "local-hand-q2-core-carrier-bind/v1", "scope": d.SCOPE,
        "session_id": d.SESSION, "hello_sha256": _sha(d.canonical(hello, newline=True)),
        "consumption_sha256": "0" * 64, "package_basename": "only.lhfp",
        "package_bytes": len(package), "package_sha256": _sha(package),
        "host_boottime_origin_ns": host_origin, "host_monotonic_origin_ns": host_mono_origin,
        "host_boottime_deadline_ns": host_boot_deadline,
        "host_monotonic_deadline_ns": host_mono_deadline,
        "host_boottime_bind_ns": host_boot_deadline - remaining,
        "host_monotonic_bind_ns": host_mono_deadline - remaining,
        "host_remaining_floor_ns": remaining, "clock_margin_ns": 2 * d.NS,
        "local_final_reserve_ns": 15 * d.NS, "mapped_duration_ns": guest_duration_ns,
        "guest_duration_cap_ns": 750 * d.NS, "guest_duration_ns": guest_duration_ns,
    }
    marker = {
        "schema": d.CONSUMPTION_SCHEMA, "scope": d.SCOPE, "session_id": d.SESSION,
        "baseline": d.BASELINE, "owner_decision": d.OWNER_DECISION, "closure": d.CLOSURE,
        "implementation": manifest["implementation"], "candidate": d.CANDIDATE,
        "package": {"basename": bind["package_basename"], "bytes": len(package),
                    "sha256": _sha(package), "manifest_sha256": _sha(manifest_raw)},
        "management_entry_binding_sha256": entry["management_entry_binding_sha256"],
        "carrier_argv_sha256": entry["carrier_argv_sha256"],
        "host_boottime_origin_ns": bind["host_boottime_origin_ns"],
        "host_monotonic_origin_ns": bind["host_monotonic_origin_ns"],
        "host_boottime_deadline_ns": bind["host_boottime_deadline_ns"],
        "host_monotonic_deadline_ns": bind["host_monotonic_deadline_ns"],
        "state": "CONSUMPTION_RECORD_COMPLETE",
    }
    bind["consumption_sha256"] = _sha(d.canonical(marker, newline=True))
    bind_raw = d.canonical(bind, newline=True)
    return {
        "schema": d.CONTEXT_SCHEMA, "hello": hello, "bind": bind, "manifest": manifest,
        "members": {path: memoryview(raw) for path, raw in blobs.items()},
        "guest_deadlines": {"boot_id": hello["guest_boot_id"],
                            "boottime_deadline_ns": hello["guest_boottime_origin_ns"] + guest_duration_ns,
                            "monotonic_deadline_ns": hello["guest_monotonic_origin_ns"] + guest_duration_ns},
        "stdin_bytes_received": 16 + len(bind_raw) + len(package),
    }


def _source(path, role, raw=None, mode=384):
    raw = raw if raw is not None else (d.canonical({"path": path}, newline=True)
                                       if path.endswith(".json") else b"field-stream")
    return {"path": path, "role": role, "mode": mode, "raw": raw}


def _ref(source):
    return {"path": source["path"], "bytes": len(source["raw"]),
            "sha256": _sha(source["raw"])}


class FakeEffects:
    """A deterministic evidence-bearing effect transcript, never field proof."""

    def __init__(self, value):
        self.context = value
        self.tick = 0
        self.log = []
        self.planned = {}

    def now(self):
        self.tick += 1
        self.log.append(("clock", self.tick))
        hello = self.context["hello"]
        return {"boot_id": hello["guest_boot_id"],
                "boottime_ns": hello["guest_boottime_origin_ns"] + self.tick * d.NS,
                "monotonic_ns": hello["guest_monotonic_origin_ns"] + self.tick * d.NS}

    def admit(self, _expected):
        self.log.append(("admit", None))
        boot = self.context["hello"]["guest_boot_id"]
        uuid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        program_paths = {"python": "/usr/bin/python3", "git": "/usr/bin/git",
                         "cc": "/usr/bin/cc", "setpriv": "/usr/bin/setpriv",
                         "systemctl": "/usr/bin/systemctl",
                         "systemd_run": "/usr/bin/systemd-run"}
        programs = {name: {"path": path, "dev": 1, "ino": index + 10, "mode": 0o755,
                           "uid": 0, "gid": 0, "nlink": 1, "bytes": 100,
                           "sha256": str(index + 1) * 64}
                    for index, (name, path) in enumerate(program_paths.items())}
        policies = {name: {"paths": ["/etc/" + name], "bytes": 10,
                           "sha256": str(index + 1) * 64, "relation": {"matched": True}}
                    for index, name in enumerate(("sudo", "sshd", "authorized_keys", "rc"))}
        directory_roles = ("state", "quota", "install", "journal", "evidence")
        parents = {role: {"path": "/" + role, "dev": index + 20, "ino": index + 30,
                          "mode": 0o755, "uid": 0, "gid": 0, "nlink": 2,
                          "mount_id": index + 40, "fs_uuid": uuid}
                   for index, role in enumerate(directory_roles)}
        cgroups = ("controller_cgroup", "management_cgroup", "supervisor_cgroup",
                   "query_cgroup", "ordinary_cgroup", "retained_ordinary_cgroup")
        parents.update({role: {"path": "/" + role.replace("_cgroup", ".slice"),
                               "dev": 99, "ino": index + 50,
                               "unit": role.replace("_cgroup", ".slice"),
                               "invocation_id": str(index + 1) * 32,
                               "controllers": ["cpu", "memory", "pids"]}
                        for index, role in enumerate(cgroups)})
        filesystems = {role: {"mount_id": parents[role]["mount_id"],
                              "dev": parents[role]["dev"], "fs_uuid": uuid,
                              "fstype": "ext4", "mount_options": ["rw", "prjquota"],
                              "bytes_available": 2**30, "inodes_available": 100000}
                       for role in directory_roles}
        capacity = [{"dev": 20, "fs_uuid": uuid, "roles": sorted(directory_roles),
                     "historical_bytes": 0, "historical_inodes": 0,
                     "new_required_bytes": d.LIMITS["total_guest_admission_bytes"],
                     "new_required_inodes": d.LIMITS["total_guest_admission_inodes"],
                     "bytes_available": 2**30, "inodes_available": 100000,
                     "admitted": True}]
        absence = [{"kind": "path", "name": "/install/future", "parent_dev": 22,
                    "parent_ino": 32, "project_id": None, "unit": None,
                    "absent": True, "collision": False}]
        guest = {"hostname": "synthetic-qemu", "dmi_vendor": "QEMU",
                 "dmi_product": "KVM", "initial_userns": {"dev": 4, "ino": 1},
                 "boot_id": boot, "pid1_exe": "/usr/lib/systemd/systemd",
                 "pid1_version": "systemd 255", "cgroup_version": 2,
                 "ordinary_user": "q2job", "ordinary_uid": 1100, "ordinary_gid": 1100,
                 "ordinary_groups": [1100], "user_manager_unit": "user@1100.service",
                 "user_manager_invocation_id": "a" * 32,
                 "user_manager_cgroup": "/user.slice/user-1100.slice/user@1100.service"}
        return {"guest": guest, "programs": programs, "policies": policies,
                "parents": parents, "filesystems": filesystems,
                "capacity": capacity, "absence": absence}

    def install(self, expected):
        self.log.append(("install", None))
        return {"destination": "/install/" + d.INSTALL_BASENAME,
                "staging": "/install/" + d.STAGING_BASENAME,
                "receipt_path": "/state/" + d.SESSION + "/carrier/installation.json",
                "dev": 1, "ino": 2,
                "mode": 493, "uid": 0, "gid": 0,
                "members_sha256": _sha(d.canonical(expected["manifest"]["members"])),
                "native_sha256": "c" * 64, "projection_sha256": d.PROJECTION["sha256"],
                "wheel_sha256": d.WHEEL["sha256"], "allocated_bytes": 1024,
                "allocated_inodes": 10, "status": "INSTALLED"}

    @staticmethod
    def _role(path):
        if path == "carrier/admission.json": return "admission"
        if path == "carrier/installation.json": return "installation"
        if path == "carrier/session.json": return "session"
        if path.endswith("/intent.json"): return "intent"
        if "/phase-" in path and path.endswith("-receipt.json"): return "phase-receipt"
        if path.endswith("/h11-recovery-proof.json"): return "recovery-proof"
        if path.endswith("/case-verdict.json"): return "verdict"
        raise AssertionError(path)

    def persist(self, case_id, path, raw, mode):
        role = self._role(path)
        self.log.append(("persist", case_id, role, path))
        return _source(path, role, raw, mode)

    def prepare_case(self, case, intent, preparation_deadline_ns):
        self.log.append(("prepare", case["case_id"], preparation_deadline_ns))
        return {"case_id": case["case_id"], "intent_sha256": _sha(d.canonical(intent))}

    def plan_case(self, case, _prepared, deadlines):
        identity = dict(d._identity(case), authority_digest="d" * 64,
                        manifest_digest="e" * 64, expires_at=1_800_000_000)
        expected = {"node_id": identity["node_id"], "install_uuid": identity["install_uuid"],
                    "deployment_epoch": 1, "profile_digest": "1" * 64,
                    "policy_digest": "2" * 64, "registry_digest": "3" * 64}
        roots = []
        for planned in d._planned_roots(case):
            observed = {"path": planned["path"], "role": planned["role"], "device": 10,
                        "inode": planned["project_id"], "uid": 1000, "gid": 1000,
                        "mode": 0o40700, "filesystem": "ext4",
                        "filesystem_uuid": "11111111-2222-3333-4444-555555555555",
                        "project_id": planned["project_id"], "xflags": 512,
                        "hard_bytes": planned["hard_bytes"], "accounting": True,
                        "enforcement": True, "identity_unchanged": True,
                        "hard_inodes": planned["inode_hard_limit"]}
            roots.append({"ref": planned["ref"], "slot": planned["slot"],
                          "planned": planned, "observed": observed})
        plan = {
            "schema": d.PLAN_SCHEMA, "session_id": d.SESSION, "index": case["index"],
            "case_id": case["case_id"], "kind": case["kind"],
            "predecessor": case["predecessor"], "preparation_id": case["preparation_id"],
            "identity": identity,
            "principal": {"principal_id": identity["principal_id"],
                          "scopes": ["lh:submit", "lh:read", "lh:evidence"] +
                                    (["lh:cancel"] if case["index"] == 2 else [])},
            "authority_path": "/state/" + case["case_id"] + "/authority/authority.json",
            "ledger_path": "/state/" + case["case_id"] + "/state/jobs.sqlite",
            "request": {"schema_version": "lh-job-v1", "operation_id": case["operation_id"],
                        "kind": "host.inspect", "profile_ref": identity["profile_ref"],
                        "expected": expected, "inputs": {}, "expires_at": identity["expires_at"],
                        "request_digest": "4" * 64},
            "operation_id": case["operation_id"], "roots": roots,
            "controllers": {"target": {}, "supervisor": {}, "controller_parent": {},
                            "query_parent": {}, "management_parent": {}, "supervisor_parent": {},
                            "target_storage_bytes": 1048576, "target_storage_inodes": 64,
                            "supervisor_storage_bytes": 8388608,
                            "supervisor_storage_inodes": 64},
            "system_geometry": None if case["index"] == 2 else {
                "schema": "local-hand-q2-system-geometry/v1", "controller_parent": {},
                "ordinary_parent": {}, "retained_ordinary_parent": {}},
            "phases": d._phase_units(case["operation_id"], case["phases"]),
            "empty_ledger_expectation": {"ledger_path": "/state/" + case["case_id"] + "/state/jobs.sqlite",
                                         "authority_id": identity["authority_id"],
                                         "ledger_id": identity["ledger_id"],
                                         "expected_operations": 0, "expected_events": 0,
                                         "expected_leases": 0, "expected_sidecars": []},
            "deadlines": deadlines, "budgets": d._budget(case["phases"]),
        }
        prefix = "cases/" + case["case_id"] + "/"
        sources = [
            _source(prefix + "reservation/case-plan.json", "plan", d.canonical(plan, newline=True)),
            _source(prefix + "reservation/preparation-plan.json", "preparation-plan"),
            _source(prefix + "reservation/preparation-result.json", "preparation-result"),
            _source(prefix + "reservation/empty-ledger-gate.json", "empty-ledger-gate"),
            _source(prefix + "owner_declarations/fixture-check.json", "fixture-check"),
            _source(prefix + "authority/authority.json", "authority"),
        ]
        self.planned[case["case_id"]] = sources
        self.log.append(("plan", case["case_id"], deadlines["owner_deadline_ns"]))
        return {"plan": plan, "sources": sources}

    @staticmethod
    def _units(case):
        rows = []
        for phase in case["phases"]:
            units = next(item for item in d._phase_units(case["operation_id"], case["phases"])
                         if item["phase"] == phase)
            for stage in ("bootstrap", "helper", "result_reader"):
                rows.append({"phase": phase, "stage": stage,
                             "unit": units[stage + "_unit"],
                             "invocation_id": hashlib.md5(
                                 (case["case_id"] + phase + stage).encode()).hexdigest()})
        return sorted(rows, key=lambda row: (row["phase"], row["stage"], row["unit"]))

    def _base_observations(self, case):
        empty = next(item for item in self.planned[case["case_id"]]
                     if item["role"] == "empty-ledger-gate")
        result = {"empty_ledger_gate": _ref(empty),
                  "resident_empty_gate": {"passed": True,
                    "candidate_commit": d.CANDIDATE["commit"], "resident_source_sha256": "5" * 64,
                    "accepted_operation_id": case["operation_id"], "accepted_event_seq": 1}}
        if case["index"] != 3:
            result["unit_identities"] = self._units(case)
        return result

    def _special(self, case, special):
        prefix = "cases/" + case["case_id"] + "/"
        rows = []
        owner_deadline = self._plan(case)["deadlines"]["owner_deadline_ns"]
        for suffix, role, mode in special:
            if role in ("phase-receipt", "recovery-proof"):
                continue
            raw = (d.canonical({"controller": {"deadline_ns": owner_deadline}}, newline=True)
                   if role == "launcher-reservation" else None)
            rows.append(_source(prefix + suffix, role, raw, mode))
        return rows

    def _plan(self, case):
        source = next(item for item in self.planned[case["case_id"]] if item["role"] == "plan")
        return d.document(source["raw"], limit=d.MEMBER_LIMIT)

    def run_h01(self, case, _prepared, plan):
        self.log.append(("run_h01", case["case_id"]))
        seal_id = "12345678-1234-4abc-8abc-123456789abc"
        sources = self._special(case, d._h01_special(seal_id))
        observations = self._base_observations(case)
        for key in d.H01_OBSERVATIONS:
            observations.setdefault(key, True)
        stop = {"requested": True, "acknowledged": True, "tree_exited": True,
                "writers_stopped": True, "deadline_ns": plan["deadlines"]["owner_deadline_ns"]}
        return {"sources": sources, "observations": observations, "stop": stop,
                "proof": None, "seal_id": seal_id,
                "summary": {"business_invocation_id": "6" * 32, "business_wait_status": 0}}

    def run_q4(self, case, _prepared, plan):
        self.log.append(("run_q4", case["case_id"]))
        sources = self._special(case, d.Q4_SPECIAL)
        observations = self._base_observations(case)
        false = {"chain_closed", "ordinary_phase_closed", "full_h07"}
        for key in d.Q4_OBSERVATIONS:
            observations.setdefault(key, key not in false)
        stop = {"requested": True, "acknowledged": True, "tree_exited": True,
                "writers_stopped": True, "deadline_ns": plan["deadlines"]["owner_deadline_ns"]}
        return {"sources": sources, "observations": observations, "stop": stop,
                "proof": None, "seal_id": None, "summary": {}}

    def recover_h11(self, case, _prepared, plan):
        self.log.append(("recover_h11", case["case_id"]))
        sources = self._special(case, d.H11_SPECIAL)
        by_role = {item["role"]: item for item in sources}
        by_suffix = {item["path"].split("/", 2)[-1]: item for item in sources}
        recovery_plan = dict(_ref(by_role["recovery-plan"]), embedded_plan_sha256="7" * 64)
        proof = {
            "schema": d.PROOF_SCHEMA, "session_id": d.SESSION, "index": 3,
            "case_id": case["case_id"],
            "candidate": {"commit": d.CANDIDATE["commit"], "tree": d.CANDIDATE["tree"],
                          "h11_source_path": "tests/e3_host/q4_h11_recovery.py",
                          "h11_source_sha256": "8" * 64,
                          "resident_source_path": "tests/e3_host/q2_resident.py",
                          "resident_source_sha256": "9" * 64,
                          "launcher_source_path": "tests/e3_host/q2_launcher.py",
                          "launcher_source_sha256": "a" * 64},
            "ledger_identity": {"path": plan["ledger_path"], "dev": 10, "ino": 20,
                                "unchanged": True},
            "recovery_plan": recovery_plan,
            "recovery_summary": _ref(by_role["recovery-summary"]),
            "launcher_result": _ref(by_role["launcher-result"]),
            "gateway_snapshot": _ref(by_role["gateway"]),
            "origin_capture": _ref(by_role["origin-capture"]),
            "control_seal": _ref(by_suffix["owner_output/seal.json"]),
            "result_identity": {"expected_path": "/evidence/result-f7b176ecb6b8081fac3a7a47.json",
                                "expected_basename": "result-f7b176ecb6b8081fac3a7a47.json",
                                "stat_performed": False, "opened": False, "hashed": False},
            "assertions": {
                "same_operation": True, "same_request_digest": True,
                "original_handle_admitted": True, "same_original_stage_units": True,
                "same_grant_and_deadlines": True, "leases_retained": True,
                "delivery_intents_unchanged": True, "recovery_launch_forbidden": True,
                "gateway_parts_unchanged": True, "recovery_barrier_count": 1,
                "quota_exit_pending_count": 1, "start_replayed": False,
                "result_reread": False, "deadline_extended": False,
                "future_start_blocked": True, "tree_exited": True, "writers_stopped": True,
                "collectors_stopped": False, "effects_checked": False, "outcome": "UNKNOWN",
                "business_evidence_sealed": False,
            },
        }
        observations = self._base_observations(case)
        for key in ("recovery_plan", "recovery_summary", "launcher_result", "gateway_snapshot",
                    "origin_capture", "ledger_identity", "result_identity"):
            observations[key] = proof[key]
        proof_raw = d.canonical(proof, newline=True)
        observations["recovery_proof"] = {"path": "cases/" + case["case_id"] +
            "/reservation/h11-recovery-proof.json", "bytes": len(proof_raw), "sha256": _sha(proof_raw)}
        true = {"original_request_accepted", "future_start_blocked", "tree_exited",
                "writers_stopped", "leases_retained", "control_closure_sealed"}
        false = {"collectors_stopped", "effects_checked", "result_reread", "start_replayed",
                 "business_evidence_sealed"}
        for key in true: observations[key] = True
        for key in false: observations[key] = False
        observations["outcome"] = "UNKNOWN"
        stop = {"requested": True, "acknowledged": True, "tree_exited": True,
                "writers_stopped": True, "deadline_ns": plan["deadlines"]["owner_deadline_ns"]}
        return {"sources": sources, "observations": observations, "stop": stop,
                "proof": proof, "seal_id": None, "summary": {}}

    def phase_facts(self, case, phase, plan, _sources):
        digest = hashlib.sha256((case["case_id"] + phase).encode()).hexdigest()
        owner = plan["deadlines"]["owner_deadline_ns"]
        return {"quota_request_id": "request-" + phase, "quota_request_sha256": digest,
                "query_unit": "lhqo-" + digest + ".service",
                "listener_unit": "lhqoc-" + digest + ".service",
                "admission_unit": "lhqoa-" + digest + ".service",
                "budget_deadline_ns": owner, "phase_deadline_ns": owner - 2 * d.NS,
                "stage_deadline_ns": owner - 3 * d.NS,
                "controller_deadline_ns": owner}

    def usage(self):
        return {"guest_elapsed_ns": self.tick * d.NS, "carrier_cpu_ns": d.NS,
                "carrier_memory_peak_bytes": 1024, "carrier_pids_peak": 1,
                "stdin_bytes_received": self.context["stdin_bytes_received"],
                "output_frame_bytes": 0, "guest_allocated_bytes": 4096,
                "guest_allocated_inodes": 10, "job_units_started": 15,
                "controller_units_started": 6, "quota_query_units_started": 5,
                "dynamic_quota_units_started": 15, "native_children_started": 16}


def test_exact_member_and_phase_raw_source_closures_include_launcher_reservation():
    assert [len(d.required_paths(case, seal_id=(
        "12345678-1234-4abc-8abc-123456789abc" if case["index"] == 1 else None)))
            for case in d.CASES] == [32, 21, 26]
    assert [len(d.phase_source_specs(case, phase)) for case in d.CASES
            for phase in case["phases"]] == [5, 5, 5, 5, 8]
    for case in d.CASES:
        for phase in case["phases"]:
            assert ("launcher_output/reservation.json", "launcher-reservation") in {
                (path.split("/", 2)[-1], role) for path, role in d.phase_source_specs(case, phase)}


def test_context_accepts_readonly_member_views_and_rejects_mutable_or_wrong_a_before_effects():
    value = context()
    assert d._validate_context(value) is value
    changed = context()
    changed["manifest"]["baseline"]["commit"] = "0" * 40
    effects = FakeEffects(changed)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_MANIFEST_AUTHORITY"):
        d.dispatch(changed, effects)
    assert effects.log == []
    mutable = context()
    mutable["members"]["field/loader.py"] = memoryview(bytearray(b"loader"))
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_PACKAGE_MEMBER"):
        d._validate_context(mutable)


def test_default_high_level_effects_are_explicitly_non_releasable():
    value = context()

    class OnlyClock(d.FieldEffects):
        def now(self):
            return {"boot_id": value["guest_deadlines"]["boot_id"],
                    "boottime_ns": value["hello"]["guest_boottime_origin_ns"] + d.NS,
                    "monotonic_ns": value["hello"]["guest_monotonic_origin_ns"] + d.NS}

    with pytest.raises(d.DispatchError, match="CORE_EFFECT_ADMISSION_POLICY_PREIMAGE_UNBOUND"):
        d.dispatch(value, OnlyClock(value))


def test_field_readiness_separates_unbound_inputs_from_unimplemented_code():
    value = d.field_readiness()
    assert value == {
        "schema": "local-hand-q2-core-field-readiness/v1",
        "scope": d.SCOPE,
        "releasable": False,
        "unbound_approved_inputs": [
            "admission.policy_expected_entities",
            "admission.historical_capacity_obligations",
            "preparation.retained_paths_and_domains",
        ],
        "unimplemented_effects": [
            "admission.current_guest_collector",
            "installation.protected_staging_and_native_build",
            "preparation.existing_account_completion",
            "execution.h01_normal",
            "execution.q4_running_cancel_subset",
            "execution.h11_same_ledger_recovery",
            "evidence.dynamic_phase_fact_extraction",
            "evidence.usage_and_peak_accounting",
        ],
    }


def test_outer_deadline_is_exactly_origin_plus_900_seconds():
    value = context()
    assert d._validate_context(value) is value
    for key in ("host_boottime_deadline_ns", "host_monotonic_deadline_ns"):
        changed = context()
        changed["bind"][key] += d.NS
        # The marker digest binds the BIND values, but deadline rejection must
        # occur before an altered marker can disguise a 901-second window.
        with pytest.raises(d.DispatchError, match="CORE_DISPATCH_OUTER_DEADLINE"):
            d._validate_context(changed)


def test_candidate_preparation_paths_are_absolute_and_keep_intent_relative():
    case = d.CASES[0]
    locators = {"state_parent": "/state", "quota_parent": "/quota",
                "journal_parent": "/journal", "evidence_parent": "/evidence"}
    resolved = d.FieldEffects.preparation_paths(case, locators)
    intent = d.build_intent(case)
    assert all(not row["relative_path"].startswith("/")
               for row in intent["planned_directories"])
    assert all(row["path"].startswith("/") for row in resolved["directories"].values())
    assert all(row["path"].startswith("/") for row in resolved["roots"])
    assert resolved["directories"]["journal"]["path"].startswith("/journal/")
    assert resolved["directories"]["profile_work"]["path"].startswith("/quota/")


def test_create_only_uses_held_parent_and_refuses_collision(tmp_path):
    parent = d.FieldEffects._held_directory(str(tmp_path))
    try:
        identity = d.FieldEffects.create_only_at(parent, "receipt.json", b"{}\n", mode=0o600)
        assert identity["bytes"] == 3
        assert identity["mode"] == 0o600
        with pytest.raises(FileExistsError):
            d.FieldEffects.create_only_at(parent, "receipt.json", b"{}\n", mode=0o600)
    finally:
        import os
        os.close(parent)


def test_deadline_gate_refuses_h01_intent_after_admission_install_without_refresh():
    value = context(guest_duration_ns=314 * d.NS)
    effects = FakeEffects(value)
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_CASE_GATE"):
        d.dispatch(value, effects)
    assert not any(row[:3] == ("persist", d.CASES[0]["case_id"], "intent")
                   for row in effects.log)


def test_plan_rejects_deadline_and_budget_replacement():
    value = context()
    effects = FakeEffects(value)
    case = d.CASES[0]
    intent = d.build_intent(case)
    deadlines = {"case_origin_ns": 10, "preparation_deadline_ns": 20,
                 "owner_deadline_ns": 30, "remote_final_deadline_ns": 40,
                 "carrier_deadline_ns": 50}
    plan = effects.plan_case(case, {}, deadlines)["plan"]
    assert d.validate_plan(case, intent, plan, deadlines) is plan
    changed = copy.deepcopy(plan); changed["deadlines"]["owner_deadline_ns"] += 1
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_PLAN_DEADLINE"):
        d.validate_plan(case, intent, changed, deadlines)
    changed = copy.deepcopy(plan); changed["budgets"]["operation"]["cpu_seconds"] += 1
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_PLAN_BINDING"):
        d.validate_plan(case, intent, changed, deadlines)


def test_full_injected_transcript_is_strictly_h01_then_q4_then_h11_and_frames_79_case_members():
    value = context()
    effects = FakeEffects(value)
    frame = d.dispatch(value, effects)
    assert frame.startswith(d.OUTPUT_MAGIC)
    length = struct.unpack(">Q", frame[len(d.OUTPUT_MAGIC):len(d.OUTPUT_MAGIC) + 8])[0]
    start = len(d.OUTPUT_MAGIC) + 8
    manifest = d.document(frame[start:start + length], limit=d.MANIFEST_LIMIT)
    assert manifest["remote_result"]["state"] == "REMOTE_FINALIZED"
    assert [row["status"] for row in manifest["cases"]] == ["PASS", "PASS", "PASS"]
    assert len(manifest["members"]) == 82
    assert [sum(row["case_id"] == case["case_id"] for row in manifest["members"])
            for case in d.CASES] == [32, 21, 26]
    h11 = [row for row in manifest["members"] if row["case_id"] == d.CASES[2]["case_id"]]
    assert sum(row["role"] == "recovery-plan" and row["mode"] == 420 for row in h11) == 1
    assert not ({"ledger", "result", "business-evidence-archive",
                 "business-evidence-manifest", "business-evidence-seal"} &
                {row["role"] for row in h11})
    operations = [row[0] for row in effects.log if row[0] in
                  ("run_h01", "run_q4", "recover_h11")]
    assert operations == ["run_h01", "run_q4", "recover_h11"]
    for previous, following in (("c01-h01-normal", "c02-q4-cancel"),
                                ("c02-q4-cancel", "c03-h11-recovery")):
        previous_verdict = next(i for i, row in enumerate(effects.log)
                                if row[:3] == ("persist", previous, "verdict"))
        following_intent = next(i for i, row in enumerate(effects.log)
                               if row[:3] == ("persist", following, "intent"))
        assert previous_verdict < following_intent


def test_h11_forbidden_business_result_and_deadline_extension_are_rejected():
    value = context()
    effects = FakeEffects(value)
    original = effects.recover_h11

    def forbidden(case, prepared, plan):
        outcome = original(case, prepared, plan)
        outcome["sources"].append(_source(
            "cases/c03-h11-recovery/business/result-f7b176ecb6b8081fac3a7a47.json", "result"))
        return outcome

    effects.recover_h11 = forbidden
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_PREVERDICT_SET"):
        d.dispatch(value, effects)

    value = context(); effects = FakeEffects(value)
    original_facts = effects.phase_facts

    def extended(case, phase, plan, sources):
        facts = original_facts(case, phase, plan, sources)
        if case["index"] == 3:
            facts["controller_deadline_ns"] += 1
        return facts

    effects.phase_facts = extended
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_CONTROLLER_DEADLINE"):
        d.dispatch(value, effects)

"""Three-phase declaration/budget selection and real create-only persistence.

Fixtures model protected ownership/program admission only. Journal bytes,
predecessor closure, immutable configuration prefixes and replay barriers are
real local files; these tests make no systemd, quota or Q3 host-success claim.
"""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from local_hand_jobs import bootstrap_roots, quota_contract as q, quota_grant as g
from local_hand_jobs.contract import JobError
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs.state import StateStore
from test_local_hand_jobs_policy import policy_fixture
from q2_fixtures import BOOT, SECOND, grant_data, query
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import q2_assembly as a, q2_chain as chain, q2_config as c
    from admin.local_hand_quota_observer import protected_inputs, q2_service
    from admin.local_hand_quota_observer.q2_journal import Journal
    from test_e3_quota_q2_assembly import SESSION, argv, declaration_template
    from test_e3_quota_q2_closure import complete
    from test_e3_quota_q2_runtime import fixture_open

PHASES = ("preflight", "business", "evidence")


def declaration_chain():
    first, _ = declaration_template()
    value = {key: copy.deepcopy(first[key]) for key in
             ("id", "installation", "original_budgets", "broker_generation", "journal")}
    value.update(schema="local-hand-q2-chain/v1", purpose="ISOLATED_Q2_THREE_PHASE", phases={})
    original = {}
    for index, phase in enumerate(PHASES):
        data = grant_data(number=index + 1, phase=phase, offset=20 if phase == "evidence" else 0)
        data["budget"]["reserved_boottime_ns"] = (1 + index * 10) * SECOND
        original[phase] = data.pop("budget")
        data.pop("predecessors")
        data["request"].pop("deadline_ns")
        data["management"].pop("issued_ns")
        data["management"]["storage_inodes"] = 11
        data["management"]["stop_ns"] = SECOND // 10
        for stage in data["management"]["stages"].values():
            stage["memory_bytes"] = 16 * 1024**2
        data["query_parent"] = copy.deepcopy(first["grant"]["query_parent"])
        data["management_parent"] = copy.deepcopy(first["grant"]["management_parent"])
        data["endpoint"]["path"] = "/synthetic/control/" + phase + ".sock"
        value["phases"][phase] = {
            "grant": data,
            "output": dict(path="/synthetic/" + phase + "-output", device=7, inode=330 + index),
            "service": dict(copy.deepcopy(first["service"]), control_path="/synthetic/control/" + phase + "-private.sock"),
            "peer": copy.deepcopy(first["peer"]),
        }
    return value, original


def decoded(value):
    raw = q._canonical(value, c.LIMIT)
    return chain.decode(raw, hashlib.sha256(raw).hexdigest())


def preparation(value, original, phase):
    return dict(preparation=dict(phase=phase, session=SESSION,
        budget=copy.deepcopy(original[phase]),
        allocation=copy.deepcopy(value["phases"][phase]["grant"]["allocation"]),
        generation=copy.deepcopy(value["broker_generation"])),
        observation=None, pending=None, closed=None)


def clock(phase):
    return dict(boot_id=BOOT, boottime_ns=(2 + PHASES.index(phase) * 10) * SECOND)


def policy_allocations(value, state):
    """Real Policy and durable broker allocator; only OS quota facts are synthetic."""
    config = policy_fixture("/synthetic/ordinary")
    config["source_commit"] = value["installation"]["source_commit"]
    config["process_manager"] = dict(uid=1234, slice="fixture.slice", cgroup="/sys/fs/cgroup/fixture")
    profile = config["profiles"]["fixture"]
    slots = []
    for phase in ("preflight", "evidence"):
        grant = value["phases"][phase]["grant"]
        slot_id = grant["allocation"]["slot_id"]
        slots.append(dict(slot_id=slot_id, roots={root["role"]: dict(
            path=profile[root["role"] + "_root"] + "/" + slot_id,
            **{key: root[key] for key in ("device", "inode", "uid")})
            for root in grant["roots"] if root["role"] != "retained_store"}))
    store = next(root for root in value["phases"]["evidence"]["grant"]["roots"] if root["role"] == "retained_store")
    profile["bootstrap_slots"] = slots
    profile["bootstrap_evidence_store"] = dict(path="/synthetic/ordinary/sealed",
        **{key: store[key] for key in ("device", "inode", "uid")})
    policy = Policy(config)
    profile = thaw(policy.profiles["fixture"])
    with state.transaction() as tx:
        row = state.insert(tx, "job", "fixture", "fixture", "owner", "request-digest", {},
            dict(execution=dict(roots={name: profile[name + "_root"] + "/fixture"
                for name in bootstrap_roots.ROOT_NAMES}), expected=dict(deployment_epoch=1)), 4096)
    for phase in PHASES:
        with state.transaction() as tx:
            allocation = bootstrap_roots.reserve(state, tx, row, phase, profile["bootstrap_slots"],
                extra_roots={"evidence_store": profile["bootstrap_evidence_store"]} if phase == "evidence" else None)
        grant = value["phases"][phase]["grant"]
        grant["allocation"] = allocation
        grant["request"].update(allocation_digest=allocation["allocation_id"], slot_ref=allocation["slot_id"])
    return policy


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux administrative chain")
class DeclarationTests(unittest.TestCase):
    def setUp(self):
        self.value, self.original = declaration_chain()

    def test_exact_three_phases_have_no_fabricated_future_budget_or_deadline(self):
        contract = decoded(self.value)
        self.assertEqual(self.value, contract.data())
        self.assertEqual(set(PHASES), set(contract.data()["phases"]))
        for phase in PHASES:
            view = chain.phase_template(contract, phase).data()
            self.assertEqual(self.value["phases"][phase]["grant"], view["grant"])
            self.assertEqual(self.value["original_budgets"], view["original_budgets"])
            self.assertEqual(self.value["journal"], view["journal"])
            self.assertNotIn("budget", view["grant"])
            self.assertNotIn("predecessors", view["grant"])
            self.assertNotIn("deadline_ns", view["grant"]["request"])
            self.assertNotIn("issued_ns", view["grant"]["management"])

    def test_missing_extra_phase_or_future_reservation_is_not_a_declaration(self):
        for fault in ("missing", "extra", "budget", "deadline", "issued", "predecessors", "schema", "purpose", "extra-field"):
            value = copy.deepcopy(self.value)
            target = value["phases"]["business"]["grant"]
            if fault == "missing": value["phases"].pop("evidence")
            elif fault == "extra": value["phases"]["reconcile"] = copy.deepcopy(value["phases"]["business"])
            elif fault == "budget": target["budget"] = self.original["business"]
            elif fault == "deadline": target["request"]["deadline_ns"] = 91 * SECOND
            elif fault == "issued": target["management"]["issued_ns"] = SECOND
            elif fault == "predecessors": target["predecessors"] = []
            elif fault == "schema": value["schema"] = "local-hand-q2-chain/v2"
            elif fault == "purpose": value["purpose"] = "PRODUCTION"
            else: value["command"] = ["arbitrary"]
            with self.subTest(fault=fault), self.assertRaises(ValueError): decoded(value)

    def test_phase_operation_authority_or_peer_substitution_is_rejected(self):
        for fault in ("phase", "namespace", "operation", "boot", "authority", "generation", "installation", "manifest", "peer", "query-parent", "management-parent", "request-id", "management-id"):
            value = copy.deepcopy(self.value)
            phase = value["phases"]["business"]; grant = phase["grant"]
            if fault == "phase": grant["request"]["phase"] = "evidence"
            elif fault == "namespace": grant["allocation"]["namespace"] = "reconcile"
            elif fault == "operation": grant["allocation"]["operation_id"] = "foreign"
            elif fault in ("authority", "installation", "manifest"):
                grant["request"][fault + "_digest"] = "f" * 64
            elif fault == "boot": grant["request"]["boot_id"] = "99999999-2222-3333-4444-555555555555"
            elif fault == "generation": grant["request"]["generation"] = "f" * 32
            elif fault == "peer": phase["peer"]["executable"]["inode"] += 1
            elif fault == "query-parent": grant["query_parent"]["inode"] += 1
            elif fault == "management-parent": grant["management_parent"]["inode"] += 1
            elif fault == "request-id": grant["request"]["request_id"] = value["phases"]["preflight"]["grant"]["request"]["request_id"]
            else: grant["management"]["id"] = value["phases"]["preflight"]["grant"]["management"]["id"]
            with self.subTest(fault=fault), self.assertRaises(ValueError): decoded(value)

    def test_full_declared_management_cost_is_charged_before_first_grant(self):
        contract = decoded(self.value)
        total = chain.declared_totals(contract)
        expected = dict.fromkeys(self.value["installation"]["capacity"]["management"], 0)
        for phase in PHASES:
            management = self.value["phases"][phase]["grant"]["management"]
            for key in expected:
                expected[key] += management[key] if key.startswith("storage_") else sum(item[key] for item in management["stages"].values())
        self.assertEqual(expected, total)
        for key, charged in expected.items():
            value = copy.deepcopy(self.value)
            capacity = value["installation"]["capacity"]
            capacity["management"][key] = charged - 1
            for phase in PHASES:
                value["phases"][phase]["grant"]["management"]["capacity_digest"] = g.digest(capacity)
            with self.subTest(resource=key), self.assertRaises(ValueError): decoded(value)
        for phase in PHASES:
            value = copy.deepcopy(self.value)
            value["phases"][phase]["grant"]["management"]["stages"]["query"]["runtime_ns"] = 30 * SECOND
            with self.subTest(impossible_phase=phase), self.assertRaisesRegex(ValueError, "CHAIN_MANAGEMENT_DEADLINE"):
                decoded(value)

    def test_shared_business_allocation_and_explicit_retained_root_are_required(self):
        for fault in ("business-slot", "business-root", "retained-root", "retained-path"):
            value = copy.deepcopy(self.value)
            if fault == "business-slot": value["phases"]["business"]["grant"]["allocation"]["allocation_id"] = "f" * 64
            elif fault == "business-root": value["phases"]["business"]["grant"]["roots"][0]["inode"] += 1
            elif fault == "retained-root": value["phases"]["evidence"]["grant"]["roots"][-1]["inode"] += 1
            else: value["phases"]["evidence"]["grant"]["allocation"]["retained_paths"][0] = "/synthetic/foreign"
            with self.subTest(fault=fault), self.assertRaises(ValueError): decoded(value)

    def test_independent_store_cannot_alias_consumed_preflight_path_inode_or_domain(self):
        for fault in ("path", "inode", "domain"):
            value = copy.deepcopy(self.value)
            old = value["phases"]["preflight"]["grant"]
            target = value["phases"]["evidence"]["grant"]
            kept = next(root for root in target["roots"] if root["role"] == "retained_store")
            allocation = target["allocation"]
            if fault == "domain":
                kept["project_id"] = old["roots"][0]["project_id"]
            elif fault == "inode":
                kept["inode"] = old["roots"][0]["inode"]
                allocation["paths"][allocation["retained_paths"][0]]["inode"] = kept["inode"]
            else:
                identity = allocation["paths"].pop(allocation["retained_paths"][0])
                reused = old["allocation"]["roots"]["work"]
                allocation["retained_paths"] = [reused]
                allocation["paths"][reused] = identity
            allocation["allocation_id"] = bootstrap_roots._allocation_id("job", "fixture", allocation["slot_id"],
                allocation["roots"], allocation["paths"])
            allocation["grant_digest"] = bootstrap_roots._digest({key: item for key, item in allocation.items() if key != "grant_digest"})
            target["request"]["allocation_digest"] = allocation["allocation_id"]
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, "RESOURCE_CONSUMED"):
                decoded(value)

    def test_evidence_store_can_share_consistent_domain_with_same_phase_fresh_root(self):
        target = self.value["phases"]["evidence"]["grant"]
        target["roots"][-1]["project_id"] = target["roots"][0]["project_id"]
        contract = decoded(self.value)
        self.assertEqual(target["roots"], contract.data()["phases"]["evidence"]["grant"]["roots"])

    def test_real_policy_allocations_bind_exact_store_slot_and_source(self):
        with tempfile.TemporaryDirectory() as root:
            state = StateStore(Path(root) / "state.sqlite", "authority", "ledger", initialize=True)
            self.addCleanup(state.close)
            policy = policy_allocations(self.value, state)
            contract = decoded(self.value)
            chain.check_policy(contract, policy, "fixture")
            for fault in ("path", "inode", "slot-inode", "source", "uid"):
                changed = thaw(policy.config)
                profile = changed["profiles"]["fixture"]
                if fault == "path": profile["bootstrap_evidence_store"]["path"] += "-other"
                elif fault == "inode": profile["bootstrap_evidence_store"]["inode"] += 1000
                elif fault == "slot-inode": profile["bootstrap_slots"][0]["roots"]["work"]["inode"] += 1000
                elif fault == "source": changed["source_commit"] = "f" * 40
                else:
                    changed["process_manager"]["uid"] += 1
                    for slot in profile["bootstrap_slots"]:
                        for binding in slot["roots"].values(): binding["uid"] += 1
                    profile["bootstrap_evidence_store"]["uid"] += 1
                changed_policy = Policy(changed)
                with self.subTest(fault=fault), self.assertRaises(ValueError):
                    chain.check_policy(contract, changed_policy, "fixture")
            aliased = thaw(policy.config)
            profile = aliased["profiles"]["fixture"]
            profile["bootstrap_evidence_store"] = copy.deepcopy(profile["bootstrap_slots"][0]["roots"]["work"])
            with self.assertRaises(JobError): Policy(aliased)

    def test_output_journal_root_and_socket_aliases_are_rejected(self):
        for fault in ("outputs", "journal", "evidence", "root", "socket", "control"):
            value = copy.deepcopy(self.value)
            target = value["phases"]["business"]
            if fault == "outputs": target["output"] = copy.deepcopy(value["phases"]["preflight"]["output"])
            elif fault == "journal": target["output"] = copy.deepcopy(value["journal"])
            elif fault == "evidence": target["output"] = copy.deepcopy(value["installation"]["evidence"])
            elif fault == "root": target["output"]["path"] = target["grant"]["allocation"]["roots"]["work"] + "/config"
            elif fault == "socket": target["grant"]["endpoint"]["path"] = value["phases"]["preflight"]["grant"]["endpoint"]["path"]
            else: target["service"]["control_path"] = target["grant"]["endpoint"]["path"]
            with self.subTest(fault=fault), self.assertRaises(ValueError): decoded(value)

    def test_current_preflight_copies_original_budget_and_allocation_without_renewal(self):
        contract = decoded(self.value)
        snap = preparation(self.value, self.original, "preflight")
        first = chain.build_grant(contract, snap, session=SESSION, clock=clock("preflight"))
        later = chain.build_grant(contract, snap, session=SESSION, clock=dict(clock("preflight"), boottime_ns=3*SECOND))
        self.assertEqual(self.original["preflight"], first.as_dict()["budget"])
        self.assertEqual(self.value["phases"]["preflight"]["grant"]["allocation"], first.as_dict()["allocation"])
        self.assertEqual([], first.as_dict()["predecessors"])
        self.assertEqual(30*SECOND, first.request.as_dict()["deadline_ns"])
        self.assertEqual(first.request.as_dict()["deadline_ns"], later.request.as_dict()["deadline_ns"])
        self.assertEqual(self.value, contract.data())

    def test_snapshot_budget_allocation_session_generation_and_started_state_are_exact(self):
        for fault in ("budget", "limits", "operation", "allocation", "session", "generation", "started", "observation", "pending", "closed"):
            snap = preparation(self.value, self.original, "preflight")
            prep = snap["preparation"]
            if fault == "budget": prep["budget"]["budget_digest"] = "f" * 64
            elif fault == "limits": prep["budget"]["limits"]["cpu_seconds"] += 1
            elif fault == "operation": prep["budget"]["operation_id"] = "foreign"
            elif fault == "allocation": next(iter(prep["allocation"]["paths"].values()))["inode"] += 1
            elif fault == "session": prep["session"] = "b" * 64
            elif fault == "generation": prep["generation"] = [1, 2]
            elif fault == "started": prep["budget"]["started_boottime_ns"] += 1
            else: snap[fault] = {}
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                chain.build_grant(decoded(self.value), snap, session=SESSION, clock=clock("preflight"))

    def test_later_phase_cannot_skip_immutable_predecessor_configs(self):
        for phase in ("business", "evidence"):
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                chain.build_grant(decoded(self.value), preparation(self.value, self.original, phase), session=SESSION, clock=clock(phase))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux real create-only chain journal")
class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.home())
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.value, self.original = declaration_chain()

        def pin(path):
            info = path.stat()
            return dict(path=str(path), device=info.st_dev, inode=info.st_ino)

        for name in ("journal", "evidence_store", *PHASES):
            path = self.root / name
            path.mkdir(mode=0o700)
            if name == "journal": self.value[name] = pin(path)
            elif name == "evidence_store": self.value["installation"]["evidence"] = pin(path)
            else: self.value["phases"][name]["output"] = pin(path)
        executable = self.root / "python"
        executable.write_bytes(b"synthetic executable")
        executable.chmod(0o755)
        script = self.root / "runner.py"
        script.write_bytes(b"# synthetic pinned runner\n")
        for phase in PHASES:
            self.value["phases"][phase]["peer"]["executable"] = pin(executable)
            self.value["phases"][phase]["peer"]["runner"] = dict(
                path=str(script), sha256=hashlib.sha256(script.read_bytes()).hexdigest())
        self.contract = decoded(self.value)
        self.configs = []
        self.current_clock = clock("preflight")
        # Model administrator ownership and ELF pin qualification only.
        # Actual file identity, nofollow, O_EXCL, journal bytes, transitions,
        # immutable prior configuration reads and fsync remain exercised.
        patches = [mock.patch.object(a, "_administrator"),
            mock.patch.object(c, "open_protected", side_effect=fixture_open),
            mock.patch.object(protected_inputs, "open_protected", side_effect=fixture_open),
            mock.patch.object(q2_service, "_clock", side_effect=lambda:
                dict(boot_id=self.current_clock["boot_id"], ns=self.current_clock["boottime_ns"])),
            mock.patch.object(c, "load", side_effect=lambda path, digest:
                c.decode(Path(path).read_bytes(), path, digest))]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def build(self, phase, *, previous=None, snap=None):
        return chain.build_grant(self.contract,
            preparation(self.value, self.original, phase) if snap is None else snap,
            previousconfigs=tuple(self.configs) if previous is None else previous,
            session=SESSION, clock=clock(phase))

    def install(self, phase, *, previous=None):
        self.current_clock = clock(phase)
        prior = tuple(self.configs) if previous is None else previous
        grant = self.build(phase, previous=prior)
        view = chain.phase_template(self.contract, phase).data()
        return chain.install(self.contract, grant, bootstrap_argv=argv(view, grant),
            previousconfigs=prior, session=SESSION, clock=clock(phase))["config"]

    def close_phase(self, cfg):
        grant = cfg.active()
        proof, _, receipt, peer = complete(grant)
        data = cfg.data()
        journal = Journal(data["journal"]["path"], data["journal"]["pin"], data["capacity"], list(cfg.grants().values()))
        try:
            key = grant.request.as_dict()["request_id"]
            with journal.locked():
                journal.append(key, "INTENT", dict(request_digest=grant.request.digest,
                    peer=peer, reserved_ns=grant.as_dict()["management"]["issued_ns"]))
                journal.append(key, "INVOCATION", query(grant))
                journal.append(key, "RESULT", dict(receipt=receipt.as_dict(), received_ns=proof["closed_ns"]))
                journal.append(key, "CLOSED", proof)
                self.assertEqual("CLOSED", journal.scan()[key]["status"])
        finally:
            journal.close()

    def advance(self, phase):
        cfg = self.install(phase)
        self.close_phase(cfg)
        self.configs.append(cfg)
        return cfg

    def retained(self):
        return {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def test_all_three_phases_use_one_journal_and_cumulative_immutable_prefix(self):
        original_configs = {}
        previous_keys = []
        first_pin = None
        for phase in PHASES:
            cfg = self.advance(phase)
            data = cfg.data()
            active = cfg.active().as_dict()
            self.assertEqual(self.original[phase], active["budget"])
            self.assertEqual(self.value["phases"][phase]["grant"]["allocation"], active["allocation"])
            self.assertEqual(previous_keys, active["predecessors"])
            previous_keys.append(active["request"]["request_id"])
            self.assertEqual(set(previous_keys), set(data["grants"]))
            self.assertEqual(set(previous_keys), set(data["peers"]))
            self.assertEqual(str(self.root / "journal"), data["journal"]["path"])
            if first_pin is None: first_pin = copy.deepcopy(data["journal"]["pin"])
            else:
                self.assertEqual(first_pin["directory"], data["journal"]["pin"]["directory"])
                for name, pin in first_pin["files"].items():
                    self.assertEqual(pin, data["journal"]["pin"]["files"][name])
            for old, raw in original_configs.items(): self.assertEqual(raw, Path(old).read_bytes())
            original_configs[cfg.path] = Path(cfg.path).read_bytes()
        self.assertEqual(3, len(original_configs))
        self.assertEqual(3, len(list((self.root / "journal").glob("*.cell"))))

    def test_policy_admitted_durable_allocations_complete_three_phase_chain(self):
        state = StateStore(self.root / "broker.sqlite", "authority", "ledger", initialize=True)
        self.addCleanup(state.close)
        policy = policy_allocations(self.value, state)
        self.contract = decoded(self.value)
        chain.check_policy(self.contract, policy, "fixture")
        for phase in PHASES:
            config = self.advance(phase)
            allocation = config.active().as_dict()["allocation"]
            with state.transaction() as tx:
                bootstrap_roots.assert_reserved(tx, allocation)
            original = state.get("job", "fixture")["record"]["bootstrap_grants"][phase]
            self.assertEqual(original, allocation)
        evidence = self.configs[-1].active().as_dict()["allocation"]
        self.assertEqual([policy.profiles["fixture"]["bootstrap_evidence_store"]["path"]], evidence["retained_paths"])
        self.assertEqual(3, len(list((self.root / "journal").glob("*.cell"))))

    def test_unclosed_predecessor_cannot_enroll_or_create_next_observer(self):
        first = self.install("preflight")
        self.configs.append(first)
        before = self.retained()
        with self.assertRaises(ValueError): self.install("business")
        after = self.retained()
        self.assertEqual(before, {name: after[name] for name in before})
        self.assertTrue((self.root / "business" / "reservation.json").exists())
        self.assertFalse((self.root / "business" / "observer.json").exists())
        self.assertEqual(1, len(list((self.root / "journal").glob("*.cell"))))
        with self.assertRaises(ValueError): self.install("business")
        self.assertEqual(after, self.retained())

    def test_missing_reordered_or_duplicate_prior_config_prefix_is_rejected(self):
        first = self.advance("preflight")
        second = self.advance("business")
        # Individually decodable configs are insufficient when the later
        # declaration omits or changes an already committed prefix entry.
        truncated = second.data()
        first_key = first.active().request.as_dict()["request_id"]
        truncated["grants"].pop(first_key)
        truncated["peers"].pop(first_key)
        truncated["journal"]["pin"]["files"].pop(first_key + ".cell")
        wire = q._canonical(truncated, c.LIMIT)
        omitted = c.decode(wire, second.path, hashlib.sha256(wire).hexdigest())
        altered = second.data()
        altered["peers"][first_key]["command_sha256"] = "f" * 64
        wire = q._canonical(altered, c.LIMIT)
        changed = c.decode(wire, second.path, hashlib.sha256(wire).hexdigest())
        before = self.retained()
        for prior in ((), (second,), (first,), (second, first), (first, first),
                      (first, second, second), (first, omitted), (first, changed)):
            with self.subTest(prefix=[item.path for item in prior]), self.assertRaises(ValueError):
                self.build("evidence", previous=prior)
        self.assertEqual(before, self.retained())

    def test_changed_protected_prior_configuration_cannot_be_reused(self):
        first = self.advance("preflight")
        original = Path(first.path).read_bytes()
        Path(first.path).write_bytes(original + b"\n")
        before = self.retained()
        with self.assertRaises(ValueError): self.install("business")
        self.assertEqual(before, self.retained())
        self.assertEqual([], list((self.root / "business").iterdir()))

    def test_later_phase_cannot_renew_operation_budget_or_replace_original_session(self):
        self.advance("preflight")
        before = self.retained()
        snap = preparation(self.value, self.original, "business")
        # This pair remains valid against original_budgets in isolation, but
        # would renew the operation's original clock boundary across phases.
        snap["preparation"]["budget"]["started_boottime_ns"] += SECOND
        snap["preparation"]["budget"]["deadline_boottime_ns"] += SECOND
        with self.assertRaisesRegex(ValueError, "ORIGINAL_BUDGET_CHANGED"):
            self.build("business", snap=snap)
        self.assertEqual(before, self.retained())

        session = "b" * 64
        snap = preparation(self.value, self.original, "business")
        snap["preparation"]["session"] = session
        grant = chain.build_grant(self.contract, snap, previousconfigs=tuple(self.configs),
            session=session, clock=clock("business"))
        view = chain.phase_template(self.contract, "business").data()
        with self.assertRaisesRegex(ValueError, "CHAIN_RESERVATION_CHANGED"):
            chain.install(self.contract, grant, bootstrap_argv=argv(view, grant),
                previousconfigs=tuple(self.configs), session=session, clock=clock("business"))
        self.assertEqual(before, self.retained())
        self.assertEqual([], list((self.root / "business").iterdir()))

    def test_same_phase_replay_retains_existing_config_cell_and_reservation(self):
        first = self.advance("preflight")
        before = self.retained()
        with self.assertRaises(ValueError): self.install("preflight", previous=())
        self.assertEqual(before, self.retained())
        self.assertEqual(first.wire, Path(first.path).read_bytes())

    def test_fsync_failure_keeps_consumed_reservation_and_prevents_retry(self):
        real_fsync = a.os.fsync
        calls = []
        def fail(fd):
            calls.append(fd)
            if len(calls) == 1: raise OSError("synthetic chain fsync failure")
            return real_fsync(fd)
        with mock.patch.object(a.os, "fsync", side_effect=fail), self.assertRaises(OSError):
            self.install("preflight")
        self.assertTrue((self.root / "preflight" / "reservation.json").exists())
        before = self.retained()
        with self.assertRaises(ValueError): self.install("preflight")
        self.assertEqual(before, self.retained())

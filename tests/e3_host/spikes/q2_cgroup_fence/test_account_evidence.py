"""Pure synthetic account receipts; never call useradd, NSS or the live observer."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

_SPEC = importlib.util.spec_from_file_location("h07_account_evidence_tests", Path(__file__).with_name("account_evidence.py"))
assert _SPEC and _SPEC.loader
account = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(account)

NAME = "q2hf123456r2"


def make_observation(kind="pair", *, expected=False, conflicts=None):
    identity = {"name": NAME, "uid": 991, "gid": 991, "home": "/nonexistent",
                "shell": "/usr/sbin/nologin", "supplementary_gids": [991], "group_member_count": 0}
    group = {"name": NAME, "gid": 991, "member_count": 0}
    if kind == "absent":
        identity = group = None
    elif kind == "group":
        identity = None
    return {"schema_version": 1, "target": NAME, "expected_uid": 991 if expected else None,
            "expected_gid": 991 if expected else None,
            "classification": {"pair": "EXACT_PAIR", "absent": "ABSENT_BOTH", "group": "PARTIAL"}[kind],
            "complete": True, "reason": None,
            "sources": [{"path": path, "dev": 1, "ino": n + 1, "size": 10, "mtime_ns": 1,
                         "ctime_ns": 1, "sha256": "a" * 64} for n, path in enumerate(account.SOURCE_LIMITS)],
            "providers": {"passwd": ["files"], "group": ["files"], "initgroups": ["files"]},
            "identity": identity, "group": group,
            "conflicts": conflicts or {"uid_aliases": 0, "gid_aliases": 0, "other_primary_refs": 0, "group_members": 0},
            "nss_match": True, "stable": True,
            "clocks": {"start_mono_ns": 110, "start_boot_ns": 110, "end_mono_ns": 120, "end_boot_ns": 120}}


def make_audit(role, seq, raw=b"", rc=0, **changes):
    audit = {"command_id": "123456-2-" + str(seq), "role": role, "attempted": True,
             "started": True, "exit_observed": True, "rc": rc, "timeout": False,
             "termination_requested": False,
             "stdout": {"eof": True, "complete": True, "bytes": len(raw), "sha256": account._sha(raw)},
             "stderr": {"eof": True, "complete": True, "bytes": 0, "sha256": account.EMPTY_SHA},
             "deadline_met": True, "pending": False,
             "start_mono_ns": 100, "start_boot_ns": 100, "deadline_mono_ns": 150,
             "deadline_boot_ns": 150, "end_mono_ns": 130, "end_boot_ns": 130}
    audit.update(changes)
    for key in ("start_mono_ns", "start_boot_ns", "deadline_mono_ns", "deadline_boot_ns", "end_mono_ns", "end_boot_ns"):
        audit[key] += seq * 1000
    return audit


def make_tools():
    return [{"path": path, "sha256": "b" * 64, "size": 12, "version": None,
             "version_basis": "not_invoked", "dev": 1, "ino": n + 1, "mtime_ns": 1, "ctime_ns": 1}
            for n, path in enumerate(account.TOOLS)]


class FakeFixture:
    def __init__(self, observations=None, changes=None):
        self.account, self.run_id, self.round = NAME, "123456", 2
        self.account_id, self.account_attempted = None, False
        self.facts = {"account": None}
        self.pending_commands = []
        self.account_commands_blocked = False
        self.calls = []
        self.observations = observations or {
            "pre_create": make_observation("absent"), "post_create": make_observation(),
            "pre_cleanup": make_observation(expected=True),
            "post_userdel": make_observation("group", expected=True),
            "post_groupdel": make_observation("absent", expected=True)}
        self.changes = changes or {}

    def observer_deadline(self, parent):
        return parent

    def audit_command(self, argv, deadline, *, role, stdout_limit, cleanup):
        self.calls.append((role, argv, cleanup))
        raw = b""
        if role in account.PHASES:
            observation = copy.deepcopy(self.observations[role])
            for key in observation["clocks"]:
                observation["clocks"][key] += len(self.calls) * 1000
            raw = json.dumps(observation, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"
        audit = make_audit(role, len(self.calls), raw, **self.changes.get(role, {}))
        self.last_command_audit = audit
        return audit["rc"], raw, audit


@pytest.fixture
def deadline():
    return SimpleNamespace(check=lambda: None)


@pytest.fixture(autouse=True)
def no_live_tools(monkeypatch):
    monkeypatch.setattr(account, "pin_tools", make_tools)
    monkeypatch.setattr(account, "_open_sources", lambda: pytest.fail("no live source access"))
    monkeypatch.setattr(account, "_Resolver", lambda: pytest.fail("no live NSS"))


def successful_setup(deadline, monkeypatch=None, *, group_deleted=False):
    fake = FakeFixture()
    if group_deleted:
        fake.observations["post_userdel"] = make_observation("absent", expected=True)
    life = account.AccountLifecycle(fake)
    life.create(deadline)
    assert life.cleanup(deadline) == (True, [])
    return fake, life


def test_successful_ownership_and_exact_five_observation_cleanup(deadline):
    fake, life = successful_setup(deadline)
    assert len(life.record["observations"]) == 5
    assert account.validate_account_setup(life.record, run={"id": "123456", "attempt": 1, "round": 2},
                                          fixture_account=fake.facts["account"], cleanup={"verified": True}) == []
    facts = account.account_setup_facts(life.record)
    assert facts["admitted"] and facts["cleanup_verified"] and facts["diagnostic_bytes"] > 0
    assert fake.account_id == (991, 991)
    argv = next(argv for role, argv, _ in fake.calls if role == "useradd")
    assert argv == ["/usr/sbin/useradd", "--system", "--user-group", "--no-create-home", "--no-log-init",
                    "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin", NAME]
    assert all("--remove" not in argv and "-r" not in argv for _, argv, _ in fake.calls)
    assert next(argv for role, argv, _ in fake.calls if role == "post_userdel")[-4:] == ["--uid", "991", "--gid", "991"]


def test_userdel_already_removed_group_uses_only_four_observations(deadline):
    fake, life = successful_setup(deadline, group_deleted=True)
    assert "groupdel" not in [role for role, _, _ in fake.calls]
    assert len(life.record["observations"]) == 4
    assert account.validate_account_setup(life.record) == []


@pytest.mark.parametrize("kind", ["pair", "group", "absent"])
def test_nonzero_creation_never_grants_delete_even_when_pair_exists(deadline, kind):
    fake = FakeFixture(changes={"useradd": {"rc": 3}})
    fake.observations["post_create"] = make_observation(kind)
    life = account.AccountLifecycle(fake)
    with pytest.raises(account.AccountEvidenceError, match="account_creation_not_confirmed"):
        life.create(deadline)
    assert fake.account_id is None and life.record["admitted_identity"] is None
    assert life.record["observed_identity"] == fake.observations["post_create"]["identity"]
    assert life.cleanup(deadline)[0] is False
    assert [role for role, _, _ in fake.calls] == ["pre_create", "useradd", "post_create"]
    assert account.validate_account_setup(life.record, fixture_account={}) == []
    life.record["cleanup_verified"] = True
    assert account.validate_account_setup(life.record)


def test_partial_capture_does_not_establish_admission(deadline):
    stream = {"eof": True, "complete": False, "bytes": 0, "sha256": account.EMPTY_SHA}
    fake = FakeFixture(changes={"useradd": {"stderr": stream}})
    life = account.AccountLifecycle(fake)
    with pytest.raises(account.AccountEvidenceError, match="account_creation_not_confirmed"):
        life.create(deadline)
    assert life.record["admitted_identity"] is None
    assert life.cleanup(deadline)[0] is False
    assert account.validate_account_setup(life.record) == []


def test_unresolved_original_observer_stops_all_further_actions(deadline):
    stream = {"eof": False, "complete": False, "bytes": 0, "sha256": account.EMPTY_SHA}
    fake = FakeFixture(changes={"pre_create": {"exit_observed": False, "rc": None,
                                               "pending": True, "stderr": stream}})
    life = account.AccountLifecycle(fake)
    with pytest.raises(account.AccountEvidenceError, match="observer_capture_incomplete"):
        life.create(deadline)
    assert len(fake.calls) == 1 and not fake.account_attempted
    assert life.cleanup(deadline)[0] is False
    assert account.validate_account_setup(life.record) == []
    assert account.validate_account_setup(life.record, cleanup={"verified": True})


@pytest.mark.parametrize("phase,mutation", [
    ("post_create", lambda row: row["identity"].update(home="/home/other")),
    ("post_create", lambda row: row["identity"].update(supplementary_gids=[991, 5])),
    ("post_create", lambda row: row["conflicts"].update(uid_aliases=1)),
    ("pre_cleanup", lambda row: row["identity"].update(uid=992)),
    ("pre_cleanup", lambda row: row["conflicts"].update(other_primary_refs=1)),
    ("post_userdel", lambda row: row["conflicts"].update(gid_aliases=1)),
    ("post_userdel", lambda row: row["conflicts"].update(other_primary_refs=1)),
])
def test_identity_or_shared_object_never_guessed_away(deadline, phase, mutation):
    fake = FakeFixture()
    mutation(fake.observations[phase])
    life = account.AccountLifecycle(fake)
    if phase == "post_create":
        with pytest.raises(account.AccountEvidenceError):
            life.create(deadline)
        assert fake.account_id is None
    else:
        life.create(deadline)
    assert not life.cleanup(deadline)[0]
    assert "groupdel" not in [role for role, _, _ in fake.calls]
    if phase == "pre_cleanup":
        assert "userdel" not in [role for role, _, _ in fake.calls]
    assert account.validate_account_setup(life.record) == []


def test_zero_userdel_without_postcheck_is_not_cleanup(deadline):
    fake = FakeFixture(changes={"post_userdel": {"rc": 3}})
    life = account.AccountLifecycle(fake)
    life.create(deadline)
    assert not life.cleanup(deadline)[0]
    assert life.record["cleanup_verified"] is False
    assert account.validate_account_setup(life.record) == []


def raw_sources(nss=b"passwd: files systemd\ngroup: files systemd\n", passwd=b"root:x:0:0::/root:/bin/bash\n", group=b"root:x:0:\n"):
    return {"/etc/nsswitch.conf": nss, "/etc/passwd": passwd, "/etc/group": group}


@pytest.mark.parametrize("nss", [b"passwd: files ldap\ngroup: files\n", b"passwd: files [SUCCESS=return]\ngroup: files\n",
                                 b"passwd: files\npasswd: files\ngroup: files\n", b"passwd: files\ngroup: files\ninitgroups: sss\n",
                                 b"passwd: files\ngroup: files systemd\ninitgroups: files\n", b"group: files\n"])
def test_provider_rejections_are_before_any_nss(nss):
    with pytest.raises(account.AccountEvidenceError):
        account.parse_sources(raw_sources(nss=nss))


@pytest.mark.parametrize("key,raw", [("/etc/passwd", b"x" * 262145), ("/etc/nsswitch.conf", b"x" * 16385),
                                    ("/etc/passwd", b"root:x:0:0::/:/bin/sh\nroot:x:1:1::/:/bin/sh\n"),
                                    ("/etc/group", b"group:x:1:other,other\n"),
                                    ("/etc/passwd", b"bad:x:true:1::/:/bin/sh\n")])
def test_local_source_limits_and_malformed_rows(key, raw):
    inputs = raw_sources()
    inputs[key] = raw
    with pytest.raises(account.AccountEvidenceError):
        account.parse_sources(inputs)


def test_exact_point_queries_and_local_alias_counts_without_nss_enumeration():
    providers, users, groups = account.parse_sources(raw_sources(
        passwd=(f"{NAME}:x:991:991::/nonexistent:/usr/sbin/nologin\nother:x:991:991::/none:/bin/false\n").encode(),
        group=(f"{NAME}:x:991:\nalias:x:991:\n").encode()))
    calls = []
    def take(name, value):
        calls.append(name)
        return value
    resolver = SimpleNamespace(user_name=lambda _: take("getpwnam", users[0]),
                               group_name=lambda _: take("getgrnam", groups[0]),
                               user_id=lambda _: take("getpwuid", users[0]),
                               group_id=lambda _: take("getgrgid", groups[0]),
                               memberships=lambda *_: take("getgrouplist", [991]))
    result = account._target_facts(NAME, None, None, providers, users, groups, resolver)
    assert calls == ["getpwnam", "getgrnam", "getpwuid", "getgrgid", "getgrouplist"]
    assert result["conflicts"] == {"uid_aliases": 1, "gid_aliases": 1, "other_primary_refs": 1, "group_members": 0}
    assert "other" not in json.dumps(result) .replace("other_primary_refs", "")


def test_postdelete_uses_original_ids_for_remaining_local_aliases():
    providers, users, groups = account.parse_sources(raw_sources(passwd=b"alias:x:991:991::/:/bin/sh\n", group=b"alias:x:991:\n"))
    resolver = SimpleNamespace(user_name=lambda _: None, group_name=lambda _: None)
    result = account._target_facts(NAME, 991, 991, providers, users, groups, resolver)
    assert result["classification"] == "ABSENT_BOTH"
    assert result["conflicts"]["uid_aliases"] == result["conflicts"]["other_primary_refs"] == 1


@pytest.mark.parametrize("mutate", [
    lambda rec: rec.update(extra=True), lambda rec: rec.update(assumptions=None),
    lambda rec: rec.update(tools=None), lambda rec: rec.update(observations=None),
    lambda rec: rec.update(round=True), lambda rec: rec.update(cleanup_verified=False),
    lambda rec: rec.update(failure="retained_failure"),
    lambda rec: rec["observations"][0]["audit"].update(deadline_met=False),
    lambda rec: rec["observations"][0]["audit"].update(command_id="123456-2-2"),
    lambda rec: rec["observations"][0]["observation"].update(complete=False),
    lambda rec: rec["admitted_identity"].update(uid=0),
    lambda rec: rec["observations"][-1]["observation"].update(expected_uid=None),
    lambda rec: rec["observations"][1]["audit"].update(start_boot_ns=1),
])
def test_receipt_forgery_and_malformed_shapes_rejected_without_crash(deadline, mutate):
    _, life = successful_setup(deadline)
    value = copy.deepcopy(life.record)
    mutate(value)
    assert account.validate_account_setup(value)
    assert account.account_setup_facts(value)["admitted"] is False


def test_audit_timeout_and_dual_clock_boundary_are_not_normal_exit():
    audit = make_audit("pre_create", 1, timeout=True, end_boot_ns=151, deadline_met=False)
    assert account.validate_audit(audit) == []
    assert not account._complete(audit)
    audit["deadline_met"] = True
    assert account.validate_audit(audit)
    audit = make_audit("pre_create", 1, deadline_boot_ns=2_000_000_101)
    assert account.validate_audit(audit)


@pytest.mark.parametrize("argv", [[], ["--observe", "root"], ["--observe", NAME, "--path", "/tmp/x"],
                                   ["--observe", NAME, "--uid", "-1", "--gid", "1"],
                                   ["--observe", NAME, "--uid", "4294967295", "--gid", "1"]])
def test_internal_cli_has_no_arbitrary_paths_or_commands(argv):
    assert account.main(argv) == 2


def test_duplicate_json_and_nonfinite_rejected():
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
        with pytest.raises(account.AccountEvidenceError):
            account._json(raw)


def test_incomplete_observation_cannot_smuggle_unknown_nested_fields():
    row = make_observation()
    row.update(complete=False, stable=False, classification="AMBIGUOUS", reason="source_changed")
    assert account.validate_observation(row) == []
    row["identity"]["extra"] = "not admitted"
    assert account.validate_observation(row)


def test_invalid_observer_json_retains_parse_failure(deadline):
    fake = FakeFixture()
    raw = b'{"duplicate":1,"duplicate":2}'
    def capture(argv, deadline, *, role, **kwargs):
        fake.calls.append((role, argv, False))
        audit = make_audit(role, len(fake.calls), raw)
        fake.last_command_audit = audit
        return 0, raw, audit
    fake.audit_command = capture
    life = account.AccountLifecycle(fake)
    with pytest.raises(account.AccountEvidenceError, match="observer_json_invalid"):
        life.create(deadline)
    assert life.record["failure"] == "observer_json_invalid"
    assert not fake.account_attempted and len(fake.calls) == 1
    assert account.validate_account_setup(life.record) == []

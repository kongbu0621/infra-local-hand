import base64
import hashlib
import struct

import pytest

from e3_host import q2_core_policy_basis as p


def fixture(monkeypatch):
    key = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + b"x" * 32
    raw = dict(fixture_cloud_config=b'#cloud-config\nusers:\n  - name: q1admin\n    sudo: ["ALL=(ALL) NOPASSWD:ALL"]\n',
               identity_public=b"ssh-ed25519 " + base64.b64encode(key) + b" unit-fixture\n",
               known_hosts=b"synthetic fixture host key\n")
    monkeypatch.setattr(p, "SOURCE_PINS", {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()})
    tokens = ["/usr/bin/sudo", "-n", "/unit fixture"]
    return raw, tokens, p.build_policy_basis(source_raw=raw, tokens=tokens)


def test_exact_static_profiles_and_corrected_sudo_semantics(monkeypatch):
    raw, tokens, value = fixture(monkeypatch)
    assert p.verify_policy_basis(value, source_raw=raw, tokens=tokens) == p._hash(value)
    assert set(value) == {"schema", "fixture_cloud_config", "identity_public", "known_hosts",
                          "remote_expectation", "policies", "policy_predicates_sha256"}
    policies = value["policies"]
    assert policies["sudo"]["predicate"]["parameters"]["required_grant"] == dict(
        commands=["ALL"], host="ALL", runas_groups=[], runas_users=["ALL"], tags=["NOPASSWD"])
    for name in ("sudo", "sshd"):
        assert policies[name]["execution"]["max_invocations"] == 1
        assert policies[name]["execution"]["require_stdout_eof"] is True
        assert policies[name]["execution"]["require_stderr_eof"] is True
        assert policies[name]["limits"]["command_cpu_seconds"] == 2
    for name in ("authorized_keys", "rc"):
        assert policies[name]["execution"]["max_invocations"] == 0
        assert policies[name]["argv"] == [] and policies[name]["environment"] == {}
    assert value["remote_expectation"]["remote_entity_preimages_stage"] == "HELLO_JIT"
    assert "uid" not in value["remote_expectation"]
    assert "matched" not in policies["sudo"]  # no fabricated current observation


@pytest.mark.parametrize("change", ["extra", "group", "budget", "argv", "key", "no_followup_profile"])
def test_predicate_or_profile_drift_cannot_be_adopted_from_current_observations(monkeypatch, change):
    raw, tokens, value = fixture(monkeypatch)
    if change == "extra":
        value["current_pass"] = True
    elif change == "group":
        value["policies"]["sudo"]["predicate"]["parameters"]["required_grant"]["runas_groups"] = ["ALL"]
    elif change == "budget":
        value["policies"]["sshd"]["limits"]["command_seconds"] += 1
    elif change == "argv":
        value["policies"]["sudo"]["argv"].append("--alternate")
    elif change == "key":
        value["identity_public"]["binding_pointer"] = "/different_key"
    else:
        value["policies"]["rc"]["predicate"]["parameters"]["bashrc_guard_profile"] = "accept-anything"
    with pytest.raises(p.c.ContractError, match="RELATION"):
        p.verify_policy_basis(value, source_raw=raw, tokens=tokens)


def test_wrong_source_and_key_options_fail_without_helper_execution(monkeypatch):
    raw, tokens, _value = fixture(monkeypatch)
    raw["fixture_cloud_config"] += b" "
    with pytest.raises(p.c.ContractError, match="SOURCE_PIN"):
        p.build_policy_basis(source_raw=raw, tokens=tokens)
    for key in (b'command="unsafe" ssh-ed25519 AAAA', b'ssh-rsa AAAA', b'ssh-ed25519 !!!!'):
        with pytest.raises(p.c.ContractError):
            p._key(key)


def test_component_digest_preimages_and_calls_do_not_share_mutable_predicates(monkeypatch):
    raw, tokens, first = fixture(monkeypatch)
    second = p.build_policy_basis(source_raw=raw, tokens=tokens)
    for value in first["policies"].values():
        assert value["predicate_sha256"] == p._hash(value["predicate"])
    assert first["policy_predicates_sha256"] == p._hash(first["policies"])
    assert first["remote_expectation"]["remote_tokens_sha256"] == p._hash(tokens)
    first["policies"]["sudo"]["environment"]["LANG"] = "modified"
    assert second["policies"]["sudo"]["environment"]["LANG"] == "C"

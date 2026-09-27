"""The closed Gate does not turn unavailable field evidence into admission."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from e3_host import q2_reconciliation_entry as entry


def forbidden(*args, **kwargs):
    raise AssertionError("offline refusal performed a field operation")


@pytest.mark.parametrize("config", [None, {}, {"attempt_id": "arbitrary"}])
def test_invalid_configuration_never_starts_or_consumes_window(config):
    with patch.object(entry.delivery, "Window", side_effect=forbidden), \
         patch.object(entry.old, "read_history", side_effect=forbidden), \
         patch.object(entry, "HostStore", side_effect=forbidden):
        result = entry.run_host(config, guest_input_builder=forbidden)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "RECONCILIATION_HOST_CONFIG"
    assert result["authority"] == entry.HOST_AUTHORITY
    assert result["local_read_only_preflight_repeatable"] is True
    for name in ("execution_window_started", "execution_window_consumed",
                 "host_persistence_attempted", "batch_delivery_issued", "replay_allowed",
                 "field_reads_performed", "readiness_proven", *entry.FALSE_FIELDS):
        assert result[name] is False


def test_no_anchors_refuses_before_field_effect_even_when_offline_inputs_pass():
    # Only the offline provenance result is modeled; the real deadline checker
    # runs, so a source-verified package still cannot dispatch or consume.
    verified = SimpleNamespace(implementation_commit="a" * 40,
        execution={"source": {"tree": "b" * 40}}, digest="c" * 64, raw_by_path={})
    boot = "11111111-1111-1111-1111-111111111111"
    config = {"guest_pin": {"boot_id": boot}}
    with patch.object(entry, "offline_inputs", return_value=(verified, {"expected_boot_id": boot})), \
         patch.object(entry.delivery, "Window", side_effect=forbidden), \
         patch.object(entry, "HostStore", side_effect=forbidden):
        result = entry.run_host(config, guest_input_builder=forbidden, retained_anchors=[])
    assert result["reason"] == "HOST_WINDOW_REMOTE_DEADLINE_UNPROVEN"
    assert result["offline_sources_verified"] is True
    assert result["remote_deadline_proof"]["dispatch_allowed"] is False
    assert result["execution_window_consumed"] is False
    assert result["field_reads_performed"] is False


def test_caller_cannot_pass_admitted_deadline_record():
    verified = SimpleNamespace(implementation_commit="a" * 40,
        execution={"source": {"tree": "b" * 40}}, digest="c" * 64, raw_by_path={})
    boot = "11111111-1111-1111-1111-111111111111"
    with patch.object(entry, "offline_inputs", return_value=(verified, {"expected_boot_id": boot})), \
         patch.object(entry.delivery, "Window", side_effect=forbidden):
        result = entry.run_host({"guest_pin": {"boot_id": boot}},
            retained_anchors={"status": "ADMITTED", "dispatch_allowed": True})
    assert result["status"] == "BLOCKED"
    assert result["execution_window_consumed"] is False
    assert "remote_deadline_proof" not in result


def test_live_and_ready_require_exact_host_bindings():
    config = dict(attempt_id="example-attempt", amendment_sha256="a" * 64,
        inputs_sha256="a" * 64, source_commit="b" * 40, source_tree="c" * 40)
    anchor = {"example": 1}
    bindings = dict.fromkeys(entry.HOST_BINDING_FIELDS, "d" * 64)
    value = dict(config, schema=entry.ADMITTED_SCHEMA, status="LIVE_ATTESTED",
        clock_anchor_sha256=entry.sha(entry.encoded(anchor)), live_attestation_sha256="e" * 64,
        **dict.fromkeys(entry.FALSE_FIELDS, False), **bindings)
    assert entry.checked_live(value, config, anchor, host_bindings=bindings) == value
    with pytest.raises(ValueError, match="SIGNAL_BINDINGS_REQUIRED"):
        entry.checked_live(value, config, anchor)
    for name in bindings:
        wrong = deepcopy(value)
        wrong[name] = "f" * 64
        with pytest.raises(ValueError, match="SIGNAL_BINDING"):
            entry.checked_live(wrong, config, anchor, host_bindings=bindings)


def test_cli_is_offline_without_configuration(capsys):
    assert entry.main() == 3
    value = entry.delivery.legacy.document(capsys.readouterr().out.encode())
    assert value["status"] == "BLOCKED"
    assert value["reason"] == "EXACT_PRIVATE_OFFLINE_PACKAGE_REQUIRED"
    assert value["execution_window_consumed"] is False

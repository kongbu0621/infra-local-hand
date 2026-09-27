"""Containment of the host entry before any execution window or field effect."""
from unittest.mock import patch

from e3_host import q2_reconciliation_entry as entry


def test_open_host_order_never_creates_a_window_or_calls_guest():
    def forbidden(*args, **kwargs):
        raise AssertionError("contained entry performed a field operation")
    with patch.object(entry.delivery, "Window", side_effect=forbidden), \
         patch.object(entry.old, "read_history", side_effect=forbidden), \
         patch.object(entry, "HostStore", side_effect=forbidden):
        for config in (None, {}, {"attempt_id": "arbitrary"}):
            result = entry.run_host(config, guest_input_builder=forbidden)
            assert result["status"] == "BLOCKED"
            assert result["reason"] == "HOST_WINDOW_CONSUMPTION_DESIGN_OPEN"
            for name in ("execution_window_started", "execution_window_consumed",
                         "host_persistence_attempted", "batch_delivery_issued", "replay_allowed",
                         *entry.FALSE_FIELDS):
                assert result[name] is False


def test_cli_is_blocked_without_configuration_or_side_effects(capsys):
    assert entry.main() == 3
    value = entry.delivery.legacy.document(capsys.readouterr().out.encode())
    assert value["status"] == "BLOCKED"
    assert value["reason"] == "HOST_WINDOW_CONSUMPTION_DESIGN_OPEN"

"""Level-two admission and private diagnostics, using synthetic inputs only."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux maintenance resource interfaces", allow_module_level=True)

from e3_host import q2_journal_growth as h, q2_journal_growth_guest as g
from e3_host import q2_core_delivery_contract as c, q2_core_delivery_dispatcher as d
from e3_host import q2_core_delivery_bootstrap as b, q2_core_delivery_entry as e
from e3_host import q2_core_prior_attempt as p
from test_e3_q2_core_delivery_contract import hello_record
from test_e3_q2_journal_host_fds import CHILD


def test_producer_and_independent_consumers_agree_on_current_limits():
    assert h.HOST_FD_LIMIT == g.CONTROL_FD_LIMIT == h.custody.LIMIT == 256
    assert c.LIMITS == d.LIMITS
    assert c.PACKAGE_LIMITS == d.PACKAGE_LIMITS == b.PACKAGE_LIMITS
    assert p.JOURNAL_FILES == d.JOURNAL_FILES
    assert e.HOST_WINDOW_NS == d.LIMITS["carrier_seconds"] * d.NS == 1800 * d.NS
    assert e.GUEST_CAP_NS == d.LIMITS["guest_duration_cap_seconds"] * d.NS
    assert e.OUTPUT_FRAME_LIMIT + e.STDERR_LIMIT + e.HELLO_FRAME_LIMIT == e.CARRIER_OUTPUT_LIMIT
    assert c.PACKAGE_LIMITS["package_bytes"] + e.BIND_FRAME_LIMIT == c.LIMITS["carrier_input_bytes"]


@pytest.mark.parametrize("count,accepted", [(129, True), (236, True), (237, False)])
def test_real_256_fd_admission_keeps_twenty_free_without_releasing_identity(tmp_path, count, accepted):
    code = CHILD.replace("h.HOST_FD_LIMIT=128", "assert h.HOST_FD_LIMIT==256")
    code = code.replace("(128,128)", "(256,256)").replace("range(128)", "range(256)")
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code,
        str(Path(__file__).parent), str(tmp_path), "admission", str(count)],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr.decode()
    value = json.loads(result.stdout)
    assert value["accepted"] is accepted
    if not accepted:
        assert value["diagnostic"] == dict(operation="host_fd_admission", stage="synthetic",
            descriptor_limit=256, required_free=20, available_below_limit=19)


@pytest.mark.parametrize("cpu,rss", [(121, 513 * h.MIB), (240, 1024 * h.MIB)])
def test_measurements_above_old_limits_pass_through_new_boundary(cpu, rss):
    h._check_management_budget(cpu, rss, stage="management_usage", cpu_limit=240, components={})


@pytest.mark.parametrize("cpu,rss", [(240.125, 1024 * h.MIB), (240, 1024 * h.MIB + 1)])
def test_new_overage_has_integer_wire_values_and_exact_limits(cpu, rss):
    with pytest.raises(h.prior.r.ObservationError, match="GROWTH_MANAGEMENT_BUDGET") as caught:
        h._check_management_budget(cpu, rss, stage="management_usage", cpu_limit=240,
            components=dict(self_cpu_seconds=cpu))
    detail = g.r.parse(g.canonical(caught.value.diagnostic), g.DIAGNOSTIC_LIMIT)
    assert detail["cpu"] == dict(actual=int(cpu * 1e9), limit=240_000_000_000,
        unit="nanoseconds", exceeded=cpu > 240)
    assert detail["rss"] == dict(actual=rss, limit=1024 * h.MIB,
        unit="bytes", exceeded=rss > 1024 * h.MIB)
    assert detail["components"]["self_cpu_nanoseconds"] == int(cpu * 1e9)


def test_current_hello_accepts_new_limits_and_preserves_historical_grammar():
    current = hello_record()
    c.validate_hello(current)
    d._validate_hello_identity(current, c.CARRIER_UNIT)
    historical = copy.deepcopy(current)
    unit = "lhqcore20261006a-carrier.service"
    historical["carrier_unit"].update(name=unit, control_group="/system.slice/" + unit)
    for key in ("runtime_max_usec", "timeout_stop_usec", "memory_max", "tasks_max", "cpu_quota_per_sec_usec"):
        historical["carrier_unit"][key] //= 2
    for key in ("cpu_soft", "cpu_hard", "nofile_soft", "nofile_hard", "fsize_soft", "fsize_hard"):
        historical["process_limits"][key] //= 2
    c._validate_hello_identity(historical, carrier_unit=unit)
    d._validate_hello_identity(historical, unit)
    historical["carrier_unit"]["memory_max"] *= 2
    with pytest.raises(c.ContractError, match="CORE_HELLO_CARRIER"):
        c._validate_hello_identity(historical, carrier_unit=unit)
    with pytest.raises(d.DispatchError):
        d._validate_hello_identity(historical, unit)


def test_historical_capacity_is_not_recharged_at_current_pool_limits():
    locators = {role + "_parent": "/fixture/" + role
        for role in ("state", "quota", "journal", "evidence", "install")}
    fs = {role: dict(dev=1, fs_uuid="a" * 32) for role in ("state", "quota", "journal", "evidence", "install")}
    assert d._cap_new_reservations(fs, locators, historical=True) == {
        (1, "a" * 32): dict(bytes=276 * h.MIB, inodes=16512)}
    assert d._cap_new_reservations(fs, locators) == {
        (1, "a" * 32): dict(bytes=348 * h.MIB, inodes=21120)}
    host = c.resource_pool_definitions(locators)
    guest = d._resource_pools(locators)
    for row in guest:
        row["roots"] = sorted((root["path"], root["parent_role"]) for root in row["roots"])
    assert host == guest


def test_large_bound_guest_diagnostic_survives_host_and_receipt_encoding():
    value = dict(schema=g.REPORT_SCHEMA, session=g.SESSION, phase="pre", status="INCOMPLETE",
        nonce="1" * 64, source_binding_sha256="2" * 64,
        stage="PRE_RUNTIME_PREPARATION", reason="GROWTH_PATH_PROTECTION",
        diagnostic=dict(path_lookup=dict(path="/synthetic/retained"), detail="x" * 45000))
    raw = g.canonical(value)
    assert 32768 < len(raw) < g.RECORD_LIMIT
    transport = object.__new__(h.MaintenanceTransport)
    transport.output = dict(stdout=bytearray(), stderr=bytearray(raw))
    transport.eof = dict(stdout=True, stderr=True)
    transport.phase, transport.nonce, transport.source_sha = "pre", "1" * 64, "2" * 64
    detail = transport.captured_failure()
    assert detail["guest_failure"] == {key: value[key] for key in ("stage", "reason", "diagnostic")}
    assert detail["stderr"]["sha256"] == g.digest(raw)
    assert g.r.parse(g.canonical(detail), g.DIAGNOSTIC_LIMIT) == detail


@pytest.mark.parametrize("raw", [b"short\xff", b"a" * 1024 + b"middle" * 1000 + b"z" * 1024])
def test_preview_reports_full_digest_and_explicit_truncation(raw):
    value = g.stream_diagnostic(raw, True)
    assert value["bytes"] == len(raw) and value["sha256"] == g.digest(raw)
    assert value["eof"] is True and value["truncated"] is (len(raw) > 2048)
    if value["truncated"]:
        assert value["head"] == "a" * 1024 and value["tail"] == "z" * 1024
    else:
        assert value["head"] == "short\ufffd" and value["tail"] == ""


def test_oversized_or_unserializable_diagnostic_cannot_mask_primary_failure():
    value = dict(reason="GROWTH_PATH_PROTECTION", guest_failure=dict(stage="PRE_RUNTIME_PREPARATION",
        reason="GROWTH_PATH_PROTECTION", diagnostic=dict(detail="x" * 100000)))
    result = g.bounded_diagnostic(value)
    assert len(g.canonical(result)) <= g.DIAGNOSTIC_LIMIT
    assert result["reason"] == result["guest_failure"]["reason"] == "GROWTH_PATH_PROTECTION"
    assert result["guest_failure"]["diagnostic"]["truncated"] is True
    assert result["full_sha256"] == g.digest(g.canonical(value))
    recursive = {}; recursive["self"] = recursive
    assert g.bounded_diagnostic(recursive)["serialization_error"] == "ValueError"


def test_cap_change_does_not_release_an_unverified_dispatcher():
    # IR1 now pins the reviewed source. An altered candidate must still fail
    # the actual gate even when it carries all current level-two ceilings.
    raw = Path(d.__file__).read_bytes() + b"\n# unreviewed capacity candidate\n"
    digest = c.sha256(raw)
    assert digest not in e.RELEASABLE_DISPATCHER_SHA256
    manifest = {"entry": {"dispatcher_path": "field/dispatcher.py", "dispatcher_sha256": digest}}
    with pytest.raises(e.contract.ContractError, match="CORE_DELIVERY_RELEASE_GATE"):
        e.field_release_gate(manifest, {"field/dispatcher.py": raw})
    assert (g.OLD_SIZE, g.NEW_SIZE) == (256 * h.MIB, 512 * h.MIB)

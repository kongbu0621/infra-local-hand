"""Approved transport amendment: synthetic bytes, no field request or acceptance."""
import sys

import pytest

from core_writer_fixture import writer, host_marker
from e3_host import q2_core_delivery_contract as c
from e3_host import q2_core_delivery_package as p
from test_e3_q2_core_delivery_package import fixture, _wire


MUTATIONS = ("missing", "extra", "schema", "namespace_missing", "namespace_extra", "bool",
             "negative", "zero_inode", "zero_pid", "large", "string", "float", "credential",
             "credential_bool", "groups_tuple", "groups_bool", "groups_order", "groups_duplicate",
             "oversize")


def change(value, kind):
    if kind == "missing": value.pop("process")
    elif kind == "extra": value["guest_identity"] = {}
    elif kind == "schema": value["schema"] = c.HELLO_SCHEMA
    elif kind == "namespace_missing": value["user_namespace"].pop("ino")
    elif kind == "namespace_extra": value["pid_namespace"]["path"] = "/proc/self/ns/pid"
    elif kind == "bool": value["process"]["pid"] = True
    elif kind == "negative": value["user_namespace"]["dev"] = -1
    elif kind == "zero_inode": value["pid_namespace"]["ino"] = 0
    elif kind == "zero_pid": value["process"]["pid"] = 0
    elif kind == "large": value["process"]["starttime_ticks"] = 2**63
    elif kind == "string": value["uid"]["saved"] = "1001"
    elif kind == "float": value["process"]["pid"] = 456.0
    elif kind == "credential": value["uid"]["saved"] += 1
    elif kind == "credential_bool": value["gid"] = dict.fromkeys(value["gid"], True)
    elif kind == "groups_tuple": value["supplementary_gids"] = (1, 2)
    elif kind == "groups_bool": value["supplementary_gids"] = [True]
    elif kind == "groups_order": value["supplementary_gids"].reverse()
    elif kind == "groups_duplicate": value["supplementary_gids"] *= 2
    elif kind == "oversize": value["supplementary_gids"] = list(range(1500))
    else: raise AssertionError(kind)
    return value


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_host_writer_rejects_malformed_values(mutation):
    with pytest.raises(c.ContractError):
        c.validate_local_writer(change(writer(), mutation))


@pytest.mark.parametrize("mutation", [item for item in MUTATIONS if item != "groups_tuple"])
def test_package_rejects_malformed_transported_writer(monkeypatch, mutation):
    manifest, members = fixture(monkeypatch)
    manifest["entry"]["writer"] = change(writer(), mutation)
    # Floats are rejected by the canonical encoder before any package is built.
    with pytest.raises(p.c.ContractError):
        p.parse_package(_wire(manifest, members))


def exact_limit_writer():
    for count in range(800, 1100):
        value = writer()
        value["process"]["starttime_ticks"] = 1
        value["supplementary_gids"] = list(range(count))
        padding = 4096 - len(c.canonical(value))
        if 0 <= padding <= 17:
            value["process"]["starttime_ticks"] = 10**padding
            assert len(c.canonical(value)) == 4096
            return value
    raise AssertionError("fixture cannot reach exact boundary")


def test_no_lf_writer_limit_is_inclusive_and_does_not_truncate():
    value = exact_limit_writer()
    assert c.validate_local_writer(value) is value
    assert len(c.canonical(value, newline=True)) == 4097
    value["supplementary_gids"].append(2000)
    with pytest.raises(c.ContractError): c.validate_local_writer(value)
    assert value["supplementary_gids"][-1] == 2000


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="standalone guest parser requires Linux")
@pytest.mark.parametrize("mutation", MUTATIONS)
def test_independent_standalone_writer_validators_reject_same_bad_shape(mutation):
    from e3_host import q2_core_delivery_bootstrap as b
    from e3_host import q2_core_delivery_dispatcher as d
    for validate, error in ((b.validate_writer, ValueError), (d._validate_local_writer, d.DispatchError)):
        with pytest.raises(error): validate(change(writer(), mutation))


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="standalone guest parser requires Linux")
def test_independent_parsers_agree_at_limit_and_keep_field_blob_limits():
    from pathlib import Path
    from e3_host import q2_core_delivery_bootstrap as b
    from e3_host import q2_core_delivery_dispatcher as d
    value = exact_limit_writer()
    assert b.validate_writer(value) == d._validate_local_writer(value) == value
    assert b.encoded(value, newline=False) == d.canonical(value) == c.canonical(value)
    assert c.PACKAGE_SCHEMA == b.PACKAGE_SCHEMA == d.PACKAGE_SCHEMA == "local-hand-q2-core-field-package/v3"
    for path, limit in p.FIELD_LIMITS.items():
        name = path.rsplit("/", 1)[1]
        assert Path("tests/e3_host/q2_core_delivery_" + name).stat().st_size <= limit


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="dispatcher requires Linux")
@pytest.mark.parametrize("mutation", ["writer", "clock", "package", "marker", "no_lf", "legacy", "missing"])
def test_marker_link_rejects_drift_before_effects(mutation):
    from test_e3_q2_core_dispatch_v2 import context_v2, repack, d
    value = context_v2()
    raw, marker = host_marker(value)
    assert d._consumption_info(value) == dict(marker, state="CONSUMPTION_RECORD_COMPLETE")
    if mutation == "writer":
        value["manifest"]["entry"]["writer"]["process"]["pid"] += 1
        repack(value)  # New package hash cannot replace the consumed marker.
    elif mutation == "clock": value["bind"]["host_monotonic_origin_ns"] += 1
    elif mutation == "package": value["bind"]["package_basename"] = "changed.lhfp"
    elif mutation == "marker": value["bind"]["consumption_sha256"] = "0" * 64
    elif mutation == "no_lf": value["bind"]["consumption_sha256"] = c.sha256(raw[:-1])
    elif mutation == "legacy": value["manifest"]["schema"] = "local-hand-q2-core-field-package/v2"
    else: value["manifest"]["entry"].pop("writer")
    with pytest.raises(d.DispatchError):
        d._validate_context_envelope(value)
        d._consumption_info(value)


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_old_shape_is_not_upgraded_or_filled(monkeypatch, version):
    manifest, members = fixture(monkeypatch)
    manifest["schema"] = "local-hand-q2-core-field-package/" + version
    manifest["entry"].pop("writer")
    with pytest.raises(p.c.ContractError): p.parse_package(_wire(manifest, members))


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_v3_entry_is_exact(monkeypatch, mutation):
    manifest, members = fixture(monkeypatch)
    if mutation == "missing": manifest["entry"].pop("writer")
    else: manifest["entry"]["writer_sha256"] = c.sha256(c.canonical(writer()))
    with pytest.raises(p.c.ContractError, match="CORE_PACKAGE_ENTRY_FIELDS"):
        p.parse_package(_wire(manifest, members))


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="isolated local capture requires Linux")
def test_guest_reconstruction_matches_actual_create_fsync_reread_marker(tmp_path):
    # Real temporary local persistence, NOT the protected management anchor or F1.
    import os
    import time
    from test_e3_q2_core_dispatch_v2 import context_v2, repack, d
    from e3_host import q2_core_delivery_entry as e
    value = context_v2()
    origins = {key: value["bind"][key] for key in ("host_boottime_origin_ns", "host_monotonic_origin_ns",
                                                 "host_boottime_deadline_ns", "host_monotonic_deadline_ns")}
    def clock(which):
        return origins["host_boottime_origin_ns" if which == time.CLOCK_BOOTTIME
                       else "host_monotonic_origin_ns"]
    deadline = e.capture_contract.Deadline(origins, clock)
    current_writer = e.capture_contract.observe_writer(deadline.call)
    value["manifest"]["entry"]["writer"] = current_writer
    repack(value, marker=True)
    raw, expected = host_marker(value)
    tmp_path.chmod(0o700)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    capture = None
    try:
        info = os.fstat(fd)
        anchor = {"path": str(tmp_path), "dev": info.st_dev, "ino": info.st_ino, "mode": 0o700,
                  "uid": info.st_uid, "gid": info.st_gid, "nlink": info.st_nlink}
        capture = e.capture_contract.LiveCapture(fd, anchor=anchor, writer=current_writer,
                                                 origins=origins, clock_gettime_ns=clock)
        actual = e.create_consumption_marker(fd, c.document(raw, newline=True, limit=16384), capture=capture)
        assert actual["record_complete"] is True
        assert {key: actual[key] for key in expected} == expected
        assert (tmp_path / c.MARKER_BASENAME).read_bytes() == raw
        assert d._consumption_info(value) == dict(expected, state="CONSUMPTION_RECORD_COMPLETE")
        with pytest.raises(e.ConsumedError):
            e.create_consumption_marker(fd, c.document(raw, newline=True, limit=16384), capture=capture)
        assert len(list(tmp_path.iterdir())) == 1
    finally:
        if capture is not None: capture.close_handles()
        os.close(fd)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="dispatcher requires Linux")
def test_marker_limit_is_not_increased_to_fit_unbounded_input():
    from test_e3_q2_core_dispatch_v2 import context_v2, d
    value = context_v2()
    value["bind"]["package_basename"] = "x" * 16384 + ".lhfp"
    with pytest.raises(d.DispatchError, match="CORE_DISPATCH_JSON_LIMIT"):
        d._consumption_info(value)

"""Host/standalone BIND compatibility before consuming a field request."""
import copy
import sys

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Field BIND requires Linux bootstrap and entry modules", allow_module_level=True)

from e3_host import q2_core_delivery_dispatcher as dispatcher
import test_e3_q2_core_delivery_bootstrap as bootstrap_fixture
import test_e3_q2_core_delivery_entry as entry_fixture


INVALID_BASENAMES = ("sub/frozen.lhfp", "./frozen.lhfp", "../frozen.lhfp",
                     "/frozen.lhfp", "frozen\\name.lhfp", ".lhfp",
                     "frozen name.lhfp", "frozen.lhfp\n", "名字.lhfp",
                     "frozen.lhfp", ".frozen-1_2.lhfp", "lhqcore-20261003a.lhfp")


def prepared(monkeypatch, basename="lhqcore-20261005c.lhfp"):
    """Use a real packaged entry; private source bodies remain synthetic."""
    fixture = bootstrap_fixture
    bootstrap_sha, raw = fixture.package_fixture(monkeypatch)
    manifest, members = fixture.p.parse_package(raw)
    guest_manifest, guest_members = fixture.b.parse_package(raw, bootstrap_sha)
    assert guest_manifest == manifest and guest_members == members
    e, c = entry_fixture.e, entry_fixture.c
    hello = entry_fixture.hello()
    hello.update(loader_sha256=manifest["entry"]["loader_sha256"],
                 bootstrap_sha256=bootstrap_sha)
    assert fixture.b.validate_hello(copy.deepcopy(hello), bootstrap_sha) == hello
    origins = e.freeze_host_window(lambda _clock: 1_000_000_000_000)
    package = dict(basename=basename, bytes=len(raw), sha256=c.sha256(raw),
                   manifest_sha256=c.sha256(c.canonical(manifest, newline=True)))
    record = e.consumption_record(
        implementation=manifest["implementation"], amendment=manifest["amendment"],
        package=package, approved_inputs_sha256=manifest["approved_inputs"]["sha256"],
        local_management_binding_sha256=manifest["entry"]["local_management_binding_sha256"],
        writer=manifest["entry"]["writer"],
        carrier_argv_sha256=manifest["entry"]["carrier_argv_sha256"], origins=origins)
    marker_raw = c.canonical(record, newline=True)
    return dict(manifest=manifest, members=members, package_raw=raw, hello=hello,
                origins=origins, marker_raw=marker_raw)


def host_bind(value, basename):
    return entry_fixture.e.build_bind(
        value["hello"], entry_fixture.c.sha256(value["marker_raw"]), basename,
        value["package_raw"], value["origins"], package_entry=value["manifest"]["entry"],
        remote_expectation=entry_fixture.remote_expectation(),
        boot_bind_ns=1_001_000_000_000, mono_bind_ns=1_001_000_000_000)


@pytest.mark.parametrize("basename", ("lhqcore-20261005c.lhfp",))
def test_packaged_entry_crosses_host_and_guest_bind_and_marker(monkeypatch, basename):
    value = prepared(monkeypatch, basename)
    bind = host_bind(value, basename)
    b, c = bootstrap_fixture.b, entry_fixture.c
    assert b.validate_bind(copy.deepcopy(bind), b.encoded(value["hello"])) == bind
    assert dispatcher._consumption_info(dict(manifest=value["manifest"], bind=bind)) == {
        "basename": c.MARKER_BASENAME, "bytes": len(value["marker_raw"]),
        "sha256": c.sha256(value["marker_raw"]), "state": "CONSUMPTION_RECORD_COMPLETE"}


@pytest.mark.parametrize("basename", INVALID_BASENAMES)
def test_host_bind_rejects_names_rejected_by_guest(monkeypatch, basename):
    value = prepared(monkeypatch)
    valid = host_bind(value, "lhqcore-20261005c.lhfp")
    invalid = dict(valid, package_basename=basename)
    with pytest.raises(ValueError, match="CORE_BOOTSTRAP_BIND_PACKAGE"):
        bootstrap_fixture.b.validate_bind(invalid, bootstrap_fixture.b.encoded(value["hello"]))
    with pytest.raises(entry_fixture.c.ContractError, match="CORE_BIND_PACKAGE"):
        host_bind(value, basename)


@pytest.mark.parametrize("basename", INVALID_BASENAMES)
def test_delivery_rejects_bad_name_before_anchor_marker_or_carrier(monkeypatch, basename):
    value = prepared(monkeypatch)
    e = entry_fixture.e
    package_module = e._helper("q2_core_delivery_package")
    # Only bypass the intentionally closed release gate for this local preflight test.
    monkeypatch.setattr(package_module, "parse_package",
                        lambda _raw: (value["manifest"], value["members"]))
    monkeypatch.setattr(e, "_helper", lambda _name: package_module)
    monkeypatch.setattr(e, "field_release_gate", lambda *_args: None)
    def forbidden(*_args, **_kwargs):
        pytest.fail("bad package basename reached management or request work")
    for name in ("remote_tokens", "requalify_management_anchor", "create_consumption_marker",
                 "execute_carrier_once"):
        monkeypatch.setattr(e, name, forbidden)
    with pytest.raises(entry_fixture.c.ContractError, match="CORE_DELIVERY_PACKAGE_BASENAME"):
        e.deliver_once(-1, binding={}, package_basename=basename,
            package_raw=value["package_raw"], loader_raw=value["members"]["field/loader.py"],
            bootstrap_raw=value["members"]["field/bootstrap.py"], wrapper_raw=b"unused",
            origins=value["origins"], popen_factory=forbidden)

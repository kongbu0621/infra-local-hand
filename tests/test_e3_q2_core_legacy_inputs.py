import hashlib

import pytest

from e3_host import q2_core_legacy_inputs as legacy


def test_unpinned_frame_and_manifest_fail_before_parsing_or_execution():
    with pytest.raises(legacy.c.ContractError, match="LEGACY_FRAME_PIN"):
        legacy.recover_inputs(b"arbitrary archive", {})
    with pytest.raises(legacy.c.ContractError, match="LEGACY_LATER_MANIFEST_PIN"):
        legacy.restore_manifest(b"arbitrary source", {})


def fixture(monkeypatch):
    tools = {"tool_" + str(i) + ".py": b"# never executed\n" for i in range(42)}
    paths = {"/protected/tools/" + name: "a" * 64 for name in tools}
    paths["/protected/tools/later_only.py"] = "b" * 64
    value = dict(implementation_commit="1" * 40,
                 execution=dict(source=dict(commit="1" * 40, tree="2" * 40, files=paths)))
    later = legacy.c.canonical(value, newline=True)
    monkeypatch.setattr(legacy, "LATER_MANIFEST_PIN", (len(later), hashlib.sha256(later).hexdigest()))
    value["implementation_commit"] = legacy.LEGACY_COMMIT
    source = value["execution"]["source"]
    source.update(commit=legacy.LEGACY_COMMIT, tree=legacy.LEGACY_TREE,
                  files={"/protected/tools/" + name: hashlib.sha256(raw).hexdigest()
                         for name, raw in tools.items()})
    expected = legacy.c.canonical(value, newline=True)
    monkeypatch.setattr(legacy, "MANIFEST_PIN", (len(expected), hashlib.sha256(expected).hexdigest()))
    return later, tools, expected


def test_restore_is_exact_data_transform_without_old_payload_execution(monkeypatch):
    later, tools, expected = fixture(monkeypatch)
    assert legacy.restore_manifest(later, tools) == expected
    assert len(tools) == 42
    assert b"later_only.py" in later  # original input is never modified


def test_missing_or_wrong_historical_tool_cannot_make_equivalent_manifest(monkeypatch):
    later, tools, _expected = fixture(monkeypatch)
    changed = dict(tools)
    changed.pop(next(iter(changed)))
    with pytest.raises(legacy.c.ContractError, match="TOOL_CLOSURE"):
        legacy.restore_manifest(later, changed)
    changed = dict(tools)
    changed[next(iter(changed))] = b"# different original bytes\n"
    with pytest.raises(legacy.c.ContractError, match="LEGACY_ORIGINAL_MANIFEST_PIN"):
        legacy.restore_manifest(later, changed)

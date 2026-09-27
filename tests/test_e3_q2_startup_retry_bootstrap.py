"""Pinned bootstrap bytes and inert failure boundaries, no guest execution."""
import importlib.util
import os
from pathlib import Path

import pytest


def module():
    path = Path(__file__).parent / "e3_host/q2_startup_retry_bootstrap.py"
    spec = importlib.util.spec_from_file_location("startup_bootstrap_test", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sources():
    boot = module()
    files = {"/root/new/tools/q2_example.py": "VALUE = 1\n"}
    hashes = {path: boot.sha(raw.encode()) for path, raw in files.items()}
    checked = {"members": [dict(name="tools/q2_example.py", kind="file", data=b"VALUE = 1\n")]}
    return boot, checked, files, hashes


def test_exact_in_memory_and_staged_sources_match():
    boot, checked, files, hashes = sources()
    boot.check_archive_sources(checked, files, hashes, "/root/new/tools")


@pytest.mark.parametrize("mutation", ["archive_bytes", "missing", "unknown", "duplicate", "digest", "alias"])
def test_any_staged_source_substitution_is_rejected(mutation):
    boot, checked, files, hashes = sources()
    if mutation == "archive_bytes":
        checked["members"][0]["data"] = b"VALUE = 2\n"
    elif mutation == "missing":
        checked["members"] = []
    elif mutation == "unknown":
        checked["members"].append(dict(name="tools/q2_extra.py", kind="file", data=b""))
    elif mutation == "duplicate":
        checked["members"] *= 2
    elif mutation == "digest":
        hashes[next(iter(hashes))] = "0" * 64
    else:
        path = next(iter(files))
        files[path.replace("/tools/", "/other/")] = files.pop(path)
        hashes[path.replace("/tools/", "/other/")] = hashes.pop(path)
    with pytest.raises(ValueError, match="STARTUP_BOOTSTRAP_"):
        boot.check_archive_sources(checked, files, hashes, "/root/new/tools")


def test_untrusted_configuration_cannot_load_helpers_or_create_state(monkeypatch, capsys):
    boot = module()
    def unexpected(*args):
        pytest.fail("must reject the shape before importing or acting")
    monkeypatch.setattr(boot, "helper", unexpected)
    result = boot.bootstrap({"shell": "unapproved"}, {})
    assert result["ready"] is False and result["argv"] is None
    assert result["record"]["reason"] == "STARTUP_BOOTSTRAP_FIELDS"
    assert not result["record"]["q2_accepted"]
    assert "INCOMPLETE" in capsys.readouterr().out


def test_diagnostic_retains_errno_without_arbitrary_exception_text():
    boot = module()
    detail = boot.diagnostic(PermissionError(13, "private detail", "/private/path"), "preflight")
    assert detail == dict(stage="preflight", type="PermissionError", errno=13, reason="PermissionError")
    assert boot.diagnostic(ValueError("arbitrary private text"), "records")["reason"] == "ValueError"


def test_whole_stage_and_intent_must_be_charged_and_archive_has_no_extra_domain():
    boot = module()
    root = "/root/fresh"
    wheel = "infra_local_hand-0.2.0a1-py3-none-any.whl"
    retry = dict(candidate=dict(source=root + "/source", wheel=root + "/" + wheel, destination="/opt/fresh"),
                 retained_inputs=[dict(path=root, category="installation"),
                                  dict(path=root + ".intent.json", category="installation")],
                 old_files={"/root/old/plan.json": "0" * 64}, directories={})
    checked = dict(members=[dict(name=wheel, kind="file")])
    boot.check_stage_layout(dict(stage=root), retry, {}, checked)
    checked["members"].append(dict(name="uncharged/report.json", kind="file"))
    with pytest.raises(ValueError, match="ARCHIVE_LAYOUT"):
        boot.check_stage_layout(dict(stage=root), retry, {}, checked)
    checked["members"].pop()
    retry["retained_inputs"][0]["path"] = root + "/tools"
    with pytest.raises(ValueError, match="STAGE_COVERAGE"):
        boot.check_stage_layout(dict(stage=root), retry, {}, checked)


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="POSIX protected staging")
def test_expired_boot_guard_retains_intent_and_partial_stage_without_replay(tmp_path, monkeypatch):
    boot = module()
    base = boot.helper("q2_prepare_delivery")
    # Model the guest identity/ancestor admission; writes, fsync, fd device and
    # create-only behavior below are real temporary filesystem operations.
    monkeypatch.setattr(base, "verify_guest", lambda pin: pin)
    monkeypatch.setattr(base, "protected_parent", Path)
    root = tmp_path / "stage"
    checked = dict(staging_bytes=8192, entries=1,
                   members=[dict(name="payload", kind="file", data=b"payload", mode=0o644)])
    def guard():
        if root.exists():
            raise ValueError("BOOT_DEADLINE_EXPIRED")
    kwargs = dict(destination=str(root), guest_pin={}, admission=dict(installation_reservation_bytes=4096),
                  ceiling_bytes=16*1024**2, system_device=tmp_path.stat().st_dev,
                  issued_ns=1, deadline_ns=2, guard=guard)
    with pytest.raises(ValueError, match="BOOT_DEADLINE_EXPIRED"):
        boot.guarded_extract(base, checked, "0" * 64, **kwargs)
    assert Path(str(root) + ".intent.json").is_file()
    assert root.is_dir() and not (root / "payload").exists()
    kwargs["guard"] = lambda: None
    with pytest.raises(ValueError, match="ALREADY_RESERVED"):
        boot.guarded_extract(base, checked, "0" * 64, **kwargs)


def test_failure_metadata_cannot_write_after_its_clock_guard_expires(tmp_path):
    boot = module()
    base = boot.helper("q2_prepare_delivery")
    def expired():
        raise ValueError("BOOT_DEADLINE_EXPIRED")
    with pytest.raises(ValueError, match="BOOT_DEADLINE_EXPIRED"):
        boot.write_metadata(base, tmp_path, "bootstrap-failed.json", b"{}", expired)
    assert not (tmp_path / "bootstrap-failed.json").exists()

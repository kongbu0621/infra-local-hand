import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Core freeze requires Linux protected FDs and executable ownership checks",
                allow_module_level=True)

from e3_host import q2_core_delivery_freeze as f


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii") + b"\n"


def _source(path, size, inode):
    return {
        "atime_ns": 1_000_000_000, "blocks": 8, "ctime_ns": 1_000_000_000,
        "device": 1, "gid": 0, "inode": inode, "mode": 0o600,
        "mtime_ns": 1_000_000_000, "nlink": 1, "path": "/" + path,
        "size": size, "st_mode": stat.S_IFREG | 0o600, "type": "regular", "uid": 0,
    }


def retained_fixture(tmp_path, monkeypatch):
    tmp_path.mkdir(parents=True, exist_ok=True)
    plan = {
        "directories": {"state": {"path": "/state/core"}},
        "mounts": {
            "quota": {"path": "/quota"}, "journal": {"path": "/journal"},
            "evidence": {"path": "/evidence"},
        },
        "candidate": {"destination": "/install/core"},
        "account": {"name": "fixturejob"},
        "parents": {
            "query": {"unit": "fixture-query.slice"},
            "controller": {"unit": "fixture-controller.slice"},
            "management": {"unit": "fixture-management.slice"},
            "supervisor": {"unit": "fixture-supervisor.slice"},
            "ordinary": {"unit": "fixture-ordinary.slice"},
        },
    }
    retry = {"facts": {"parents": {
        "manager": {"unit": "user@1234.service"},
        "ordinary": {"path": "/user.slice/user-1234.slice/fixture-ordinary.slice"},
    }}}
    targets = {
        "plan": ("root/q2-transfer-20260926a/plan.json", _json(plan)),
        "retry": ("root/q2-retry-setup-20260927a/retry-preparation.json", _json(retry)),
    }
    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        for index, (_role, (name, raw)) in enumerate(targets.items(), 1):
            item = tarfile.TarInfo(name)
            item.size = len(raw); item.mode = 0o600; item.uid = item.gid = 0; item.mtime = index
            item.pax_headers = {"atime": str(index), "ctime": str(index), "mtime": str(index)}
            archive.addfile(item, io.BytesIO(raw))
    archive_raw = archive_buffer.getvalue()

    entries = []
    inventory = []
    with tarfile.open(fileobj=io.BytesIO(archive_raw), mode="r:gz") as archive:
        for index, item in enumerate(archive.getmembers(), 1):
            raw = archive.extractfile(item).read()
            source = _source(item.name, len(raw), index)
            inventory.append(source)
            entries.append({
                "archive_metadata": {
                    "gid": item.gid, "mode": item.mode,
                    "mtime_ns": int(item.mtime * 1_000_000_000),
                    "pax_headers": item.pax_headers, "size": item.size, "uid": item.uid,
                },
                "archive_path": item.name, "sha256": hashlib.sha256(raw).hexdigest(),
                "source_metadata": source, "source_path": "/" + item.name,
                "type": "regular",
            })
    archive_sha = hashlib.sha256(archive_raw).hexdigest()
    manifest_raw = _json({
        "schema": "local-hand-q2-readonly-return-manifest/v1",
        "archive": "q2_guest_raw.tar.gz", "archive_bytes": len(archive_raw),
        "archive_sha256": archive_sha, "entries": entries, "entry_count": len(entries),
        "origin": "unit-fixture", "regular_file_bytes": sum(x["size"] for x in inventory),
        "regular_file_count": len(inventory),
    })
    # Deliberately use a different order: the verifier must join by exact path,
    # not mistake line position for a relationship.
    inventory_raw = b"".join(_json(item) for item in reversed(inventory))
    pins = {
        "guest-raw.tar.gz": {"bytes": len(archive_raw), "sha256": archive_sha},
        "guest-manifest.json": {
            "bytes": len(manifest_raw), "sha256": hashlib.sha256(manifest_raw).hexdigest(),
        },
        "guest-inventory.jsonl": {
            "bytes": len(inventory_raw), "sha256": hashlib.sha256(inventory_raw).hexdigest(),
        },
    }
    capture = {
        "schema": "local-hand-q2-readonly-return-capture/v1",
        "completed_realtime_ns": 10, "connection": "retained unit fixture",
        "files": {
            "guest_archive": pins["guest-raw.tar.gz"],
            "guest_inventory": pins["guest-inventory.jsonl"],
            "guest_manifest": pins["guest-manifest.json"],
            "host_archive": {"bytes": 1, "sha256": "1" * 64},
            "host_manifest": {"bytes": 1, "sha256": "2" * 64},
        },
        "gate_rule_http_status": 404, "guest": "unit", "guest_attestation_stderr_bytes": 0,
        "guest_boot_id": "historical", "guest_entries": len(entries),
        "guest_regular_bytes": sum(x["size"] for x in inventory),
        "guest_regular_files": len(inventory), "guest_tar_stderr_bytes": 0,
        "host": "unit", "host_entries": 1, "host_regular_bytes": 1,
        "host_regular_files": 1, "inventory_stderr_bytes": 0,
        "known_deviation_file": "collection-metadata-note.json",
        "private_bundle_present": False,
        "prohibited_actions": {name: False for name in f.PROHIBITED_FIELDS},
        "source_repository_commit": "a" * 40,
    }
    capture_raw = _json(capture)
    pins["collection-capture.json"] = {
        "bytes": len(capture_raw), "sha256": hashlib.sha256(capture_raw).hexdigest(),
    }
    root = tmp_path / "retained"
    root.mkdir(mode=0o700)
    values = {
        "collection-capture.json": capture_raw, "guest-raw.tar.gz": archive_raw,
        "guest-manifest.json": manifest_raw, "guest-inventory.jsonl": inventory_raw,
    }
    for name, raw in values.items():
        path = root / name
        path.write_bytes(raw); path.chmod(0o600)
    monkeypatch.setattr(f, "RETAINED_PINS", pins)
    monkeypatch.setattr(f, "TARGET_MEMBERS", {
        role: {"archive_path": name, "bytes": len(raw),
               "sha256": hashlib.sha256(raw).hexdigest()}
        for role, (name, raw) in targets.items()
    })
    paths = dict(
        retained_root=root, capture_path=root / "collection-capture.json",
        archive_path=root / "guest-raw.tar.gz", manifest_path=root / "guest-manifest.json",
        inventory_path=root / "guest-inventory.jsonl",
    )
    return paths, capture


def test_locator_freeze_has_exact_pointer_relation_and_stays_not_issued(tmp_path, monkeypatch):
    paths, _capture = retained_fixture(tmp_path, monkeypatch)
    digest = "9" * 64
    monkeypatch.setattr(f.entry_api, "management_binding_digest", lambda *a, **k: digest)
    result = f.freeze_private_locators(
        **paths, management_binding_preimage={}, management_tokens=[], management_argv=[],
        management_wrapper_raw=b"wrapper",
    )
    assert result["state"] == "PRIVATE_LOCATORS_FROZEN"
    assert result["issuance"] == "NOT_ISSUED" and result["package"] is None
    assert result["locators"]["state_parent"] == "/state"
    assert result["locators"]["install_parent"] == "/install"
    assert result["locators"]["ordinary_group"] == "fixturejob"
    assert result["locators"]["retained_ordinary_parent_path"].endswith(
        "/fixture-ordinary.slice")
    mapping = result["private_source_map"]["mapping"]
    assert mapping["state_parent"]["json_pointer"] == "/directories/state/path"
    assert mapping["state_parent"]["transform"] == "dirname"
    assert result["private_source_map"]["zero_mismatch"] is True
    assert f.p.validate_locators(result["locators"], digest) == result["locators"]


def test_locator_source_without_full_management_preimage_is_not_prepared(tmp_path, monkeypatch):
    paths, _capture = retained_fixture(tmp_path, monkeypatch)
    result = f.freeze_private_locators(**paths)
    assert result["state"] == "NOT_PREPARED"
    assert result["issuance"] == "NOT_ISSUED"
    assert result["locators"] is None and result["package"] is None
    assert result["missing"] == [
        "management_anchor.binding_preimage", "management_anchor.tokens",
        "management_anchor.argv", "management_anchor.wrapper_bytes",
    ]


def test_locator_source_rejects_scattered_copy_wrong_pin_and_cross_file_mismatch(
        tmp_path, monkeypatch):
    paths, capture = retained_fixture(tmp_path, monkeypatch)
    loose = tmp_path / "guest-inventory.jsonl"
    shutil.copyfile(paths["inventory_path"], loose)
    with pytest.raises(f.c.ContractError, match="CORE_FREEZE_RETAINED_RELATION"):
        f.freeze_private_locators(**dict(paths, inventory_path=loose))

    original = paths["capture_path"].read_bytes()
    paths["capture_path"].write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(f.c.ContractError, match="CORE_FREEZE_RETAINED_PIN"):
        f.freeze_private_locators(**paths)

    # Make every outer digest agree with a changed inventory, while leaving the
    # manifest's source_metadata unchanged.  Zero-mismatch verification must
    # still reject the set.
    paths, capture = retained_fixture(tmp_path / "second", monkeypatch)
    rows = [json.loads(line) for line in paths["inventory_path"].read_text().splitlines()]
    rows[0]["inode"] += 100
    inventory_raw = b"".join(_json(row) for row in rows)
    paths["inventory_path"].write_bytes(inventory_raw)
    inventory_pin = {"bytes": len(inventory_raw),
                     "sha256": hashlib.sha256(inventory_raw).hexdigest()}
    f.RETAINED_PINS["guest-inventory.jsonl"] = inventory_pin
    capture["files"]["guest_inventory"] = inventory_pin
    capture_raw = _json(capture)
    paths["capture_path"].write_bytes(capture_raw)
    f.RETAINED_PINS["collection-capture.json"] = {
        "bytes": len(capture_raw), "sha256": hashlib.sha256(capture_raw).hexdigest(),
    }
    with pytest.raises(f.c.ContractError, match="CORE_FREEZE_INVENTORY_MISMATCH"):
        f.freeze_private_locators(**paths)


def _git(repository, *args):
    environment = dict(os.environ, GIT_AUTHOR_NAME="freeze", GIT_AUTHOR_EMAIL="freeze@example.invalid",
                       GIT_COMMITTER_NAME="freeze", GIT_COMMITTER_EMAIL="freeze@example.invalid")
    return subprocess.run(["/usr/bin/git", "-C", str(repository), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=environment).stdout.decode().strip()


def package_fixture(tmp_path, monkeypatch):
    tmp_path.mkdir(parents=True, exist_ok=True)
    candidate = tmp_path / "candidate"
    candidate.mkdir(); _git(candidate, "init", "-q")
    (candidate / "README.md").write_text("candidate\n")
    (candidate / "empty.log").write_bytes(b"")
    _git(candidate, "add", "README.md", "empty.log")
    _git(candidate, "commit", "-q", "-m", "candidate")
    candidate_commit = _git(candidate, "rev-parse", "HEAD")
    candidate_tree = _git(candidate, "rev-parse", "HEAD^{tree}")
    shutil.rmtree(candidate / ".git" / "hooks")

    implementation = tmp_path / "implementation"
    implementation.mkdir(); _git(implementation, "init", "-q")
    _git(implementation, "commit", "--allow-empty", "-q", "-m", "closure")
    closure_commit = _git(implementation, "rev-parse", "HEAD")
    closure_tree = _git(implementation, "rev-parse", "HEAD^{tree}")
    source = implementation / "tests" / "e3_host"
    source.mkdir(parents=True)
    loader = b"def main():\n    return None\n"
    bootstrap = ("LOADER_SHA256 = %r\n" % hashlib.sha256(loader).hexdigest()).encode()
    dispatcher = b"def dispatch(context, effects):\n    return b''\n"
    for name, raw in (("loader", loader), ("bootstrap", bootstrap),
                      ("dispatcher", dispatcher)):
        (source / f"q2_core_delivery_{name}.py").write_bytes(raw)
    _git(implementation, "add", "tests/e3_host")
    _git(implementation, "commit", "-q", "-m", "implementation")
    implementation_commit = _git(implementation, "rev-parse", "HEAD")
    implementation_tree = _git(implementation, "rev-parse", "HEAD^{tree}")

    monkeypatch.setattr(f.c, "CANDIDATE", {"commit": candidate_commit, "tree": candidate_tree})
    monkeypatch.setattr(f.c, "CLOSURE", {"commit": closure_commit, "tree": closure_tree})
    wheel_raw = b"exact-wheel"
    wheel = tmp_path / "unit.whl"; wheel.write_bytes(wheel_raw)
    projection_value = {
        "schema": "local-hand-q2-source-projection/v1",
        "source_commit": candidate_commit, "source_tree": candidate_tree,
        "files": {"README.md": {
            "mode": 0o644, "sha256": hashlib.sha256(b"candidate\n").hexdigest(),
        }},
    }
    projection_raw = f.c.canonical(projection_value, newline=True)
    projection = tmp_path / "projection.json"; projection.write_bytes(projection_raw)
    monkeypatch.setattr(f.c, "WHEEL", {
        "basename": wheel.name, "bytes": len(wheel_raw),
        "sha256": hashlib.sha256(wheel_raw).hexdigest(), "payload_digest": "a" * 64,
    })
    monkeypatch.setattr(f.c, "PROJECTION", {
        "basename": projection.name, "bytes": len(projection_raw),
        "sha256": hashlib.sha256(projection_raw).hexdigest(), "file_count": 1,
    })
    arguments = dict(
        candidate_checkout=candidate, wheel_path=wheel, projection_path=projection,
        implementation_repository=implementation,
        implementation_commit=implementation_commit, implementation_tree=implementation_tree,
    )
    return arguments


def test_static_member_freeze_reads_committed_blobs_and_does_not_build_package(
        tmp_path, monkeypatch):
    arguments = package_fixture(tmp_path, monkeypatch)
    result = f.freeze_package_members(**arguments)
    assert result["state"] == "STATIC_MEMBERS_FROZEN"
    assert result["issuance"] == "NOT_ISSUED" and result["package"] is None
    paths = {row["path"] for row in result["members"]}
    assert "candidate/README.md" in paths and "candidate/empty.log" in paths
    assert {"field/loader.py", "field/bootstrap.py", "field/dispatcher.py"} <= paths
    assert any(path.startswith("candidate/.git/objects/") for path in paths)
    empty = next(row for row in result["members"] if row["path"] == "candidate/empty.log")
    assert empty["bytes"] == 0 and result["member_bytes"]["candidate/empty.log"] == b""
    for row in result["members"]:
        assert hashlib.sha256(result["member_bytes"][row["path"]]).hexdigest() == row["sha256"]


def test_static_member_freeze_rejects_untracked_checkout_and_uncommitted_d(
        tmp_path, monkeypatch):
    not_ready = f.freeze_package_members(
        candidate_checkout=tmp_path / "absent", wheel_path=tmp_path / "absent.whl",
        projection_path=tmp_path / "absent.json", implementation_repository=tmp_path,
    )
    assert not_ready["state"] == "NOT_PREPARED"
    assert not_ready["missing"] == ["implementation.commit", "implementation.tree"]
    arguments = package_fixture(tmp_path / "ready", monkeypatch)
    (arguments["candidate_checkout"] / "untracked.txt").write_text("not clean\n")
    with pytest.raises(f.c.ContractError, match="CORE_FREEZE_CHECKOUT_SET"):
        f.freeze_package_members(**arguments)


@pytest.mark.parametrize("unsafe_config", [
    "[core]\nworktree = /tmp/alternate-worktree\n",
    "[core]\nhooksPath = /tmp/alternate-hooks\n",
    "[core]\nalternateRefsCommand = /bin/false\n",
    "[extensions]\nworktreeConfig = true\n",
    "[extensions]\nobjectFormat = sha1\n",
])
def test_static_member_freeze_rejects_git_source_configuration_before_git_exec(
        tmp_path, monkeypatch, unsafe_config):
    arguments = package_fixture(tmp_path, monkeypatch)
    config = arguments["candidate_checkout"] / ".git" / "config"
    config.write_text(config.read_text() + unsafe_config)

    def unexpected_git(*_args, **_kwargs):
        raise AssertionError("unsafe candidate config reached a Git subprocess")

    monkeypatch.setattr(f.subprocess, "run", unexpected_git)
    with pytest.raises(f.c.ContractError, match="CORE_FREEZE_GIT_DEPENDENCY"):
        f.freeze_package_members(**arguments)


def test_bound_executable_rejects_wrong_digest(tmp_path):
    executable = tmp_path / "program"
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    raw, info = f._read_regular(
        executable, limit=4096, code="TEST_DEPENDENCY", noatime=False,
    )
    expected = {
        "role": "program", **f._file_identity(str(executable), info, raw),
    }
    expected["sha256"] = "0" * 64
    with pytest.raises(f.c.ContractError, match="TEST_DEPENDENCY"):
        f._open_bound_executable(expected, limit=4096, code="TEST_DEPENDENCY")


def test_management_anchor_verifies_dependencies_before_held_ssh_keygen_exec(
        tmp_path, monkeypatch):
    anchor = tmp_path / "anchor"
    anchor.mkdir(mode=0o700)
    public = b"ssh-ed25519 UNIT-TEST\n"
    anchor_values = {
        "ssh.sh": (b"wrapper\n", 0o700, "wrapper"),
        "start.sh": (b"start\n", 0o700, "fixture_start"),
        "user-data": (
            b"#cloud-config\nq1admin ALL=(ALL) NOPASSWD:ALL\n",
            0o600,
            "fixture_cloud_config",
        ),
        "id_ed25519.pub": (public, 0o600, "identity_public"),
        "known_hosts": (b"host key\n", 0o644, "known_hosts"),
    }
    pins = {}
    for name, (raw, mode, role) in anchor_values.items():
        path = anchor / name
        path.write_bytes(raw)
        path.chmod(mode)
        pins[name] = (mode, hashlib.sha256(raw).hexdigest(), role)
    private = anchor / "id_ed25519"
    private.write_bytes(b"protected-private-key\n")
    private.chmod(0o600)
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    monkeypatch.setattr(f, "ANCHOR_FILES", pins)
    monkeypatch.setattr(f.entry_api, "PUBLIC_KEY_SHA256",
                        hashlib.sha256(public).hexdigest())
    observed_dependencies = []
    original_read = f._read_regular

    def observing_read(path, **kwargs):
        observed_dependencies.append(os.fspath(path))
        return original_read(path, **kwargs)

    def derived_key(command, **kwargs):
        assert observed_dependencies == [path for _role, path in f.LOCAL_DEPENDENCIES]
        assert command == [
            "/usr/bin/ssh-keygen", "-y", "-f", command[-1],
        ]
        executable = kwargs["executable"]
        assert executable.startswith("/proc/self/fd/")
        executable_fd = int(executable.rsplit("/", 1)[1])
        assert executable_fd in kwargs["pass_fds"]
        held = os.fstat(executable_fd)
        current = os.lstat("/usr/bin/ssh-keygen")
        assert f._same_stat(held, current)
        return SimpleNamespace(returncode=0, stdout=public, stderr=b"")

    monkeypatch.setattr(f, "_read_regular", observing_read)
    monkeypatch.setattr(f.subprocess, "run", derived_key)
    result = f.inspect_management_anchor(
        anchor_root=anchor,
        cwd=cwd,
        environment={"HOME": "/unit", "USER": "unit", "LOGNAME": "unit"},
    )
    assert result["state"] == "NOT_PREPARED"
    assert result["issuance"] == "NOT_ISSUED"
    assert result["package"] is None
    assert [item["role"] for item in result["private_local_anchor"]["dependencies"]] == [
        role for role, _path in f.LOCAL_DEPENDENCIES
    ]

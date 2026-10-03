"""Offline tests for the approved namespace-fixture delivery contract."""
from __future__ import annotations

import ast
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex

import pytest


SOURCE = Path(__file__).parents[1] / "tools/q2_namespace_delivery.py"


def module():
    spec = importlib.util.spec_from_file_location("_q2_namespace_delivery_test", SOURCE)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def digest(label):
    return hashlib.sha256(label.encode()).hexdigest()


def external_success_receipt(value, expected):
    """Encode bytes attributed to an external native tail, never the module."""
    raw = bytearray(value.SUCCESS_RECEIPT_SIZE)
    raw[:8] = value.SUCCESS_RECEIPT_MAGIC
    for name, offset in (
        ("version", 8),
        ("process_cpu_ns", 16),
        ("boottime_ns", 24),
        ("monotonic_ns", 32),
        ("realtime_ns", 40),
        ("counter", 48),
    ):
        raw[offset:offset + 8] = expected[name].to_bytes(8, "little")
    for name, offset in (
        ("previous_digest", 56),
        ("handoff_sha256", 88),
        ("cleanup_final_sha256", 120),
        ("capture_head_sha256", 152),
    ):
        raw[offset:offset + 32] = bytes.fromhex(expected[name])
    raw[192:224] = hashlib.sha256(raw[:192]).digest()
    return bytes(raw)


def identity(path, label, *, regular):
    value = {
        "path": path,
        "mount_id": 11,
        "device": 12,
        "inode": int(digest(label)[:8], 16) + 1,
        "uid": 0,
        "gid": 0,
        "mode": 0o500 if regular else 0o700,
        "parents_unwritable": True,
    }
    if regular:
        value.update(size=4096, sha256=digest(label + "-bytes"))
    return value


def watchdog(value, runtime_path, loader, token, args):
    watchdog_identity = identity("/opt/sealed/bin/q2-watchdog", "watchdog", regular=True)
    loader_identity = identity("/lib64/ld-linux-x86-64.so.2", "loader", regular=True)
    libc_identity = identity("/lib/x86_64-linux-gnu/libc.so.6", "libc", regular=True)
    dependencies = [{"name": "libc.so.6", "identity": libc_identity}]
    watchdog_argv = [watchdog_identity["path"], *args, "--", runtime_path,
        "-I", "-B", "-c", loader, token]
    return {
        "schema": value.WATCHDOG_SCHEMA,
        "version": "q2-watchdog-1.0",
        "identity": watchdog_identity,
        "source": {
            "source_sha256": digest("watchdog-source"),
            "binary_sha256": watchdog_identity["sha256"],
            "relation_sha256": digest("watchdog-relation"),
            "build_manifest_sha256": digest("watchdog-build"),
            "fault_trace_sha256": digest("watchdog-trace"),
        },
        "elf": {
            "class": "ELF64",
            "machine": "EM_X86_64",
            "pt_interp": loader_identity["path"],
            "loader": loader_identity,
            "dt_needed": dependencies,
            "dt_needed_sha256": value.canonical_digest(dependencies),
            "complete": True,
        },
        "invocation": {
            "argv_sha256": value.canonical_digest(watchdog_argv),
            "environment": {"LANG": "C", "LC_ALL": "C"},
            "cwd": "/",
            "umask": 0o077,
        },
        "security": {
            "setid": False,
            "file_caps": False,
            "ambient_caps": [],
            "capabilities_sha256": digest("watchdog-caps"),
            "securebits_sha256": digest("watchdog-securebits"),
            "seccomp_sha256": digest("watchdog-seccomp"),
            "lsm_sha256": digest("watchdog-lsm"),
            "affinity_sha256": digest("watchdog-affinity"),
            "scheduler_sha256": digest("watchdog-scheduler"),
        },
        "prefix": {
            "cpu_ns": 100_000_000,
            "wall_ns": 200_000_000,
            "tasks": 1,
            "userspace_as_bytes": 8 * value.MIB,
            "userspace_rss_bytes": 4 * value.MIB,
            "physical_risk_bytes": 8 * value.MIB,
            "entry_installed_fds": 3,
            "outer_read_calls": 0,
            "outer_write_calls": 0,
            "pipe_bytes": 8192,
            "kernel_object_bytes": 4096,
            "kernel_object_inodes": 3,
            "audit_bytes": 4096,
            "audit_inodes": 2,
            "fault_trace_qualified": True,
            "mutation_before_clone": False,
        },
        "state_machine": copy.deepcopy(value.WATCHDOG_STATE_CONTRACT),
        "resources": {
            "rlimits": {
                "CPU": [8, 9],
                "AS": [64 * value.MIB, 64 * value.MIB],
                "DATA": [64 * value.MIB, 64 * value.MIB],
                "NOFILE": [8, 8],
                "CORE": [0, 0],
                "FSIZE": [0, 0],
                "STACK": [8 * value.MIB, 8 * value.MIB],
                "MEMLOCK": [0, 0],
                "MSGQUEUE": [0, 0],
                "NICE": [0, 0],
                "RTPRIO": [0, 0],
                "RTTIME": [0, 0],
            },
            "preclone_installed_fds": 5,
            "postclone_base_fds": 6,
            "peak_installed_fds": 7,
            "steady_fds": 3,
            "tasks": 1,
            "physical_risk_bytes": 32 * value.MIB,
            "full_failure_cpu_ns": 9_000_000_000,
            "success_cpu_ns": 900_000_000,
            "remote_exit_ns": 830_000_000_000,
            "wake_to_kill_ns": 4_000_000_000,
            "kill_to_reap_ns": 4_000_000_000,
            "reap_to_status_eof_ns": 4_000_000_000,
        },
        "status_map": {
            "zero": "L_CLD_EXITED_0_ONLY",
            "nonzero": "COARSE_FAILURE_ONLY",
            "signal_or_unreaped": "UNKNOWN_RETAINED",
        },
    }


def device(value, role, seed, *, available=1024 * 1024 * 1024,
           available_inodes=100_000):
    floor = value.DEVICE_ROLE_FLOORS[role]
    obligation = {
        "id": role + "-old",
        "current_bytes": 4096,
        "current_inodes": 1,
        "future_ceiling_bytes": 8192,
        "future_ceiling_inodes": 2,
    }
    total = {"bytes": 8192 + floor["bytes"] + 4096,
        "inodes": 2 + floor["inodes"] + 2}
    return {
        "role": role,
        "device_ref": digest(seed),
        "available_bytes": available,
        "available_inodes": available_inodes,
        "obligations": [obligation],
        "new_peak": copy.deepcopy(floor),
        "margin": {"bytes": 4096, "inodes": 2},
        "claimed_total": total,
        "policy": {
            "same_obligation_uses_max": True,
            "hardlink_dedup_same_device_inode_only": True,
            "reflink_or_sparse_credit_requires_extent_proof": True,
            "partial_final_inode_uses_simultaneous_peak": True,
            "concurrent_writers_absent": True,
            "deletion_refunds_budget": False,
        },
    }


def manifest(value, runtime_path):
    source = "raise SystemExit(0)\n"
    token = base64.urlsafe_b64encode(source.encode()).rstrip(b"=").decode()
    loader = "import base64;exec(base64.urlsafe_b64decode(__import__('sys').argv[1]+'=='))"
    args = ["--contract", digest("watchdog-contract")]
    bridge_source = (SOURCE.parents[1] / "tests" / "e3_host" /
        "q2_namespace_clone_bridge.c").read_bytes()
    bridge_binary = b"\x7fELF" + b"\x00" * (8192 - 4)
    bridge_binary_sha256 = hashlib.sha256(bridge_binary).hexdigest()
    members = [
        {"basename": "q2_namespace_reference.py", "role": "collector", "bytes": 4096,
            "sha256": digest("collector"), "mode": 0o400},
        {"basename": "q2_namespace_fixture.py", "role": "supervisor", "bytes": 6144,
            "sha256": digest("supervisor"), "mode": 0o400},
        {"basename": "q2_namespace_clone_bridge.so", "role": "bridge",
            "bytes": len(bridge_binary), "sha256": bridge_binary_sha256, "mode": 0o500},
        {"basename": "q2_namespace_schema.json", "role": "schema", "bytes": 1024,
            "sha256": digest("schema"), "mode": 0o400},
        {"basename": "fixture-manifest.json", "role": "manifest", "bytes": 2048,
            "sha256": digest("fixture-manifest"), "mode": 0o400},
        {"basename": "q2_namespace_launcher.py", "role": "launcher", "bytes": 4096,
            "sha256": digest("launcher"), "mode": 0o400},
    ]
    aggregate = [{key: member[key] for key in ("basename", "bytes", "sha256")}
        for member in sorted(members, key=lambda item: item["basename"])]
    bridge_loader = identity("/lib64/ld-linux-x86-64.so.2", "bridge-loader",
        regular=True)
    bridge_dependencies = [{"name": "libc.so.6", "identity": identity(
        "/lib/x86_64-linux-gnu/libc.so.6", "bridge-libc", regular=True)}]
    bridge_flags = [
        "-std=c11", "-O2", "-fPIC", "-shared", "-fno-ident", "-Wall",
        "-Wextra", "-Werror", "-Wl,--build-id=none",
        "-I/opt/q2/runtime/include/python3.12",
    ]
    bridge_exports = list(value.REQUIRED_BRIDGE_EXPORTS)
    bridge_elf = {
        "class": "ELF64",
        "machine": "EM_X86_64",
        "type": "ET_DYN",
        "pt_interp_absent": True,
        "dt_needed": bridge_dependencies,
        "dt_needed_sha256": value.canonical_digest(bridge_dependencies),
        "complete": True,
    }
    runtime_loader = {
        "runtime_path": runtime_path,
        "runtime_sha256": digest("runtime-bytes"),
        "pt_interp": bridge_loader["path"],
        "loader": bridge_loader,
    }
    native_abi = value.native_bridge_abi()
    source_sha256 = hashlib.sha256(bridge_source).hexdigest()
    compiler_sha256 = hashlib.sha256(b"sealed-cc-binary-v1").hexdigest()
    compiler_version_sha256 = hashlib.sha256(
        b"sealed-cc-version-output-v1").hexdigest()
    flags_sha256 = value.canonical_digest(bridge_flags)
    build_manifest = {
        "schema": value.BRIDGE_BUILD_SCHEMA,
        "source_sha256": source_sha256,
        "compiler_sha256": compiler_sha256,
        "compiler_version_sha256": compiler_version_sha256,
        "flags": bridge_flags,
        "flags_sha256": flags_sha256,
        "deterministic_build_id_disabled": True,
        "python_abi": "linux-x86_64-lp64-cpython-3.12",
        "soabi": "cpython-312-x86_64-linux-gnu",
        "elf_sha256": value.canonical_digest(bridge_elf),
        "runtime_loader_sha256": value.canonical_digest(runtime_loader),
        "native_abi_sha256": value.canonical_digest(native_abi),
    }
    build_manifest_sha256 = value.canonical_digest(build_manifest)
    relation = {
        "schema": value.BRIDGE_RELATION_SCHEMA,
        "source_sha256": source_sha256,
        "build_manifest_sha256": build_manifest_sha256,
        "binary_bytes": len(bridge_binary),
        "binary_sha256": bridge_binary_sha256,
    }
    bridge = {
        "schema": value.BRIDGE_SCHEMA,
        "member_basename": "q2_namespace_clone_bridge.so",
        "binary_bytes": len(bridge_binary),
        "binary_sha256": bridge_binary_sha256,
        "source_sha256": source_sha256,
        "relation": relation,
        "relation_sha256": value.canonical_digest(relation),
        "build_manifest": build_manifest,
        "build_manifest_sha256": build_manifest_sha256,
        "compiler_sha256": compiler_sha256,
        "compiler_version_sha256": compiler_version_sha256,
        "flags": bridge_flags,
        "flags_sha256": flags_sha256,
        "deterministic_build_id_disabled": True,
        "python_abi": "linux-x86_64-lp64-cpython-3.12",
        "soabi": "cpython-312-x86_64-linux-gnu",
        "elf": bridge_elf,
        "runtime_loader": runtime_loader,
        "native_abi": native_abi,
        "exports": bridge_exports,
        "exports_sha256": value.canonical_digest(bridge_exports),
        "clean_build_one_sha256": bridge_binary_sha256,
        "clean_build_two_sha256": bridge_binary_sha256,
    }
    return {
        "schema": value.MANIFEST_SCHEMA,
        "watchdog": watchdog(value, runtime_path, loader, token, args),
        "watchdog_args": args,
        "bootstrap": {
            "source": source,
            "source_bytes": len(source.encode()),
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "token": token,
            "fixed_loader": loader,
            "fixed_loader_sha256": hashlib.sha256(loader.encode()).hexdigest(),
        },
        "bundle": {
            "members": members,
            "total_bytes": sum(member["bytes"] for member in members),
            "file_count": len(members),
            "aggregate_sha256": value.canonical_digest(aggregate),
        },
        "bridge": bridge,
        "stage": {
            "action_journal_bytes": 64 * 1024,
            "result_journal_bytes": 752 * 1024,
            "case_slot_bytes": 16 * 1024,
            "case_slot_count": 12,
            "result_offsets": {"header": 0, "cases": 8192, "excursions": 598016,
                "terminal": 753664, "eof": 770048},
            "actual": {
                "bundle_bytes": sum(member["bytes"] for member in members),
                "bundle_files": len(members),
                "logical_bytes": (sum(member["bytes"] for member in members)
                    + 64 * 1024 + 752 * 1024 + 12 * 16 * 1024),
                "regular_inodes": len(members) + 14,
                "total_inodes": len(members) + 15,
            },
            "ceilings": {
                "bundle_bytes": value.MAX_BUNDLE_BYTES,
                "bundle_files": value.MAX_BUNDLE_FILES,
                "logical_bytes": 2_080_768,
                "regular_inodes": 22,
                "total_inodes": 23,
            },
        },
        "protocol": {
            "case_ids": list(value.CASE_IDS),
            "reference_report_schema": value.REFERENCE_REPORT_SCHEMA,
            "collector_frames": 15,
            "reference_contract": value.reference_contract(),
            "carrier_requests": 1,
            "batch_releases": 1,
            "native_batches": 1,
            "action_commits": 37,
            "old_carrier_self_writes": 38,
            "guardian_self_writes": 38,
            "total_self_writes": 76,
            "guardian_outer_write_calls": 0,
            "guardian_outer_write_bytes": 0,
            "handoff_max_bytes": value.MAX_H_BYTES,
            "cleanup_final_max_bytes": value.MAX_CLEANUP_FINAL_BYTES,
            "success_receipt_bytes": value.SUCCESS_RECEIPT_SIZE,
            "success_receipt_layout_sha256": value.canonical_digest(
                value.SUCCESS_RECEIPT_LAYOUT),
        },
        "deadlines": copy.deepcopy(value.DEADLINE_CEILINGS),
        "source_review": {
            "watchdog_source_reviewed": True,
            "watchdog_fault_trace_reviewed": True,
            "implementation_source_reviewed": True,
            "bridge_source_reviewed": True,
            "bridge_clean_builds_verified": True,
            "bridge_exports_verified": True,
            "strict_parser_tests_passed": True,
            "fault_tests_passed": True,
            "native_supported_results_retained": True,
            "unsupported_results_retained": True,
            "review_sha256": digest("independent-source-review"),
        },
    }


def plan(value, sealed_manifest):
    runtime = identity("/opt/q2/runtime/bin/python3", "runtime", regular=True)
    manifest_sha = value.canonical_digest(sealed_manifest)
    wrapper_source = """#!/usr/bin/env bash
set -euo pipefail
q1_vm=/private/fixed
exec ssh -F /dev/null \\
  -i "$q1_vm/id_ed25519" -p 22022 \\
  -o IdentitiesOnly=yes -o BatchMode=yes \\
  -o StrictHostKeyChecking=accept-new \\
  -o UserKnownHostsFile="$q1_vm/known_hosts" \\
  -o ConnectTimeout=10 \\
  fixture@fixture.invalid "$@"
"""
    wrapper_raw = wrapper_source.encode()
    wrapper_identity = identity("/private/fixed/carrier-wrapper.sh", "wrapper",
        regular=True)
    wrapper_identity["size"] = len(wrapper_raw)
    wrapper_identity["sha256"] = hashlib.sha256(wrapper_raw).hexdigest()
    host_environment = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
    identity_object = identity("/private/fixed/id_ed25519", "identity-file",
        regular=True)
    identity_object["mode"] = 0o400
    known_hosts_object = identity("/private/fixed/known_hosts", "known-hosts-file",
        regular=True)
    known_hosts_object["mode"] = 0o400
    result = {
        "schema": value.PLAN_SCHEMA,
        "authority": {
            "R": value.RULE,
            "A": value.BASELINE,
            "C": value.CLOSURE,
            "owner_event": value.OWNER_DECISION,
            "scope": value.SCOPE,
            "phases": list(value.PHASES),
            "endpoint_integrity_premise_accepted": True,
            "original_terminal_provenance_accepted": False,
        },
        "implementation": {
            "commit": "1" * 40,
            "tree": "2" * 40,
            "source_files_sha256": digest("source-files"),
            "closure_ancestor_verified": True,
            "clean_tree": True,
            "targeted_tests_sha256": digest("targeted-tests"),
            "full_suite_sha256": digest("full-suite"),
            "native_ci_sha256": digest("native-ci"),
            "independent_review_sha256": digest("independent-review"),
        },
        "batch_id": "fixture-20261003-a",
        "case_ids": list(value.CASE_IDS),
        "target": {
            "guest_ref": digest("private-guest-reference"),
            "guest_source_sha256": digest("guest-source"),
            "expected_boot_id": "11111111-2222-3333-4444-555555555555",
            "uid": 12001,
            "gid": 12001,
            "groups": [12001, 12002],
            "groups_source_sha256": digest("groups-source"),
            "same_uid_allowlist_sha256": digest("same-uid-allowlist"),
            "historical_fixture_only": True,
        },
        "manager_read": {
            "unit": "user@12001.service",
            "source_role": "sealed-manager-read-v1",
            "api": "fixed.show.properties",
            "fields": ["MainPID", "InvocationID", "ControlGroup"],
            "calls": 1,
            "source_sha256": digest("manager-read-source"),
            "writes_forbidden": True,
            "enumeration_forbidden": True,
        },
        "carrier": {
            "profile": "env-bash-literal-ssh-v1",
            "profile_sha256": hashlib.sha256(wrapper_raw).hexdigest(),
            "host": {
                "PATH": "/usr/bin:/bin",
                "cwd": "/",
                "environment": host_environment,
                "environment_sha256": value.canonical_digest(host_environment),
                "env_binary": "/usr/bin/env",
                "env_identity": identity("/usr/bin/env", "host-env", regular=True),
                "bash_binary": "/usr/bin/bash",
                "bash_identity": identity("/usr/bin/bash", "host-bash", regular=True),
                "ssh_binary": "/usr/bin/ssh",
                "ssh_identity": identity("/usr/bin/ssh", "host-ssh", regular=True),
                "wrapper_source": wrapper_source,
                "wrapper_source_bytes": len(wrapper_raw),
                "wrapper_source_sha256": hashlib.sha256(wrapper_raw).hexdigest(),
                "wrapper_identity": wrapper_identity,
                "identity_file": "/private/fixed/id_ed25519",
                "identity_sha256": identity_object["sha256"],
                "identity_object": identity_object,
                "known_hosts": "/private/fixed/known_hosts",
                "known_hosts_sha256": known_hosts_object["sha256"],
                "known_hosts_object": known_hosts_object,
                "host_key_sha256": digest("host-key"),
                "local_argv": [],
                "local_argv_sha256": digest("placeholder-local-argv"),
                "ssh_argv": [],
                "ssh_argv_sha256": digest("placeholder-ssh-argv"),
                "excluded_environment": list(value.FORBIDDEN_LAUNCH_ENV),
                "fixed_identity_only": True,
                "known_host_preexisting": True,
                "new_host_key_adoption": False,
            },
            "remote": {
                "login_shell": "/bin/bash",
                "login_shell_identity": identity("/bin/bash", "remote-login-shell",
                    regular=True),
                "login_shell_version_sha256": digest("remote-login-shell-version"),
                "parser": "bash-posix-c-v1",
                "shell_argv_sha256": digest("placeholder-shell-argv"),
                "sudo_path": "/usr/bin/sudo",
                "sudo_identity": identity("/usr/bin/sudo", "remote-sudo", regular=True),
                "env_path": "/usr/bin/env",
                "env_identity": identity("/usr/bin/env", "remote-env", regular=True),
                "sudo_policy_sha256": digest("sudo-policy"),
                "no_pty": True,
                "stdin_binary": True,
                "stdout_stderr_separate": True,
                "wrapper_reads_stdin": False,
                "wrapper_redirects_stdio": False,
                "force_command_absent": True,
                "authorized_keys_command_absent": True,
                "ssh_rc_absent": True,
                "shell_startup_hooks_absent": True,
                "bash_env_absent": True,
                "env_hook_absent": True,
                "sudo_use_pty_absent": True,
                "sudo_io_plugin_absent": True,
                "sudo_prompt_absent": True,
            },
            "core_pattern": {"source_sha256": digest("core-source"),
                "value_sha256": digest("core-value"), "is_pipe": False},
            "remote_command": "placeholder",
            "remote_command_sha256": digest("placeholder"),
        },
        "runtime": {"identity": runtime, "abi": "linux-x86_64-lp64-cpython-3.12",
            "soabi": "cpython-312-x86_64-linux-gnu",
            "import_closure_sha256": digest("runtime-imports"),
            "supports_isolated_mode": True, "guest_compilation": False},
        "anchor": {
            "identity": identity("/sys/fs/cgroup/q2-fixture-anchor", "anchor", regular=False),
            "source_sha256": digest("anchor-source"),
            "fs_magic": "CGROUP2_SUPER_MAGIC",
            "root_owned": True,
            "ordinary_delegation": False,
            "other_writer": False,
            "cgroup_type": "domain",
            "procs_empty": True,
            "subtree_control": list(value.CONTROLLERS),
            "nr_dying_descendants": 0,
            "live_descendants_d0": 0,
            "depth_remaining": 3,
            "descendants_remaining_after_d0": 4,
            "cpuset_cpus": "2",
            "cpuset_mems": "0",
            "parent_controls_read_only": True,
        },
        "carrier_leaf": {
            "identity": identity("/sys/fs/cgroup/carrier/session", "carrier-leaf",
                regular=False),
            "source_sha256": digest("carrier-leaf-source"),
            "cgroup_type": "domain",
            "subtree_control": [],
            "freeze": 0,
            "populated": 1,
            "frozen": 0,
            "cpuset_cpus_effective": "2",
            "cpuset_mems_effective": "0",
            "parent_persistent": True,
            "held_fd_required": True,
            "cleanup_or_limit_race_absent": True,
            "numeric_pid_writes": False,
            "action_roundtrips": 37,
            "final_entries": 1,
            "old_carrier_self_writes": 38,
            "guardian_self_writes": 38,
            "total_self_writes": 76,
        },
        "stage_parent": identity("/run", "run-parent", regular=False),
        "capture": {
            "private_parent_ref": digest("private-capture-parent"),
            "private_parent_source_sha256": digest("private-capture-source"),
            "append_fsync_before_ack": True,
            "raw_publication": False,
            "public_summary_only": True,
            "max_logical_bytes": 8 * value.MIB,
            "max_logical_inodes": 256,
            "max_physical_bytes": 12 * value.MIB,
            "max_physical_inodes": 320,
        },
        "clocks": {
            "ceilings": copy.deepcopy(value.DEADLINE_CEILINGS),
            "owner_adjtimex_sha256": digest("owner-adjtimex"),
            "guest_adjtimex_sha256": digest("guest-adjtimex"),
            "owner_clocksource_sha256": digest("owner-clocksource"),
            "guest_clocksource_sha256": digest("guest-clocksource"),
            "relative_frequency_bound_sha256": digest("relative-frequency"),
            "refresh_allowed": False,
        },
        "budgets": {
            "ceilings": copy.deepcopy(value.BUDGET_CEILINGS),
            "kernel_object_bytes": sealed_manifest["watchdog"]["prefix"][
                "kernel_object_bytes"],
            "kernel_object_inodes": sealed_manifest["watchdog"]["prefix"][
                "kernel_object_inodes"],
            "watchdog_prefix": {key: sealed_manifest["watchdog"]["prefix"][key]
                for key in ("userspace_as_bytes", "userspace_rss_bytes",
                    "physical_risk_bytes", "pipe_bytes", "kernel_object_bytes",
                    "kernel_object_inodes", "audit_bytes", "audit_inodes")},
            "watchdog_and_carrier_shared_extent_proven": False,
            "devices": [device(value, role, role + "-device") for role in
                ("carrier", "guest_tmpfs", "private_capture", "public_record")],
            "source_sha256": digest("budget-source"),
        },
        "fixed_sources": {name: True for name in ("target", "ordinary_identity",
            "manager", "runtime", "carrier", "anchor", "carrier_leaf", "stage_parent",
            "watchdog", "budget", "clock", "audit", "capture")},
        "manifest_sha256": manifest_sha,
        "initial_state": {},
    }
    command = value.expected_remote_command(result, sealed_manifest)
    result["carrier"]["remote_command"] = command
    result["carrier"]["remote_command_sha256"] = hashlib.sha256(command.encode()).hexdigest()
    host = result["carrier"]["host"]
    host["local_argv"] = [host["env_binary"], "bash", "-c", host["wrapper_source"],
        host["wrapper_identity"]["path"], command]
    host["local_argv_sha256"] = value.canonical_digest(host["local_argv"])
    host["ssh_argv"] = ["ssh", "-F", "/dev/null", "-i", host["identity_file"],
        "-p", "22022", "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new", "-o",
        "UserKnownHostsFile=" + host["known_hosts"], "-o", "ConnectTimeout=10",
        "fixture@fixture.invalid", command]
    host["ssh_argv_sha256"] = value.canonical_digest(host["ssh_argv"])
    result["carrier"]["remote"]["shell_argv_sha256"] = value.canonical_digest(
        shlex.split(command, posix=True))
    without_state = copy.deepcopy(result)
    without_state.pop("initial_state")
    result["initial_state"] = value.initial_state(
        value.canonical_digest(without_state), manifest_sha)
    return result


@pytest.fixture
def contract():
    value = module()
    runtime_path = "/opt/q2/runtime/bin/python3"
    sealed_manifest = manifest(value, runtime_path)
    private_plan = plan(value, sealed_manifest)
    return value, private_plan, sealed_manifest


def mutate(data, path, replacement):
    value = copy.deepcopy(data)
    cursor = value
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = replacement
    return value


def rebind_plan_state(value, private_plan):
    rebound = copy.deepcopy(private_plan)
    manifest_sha = rebound["manifest_sha256"]
    without_state = copy.deepcopy(rebound)
    without_state.pop("initial_state")
    rebound["initial_state"] = value.initial_state(
        value.canonical_digest(without_state), manifest_sha)
    return rebound


def external_capture_ack(value, state, raw):
    frame = value.verify_frame(raw)
    return {
        "schema": value.CAPTURE_ACK_SCHEMA,
        "counter": frame["counter"],
        "frame_digest": hashlib.sha256(raw).hexdigest(),
        "capture_head": value.next_capture_head(state["capture_head"], raw),
        "append_complete": True,
        "fsync_complete": True,
    }


def external_field_frame(value, kind, payload, *, counter, previous_digest):
    """Model bytes received from a field writer; this is not product code."""
    payload_raw = value.canonical_bytes(payload, maximum=value.MAX_FRAME_PAYLOAD_BYTES)
    return value.canonical_bytes({
        "schema": value.FRAME_SCHEMA,
        "kind": kind,
        "counter": counter,
        "previous_digest": previous_digest,
        "payload_bytes": len(payload_raw),
        "payload_sha256": hashlib.sha256(payload_raw).hexdigest(),
        "payload": payload,
    }, maximum=value.MAX_FRAME_PAYLOAD_BYTES + 4096)


def test_authority_and_hard_limits_are_exact():
    value = module()
    assert (value.RULE, value.BASELINE, value.CLOSURE, value.OWNER_DECISION) == (
        "10d2a5c827964989f41ca6e8eeac3d44de6d0f04",
        "ad5abaee642cba02d997149badf75a08c219a35c",
        "f5d60351c95c0276a95c7843215e02b0a69fdc3f",
        "LH-Q2-NAMESPACE-FIXTURE-DELIVERY-CLOSURE-20261003-01",
    )
    assert value.CASE_IDS == tuple(f"N{number:02d}" for number in range(1, 13))
    assert (value.MAX_CARRIER_REQUESTS, value.MAX_BATCH_RELEASES,
        value.MAX_NATIVE_BATCHES, value.MAX_CASES, value.MAX_ACTIONS) == (1, 1, 1, 12, 37)
    assert (value.MAX_H_BYTES, value.MAX_CLEANUP_FINAL_BYTES,
        value.MAX_SUCCESS_RECEIPT_BYTES) == (16384, 32768, 224)
    assert value.SUCCESS_RECEIPT_LAYOUT["digest_offsets"] == {
        "previous_digest": 56,
        "handoff_sha256": 88,
        "cleanup_final_sha256": 120,
        "capture_head_sha256": 152,
    }


def test_module_has_no_execution_or_field_io_primitive():
    tree = ast.parse(SOURCE.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert not imports.intersection({"ctypes", "fcntl", "os", "socket", "subprocess", "sys"})
    calls = {node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not calls.intersection({"open", "exec", "eval", "compile", "__import__"})
    strings = [node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    assert not any(text.startswith(("/home/", "/mnt/")) for text in strings)


def test_absent_private_inputs_are_not_issued():
    value = module()
    result = value.evaluate_f0()
    assert result["status"] == "NOT_ISSUED"
    assert result["blockers"] == ["F0_PRIVATE_PLAN_ABSENT", "F0_SEALED_MANIFEST_ABSENT"]
    assert not result["can_issue_carrier"]
    assert not result["fixture_delivery_issued"]
    assert result["batch_release_outcome"] == "NOT_SENT"
    partial = value.evaluate_f0({"target": {}}, {"watchdog": {}})
    assert "F0_PLAN_CARRIER_ABSENT" in partial["blockers"]
    assert "F0_MANIFEST_BOOTSTRAP_ABSENT" in partial["blockers"]


def test_complete_offline_contract_shape_is_bound_but_not_artifact_or_live_authority(contract):
    value, private_plan, sealed_manifest = contract
    result = value.evaluate_f0(private_plan, sealed_manifest)
    assert result["status"] == "OFFLINE_CONTRACT_SHAPE_VERIFIED"
    assert result["contract_shape_only"]
    assert result["external_source_checks_required"]
    assert not result["can_issue_carrier"]
    assert not result["can_issue_release"] and not result["can_issue_native"]
    for name in ("field_facts_proven", "source_bytes_proven", "build_proven",
                 "live_proven", "durability_proven", "guest_contacted"):
        assert result[name] is False
    assert result["remote_command_bytes"] <= 48 * 1024
    assert result["remote_command_sha256"] == private_plan["carrier"]["remote_command_sha256"]


def test_remote_command_is_exact_shlex_join_and_excludes_agent(contract):
    value, private_plan, sealed_manifest = contract
    command = value.expected_remote_command(private_plan, sealed_manifest)
    assert command == private_plan["carrier"]["remote_command"]
    assert command.startswith("exec /usr/bin/sudo -n -- /usr/bin/env -i LANG=C LC_ALL=C ")
    assert " -- /opt/q2/runtime/bin/python3 -I -B -c " in command
    assert "SSH_AUTH_SOCK" not in command and "SSH_AGENT_PID" not in command
    assert private_plan["carrier"]["host"]["excluded_environment"] == [
        "SSH_AGENT_PID", "SSH_AUTH_SOCK"]
    host = private_plan["carrier"]["host"]
    assert host["local_argv"][-1] == command and host["ssh_argv"][-1] == command
    assert not set(value.FORBIDDEN_LAUNCH_ENV) & set(host["environment"])
    assert host["ssh_argv"][0:3] == ["ssh", "-F", "/dev/null"]
    assert "IdentitiesOnly=yes" in host["ssh_argv"]
    assert "UserKnownHostsFile=" + host["known_hosts"] in host["ssh_argv"]


@pytest.mark.parametrize(("path", "replacement", "reason"), [
    (("carrier", "host", "new_host_key_adoption"), True, "HOST_AUTHENTICATION"),
    (("carrier", "remote", "no_pty"), False, "REMOTE_PROTOCOL"),
    (("carrier", "remote", "sudo_use_pty_absent"), False, "REMOTE_PROTOCOL"),
    (("carrier", "core_pattern", "is_pipe"), True, "CORE_PATTERN_PIPE"),
    (("anchor", "ordinary_delegation"), True, "ANCHOR_QUALIFICATION"),
    (("anchor", "subtree_control"), ["cpu", "memory"], "ANCHOR_CONTROLLERS"),
    (("carrier_leaf", "numeric_pid_writes"), True, "CARRIER_LEAF_GUARDS"),
    (("capture", "raw_publication"), True, "CAPTURE_CONTRACT"),
])
def test_plan_security_and_scope_drift_fail_closed(contract, path, replacement, reason):
    value, private_plan, sealed_manifest = contract
    changed = mutate(private_plan, path, replacement)
    with pytest.raises(value.NamespaceDeliveryContractError, match=reason):
        value.validate_contract(changed, sealed_manifest)


def test_target_group_vector_preserves_sorted_duplicates_and_is_capped_at_32(contract):
    value, private_plan, sealed_manifest = contract
    duplicated = copy.deepcopy(private_plan)
    duplicated["target"]["groups"] = [12001, 12001, 12002]
    duplicated = rebind_plan_state(value, duplicated)
    assert value.validate_contract(duplicated, sealed_manifest)[
        "status"] == "OFFLINE_CONTRACT_SHAPE_VERIFIED"

    too_many = copy.deepcopy(private_plan)
    too_many["target"]["groups"] = [12001] * 33
    with pytest.raises(value.NamespaceDeliveryContractError, match="TARGET_GROUPS"):
        value.validate_contract(too_many, sealed_manifest)
    unsorted = copy.deepcopy(private_plan)
    unsorted["target"]["groups"] = [12002, 12001]
    with pytest.raises(value.NamespaceDeliveryContractError, match="TARGET_GROUPS"):
        value.validate_contract(unsorted, sealed_manifest)
    wrong_type = copy.deepcopy(private_plan)
    wrong_type["target"]["groups"] = [12001, "12002"]
    with pytest.raises(value.NamespaceDeliveryContractError, match="TARGET_GROUP"):
        value.validate_contract(wrong_type, sealed_manifest)
    root_group = copy.deepcopy(private_plan)
    root_group["target"]["groups"] = [0, 12001]
    with pytest.raises(value.NamespaceDeliveryContractError, match="TARGET_GROUP"):
        value.validate_contract(root_group, sealed_manifest)


@pytest.mark.parametrize(("path", "replacement", "reason"), [
    (("watchdog", "prefix", "cpu_ns"), 1_000_000_001, "WATCHDOG_PREFIX_CPU"),
    (("watchdog", "prefix", "outer_write_calls"), 1, "WATCHDOG_PREFIX_IO"),
    (("watchdog", "resources", "remote_exit_ns"), 830_000_000_001,
        "WATCHDOG_REMOTE_EXIT"),
    (("watchdog", "resources", "wake_to_kill_ns"), 5_000_000_000,
        "WATCHDOG_MARGIN_TOTAL"),
    (("watchdog", "state_machine", "fork_fallback"), True,
        "WATCHDOG_STATE_MACHINE"),
    (("protocol", "batch_releases"), 2, "PROTOCOL_CONTRACT"),
    (("stage", "result_journal_bytes"), 752 * 1024 - 1, "STAGE_LAYOUT"),
])
def test_manifest_and_watchdog_drift_fail_closed(contract, path, replacement, reason):
    value, private_plan, sealed_manifest = contract
    changed = mutate(sealed_manifest, path, replacement)
    with pytest.raises(value.NamespaceDeliveryContractError, match=reason):
        value.validate_contract(private_plan, changed)


@pytest.mark.parametrize(("path", "replacement", "reason"), [
    (("watchdog", "version"), "", "WATCHDOG_VERSION"),
    (("watchdog", "identity", "mode"), 0o700, "IDENTITY_WRITABLE_OR_SETID"),
    (("watchdog", "identity", "mode"), 0o4500, "IDENTITY_WRITABLE_OR_SETID"),
    (("watchdog", "elf", "pt_interp"), "/lib64/not-the-loader.so",
        "WATCHDOG_PT_INTERP_BINDING"),
    (("watchdog", "prefix", "userspace_as_bytes"), 64 * 1024 * 1024 + 1,
        "WATCHDOG_PREFIX_AS"),
    (("watchdog", "prefix", "userspace_rss_bytes"), 64 * 1024 * 1024 + 1,
        "WATCHDOG_PREFIX_RSS"),
    (("bridge", "clean_build_two_sha256"), digest("different-build"),
        "BRIDGE_REPRODUCIBLE_BUILD"),
    (("bridge", "deterministic_build_id_disabled"), False, "BRIDGE_BUILD_ID"),
    (("bridge", "elf", "pt_interp_absent"), False, "BRIDGE_ELF_PLATFORM"),
    (("bridge", "native_abi", "receipt_size"), 128,
        "BRIDGE_NATIVE_ABI"),
    (("bridge", "exports"), ["fixture_setup", "fixture_arm"],
        "BRIDGE_EXPORTS"),
])
def test_watchdog_and_bridge_closure_drift_fail_closed(
        contract, path, replacement, reason):
    value, private_plan, sealed_manifest = contract
    changed = mutate(sealed_manifest, path, replacement)
    with pytest.raises(value.NamespaceDeliveryContractError, match=reason):
        value.validate_contract(private_plan, changed)


def test_bridge_build_manifest_and_source_binary_relation_are_recomputed(contract):
    value, _private_plan, sealed_manifest = contract
    bridge = sealed_manifest["bridge"]
    assert bridge["build_manifest_sha256"] == value.canonical_digest(
        bridge["build_manifest"])
    assert bridge["relation_sha256"] == value.canonical_digest(bridge["relation"])
    assert bridge["relation"] == {
        "schema": value.BRIDGE_RELATION_SCHEMA,
        "source_sha256": bridge["source_sha256"],
        "build_manifest_sha256": bridge["build_manifest_sha256"],
        "binary_bytes": bridge["binary_bytes"],
        "binary_sha256": bridge["binary_sha256"],
    }

    changed = copy.deepcopy(sealed_manifest)
    changed["bridge"]["source_sha256"] = digest("different-source-bytes")
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="BRIDGE_BUILD_MANIFEST_BINDING"):
        value.validate_manifest(changed)

    changed["bridge"]["build_manifest"]["source_sha256"] = changed["bridge"][
        "source_sha256"]
    changed["bridge"]["build_manifest_sha256"] = value.canonical_digest(
        changed["bridge"]["build_manifest"])
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="BRIDGE_RELATION_BINDING"):
        value.validate_manifest(changed)


def test_bundle_requires_every_fixed_delivery_role(contract):
    value, _private_plan, sealed_manifest = contract
    changed = copy.deepcopy(sealed_manifest)
    schema_member = next(member for member in changed["bundle"]["members"]
        if member["role"] == "schema")
    schema_member["role"] = "manifest"
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="BUNDLE_REQUIRED_ROLES"):
        value.validate_manifest(changed)

    changed = copy.deepcopy(sealed_manifest)
    extra = copy.deepcopy(changed["bundle"]["members"][0])
    extra["basename"] = "second-collector.py"
    changed["bundle"]["members"].append(extra)
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="BUNDLE_REQUIRED_ROLES"):
        value.validate_manifest(changed)


def test_stage_actuals_and_reference_frame_contract_are_cross_bound(contract):
    value, _private_plan, sealed_manifest = contract
    stage = sealed_manifest["stage"]
    assert stage["actual"]["regular_inodes"] == 20
    assert stage["actual"]["total_inodes"] == 21
    assert stage["actual"]["logical_bytes"] == (
        sealed_manifest["bundle"]["total_bytes"] + 64 * 1024
        + 752 * 1024 + 12 * 16 * 1024)
    changed = copy.deepcopy(sealed_manifest)
    changed["stage"]["actual"]["regular_inodes"] += 1
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="STAGE_ACTUAL_BINDING"):
        value.validate_manifest(changed)

    reference = sealed_manifest["protocol"]["reference_contract"]
    assert reference["frame_plan_sha256"] == value.canonical_digest(
        reference["frame_plan"])
    assert reference["ordinary_groups_max"] == 32
    assert reference["synthetic_fixture_qualification"] == "NOT_RUN"
    assert reference["synthetic_field_ready"] is False
    assert reference["synthetic_allow_run"] is False
    assert reference["synthetic_native_fixture_executed"] is False
    assert reference["synthetic_result_bytes_max"] == 4096
    assert reference["synthetic_timeout_ns"] == 5_000_000_000
    assert reference["synthetic_faults"] == [
        "EARLY_EXIT", "EXTRA_FRAME", "NONE", "STALE_SESSION",
    ]
    changed = copy.deepcopy(sealed_manifest)
    changed["protocol"]["reference_contract"]["frame_plan"][5]["rights"] = []
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="PROTOCOL_CONTRACT"):
        value.validate_manifest(changed)


@pytest.mark.parametrize(("path", "replacement", "reason"), [
    (("manager_read", "fields"), ["MainPID"], "MANAGER_FIELDS_LIST"),
    (("manager_read", "calls"), 2, "MANAGER_CALLS"),
    (("carrier_leaf", "old_carrier_self_writes"), -1, "CARRIER_LEAF_WRITES"),
    (("carrier_leaf", "old_carrier_self_writes"), 37, "CARRIER_LEAF_WRITES"),
    (("carrier", "host", "local_argv"), ["/usr/bin/false"],
        "HOST_LOCAL_ARGV_BINDING"),
    (("carrier", "host", "ssh_argv"), ["ssh", "evil"],
        "HOST_SSH_ARGV_BINDING"),
    (("carrier", "remote", "parser"), "sh-posix-c-v1", "REMOTE_PARSER"),
    (("carrier", "remote", "login_shell"), "/bin/sh", "REMOTE_IDENTITY_BINDING"),
    (("runtime", "soabi"), "wrong-soabi", "BRIDGE_RUNTIME_BINDING"),
])
def test_manager_carrier_wrapper_and_runtime_drift_fail_closed(
        contract, path, replacement, reason):
    value, private_plan, sealed_manifest = contract
    changed = mutate(private_plan, path, replacement)
    with pytest.raises(value.NamespaceDeliveryContractError, match=reason):
        value.validate_contract(changed, sealed_manifest)


def test_launch_environment_and_watchdog_costs_are_bound(contract):
    value, private_plan, sealed_manifest = contract
    changed = copy.deepcopy(private_plan)
    changed["carrier"]["host"]["environment"]["SSH_AUTH_SOCK"] = "/tmp/agent"
    changed["carrier"]["host"]["environment_sha256"] = value.canonical_digest(
        changed["carrier"]["host"]["environment"])
    with pytest.raises(value.NamespaceDeliveryContractError, match="HOST_ENVIRONMENT"):
        value.validate_contract(changed, sealed_manifest)

    changed = copy.deepcopy(private_plan)
    changed["budgets"]["watchdog_prefix"]["audit_bytes"] += 1
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="WATCHDOG_PREFIX_BUDGET_BINDING"):
        value.validate_contract(changed, sealed_manifest)


def test_watchdog_is_not_a_bundle_member(contract):
    value, _private_plan, sealed_manifest = contract
    changed = copy.deepcopy(sealed_manifest)
    changed["bundle"]["members"][0]["basename"] = "watchdog"
    with pytest.raises(value.NamespaceDeliveryContractError, match="FORBIDDEN_MEMBER"):
        value.validate_manifest(changed)


def test_remote_command_or_manifest_replacement_breaks_binding(contract):
    value, private_plan, sealed_manifest = contract
    changed = copy.deepcopy(private_plan)
    changed["carrier"]["remote_command"] += " extra"
    changed["carrier"]["remote_command_sha256"] = hashlib.sha256(
        changed["carrier"]["remote_command"].encode()).hexdigest()
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="HOST_LOCAL_ARGV_BINDING"):
        value.validate_contract(changed, sealed_manifest)
    changed_manifest = copy.deepcopy(sealed_manifest)
    changed_manifest["watchdog_args"][1] = digest("other-contract")
    with pytest.raises(value.NamespaceDeliveryContractError):
        value.validate_contract(private_plan, changed_manifest)


def test_device_bill_uses_max_for_same_obligation_and_rejects_short_capacity(contract):
    value, private_plan, _sealed_manifest = contract
    sample = private_plan["budgets"]["devices"][0]
    expected = copy.deepcopy(sample["claimed_total"])
    assert value.compute_device_bill(sample) == expected
    changed = copy.deepcopy(sample)
    changed["available_bytes"] = expected["bytes"] - 1
    with pytest.raises(value.NamespaceDeliveryContractError, match="DEVICE_CAPACITY"):
        value.compute_device_bill(changed)
    changed = copy.deepcopy(sample)
    changed["policy"]["deletion_refunds_budget"] = True
    with pytest.raises(value.NamespaceDeliveryContractError, match="DEVICE_POLICY"):
        value.compute_device_bill(changed)


def test_budget_floors_kernel_costs_and_shared_devices_are_enforced(contract):
    value, private_plan, _sealed_manifest = contract
    assert value.BUDGET_CEILINGS["private_capture_logical_inodes"] == 256
    assert value.BUDGET_CEILINGS["private_capture_physical_inodes"] == 320
    assert value.BUDGET_CEILINGS["public_record_logical_inodes"] == 64
    assert value.BUDGET_CEILINGS["public_record_physical_inodes"] == 80
    assert value.BUDGET_CEILINGS["case_memory_max_bytes"] == 96 * value.MIB
    assert value.BUDGET_CEILINGS["case_memory_peak_bytes"] == 128 * value.MIB

    too_small = copy.deepcopy(private_plan["budgets"])
    carrier = next(item for item in too_small["devices"] if item["role"] == "carrier")
    carrier["new_peak"] = {"bytes": 1, "inodes": 1}
    carrier["claimed_total"] = value.compute_device_bill({**carrier,
        "claimed_total": {"bytes": 8192 + 1 + 4096, "inodes": 2 + 1 + 2}})
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="BUDGET_DEVICE_ROLE_FLOOR"):
        value._validate_budgets(too_small)

    shared = copy.deepcopy(private_plan["budgets"])
    for item in shared["devices"]:
        item["device_ref"] = digest("one-physical-device")
        item["available_bytes"] = 140 * value.MIB
        item["available_inodes"] = 2000
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="BUDGET_SHARED_DEVICE_CAPACITY"):
        value._validate_budgets(shared)

    kernel = copy.deepcopy(private_plan["budgets"])
    carrier = next(item for item in kernel["devices"] if item["role"] == "carrier")
    carrier["available_bytes"] = carrier["claimed_total"]["bytes"]
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="BUDGET_SHARED_DEVICE_CAPACITY"):
        value._validate_budgets(kernel)


def test_capture_hashes_are_structural_but_offline_module_cannot_make_durable_ack():
    value = module()
    state = value.initial_state(digest("plan"), digest("manifest"))
    raw = value.make_frame("OFFLINE_TEST_FRAME", {"intent_durable": False},
        counter=1, previous_digest=value.ZERO_DIGEST)
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="OFFLINE_FIELD_FRAME_MANUFACTURE_FORBIDDEN"):
        value.make_frame("DELIVERY_ISSUED", {"intent_durable": True},
            counter=1, previous_digest=value.ZERO_DIGEST)
    for claimed in (False, True):
        with pytest.raises(value.NamespaceDeliveryContractError,
                match="OFFLINE_DURABLE_ACK_FORBIDDEN"):
            value.make_capture_ack(state["capture_head"], raw, fsync_complete=claimed)
    ack = external_capture_ack(value, state, raw)
    verified = value.verify_capture_ack(ack, state["capture_head"], raw)
    assert all(verified[name] == ack[name] for name in ack)
    assert verified["shape_verified"] is True
    assert verified["durability_proven"] is False
    assert verified["field_fact_proven"] is False
    assert verified["live_proven"] is False
    changed = copy.deepcopy(ack)
    changed["capture_head"] = digest("tampered")
    with pytest.raises(value.NamespaceDeliveryContractError, match="CAPTURE_ACK"):
        value.verify_capture_ack(changed, state["capture_head"], raw)


@pytest.mark.parametrize(("field", "replacement"), [
    ("fixture_delivery_issued", True),
    ("fixture_batch_release_issued", True),
    ("fixture_batch_release_accepted", True),
    ("fixture_native_batch_issued", True),
    ("carrier_requests", 1),
    ("batch_releases", 1),
    ("native_batches", 1),
    ("phase", "TERMINAL"),
    ("fixture_qualification", "FIXTURE_LIVE_REFERENCE_MATCHED"),
])
def test_offline_state_accepts_only_exact_unissued_snapshot(field, replacement):
    value = module()
    state = value.initial_state(digest("plan"), digest("manifest"))
    state[field] = replacement
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="OFFLINE_STATE_NOT_INITIAL"):
        value.validate_state(state)


@pytest.mark.parametrize("kind", [
    "LOCAL_VERIFIED", "DELIVERY_ISSUED", "HELLO_VERIFIED",
    "BATCH_RELEASE_ISSUED", "BATCH_ACCEPTED", "LIVE_ADMITTED", "STAGED",
    "NATIVE_BATCH_ISSUED", "CLONE_ISSUED", "FIXTURE_MATCHED",
])
def test_offline_api_refuses_every_state_transition(kind):
    value = module()
    state = value.initial_state(digest("plan"), digest("manifest"))
    raw = external_field_frame(value, kind, {}, counter=1,
        previous_digest=value.ZERO_DIGEST)
    ack = external_capture_ack(value, state, raw)
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="OFFLINE_STATE_MUTATION_FORBIDDEN"):
        value.advance_state(state, raw, ack)
    assert value.validate_state(state) == state


def test_handoff_and_cleanup_are_bounded_but_offline_success_cleanup_is_forbidden():
    value = module()
    handoff_payload = {
        "batch_id": "fixture-20261003-a",
        "session_id": "session-20261003-a",
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "implementation_commit": "1" * 40,
        "implementation_tree": "2" * 40,
        "case_ids": list(value.CASE_IDS),
        "case_bitmap": "1" * 12,
        "action_counter": 37,
        "stop_latch": False,
        "success_latch": True,
        "final_carrier_ready": True,
        "all_stage_slots_final_or_empty": True,
        "work_deadline_boottime_ns": 10_000_000_000,
        "containment_deadline_boottime_ns": 20_000_000_000,
        "utc_not_after_ns": 30_000_000_000,
        "process_cpu_at_handoff_ns": 8_000_000_000,
        "handoff_boottime_ns": 9_000_000_000,
        "handoff_monotonic_ns": 9_000_000_001,
        "handoff_realtime_ns": 19_000_000_000,
    }
    for name in (
        "plan_sha256", "manifest_sha256", "bundle_sha256", "context_sha256",
        "runtime_sha256", "watchdog_sha256", "bridge_sha256",
        "cleanup_source_sha256", "source_catalog_sha256",
        "identity_catalog_sha256", "fd_table_sha256", "deadline_catalog_sha256",
        "cpu_ledger_sha256", "timer_catalog_sha256",
        "action_excursions_sha256", "stage_state_sha256",
        "owner_acks_sha256", "result_sha256", "action_head_sha256",
        "capture_head_sha256",
    ):
        handoff_payload[name] = digest(name)
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="OFFLINE_SUCCESS_HANDOFF_FORBIDDEN"):
        value.make_handoff(handoff_payload)
    handoff = value.canonical_bytes(
        {"schema": value.HANDOFF_SCHEMA, "payload": handoff_payload},
        maximum=value.MAX_H_BYTES,
    )

    cleanup_payload = {
        "batch_id": handoff_payload["batch_id"],
        "session_id": handoff_payload["session_id"],
        "counter": 77,
        "case_bitmap": "1" * 12,
        "action_counter": 37,
        "tc_ns": 100_000_000,
        "tw_ns": 100_000_000,
        "all_cleanup_complete": True,
        "success_eligible": False,
    }
    for name in ("previous_digest", "context_sha256", "runtime_sha256",
            "bridge_sha256", "bridge_copy_sha256", "bridge_seals_sha256",
            "cleanup_actuals_sha256", "stage_final_sha256",
            "cgroup_final_sha256", "anchor_final_sha256"):
        cleanup_payload[name] = digest(name)
    cleanup_payload["handoff_sha256"] = hashlib.sha256(handoff).hexdigest()
    cleanup = value.make_cleanup_final(cleanup_payload)
    verified_handoff = value.verify_handoff(handoff, expected=handoff_payload)
    assert verified_handoff["schema"] == value.HANDOFF_SCHEMA
    assert verified_handoff["fixture_qualification"] == "NOT_RUN"
    assert verified_handoff["durability_proven"] is False
    assert verified_handoff["field_fact_proven"] is False
    assert verified_handoff["live_proven"] is False
    verified_cleanup = value.verify_cleanup_final(
        cleanup, expected=cleanup_payload
    )
    assert verified_cleanup["schema"] == value.CLEANUP_FINAL_SCHEMA
    assert verified_cleanup["fixture_qualification"] == "NOT_RUN"
    assert verified_cleanup["durability_proven"] is False
    assert verified_cleanup["live_proven"] is False
    assert len(handoff) <= value.MAX_H_BYTES
    assert len(cleanup) <= value.MAX_CLEANUP_FINAL_BYTES
    with pytest.raises(value.NamespaceDeliveryContractError, match="JSON_NOT_CANONICAL"):
        value.verify_handoff(json.dumps(json.loads(handoff), indent=2).encode(),
            expected=handoff_payload)
    mismatched_handoff = copy.deepcopy(handoff_payload)
    mismatched_handoff["handoff_monotonic_ns"] += 1
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="HANDOFF_EXPECTED_BINDING"):
        value.verify_handoff(handoff, expected=mismatched_handoff)
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="HANDOFF_PAYLOAD_FIELDS"):
        value.make_handoff({"oversized": "x" * value.MAX_H_BYTES})
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="CLEANUP_FINAL_PAYLOAD_FIELDS"):
        value.make_cleanup_final({"oversized": "x" * value.MAX_CLEANUP_FINAL_BYTES})
    successful = copy.deepcopy(cleanup_payload)
    successful["success_eligible"] = True
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="OFFLINE_SUCCESS_CLEANUP_FORBIDDEN"):
        value.make_cleanup_final(successful)
    external = value.canonical_bytes(
        {"schema": value.CLEANUP_FINAL_SCHEMA, "payload": successful},
        maximum=value.MAX_CLEANUP_FINAL_BYTES,
    )
    verified_external = value.verify_cleanup_final(external, expected=successful)
    assert verified_external["payload"]["success_eligible"] is True
    assert verified_external["fixture_qualification"] == "NOT_RUN"
    mismatched = copy.deepcopy(successful)
    mismatched["counter"] += 1
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="CLEANUP_FINAL_EXPECTED_BINDING"):
        value.verify_cleanup_final(external, expected=mismatched)
    for field, bad in (("tc_ns", 0), ("tc_ns", 1_000_000_000), ("tw_ns", 0)):
        broken = copy.deepcopy(cleanup_payload)
        broken[field] = bad
        with pytest.raises(value.NamespaceDeliveryContractError):
            value.make_cleanup_final(broken)


def test_success_receipt_is_external_fixed_binary_and_never_proves_live():
    value = module()
    expected = {
        "version": 1,
        "process_cpu_ns": 8_100_000_000,
        "boottime_ns": 90_000_000_000,
        "monotonic_ns": 89_000_000_000,
        "realtime_ns": 1_800_000_000_000_000_000,
        "counter": 77,
        "previous_digest": digest("previous"),
        "handoff_sha256": digest("handoff"),
        "cleanup_final_sha256": digest("cleanup-final"),
        "capture_head_sha256": digest("capture-head"),
    }
    receipt = external_success_receipt(value, expected)
    checked = value.verify_success_receipt(receipt, expected=expected)
    assert len(receipt) == value.SUCCESS_RECEIPT_SIZE == 224
    assert checked["fields"] == expected
    assert checked["binary_structure_verified"] is True
    assert checked["fixture_qualification"] == "NOT_RUN"
    assert checked["source_bytes_proven"] is False
    assert checked["build_proven"] is False
    assert checked["native_execution_proven"] is False
    assert checked["durability_proven"] is False
    assert checked["live_proven"] is False
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="OFFLINE_SUCCESS_RECEIPT_FORBIDDEN"):
        value.make_success_receipt(expected)

    with pytest.raises(value.NamespaceDeliveryContractError, match="SUCCESS_RECEIPT_SIZE"):
        value.verify_success_receipt(receipt[:-1], expected=expected)
    changed = bytearray(receipt)
    changed[0] ^= 1
    with pytest.raises(value.NamespaceDeliveryContractError, match="SUCCESS_RECEIPT_MAGIC"):
        value.verify_success_receipt(bytes(changed), expected=expected)
    changed = bytearray(receipt)
    changed[184] = 1
    changed[192:224] = hashlib.sha256(changed[:192]).digest()
    with pytest.raises(value.NamespaceDeliveryContractError, match="SUCCESS_RECEIPT_RESERVED"):
        value.verify_success_receipt(bytes(changed), expected=expected)
    changed = bytearray(receipt)
    changed[-1] ^= 1
    with pytest.raises(value.NamespaceDeliveryContractError, match="SUCCESS_RECEIPT_SHA256"):
        value.verify_success_receipt(bytes(changed), expected=expected)
    for name in ("process_cpu_ns", "boottime_ns", "monotonic_ns",
            "realtime_ns", "counter"):
        changed_expected = copy.deepcopy(expected)
        changed_expected[name] += 1
        with pytest.raises(value.NamespaceDeliveryContractError,
                match="SUCCESS_RECEIPT_EXPECTED_BINDING"):
            value.verify_success_receipt(receipt, expected=changed_expected)
    for name in ("previous_digest", "handoff_sha256", "cleanup_final_sha256",
            "capture_head_sha256"):
        changed_expected = copy.deepcopy(expected)
        changed_expected[name] = digest("wrong-" + name)
        with pytest.raises(value.NamespaceDeliveryContractError,
                match="SUCCESS_RECEIPT_EXPECTED_BINDING"):
            value.verify_success_receipt(receipt, expected=changed_expected)
    for name in ("process_cpu_ns", "boottime_ns", "monotonic_ns", "realtime_ns"):
        zero_expected = copy.deepcopy(expected)
        zero_expected[name] = 0
        with pytest.raises(value.NamespaceDeliveryContractError,
                match="SUCCESS_RECEIPT_CLOCK"):
            value.verify_success_receipt(receipt, expected=zero_expected)
    zero_digest_expected = copy.deepcopy(expected)
    zero_digest_expected["previous_digest"] = value.ZERO_DIGEST
    with pytest.raises(value.NamespaceDeliveryContractError,
            match="SUCCESS_RECEIPT_DIGEST"):
        value.verify_success_receipt(receipt, expected=zero_digest_expected)


def test_duplicate_keys_floats_and_unknown_fields_are_rejected(contract):
    value, private_plan, sealed_manifest = contract
    with pytest.raises(value.NamespaceDeliveryContractError, match="JSON_DUPLICATE_KEY"):
        value.decode_canonical(b'{"a":1,"a":2}', maximum=64)
    with pytest.raises(value.NamespaceDeliveryContractError, match="JSON_NUMBER"):
        value.decode_canonical(b'{"a":1.5}', maximum=64)
    changed = copy.deepcopy(private_plan)
    changed["unexpected"] = True
    with pytest.raises(value.NamespaceDeliveryContractError, match="PLAN_FIELDS"):
        value.validate_contract(changed, sealed_manifest)

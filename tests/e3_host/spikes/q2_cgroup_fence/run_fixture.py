#!/usr/bin/env python3
"""Bounded, manual-only GitHub fixture for the approved H07 experiment.

This is test infrastructure, not a production launcher.  The native helper owns
all experimental clone/pidfd operations.  This file never runs a fixture unless
the dispatch, source identity and hosted Ubuntu image predicates are satisfied.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import grp
import re
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time


A = "71c7e842c724650a0e949a63bb898699b41107be"
C = "8deeed492edeb7e5fa79cbe95c123a27e69f9f92"
SCOPE_DIR = "tests/e3_host/spikes/q2_cgroup_fence"
WORKFLOW = ".github/workflows/q2-cgroup-fence-spike.yml"
PINNED_DOCUMENTS = {
    "REQUIREMENTS.md": "41706c5b07cfceea319f10dcab1fcc8b2606995b029566f3e13bb00e41affd51",
    "ARCHITECTURE.md": "6b7ef2487658e759df565084393e5de010db8f35de4966a4790320eea060116c",
    "IMPLEMENTATION_PLAN.md": "0bd3dab26e10e2fa9717ef218fa70846cf5ad3b5888ad2f17596c7b7b385e99d",
}
LIMITS = {
    "prep_seconds": 120, "cases_seconds": 180, "cleanup_seconds": 30,
    "case_seconds": 20, "stop_seconds": 3,
    "E_memory_bytes": 128 * 1024**2, "G_memory_bytes": 64 * 1024**2,
    "B_memory_bytes": 64 * 1024**2, "E_pids": 32, "G_pids": 4,
    "B_pids": 16, "cpu_max": "100000 100000", "swap_bytes": 0,
    "case_stream_bytes": 128 * 1024, "suite_stream_bytes": 768 * 1024,
    "diagnostic_bytes": 256 * 1024, "report_bytes": 2 * 1024**2,
    "file_logical_bytes": 32 * 1024**2, "file_count": 128,
}
ARTIFACT_NAMES = (
    "report.json", "manifest.json", "diagnostics.txt", "probe.json",
    "C1.json", "C2.json", "C3.json", "C4.json", "C5.json", "C6.json",
)


class Refusal(RuntimeError):
    """A source, environment, limit or identity predicate is not satisfied."""


class CommandFailure(Refusal):
    def __init__(self, message: str, output: bytes):
        super().__init__(message)
        self.output = output


class Deadline:
    def __init__(self, seconds: float):
        self.seconds = seconds
        self.mono = time.monotonic()
        self.boot = time.clock_gettime(time.CLOCK_BOOTTIME)

    def elapsed(self) -> float:
        return max(time.monotonic() - self.mono,
                   time.clock_gettime(time.CLOCK_BOOTTIME) - self.boot)

    def remaining(self) -> float:
        return max(0.0, self.seconds - self.elapsed())

    def check(self) -> None:
        if self.remaining() <= 0:
            raise Refusal("stage deadline exhausted")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_small(path: Path, limit: int = 16384) -> str:
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise Refusal("read limit exceeded: " + path.name)
    return raw.decode("utf-8", "strict").strip()


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["/usr/bin/git", "-c", "safe.directory=" + str(repo), "-C", str(repo), *args], check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
        env={"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"},
    )
    if result.returncode or len(result.stdout) > 4 * 1024**2:
        raise Refusal("source identity command failed")
    return result.stdout


def source_identity(repo: Path, expected: str, env: dict[str, str]) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise Refusal("expected_commit must be a complete lower-case commit SHA")
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    if head != expected or env.get("GITHUB_SHA") != expected:
        raise Refusal("expected_commit, github.sha and checkout HEAD differ")
    if git(repo, "status", "--porcelain", "--untracked-files=normal"):
        raise Refusal("checkout is not clean")
    git(repo, "merge-base", "--is-ancestor", C, expected)
    paths = git(repo, "ls-tree", "-r", "--name-only", expected, "--", SCOPE_DIR).decode().splitlines()
    if not paths or SCOPE_DIR + "/run_fixture.py" not in paths:
        raise Refusal("frozen experimental source closure is absent")
    extras = git(repo, "ls-files", "--others", "--", SCOPE_DIR).decode().splitlines()
    if extras:
        raise Refusal("untracked executable closure entries")
    paths += [WORKFLOW, "AGENTS.md",
              "docs/governance/Q2_H07_CGROUP_FENCE_SPIKE_OWNER_DECISION.md"]
    paths += ["docs/a2-execution/q2-h07-cgroup-fence-spike/" + name for name in PINNED_DOCUMENTS]
    closure = {}
    for relative in sorted(set(paths)):
        target = repo / relative
        info = target.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 2 * 1024**2:
            raise Refusal("source closure must contain bounded regular files")
        frozen = git(repo, "show", expected + ":" + relative)
        actual = target.read_bytes()
        if actual != frozen:
            raise Refusal("working source differs from frozen commit: " + relative)
        closure[relative] = digest(actual)
    for name, sha in PINNED_DOCUMENTS.items():
        if closure["docs/a2-execution/q2-h07-cgroup-fence-spike/" + name] != sha:
            raise Refusal("approved three-document baseline changed")
    return {"expected_commit": expected, "github_sha": env["GITHUB_SHA"], "head": head,
            "closure_sha256": closure, "approved_A": A, "closure_C": C}


def admission(env: dict[str, str], round_number: int) -> tuple[str, Path, dict]:
    required = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
                "GITHUB_REPOSITORY": "kongbu0621/infra-local-hand",
                "GITHUB_RUN_ATTEMPT": "1", "RUNNER_ENVIRONMENT": "github-hosted",
                "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "ImageOS": "ubuntu24"}
    for key, value in required.items():
        if env.get(key) != value:
            raise Refusal("fixture admission rejected " + key)
    run_id = env.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[1-9][0-9]{0,18}", run_id) or round_number not in (1, 2, 3):
        raise Refusal("invalid run identity/round")
    reason = env.get("LAB_REASON", "")
    if not 1 <= len(reason.encode()) <= 512 or any(ord(ch) < 32 for ch in reason):
        raise Refusal("dispatch reason is absent or not bounded single-line text")
    if os.geteuid() != 0 or platform.machine() != "x86_64":
        raise Refusal("fixed x86_64 root setup capability unavailable")
    release = {}
    for line in read_small(Path("/etc/os-release")).splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            release[key] = value.strip('"')
    if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != "24.04":
        raise Refusal("actual OS differs from approved Ubuntu 24.04 fixture")
    base = Path(env.get("RUNNER_TEMP", ""))
    if not base.is_absolute() or not base.is_dir() or base.resolve() != base:
        raise Refusal("RUNNER_TEMP is not an existing canonical directory")
    output = base / f"q2-h07-{run_id}-1-r{round_number}"
    if output.exists() or output.is_symlink():
        raise Refusal("output exists; same dispatch cannot be replayed")
    return run_id, output, {"id": release["ID"], "version_id": release["VERSION_ID"]}


class Fixture:
    def __init__(self, repo: Path, output: Path, run_id: str, round_number: int):
        self.repo, self.output = repo, output
        self.evidence, self.build = output / "evidence", output / "build"
        self.run_id, self.round = run_id, round_number
        self.account = "q2hf" + run_id[-15:] + "r" + str(round_number)
        self.e = Path("/sys/fs/cgroup") / ("q2-h07-" + run_id + "-1-r" + str(round_number))
        self.objects: list[tuple[Path, int, int]] = []
        self.cg_objects: list[tuple[Path, int, int]] = []
        self.account_id: tuple[int, int] | None = None
        self.account_attempted = False
        self.diagnostics = bytearray()
        self.diagnostic_exceeded = False
        self.helper = self.build / "helper"
        self.helper_sha: str | None = None
        self.created_files: dict[Path, tuple[int, int]] = {}
        self.native_timed_out = False
        self.native_started = False
        self.facts = {"account": None, "cgroup_objects": [], "resource_observations": []}
        self.pending_commands: list[subprocess.Popen] = []

    def diagnostic(self, data: bytes) -> None:
        capacity = LIMITS["diagnostic_bytes"] - len(self.diagnostics)
        self.diagnostics.extend(data[:capacity])
        if len(data) > capacity:
            self.diagnostic_exceeded = True

    def mkdir(self, path: Path, *, cgroup: bool = False) -> None:
        path.mkdir(mode=0o755)
        if not cgroup:
            os.chmod(path, 0o755, follow_symlinks=False)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0:
            raise Refusal("new fixture directory identity invalid")
        (self.cg_objects if cgroup else self.objects).append((path, info.st_dev, info.st_ino))

    def write_artifact(self, name: str, data: bytes) -> None:
        if name not in ARTIFACT_NAMES or len(data) > LIMITS["report_bytes"]:
            raise Refusal("artifact allowlist/size violated")
        path = self.evidence / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        try:
            os.fchmod(fd, 0o644)
            cursor = 0
            while cursor < len(data):
                written = os.write(fd, data[cursor:])
                if not written:
                    raise Refusal("short artifact write")
                cursor += written
            os.fsync(fd)
            info = os.fstat(fd)
            self.created_files[path] = (info.st_dev, info.st_ino)
        finally:
            os.close(fd)

    def command(self, argv: list[str], deadline: Deadline, *, stdout_limit: int = 65536,
                native: bool = False, cleanup: bool = False) -> tuple[int, bytes]:
        deadline.check()
        if self.diagnostic_exceeded and not cleanup:
            raise Refusal("diagnostic ceiling already exceeded; no further work started")

        def child_limits() -> None:
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2, 8 * 1024**2))
            os.umask(0o077)

        process = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, close_fds=True, cwd=self.build,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C", "LC_ALL": "C",
                 "TMPDIR": str(self.build)},
            preexec_fn=child_limits,
        )
        self.pending_commands.append(process)
        out = bytearray()
        exceeded = False
        killed = False
        selector = selectors.DefaultSelector()
        for stream, kind in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            assert stream is not None
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, kind)
        try:
            while selector.get_map():
                if deadline.remaining() <= 0 or exceeded or (self.diagnostic_exceeded and not cleanup):
                    if not killed:
                        # Exceptional outer containment only, never a native seal.
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        killed = True
                        if native:
                            self.native_timed_out = True
                    # Do not hang on a write end inherited by an unkillable child.
                    for key in list(selector.get_map().values()):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    break
                for key, _ in selector.select(min(deadline.remaining(), 0.05)):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    elif key.data == "stdout":
                        capacity = stdout_limit - len(out)
                        out.extend(chunk[:capacity])
                        exceeded |= len(chunk) > capacity
                    else:
                        self.diagnostic(chunk)
            try:
                result = process.wait(timeout=min(max(deadline.remaining(), 0.01), 1.0))
                self.pending_commands.remove(process)
            except subprocess.TimeoutExpired:
                if not killed:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if native:
                    self.native_timed_out = True
                raise CommandFailure("subprocess exit not observed by its deadline; stdout may be incomplete", bytes(out))
        finally:
            selector.close()
        if killed or exceeded or (self.diagnostic_exceeded and not cleanup):
            raise CommandFailure("subprocess deadline/output bound exceeded; retained stdout is a bounded prefix", bytes(out))
        return result, bytes(out)

    def initialize_output(self) -> None:
        self.mkdir(self.output)
        self.mkdir(self.evidence)
        self.mkdir(self.build)

    def compile(self, deadline: Deadline) -> dict:
        compiler = Path("/usr/bin/cc").resolve(strict=True)
        rc, version = self.command([str(compiler), "--version"], deadline, stdout_limit=8192)
        self.diagnostic(version)
        if rc:
            raise Refusal("existing compiler unavailable")
        rc, output = self.command(
            [str(compiler), "-std=c11", "-pipe", "-O2", "-Wall", "-Wextra", "-Werror",
             str(self.repo / SCOPE_DIR / "helper.c"), "-o", str(self.helper)], deadline,
        )
        self.diagnostic(output)
        if rc:
            raise Refusal("native helper compilation failed")
        info = self.helper.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_size > 8 * 1024**2:
            raise Refusal("native helper build identity/size invalid")
        self.created_files[self.helper] = (info.st_dev, info.st_ino)
        self.helper_sha = digest(self.helper.read_bytes())
        self.inventory()
        return {"path": str(compiler), "version": version.decode("utf-8", "replace")[:8192]}

    def create_account(self, deadline: Deadline) -> None:
        for getter in (pwd.getpwnam, grp.getgrnam):
            try:
                getter(self.account)
            except KeyError:
                continue
            raise Refusal("dedicated account/group name already exists")
        self.account_attempted = True
        # CREATE_MAIL_SPOOL is a useradd-defaults setting, not a --key
        # login.defs item. --system suppresses mail and, without -F, subids.
        rc, raw = self.command([
            "/usr/sbin/useradd", "--system", "--user-group", "--no-create-home",
            "--no-log-init", "--home-dir", "/nonexistent", "--shell", "/usr/sbin/nologin",
            self.account,
        ], deadline)
        self.diagnostic(raw)
        if rc:
            raise Refusal("dedicated account creation failed; inspect partial objects")
        entry = pwd.getpwnam(self.account)
        group = grp.getgrnam(self.account)
        self.account_id = (entry.pw_uid, entry.pw_gid)
        if (entry.pw_uid == 0 or group.gr_gid != entry.pw_gid or group.gr_mem
                or entry.pw_dir != "/nonexistent" or entry.pw_shell != "/usr/sbin/nologin"
                or os.getgrouplist(self.account, entry.pw_gid) != [entry.pw_gid]):
            raise Refusal("dedicated account does not have the approved fixed identity")
        self.facts["account"] = {"uid": entry.pw_uid, "gid": entry.pw_gid,
                                 "supplementary_groups": [], "home_created": False}

    def check_cgroup_parent(self) -> tuple[list[str], list[str]]:
        mount_lines = read_small(Path("/proc/self/mountinfo"), 256 * 1024).splitlines()
        rows = [line.split() for line in mount_lines if " - cgroup2 " in line]
        if not any(row[4] == "/sys/fs/cgroup" and "rw" in row[5].split(",") for row in rows):
            raise Refusal("writable cgroup v2 mount unavailable")
        parent = Path("/sys/fs/cgroup")
        controllers = read_small(parent / "cgroup.controllers").split()
        enabled = read_small(parent / "cgroup.subtree_control").split()
        if not {"cpu", "memory", "pids"}.issubset(set(enabled)):
            raise Refusal("shared parent has not enabled required controllers; it will not be changed")
        if parent.resolve() != parent:
            raise Refusal("unexpected cgroup mount identity")
        return controllers, enabled

    def cg_write(self, path: Path, value: str) -> None:
        if path.parent not in {entry[0] for entry in self.cg_objects}:
            raise Refusal("attempt to write outside registered cgroup objects")
        parent = path.parent.lstat()
        expected = next(entry for entry in self.cg_objects if entry[0] == path.parent)
        if (parent.st_dev, parent.st_ino) != expected[1:]:
            raise Refusal("cgroup directory identity changed")
        fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
        try:
            if os.write(fd, (value + "\n").encode()) != len(value) + 1:
                raise Refusal("short cgroup control write")
        finally:
            os.close(fd)

    def setup_cgroups(self, deadline: Deadline) -> None:
        deadline.check()
        self.mkdir(self.e, cgroup=True)
        for key, value in (("memory.max", str(LIMITS["E_memory_bytes"])),
                           ("memory.swap.max", "0"), ("pids.max", "32"),
                           ("cpu.max", LIMITS["cpu_max"]),
                           ("cgroup.subtree_control", "+cpu +memory +pids")):
            self.cg_write(self.e / key, value)
        for leaf, memory, tasks in (("G", LIMITS["G_memory_bytes"], 4),
                                    ("B", LIMITS["B_memory_bytes"], 16)):
            path = self.e / leaf
            self.mkdir(path, cgroup=True)
            self.cg_write(path / "memory.max", str(memory))
            self.cg_write(path / "memory.swap.max", "0")
            self.cg_write(path / "pids.max", str(tasks))
            self.cg_write(path / "cpu.max", LIMITS["cpu_max"])
        self.cg_write(self.e / "B/cgroup.subtree_control", "+cpu +memory +pids")
        self.mkdir(self.e / "B/S", cgroup=True)
        self.mkdir(self.e / "B/W", cgroup=True)
        assert self.account_id is not None
        for relative in ("B/cgroup.procs", "B/W/cgroup.procs"):
            path = self.e / relative
            os.chown(path, *self.account_id, follow_symlinks=False)
            os.chmod(path, 0o600, follow_symlinks=False)
        if read_small(self.e / "cgroup.procs") or read_small(self.e / "B/cgroup.procs"):
            raise Refusal("internal cgroup parents unexpectedly populated")
        for path, dev, ino in self.cg_objects:
            configured = {}
            for name in ("memory.max", "memory.swap.max", "pids.max", "cpu.max"):
                raw = read_small(path / name)
                configured[name] = raw if name == "cpu.max" else (None if raw == "max" else int(raw))
            label = "E" if path == self.e else str(path.relative_to(self.e))
            expected = {"E": (LIMITS["E_memory_bytes"], 32),
                        "G": (LIMITS["G_memory_bytes"], 4),
                        "B": (LIMITS["B_memory_bytes"], 16)}.get(label)
            if expected and (configured["memory.max"], configured["pids.max"], configured["memory.swap.max"]) != (*expected, 0):
                raise Refusal("configured cgroup resource limit readback mismatch")
            if expected and configured["cpu.max"] != LIMITS["cpu_max"]:
                raise Refusal("common cgroup CPU rate limit readback mismatch")
            self.facts["cgroup_objects"].append({"relative": label, "dev": dev, "ino": ino,
                                                  "limits": configured})
        self.verify_empty()

    def sample_resources(self, boundary: str) -> None:
        observed = {}
        for path, dev, ino in self.cg_objects:
            info = path.lstat()
            if (info.st_dev, info.st_ino) != (dev, ino):
                raise Refusal("resource observation cgroup identity mismatch")
            label = "E" if path == self.e else str(path.relative_to(self.e))
            def counters(name: str) -> dict:
                return {key: int(value) for key, value in
                        (line.split() for line in read_small(path / name).splitlines())}
            try:
                memory_peak = int(read_small(path / "memory.peak"))
            except FileNotFoundError:
                memory_peak = None
            try:
                pids_peak = int(read_small(path / "pids.peak"))
            except FileNotFoundError:
                pids_peak = None
            observed[label] = {"cpu_stat": counters("cpu.stat"),
                               "memory_current": int(read_small(path / "memory.current")),
                               "memory_peak": memory_peak,
                               "pids_current": int(read_small(path / "pids.current")),
                               "pids_peak": pids_peak,
                               "memory_events": counters("memory.events"),
                               "pids_events": counters("pids.events"),
                               "populated": counters("cgroup.events")["populated"]}
        self.facts["resource_observations"].append({"boundary": boundary, "cgroups": observed,
                                                   "mono_ns": time.monotonic_ns(),
                                                   "boot_ns": time.clock_gettime_ns(time.CLOCK_BOOTTIME)})

    def verify_empty(self) -> None:
        for path, dev, ino in self.cg_objects:
            info = path.lstat()
            if (info.st_dev, info.st_ino) != (dev, ino):
                raise Refusal("registered cgroup identity changed")
            events = dict(line.split() for line in read_small(path / "cgroup.events").splitlines())
            if events.get("populated") != "0":
                raise Refusal("previous experimental subtree is not empty")

    def native(self, case: str, deadline: Deadline) -> dict:
        self.verify_empty()
        self.sample_resources(case + "-before")
        assert self.account_id is not None
        if digest(self.helper.read_bytes()) != self.helper_sha:
            raise Refusal("native executable changed after compilation")
        window = Deadline(min(21.0, deadline.remaining()))
        command = [str(self.helper), "probe", str(self.e), *map(str, self.account_id)]
        if case != "probe":
            command = [str(self.helper), "case", case, str(self.e), *map(str, self.account_id)]
        self.native_started = True
        try:
            rc, raw = self.command(command, window, stdout_limit=192 * 1024, native=True)
        except CommandFailure as exc:
            self.write_artifact(case + ".json", exc.output)
            raise
        self.write_artifact(case + ".json", raw)
        self.sample_resources(case + "-after")
        try:
            from verify_receipt import load_report
            receipt = load_report(raw)
        except (ValueError, UnicodeError) as exc:
            raise Refusal("native result is not a complete JSON object") from exc
        if not isinstance(receipt, dict):
            raise Refusal("native result is not an object")
        # Native receipt contract and exit status are separate facts.
        if rc not in (0, 2, 3):
            raise Refusal("native helper returned an unexpected process exit code")
        return receipt

    def inventory(self) -> dict:
        total = allocated = count = 0
        inodes = set()
        for root, dirs, files in os.walk(self.output, followlinks=False):
            for name in dirs + files:
                path = Path(root) / name
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise Refusal("fixture output contains a symlink")
                inodes.add((info.st_dev, info.st_ino))
                allocated += info.st_blocks * 512
                if stat.S_ISREG(info.st_mode):
                    count += 1
                    total += info.st_size
                elif not stat.S_ISDIR(info.st_mode):
                    raise Refusal("fixture output contains a nonregular object")
        if count > LIMITS["file_count"] or total > LIMITS["file_logical_bytes"]:
            raise Refusal("fixture logical file budget exceeded")
        return {"file_logical_bytes": total, "file_count": count,
                "allocated_bytes": allocated, "inode_count": len(inodes)}

    def cleanup(self) -> dict:
        deadline = Deadline(LIMITS["cleanup_seconds"])
        records, residuals = [], []
        # Retain identity mismatches instead of guessing which object to remove.
        if self.cg_objects:
            try:
                self.cg_write(self.e / "cgroup.kill", "1")
                while deadline.remaining() > 0:
                    try:
                        self.verify_empty()
                        break
                    except Refusal:
                        time.sleep(min(0.025, deadline.remaining()))
                self.verify_empty()
            except (OSError, Refusal) as exc:
                residuals.append("registered cgroup cleanup: " + str(exc))
            if not residuals:
                for path, dev, ino in reversed(self.cg_objects):
                    try:
                        deadline.check()
                        info = path.lstat()
                        if (info.st_dev, info.st_ino) != (dev, ino):
                            raise Refusal("identity mismatch")
                        path.rmdir()
                        records.append({"object": str(path.relative_to(self.e.parent)),
                                        "operation": "rmdir", "identity_match": True, "removed": True})
                    except (OSError, Refusal) as exc:
                        residuals.append("cgroup object: " + str(exc))
                        break
        for process in list(self.pending_commands):
            try:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=max(0.001, min(1.0, deadline.remaining())))
                self.pending_commands.remove(process)
                records.append({"object": "original-subprocess-" + str(process.pid),
                                "operation": "reap", "identity_match": True, "removed": True})
            except (OSError, subprocess.TimeoutExpired):
                residuals.append("original external subprocess exit remains unobserved")
        if self.account_id is not None and not residuals:
            try:
                entry = pwd.getpwnam(self.account)
                if (entry.pw_uid, entry.pw_gid) != self.account_id:
                    raise Refusal("account identity mismatch")
                # userdel never receives --remove: there was no home/mail to delete.
                rc, raw = self.command(["/usr/sbin/userdel", self.account], deadline, cleanup=True)
                self.diagnostic(raw)
                if rc:
                    raise Refusal("userdel did not complete")
                try:
                    group = grp.getgrnam(self.account)
                except KeyError:
                    group = None
                if group is not None:
                    if group.gr_gid != self.account_id[1] or group.gr_mem:
                        raise Refusal("dedicated group identity mismatch")
                    rc, raw = self.command(["/usr/sbin/groupdel", self.account], deadline, cleanup=True)
                    self.diagnostic(raw)
                    if rc:
                        raise Refusal("groupdel did not complete")
                try:
                    pwd.getpwnam(self.account)
                except KeyError:
                    pass
                else:
                    raise Refusal("dedicated account still exists")
                try:
                    grp.getgrnam(self.account)
                except KeyError:
                    pass
                else:
                    raise Refusal("dedicated group still exists")
                records.append({"object": "dedicated-account", "operation": "delete",
                                "identity_match": True, "removed": True})
            except (KeyError, OSError, Refusal) as exc:
                residuals.append("account cleanup: " + str(exc))
        elif self.account_attempted and self.account_id is None:
            residuals.append("account creation was attempted but its exact identity is not established")
        # Only the precise registered binary can be unlinked. Intermediate files
        # that were not registered remain evidence of incomplete cleanup.
        if self.helper in self.created_files:
            try:
                info = self.helper.lstat()
                if (info.st_dev, info.st_ino) != self.created_files[self.helper]:
                    raise Refusal("build identity mismatch")
                self.helper.unlink()
                records.append({"object": "build/helper", "operation": "unlink",
                                "identity_match": True, "removed": True})
            except (OSError, Refusal) as exc:
                residuals.append("build cleanup: " + str(exc))
        if self.build.exists():
            try:
                identity = next(row for row in self.objects if row[0] == self.build)
                info = self.build.lstat()
                if (info.st_dev, info.st_ino) != identity[1:]:
                    raise Refusal("build directory identity mismatch")
                self.build.rmdir()
            except (OSError, Refusal) as exc:
                residuals.append("build directory cleanup: " + str(exc))
        return {"verified": not residuals, "records": records, "residuals": residuals,
                "elapsed_seconds": deadline.elapsed()}


def provenance(env: dict[str, str], release: dict) -> dict:
    status = {}
    for line in read_small(Path("/proc/self/status")).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            status[key] = value.strip()
    return {"runner_environment": env["RUNNER_ENVIRONMENT"], "runner_os": env["RUNNER_OS"],
            "runner_arch": env["RUNNER_ARCH"], "image_os": env["ImageOS"],
            "image_version": env.get("ImageVersion", ""), "kernel": platform.release(),
            "machine": platform.machine(), "python": platform.python_version(),
            "compiler": {"path": "", "version": ""}, "uid": os.getuid(), "euid": os.geteuid(),
            "cap_eff": status.get("CapEff"), "cap_bnd": status.get("CapBnd"),
            "no_new_privs": status.get("NoNewPrivs"), "seccomp": status.get("Seccomp"),
            "boot_id": read_small(Path("/proc/sys/kernel/random/boot_id")),
            "cgroup_mount": "/sys/fs/cgroup", "cgroup_parent_controllers": [],
            "cgroup_parent_subtree_control": [], "os_release": release, "native_sha256": None,
            "fixture": {"account": None, "cgroup_objects": [], "resource_observations": []}}


def encode_report(report: dict) -> bytes:
    return (json.dumps(report, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--round", required=True, type=int, choices=(1, 2, 3))
    args = parser.parse_args(argv)
    prep = Deadline(LIMITS["prep_seconds"])
    env = dict(os.environ)
    repo = Path(__file__).resolve().parents[4]
    try:
        # No directory/account/cgroup/build creation occurs before these checks.
        source = source_identity(repo, args.expected_commit, env)
        run_id, output, release = admission(env, args.round)
        facts = provenance(env, release)
        prep.check()
    except (Refusal, OSError, ValueError, subprocess.SubprocessError) as exc:
        print("H07 fixture REJECTED before setup: " + str(exc), file=sys.stderr)
        return 4
    fixture = Fixture(repo, output, run_id, args.round)
    facts["fixture"] = fixture.facts
    report = {"schema_version": 1, "source": source,
              "run": {"id": run_id, "attempt": 1, "round": args.round},
              "provenance": facts, "limits": dict(LIMITS), "capability": None, "cases": [],
              "cleanup": {"verified": False, "records": [], "residuals": []},
              "status": "UNSUPPORTED", "reason": "",
              "budget": {"prep_elapsed_seconds": 0.0, "cases_elapsed_seconds": 0.0,
                         "cleanup_elapsed_seconds": 0.0, "diagnostic_bytes": 0,
                         "report_bytes": 0, "file_logical_bytes": 0, "file_count": 0,
                         "allocated_bytes": 0, "inode_count": 0, "suite_stream_bytes": 0}}
    cases_deadline = None
    try:
        fixture.initialize_output()
        controllers, enabled = fixture.check_cgroup_parent()
        facts["cgroup_parent_controllers"], facts["cgroup_parent_subtree_control"] = controllers, enabled
        facts["compiler"] = fixture.compile(prep)
        facts["native_sha256"] = fixture.helper_sha
        fixture.create_account(prep)
        fixture.setup_cgroups(prep)
        capability = fixture.native("probe", prep)
        report["capability"] = capability
        prep.check()
        from verify_receipt import validate_native, derive_case, derive_capability
        errors = validate_native(capability)
        if errors:
            raise Refusal("capability receipt invalid: " + "; ".join(errors)[:2048])
        for stream in capability["streams"].values():
            fixture.diagnostic(base64.b64decode(stream["data_base64"], validate=True))
        if fixture.diagnostic_exceeded:
            raise Refusal("probe/setup diagnostics exceed their cumulative ceiling")
        fixture.verify_empty()
        probe_result = derive_capability(capability)
        if not probe_result["supported"]:
            report["reason"] = "fixed native capability probe did not establish support"
            if capability.get("status") != "UNSUPPORTED" or not capability.get("cleanup_verified"):
                report["status"] = "UNKNOWN_RETAINED"
            if probe_result["errors"]:
                report["reason"] += ": " + "; ".join(probe_result["errors"])[:2048]
        else:
            report["budget"]["prep_elapsed_seconds"] = prep.elapsed()
            cases_deadline = Deadline(LIMITS["cases_seconds"])
            for case in ("C1", "C2", "C3", "C4", "C5", "C6"):
                receipt = fixture.native(case, cases_deadline)
                report["cases"].append(receipt)
                errors = validate_native(receipt)
                if errors:
                    raise Refusal("native case receipt invalid: " + "; ".join(errors)[:2048])
                fixture.inventory()
                fixture.verify_empty()
                report["budget"]["suite_stream_bytes"] += sum(s["bytes"] for s in receipt["streams"].values())
                derived = derive_case(receipt)
                # Expected C3/C6 missing evidence is allowed only with proven cleanup.
                if receipt.get("cleanup_verified") is not True:
                    raise Refusal("native case cleanup was not proven")
                if derived["case_expectation_met"] is not True:
                    report["reason"] = "case expected facts were not established: " + case
                    break
            report["status"] = "UNKNOWN_RETAINED"
    except (Refusal, OSError, ValueError, subprocess.SubprocessError) as exc:
        report["reason"] = str(exc)[:4096]
        if fixture.native_started or fixture.native_timed_out or report["cases"]:
            report["status"] = "UNKNOWN_RETAINED"
    finally:
        if not report["budget"]["prep_elapsed_seconds"]:
            report["budget"]["prep_elapsed_seconds"] = prep.elapsed()
        if cases_deadline is not None:
            report["budget"]["cases_elapsed_seconds"] = cases_deadline.elapsed()
        cleanup = fixture.cleanup()
        report["budget"]["cleanup_elapsed_seconds"] = cleanup.pop("elapsed_seconds")
        report["cleanup"] = cleanup
        if not cleanup["verified"]:
            report["status"] = "UNKNOWN_RETAINED"
        if fixture.diagnostic_exceeded:
            report["status"] = "UNKNOWN_RETAINED"
            report["reason"] = "diagnostic ceiling exceeded; only bounded original prefix retained"
    try:
        from verify_receipt import derive_report, validate_report
        if not fixture.evidence.is_dir():
            raise Refusal("evidence directory was not created")
        fixture.write_artifact("diagnostics.txt", bytes(fixture.diagnostics))
        report["budget"]["diagnostic_bytes"] = len(fixture.diagnostics)
        report["budget"].update(fixture.inventory())
        derived = derive_report(report)
        report["status"] = derived["status"]
        if derived["errors"]:
            report["reason"] = "report verification: " + "; ".join(derived["errors"])[:2048]
        elif report["status"] == "QUALIFIED_IN_FIXTURE":
            report["reason"] = ""
        # Size includes itself; converge before the exclusive final write.
        for _ in range(6):
            size = len(encode_report(report))
            if report["budget"]["report_bytes"] == size:
                break
            report["budget"]["report_bytes"] = size
        errors = validate_report(report)
        if errors:
            report["status"] = "UNKNOWN_RETAINED"
            report["reason"] = "final report verification: " + "; ".join(errors)[:2048]
            for _ in range(6):
                size = len(encode_report(report))
                if report["budget"]["report_bytes"] == size:
                    break
                report["budget"]["report_bytes"] = size
        fixture.write_artifact("report.json", encode_report(report))
        manifest = {}
        for name in ARTIFACT_NAMES:
            path = fixture.evidence / name
            if path.exists():
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise Refusal("artifact is not an exclusive regular file")
                manifest[name] = {"size": info.st_size, "sha256": digest(path.read_bytes())}
        fixture.write_artifact("manifest.json", encode_report({"files": manifest,
                               "inventory_after_report": fixture.inventory(),
                               "inventory_note": "report budget is measured after cleanup before report/manifest; this manifest snapshot includes report but not itself; final allowlist inventory is independently checked and logged",
                               "source": source, "run": report["run"]}))
        final_inventory = fixture.inventory()
    except (Refusal, OSError, ValueError) as exc:
        print("H07 evidence preservation incomplete: " + str(exc), file=sys.stderr)
        return 3
    print("H07 fixture " + report["status"] + "; evidence=" + str(fixture.evidence)
          + "; final_allowlist_inventory=" + json.dumps(final_inventory, sort_keys=True))
    return {"QUALIFIED_IN_FIXTURE": 0, "UNSUPPORTED": 2, "REJECTED": 4}.get(report["status"], 3)


if __name__ == "__main__":
    raise SystemExit(main())

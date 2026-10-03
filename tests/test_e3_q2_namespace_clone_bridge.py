"""Source, build and isolated-tail checks for the namespace fixture bridge.

These checks do not provision a cgroup or execute a native fixture case.  The
real clone-into-cgroup path remains NOT_RUN unless an explicitly supplied,
isolated root fixture is admitted by the F0/F2 plan.
"""

from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import sysconfig
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "e3_host" / "q2_namespace_clone_bridge.c"
MODULE = "_q2_namespace_clone_bridge"
BUILD_TIMEOUT_SECONDS = 30
TOOL_TIMEOUT_SECONDS = 10
TAIL_TIMEOUT_SECONDS = 10
TAIL_REAP_TIMEOUT_SECONDS = 5


def _compiler() -> list[str]:
    configured = sysconfig.get_config_var("CC") or "cc"
    return shlex.split(configured)


def _build(directory: Path, *, extra_cflags: tuple[str, ...] = ()) -> Path:
    include = Path(sysconfig.get_paths()["include"])
    if not include.is_dir():
        raise AssertionError(f"Linux F2 gate: CPython headers are unavailable at {include}")
    suffix = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    output = directory / f"{MODULE}{suffix}"
    command = [
        *_compiler(),
        "-std=c11",
        "-O2",
        "-fPIC",
        "-shared",
        "-fno-ident",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wl,--build-id=none",
        f"-I{include}",
        *extra_cflags,
        str(SOURCE),
        "-o",
        str(output),
    ]
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True,
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "Linux F2 gate: native bridge build failed\n"
            f"command: {shlex.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return output


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(MODULE, path)
    if spec is None or spec.loader is None:
        raise AssertionError("extension loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TAIL_SCRIPT = r'''
import ctypes
import hashlib
import os
import signal
import struct
import sys
import time

sys.path.insert(0, os.environ["Q2_BRIDGE_MODULE_DIR"])
import _q2_namespace_clone_bridge as bridge

MODE = os.environ["Q2_TAIL_TEST_MODE"]
DEADLINE = signal.SIGRTMIN
STOP_SIGNALS = (
    signal.SIGCHLD, signal.SIGUSR1, signal.SIGHUP, signal.SIGTERM,
    signal.SIGINT, signal.SIGQUIT, signal.SIGXCPU, DEADLINE,
)
for signum in (*STOP_SIGNALS, signal.SIGALRM, signal.SIGPROF):
    signal.signal(signum, signal.SIG_DFL)
signal.signal(signal.SIGPIPE, signal.SIG_IGN)
signal.pthread_sigmask(signal.SIG_SETMASK, STOP_SIGNALS)
for descriptor in (0, 1, 2):
    os.set_blocking(descriptor, False)

class SigSet(ctypes.Structure):
    _fields_ = [("words", ctypes.c_ulong * 16)]

class SigVal(ctypes.Union):
    _fields_ = [("integer", ctypes.c_int), ("pointer", ctypes.c_void_p)]

class SigEvent(ctypes.Structure):
    _fields_ = [
        ("value", SigVal),
        ("signo", ctypes.c_int),
        ("notify", ctypes.c_int),
        ("padding", ctypes.c_byte * 48),
    ]

class Timespec(ctypes.Structure):
    _fields_ = [("seconds", ctypes.c_long), ("nanoseconds", ctypes.c_long)]

class Itimerspec(ctypes.Structure):
    _fields_ = [("interval", Timespec), ("value", Timespec)]

libc = ctypes.CDLL(None, use_errno=True)
mask = SigSet()
if libc.sigemptyset(ctypes.byref(mask)) != 0:
    raise OSError(ctypes.get_errno(), "sigemptyset")
signalfd_signals = (signal.SIGCHLD,) if MODE == "wrong_signalfd_mask" else STOP_SIGNALS
for signum in signalfd_signals:
    if libc.sigaddset(ctypes.byref(mask), signum) != 0:
        raise OSError(ctypes.get_errno(), "sigaddset")
signalfd = libc.signalfd(-1, ctypes.byref(mask), os.O_NONBLOCK)
if signalfd < 0:
    raise OSError(ctypes.get_errno(), "signalfd")
if signalfd != 3:
    os.dup2(signalfd, 3, inheritable=True)
    os.close(signalfd)
os.set_inheritable(3, True)
procfd = os.open("/proc", os.O_RDONLY | os.O_DIRECTORY)
if procfd != 4:
    os.dup2(procfd, 4, inheritable=True)
    os.close(procfd)
os.set_inheritable(4, True)

event = SigEvent()
event.signo = signal.SIGALRM
event.notify = 0
fatal_timer = ctypes.c_void_p()
if libc.timer_create(time.CLOCK_PROCESS_CPUTIME_ID, ctypes.byref(event), ctypes.byref(fatal_timer)) != 0:
    raise OSError(ctypes.get_errno(), "timer_create")
timer_spec = Itimerspec()
timer_spec.value.seconds = 5
if libc.timer_settime(fatal_timer, 0, ctypes.byref(timer_spec), None) != 0:
    raise OSError(ctypes.get_errno(), "timer_settime")
signal.setitimer(signal.ITIMER_PROF, 0.0)

receipt = bytearray(224)
receipt[:8] = b"Q2NSR001"
struct.pack_into("<Q", receipt, 8, 1)
struct.pack_into("<Q", receipt, 48, 1)
receipt[56:88] = hashlib.sha256(b"previous").digest()
receipt[88:120] = hashlib.sha256(b"H").digest()
receipt[120:152] = hashlib.sha256(b"cleanup-final").digest()
receipt[152:184] = hashlib.sha256(b"ack-capture-head").digest()
process = time.process_time_ns()
boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
monotonic = time.monotonic_ns()
realtime = time.time_ns()
if MODE == "clock_step":
    realtime += 5_000_000_000
limits = {
    "schema_version": 1,
    "last_process_ns": process,
    "process_accounted_ns": process,
    "carrier_accounted_ns": process,
    "guardian_accounted_ns": 0,
    "guardian_usage_ns": 0,
    "sample_round_ns": 1_000_000,
    "tail_cpu_max_ns": 50_000_000,
    "tail_wall_max_ns": 50_000_000,
    "boot_deadline_ns": boot + 5_000_000_000,
    "mono_deadline_ns": monotonic + 5_000_000_000,
    "realtime_deadline_ns": realtime + 5_000_000_000,
    "realtime_minus_boot_ns": realtime - boot,
    "realtime_minus_mono_ns": realtime - monotonic,
    "clock_step_tolerance_ns": 50_000_000,
    "fatal_timer_min_remaining_ns": 1_000_000_000,
    "fatal_timer_id": 0 if fatal_timer.value is None else fatal_timer.value,
    "fatal_timer_clock": time.CLOCK_PROCESS_CPUTIME_ID,
    "signalfd_fd": 3,
    "stop_latched": 1 if MODE == "latched" else 0,
}
if MODE == "bad_magic":
    receipt[0] ^= 1
elif MODE == "bad_version":
    struct.pack_into("<Q", receipt, 8, 2)
elif MODE == "nonzero_clock":
    struct.pack_into("<Q", receipt, 16, 1)
elif MODE == "zero_counter":
    struct.pack_into("<Q", receipt, 48, 0)
elif MODE == "zero_previous":
    receipt[56:88] = bytes(32)
elif MODE == "zero_h":
    receipt[88:120] = bytes(32)
elif MODE == "zero_cleanup":
    receipt[120:152] = bytes(32)
elif MODE == "zero_ack":
    receipt[152:184] = bytes(32)
elif MODE == "reserved_nonzero":
    receipt[184] = 1
elif MODE == "prehashed":
    receipt[192] = 1
elif MODE == "bad_size":
    receipt = receipt[:-1]
elif MODE == "wrong_timer_contract":
    limits["fatal_timer_clock"] = time.CLOCK_MONOTONIC
bridge.fixture_setup(0, 1, 2, DEADLINE)
if MODE in {
    "bad_magic", "bad_version", "nonzero_clock", "zero_counter", "zero_previous",
    "zero_h", "zero_cleanup", "zero_ack", "reserved_nonzero", "prehashed",
    "bad_size", "wrong_timer_contract", "wrong_signalfd_mask",
}:
    try:
        bridge.fixture_arm(bytes(receipt), limits)
    except bridge.BridgeError:
        os._exit(35)
    os._exit(36)
elif MODE == "latched":
    try:
        bridge.fixture_arm(bytes(receipt), limits)
    except bridge.BridgeError:
        limits["stop_latched"] = 0
        try:
            bridge.fixture_arm(bytes(receipt), limits)
        except bridge.BridgeError:
            os._exit(31)
        os._exit(33)
    os._exit(32)
bridge.fixture_arm(bytes(receipt), limits)
if MODE in {"replace_signalfd_wrong_mask", "replace_signalfd_eventfd"}:
    if MODE == "replace_signalfd_wrong_mask":
        replacement_mask = SigSet()
        if libc.sigemptyset(ctypes.byref(replacement_mask)) != 0:
            raise OSError(ctypes.get_errno(), "sigemptyset")
        if libc.sigaddset(ctypes.byref(replacement_mask), signal.SIGUSR2) != 0:
            raise OSError(ctypes.get_errno(), "sigaddset")
        replacement = libc.signalfd(-1, ctypes.byref(replacement_mask), os.O_NONBLOCK)
    else:
        replacement = libc.eventfd(0, os.O_NONBLOCK)
    if replacement < 0:
        raise OSError(ctypes.get_errno(), "replacement fd")
    if replacement != 3:
        os.dup2(replacement, 3, inheritable=True)
        os.close(replacement)
    os.set_inheritable(3, True)
elif MODE == "pending_stop":
    os.kill(os.getpid(), signal.SIGUSR1)
elif MODE == "profiler_armed":
    signal.setitimer(signal.ITIMER_PROF, 1.0)
elif MODE == "extra_blocked":
    signal.pthread_sigmask(signal.SIG_BLOCK, (signal.SIGUSR2,))
bridge.fixture_cleanup_tail()
'''


def _run_tail(module_path: Path, mode: str, *, stdin_payload: bytes = b"", close_stdout=False):
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["Q2_BRIDGE_MODULE_DIR"] = str(module_path.parent)
    environment["Q2_TAIL_TEST_MODE"] = mode
    process = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", TAIL_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    stdin_pipe = process.stdin
    if stdin_payload:
        stdin_pipe.write(stdin_payload)
        stdin_pipe.flush()
    # communicate() normally closes stdin immediately.  The native tail must
    # instead observe the still-open, empty nonblocking pipe as EAGAIN.
    process.stdin = None
    if close_stdout:
        process.stdout.close()
        process.stdout = None
    try:
        stdout, stderr = process.communicate(timeout=TAIL_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.communicate(timeout=TAIL_REAP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            if process.stdin is not None:
                process.stdin.close()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
        raise
    finally:
        stdin_pipe.close()
    if close_stdout:
        stdout = b""
    return process.returncode, stdout, stderr


IDENTITY_REJECTION_SCRIPT = r'''
import os
import sys
import time

sys.path.insert(0, os.environ["Q2_BRIDGE_MODULE_DIR"])
import _q2_namespace_clone_bridge as bridge

mode = os.environ["Q2_IDENTITY_MODE"]
role = "supervisor" if mode.startswith("supervisor") else "case"
gate_target = 8 if role == "supervisor" else 3
gate_read, gate_write = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
if gate_read != gate_target:
    os.dup2(gate_read, gate_target, inheritable=False)
    os.close(gate_read)
os.set_inheritable(gate_target, False)
cgroup_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
if mode == "case_uid_zero":
    uid, gid, groups = 0, 1, ()
elif mode == "case_gid_zero":
    uid, gid, groups = 1, 0, ()
elif mode == "case_unsorted_supplementary_groups":
    uid, gid, groups = 1, 1, (2, 1)
elif mode == "case_root_supplementary_group":
    uid, gid, groups = 1, 1, (0,)
elif mode == "case_group_upper_bound":
    uid, gid, groups = 1, 1, (2**32 - 1,)
elif mode == "supervisor_nonroot_input":
    uid, gid, groups = 1, 1, ()
elif mode == "supervisor_current_identity_mismatch":
    current_groups = tuple(os.getgroups())
    uid, gid = 0, 0
    groups = (0,) if current_groups != (0,) else ()
else:
    raise AssertionError(mode)
try:
    bridge.fixture_clone_into_cgroup(
        cgroup_fd=cgroup_fd,
        gate_fd=gate_target,
        gate_deadline_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 1_000_000_000,
        role=role,
        executable=b"/bin/false",
        argv=(b"/bin/false",),
        env=(b"LANG=C", b"LC_ALL=C"),
        expected_parent=os.getpid(),
        uid=uid,
        gid=gid,
        groups=groups,
        affinity_cpu=0,
        rlimits=tuple((0, 0) for _ in range(16)),
    )
except bridge.BridgeError as error:
    message = str(error)
    if "groups must be nondecreasing" in message:
        os._exit(44)
    if "group id outside uint32" in message:
        os._exit(45)
    os._exit(41 if "credentials or supplementary groups invalid" in message else 43)
os._exit(42)
'''


def _run_identity_rejection(module_path: Path, mode: str) -> int:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["Q2_BRIDGE_MODULE_DIR"] = str(module_path.parent)
    environment["Q2_IDENTITY_MODE"] = mode
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", IDENTITY_REJECTION_SCRIPT],
        env=environment,
        capture_output=True,
        timeout=10,
    )
    return completed.returncode


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux clone3 bridge")
class NamespaceCloneBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which(_compiler()[0]) is None:
            raise AssertionError(
                f"Linux F2 gate: configured C compiler is unavailable: {_compiler()[0]}"
            )
        cls._temporary = tempfile.TemporaryDirectory(prefix="q2-namespace-bridge-")
        cls.root = Path(cls._temporary.name)
        cls.first = _build(cls.root / "first") if (cls.root / "first").mkdir() is None else None
        cls.second = _build(cls.root / "second") if (cls.root / "second").mkdir() is None else None
        hooks_directory = cls.root / "parser-hooks"
        hooks_directory.mkdir()
        cls.parser_hooks = _build(
            hooks_directory, extra_cflags=("-DQ2_BRIDGE_NATIVE_TEST_HOOKS=1",)
        )

    @classmethod
    def tearDownClass(cls):
        cls._temporary.cleanup()

    def test_two_clean_builds_are_byte_identical_and_have_fixed_exports(self):
        first = self.first.read_bytes()
        second = self.second.read_bytes()
        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())
        bridge = _load(self.first)
        contract_spec = importlib.util.spec_from_file_location(
            "_q2_namespace_delivery_contract", ROOT / "tools" / "q2_namespace_delivery.py"
        )
        if contract_spec is None or contract_spec.loader is None:
            self.fail("delivery ABI contract loader unavailable")
        contract = importlib.util.module_from_spec(contract_spec)
        contract_spec.loader.exec_module(contract)
        self.assertEqual(bridge.manifest(), contract.native_bridge_abi())
        self.assertEqual(
            bridge.manifest(),
            {
                "abi_version": 1,
                "clone_args_size": 88,
                "clone_flags": ["CLONE_INTO_CGROUP", "CLONE_PIDFD"],
                "clone_flags_value": (1 << 33) | 0x1000,
                "exit_signal": "SIGCHLD",
                "release_byte": 1,
                "max_gate_wait_ns": 840_000_000_000,
                "max_argv": 16,
                "max_env": 2,
                "max_groups": 32,
                "module_name": "_q2_namespace_clone_bridge",
                "init_symbol": "PyInit__q2_namespace_clone_bridge",
                "exports": [
                    "fixture_clone_into_cgroup",
                    "fixture_setup",
                    "fixture_arm",
                    "fixture_cleanup_tail",
                ],
                "receipt_size": 224,
                "receipt_magic_ascii": "Q2NSR001",
                "receipt_magic_offset": 0,
                "receipt_magic_bytes": 8,
                "receipt_version": 1,
                "receipt_version_offset": 8,
                "receipt_byte_order": "little",
                "receipt_process_ns_offset": 16,
                "receipt_boottime_ns_offset": 24,
                "receipt_monotonic_ns_offset": 32,
                "receipt_realtime_ns_offset": 40,
                "receipt_counter_offset": 48,
                "receipt_previous_digest_offset": 56,
                "receipt_h_digest_offset": 88,
                "receipt_cleanup_final_digest_offset": 120,
                "receipt_ack_capture_head_offset": 152,
                "receipt_reserved_offset": 184,
                "receipt_reserved_bytes": 8,
                "receipt_hash_offset": 192,
                "receipt_hash_input_bytes": 192,
                "receipt_sha256_bytes": 32,
                "receipt_digest_size": 32,
                "receipt_single_raw_nonblocking_write": True,
                "fatal_timer_clock_identity": (
                    "caller-sealed-not-kernel-readable:CLOCK_PROCESS_CPUTIME_ID"
                ),
                "atfork_registry_guard": "BLOCKED_EXTERNAL_F2_SOURCE_PROOF",
                "main_thread_guard": "BLOCKED_EXTERNAL_CALLER_PROOF",
            },
        )
        if shutil.which("readelf"):
            symbols = subprocess.check_output(
                ["readelf", "--wide", "--dyn-syms", str(self.first)], text=True,
                timeout=TOOL_TIMEOUT_SECONDS,
            )
            self.assertIn("PyInit__q2_namespace_clone_bridge", symbols)

    def test_source_fixes_atomic_clone_and_fork_hook_order(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("_Static_assert(sizeof(struct clone_args) == Q2_CLONE_ARGS_SIZE", source)
        self.assertIn("clone_arguments.flags = CLONE_INTO_CGROUP | CLONE_PIDFD", source)
        self.assertIn("clone_arguments.exit_signal = SIGCHLD", source)
        self.assertIn("PyOS_BeforeFork();", source)
        self.assertLess(source.index("PyOS_BeforeFork();"), source.index("SYS_clone3" , source.index("PyOS_BeforeFork();")))
        parent = source.index("PyOS_AfterFork_Parent();")
        error = source.index("if (child < 0)", parent)
        self.assertLess(parent, error)
        self.assertLess(source.index("clone_errno = errno;"), parent)
        self.assertLess(source.index("validate_gate_fd(gate_fd)"), source.index("PyOS_BeforeFork();"))
        self.assertIn("gate_deadline_boottime_ns - gate_now_ns > Q2_MAX_GATE_WAIT_NS", source)
        self.assertIn("kill_reap_close_pidfd(pidfd)", source)
        containment = source[
            source.index("kill_reap_close_pidfd(int pidfd)") : source.index(
                "static void\nrun_child", source.index("kill_reap_close_pidfd(int pidfd)")
            )
        ]
        self.assertIn("SYS_pidfd_send_signal", containment)
        self.assertIn("ppoll(&watched", containment)
        self.assertIn("WEXITED | WNOHANG", containment)
        self.assertNotRegex(containment, r"waitid\([^;]*WEXITED\s*\)")
        child = source[
            source.index("run_child(child_spec *spec)") : source.index(
                "static PyObject *\npy_fixture_clone_into_cgroup"
            )
        ]
        self.assertLess(child.index("PR_SET_PDEATHSIG"), child.index("getppid()"))
        self.assertLess(child.index("getppid()"), child.index("PyOS_AfterFork_Child"))
        ordered_case_steps = (
            "clear_ambient_keepcaps_and_bounding()",
            "setgroups(",
            "setresgid(",
            "setresuid(",
            "set_and_check_fsids(",
            "clear_capability_sets()",
            "PR_SET_NO_NEW_PRIVS",
            "verify_child_identity(spec)",
            "normalize_and_verify_process(spec)",
            "prepare_exec_fds(spec)",
        )
        positions = [child.index(step) for step in ordered_case_steps]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(child.index("verify_supervisor_identity(spec)"),
                        child.index("normalize_and_verify_process(spec)"))
        identity_gate = source.index("clone role credentials or supplementary groups invalid")
        self.assertLess(identity_gate, source.index("memset(&clone_arguments", identity_gate))
        self.assertNotRegex(source, r"\bfork\s*\(")
        self.assertNotIn("cgroup.procs", source)
        reset = source[
            source.index("reset_child_signals(void)") : source.index(
                "static int\napply_rlimits", source.index("reset_child_signals(void)")
            )
        ]
        self.assertLess(reset.index("SIG_BLOCK"), reset.index("sigaction(signal_number"))
        self.assertLess(reset.index("sigaction(signal_number"), reset.index("sigpending(&pending)"))
        self.assertLess(reset.index("sigpending(&pending)"), reset.index("SIG_SETMASK"))

    def test_source_tail_binds_all_immutable_gates_and_best_effort_closes(self):
        source = SOURCE.read_text(encoding="utf-8")
        for required in (
            "stop_latched",
            "signalfd_fd",
            "fatal_timer_id",
            "fatal_timer_min_remaining_ns",
            "realtime_minus_boot_ns",
            "realtime_minus_mono_ns",
            "clock_step_tolerance_ns",
            "guardian_accounted_ns",
            "carrier_accounted_ns",
            "sample_round_ns",
            "getitimer(ITIMER_PROF",
            "tail_signalfd_empty()",
            "pending_stop_signal()",
            "signalfd_mask_matches_held_procfs()",
        ):
            self.assertIn(required, source)
        tail = source[
            source.index("py_fixture_cleanup_tail") : source.index(
                "static PyObject *\npy_manifest", source.index("py_fixture_cleanup_tail")
            )
        ]
        self.assertLess(tail.index("CLOCK_PROCESS_CPUTIME_ID"), tail.index("CLOCK_BOOTTIME"))
        self.assertIn("close_stdout_result=close(tail_plan.fd1);", tail)
        self.assertIn("close_stderr_result=close(tail_plan.fd2);", tail)
        fixed_hash = source[
            source.index("sha256_fixed192(") : source.index(
                "static void\nfree_child_spec", source.index("sha256_fixed192(")
            )
        ]
        self.assertNotIn("for (", fixed_hash)
        self.assertEqual(fixed_hash.count("LOAD_INPUT_BLOCK("), 4)  # macro plus three data blocks
        self.assertIn("w[15]=1536U", fixed_hash)

        comparison = source[
            source.index("tail_signal_configuration_valid(void)") : source.index(
                "static int\nhex_nibble", source.index("tail_signal_configuration_valid(void)")
            )
        ]
        self.assertNotIn("memcmp", comparison)
        self.assertNotIn("for (", comparison)
        for index in range(16):
            self.assertIn(f"mask_words[{index}] != expected_words[{index}]", comparison)

        restore = source[
            source.index("restore_tail_signals(void)") : source.index(
                "static PyObject *\npy_fixture_cleanup_tail",
                source.index("restore_tail_signals(void)"),
            )
        ]
        for signal_name in (
            "SIGUSR1",
            "SIGHUP",
            "SIGTERM",
            "SIGINT",
            "SIGQUIT",
            "SIGXCPU",
            "tail_plan.deadline_signal",
        ):
            self.assertIn(signal_name, restore)
        for signal_name in ("SIGCHLD", "SIGALRM", "SIGPROF"):
            self.assertNotIn(signal_name, restore)

        fdinfo_tail = source[
            source.index("tail_signalfd_fdinfo_valid(void)") : source.index(
                "static int\ntail_guards_valid",
                source.index("tail_signalfd_fdinfo_valid(void)"),
            )
        ]
        self.assertNotIn("for (", fdinfo_tail)
        self.assertNotIn("while (", fdinfo_tail)
        self.assertNotIn("memcmp", fdinfo_tail)
        self.assertIn("Q2_DIFF_32(0U);Q2_DIFF_32(32U);", fdinfo_tail)
        self.assertIn("trailing != 0", fdinfo_tail)

    def test_compiled_final_tail_call_graph_has_no_memcmp_rep_or_cycle(self):
        objdump = shutil.which("objdump")
        if objdump is None:
            self.fail("Linux F2 gate: objdump is required for the native tail binary check")
        pending_symbols = ["py_fixture_cleanup_tail"]
        checked_symbols: set[str] = set()
        while pending_symbols:
            symbol = pending_symbols.pop()
            if symbol in checked_symbols:
                continue
            checked_symbols.add(symbol)
            with self.subTest(symbol=symbol):
                disassembly = subprocess.check_output(
                    [objdump, "-dr", f"--disassemble={symbol}", str(self.first)],
                    text=True, timeout=TOOL_TIMEOUT_SECONDS,
                )
                self.assertIn(f"<{symbol}>", disassembly)
                self.assertNotIn("memcmp", disassembly)
                self.assertNotIn("memset", disassembly)
                self.assertNotRegex(disassembly, r"\brep(?:z|nz)?\s")
                self.assertNotRegex(disassembly, r"\bloop\S*\s")
                for called in re.findall(r"\bcall\S*\s+[0-9a-f]+\s+<([^>+]+)", disassembly):
                    if "@plt" not in called and called not in checked_symbols:
                        pending_symbols.append(called)
                instructions: list[tuple[int, str]] = []
                for line in disassembly.splitlines():
                    match = re.match(r"\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+\s*(.*)", line)
                    if match and match.group(2).strip():
                        instructions.append((int(match.group(1), 16), match.group(2).strip()))
                self.assertTrue(instructions)
                addresses = {address for address, _instruction in instructions}
                edges: dict[int, set[int]] = {address: set() for address in addresses}
                for index, (address, instruction) in enumerate(instructions):
                    mnemonic = instruction.split(maxsplit=1)[0]
                    successor = instructions[index + 1][0] if index + 1 < len(instructions) else None
                    branch = re.match(r"j\S*\s+([0-9a-f]+)\b", instruction)
                    if branch:
                        target = int(branch.group(1), 16)
                        if target in addresses:
                            edges[address].add(target)
                        if mnemonic != "jmp" and successor is not None:
                            edges[address].add(successor)
                    elif (
                        mnemonic.startswith("call")
                        and any(
                            target in instruction
                            for target in ("<tail_fail>", "<_exit@plt>", "<__stack_chk_fail@plt>")
                        )
                    ):
                        pass
                    elif not mnemonic.startswith("ret") and successor is not None:
                        edges[address].add(successor)

                indegree = {address: 0 for address in addresses}
                for successors in edges.values():
                    for successor in successors:
                        indegree[successor] += 1
                ready = [address for address, degree in indegree.items() if degree == 0]
                processed = 0
                while ready:
                    address = ready.pop()
                    processed += 1
                    for successor in edges[address]:
                        indegree[successor] -= 1
                        if indegree[successor] == 0:
                            ready.append(successor)
                self.assertEqual(
                    processed,
                    len(addresses),
                    f"compiled {symbol} contains a control-flow cycle",
                )
        self.assertTrue(
            {"tail_signal_configuration_valid", "tail_signalfd_fdinfo_valid", "restore_tail_signals"}
            <= checked_symbols
        )

    def test_fdinfo_signalfd_parser_is_bounded_and_requires_exact_line(self):
        library = ctypes.CDLL(str(self.parser_hooks))
        parser = library.q2_parse_signalfd_mask
        parser.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64)
        parser.restype = ctypes.c_int
        expected = sum(
            1 << (signum - 1)
            for signum in (
                signal.SIGCHLD,
                signal.SIGUSR1,
                signal.SIGHUP,
                signal.SIGTERM,
                signal.SIGINT,
                signal.SIGQUIT,
                signal.SIGXCPU,
                signal.SIGRTMIN,
            )
        )

        def parse(raw: bytes, wanted: int = expected) -> int:
            storage = ctypes.create_string_buffer(raw, len(raw))
            return parser(storage, len(raw), wanted)

        value = f"{expected:016x}".encode("ascii")
        valid = b"pos:\t0\nflags:\t02\nsigmask:\t" + value + b"\n"
        self.assertEqual(parse(valid), 1)
        for malformed in (
            b"sigmask:\t\n",
            b"sigmask:\t" + value[:-1] + b"\n",
            b"sigmask:\t" + value,
            b"prefixsigmask:\t" + value + b"\n",
            b"sigmask: " + value + b"\n",
            b"sigmask:\t" + value[:-1] + b"g\n",
            b"sigmask:\t" + value + b"0\n",
            b"sigmask:\t" + value + b" \n",
            b"sigmask:\t" + value + b"\nsigmask:\t" + value + b"\n",
        ):
            with self.subTest(raw=malformed):
                self.assertEqual(parse(malformed), 0)
        self.assertEqual(parse(valid, expected ^ 1), 0)

    def test_native_tail_has_fixed_receipt_and_correct_sha256(self):
        returncode, stdout, stderr = _run_tail(self.first, "valid")
        self.assertEqual((returncode, stderr), (0, b""))
        self.assertEqual(len(stdout), 224)
        self.assertEqual(stdout[:8], b"Q2NSR001")
        self.assertEqual(struct.unpack_from("<Q", stdout, 8)[0], 1)
        self.assertTrue(all(struct.unpack_from("<Q", stdout, offset)[0] > 0
                            for offset in (16, 24, 32, 40)))
        self.assertEqual(struct.unpack_from("<Q", stdout, 48)[0], 1)
        self.assertEqual(stdout[56:88], hashlib.sha256(b"previous").digest())
        self.assertEqual(stdout[88:120], hashlib.sha256(b"H").digest())
        self.assertEqual(stdout[120:152], hashlib.sha256(b"cleanup-final").digest())
        self.assertEqual(stdout[152:184], hashlib.sha256(b"ack-capture-head").digest())
        self.assertEqual(stdout[184:192], bytes(8))
        self.assertEqual(stdout[192:], hashlib.sha256(stdout[:192]).digest())

    def test_native_tail_rejects_mutable_or_unsafe_final_gate_state(self):
        for mode, expected in (
            ("pending_stop", 204),
            ("profiler_armed", 204),
            ("clock_step", 204),
            ("extra_blocked", 204),
            ("replace_signalfd_wrong_mask", 204),
            ("replace_signalfd_eventfd", 204),
        ):
            with self.subTest(mode=mode):
                returncode, stdout, _stderr = _run_tail(self.first, mode)
                self.assertEqual(returncode, expected)
                self.assertEqual(stdout, b"")

        returncode, stdout, _stderr = _run_tail(self.first, "valid", stdin_payload=b"x")
        self.assertEqual(returncode, 205)
        self.assertEqual(stdout, b"")

        returncode, stdout, _stderr = _run_tail(self.first, "latched")
        self.assertEqual(returncode, 31)
        self.assertEqual(stdout, b"")

    def test_native_arm_rejects_each_invalid_receipt_field_and_wrong_signalfd_mask(self):
        for mode in (
            "bad_magic",
            "bad_version",
            "nonzero_clock",
            "zero_counter",
            "zero_previous",
            "zero_h",
            "zero_cleanup",
            "zero_ack",
            "reserved_nonzero",
            "prehashed",
            "bad_size",
            "wrong_timer_contract",
            "wrong_signalfd_mask",
        ):
            with self.subTest(mode=mode):
                returncode, stdout, _stderr = _run_tail(self.first, mode)
                self.assertEqual(returncode, 35)
                self.assertEqual(stdout, b"")

    def test_native_tail_epipe_is_nonzero_and_does_not_hang(self):
        returncode, stdout, _stderr = _run_tail(self.first, "valid", close_stdout=True)
        self.assertNotEqual(returncode, 0)
        self.assertEqual(stdout, b"")

    def test_clone_refuses_unheld_or_wrong_parent_before_syscall(self):
        bridge = _load(self.first)
        limits = tuple((0, 0) for _ in range(os.sysconf_names.get("SC_RLIM_NLIMITS", 16)))
        # The exact platform count is intentionally learned only for this local
        # negative call; a real plan supplies and seals every pair.
        with self.assertRaises(bridge.BridgeError):
            bridge.fixture_clone_into_cgroup(
                cgroup_fd=-1,
                gate_fd=3,
                gate_deadline_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                + 1_000_000_000,
                role="case",
                executable=b"/bin/false",
                argv=(b"/bin/false",),
                env=(b"LANG=C", b"LC_ALL=C"),
                expected_parent=os.getpid() + 1,
                uid=os.getuid(),
                gid=os.getgid(),
                groups=tuple(os.getgroups()),
                affinity_cpu=0,
                rlimits=limits,
            )

    def test_clone_rejects_root_case_and_unbound_supervisor_identities_before_syscall(self):
        for mode in (
            "case_uid_zero",
            "case_gid_zero",
            "case_root_supplementary_group",
            "supervisor_nonroot_input",
            "supervisor_current_identity_mismatch",
        ):
            with self.subTest(mode=mode):
                self.assertEqual(_run_identity_rejection(self.first, mode), 41)

    def test_clone_rejects_unsorted_but_preserves_exact_sorted_supplementary_groups(self):
        self.assertEqual(
            _run_identity_rejection(self.first, "case_unsorted_supplementary_groups"), 44
        )
        self.assertEqual(_run_identity_rejection(self.first, "case_group_upper_bound"), 45)
        source = SOURCE.read_text(encoding="utf-8")
        parser = source[
            source.index("parse_groups(PyObject *value") : source.index(
                "static int\nparse_rlimits", source.index("parse_groups(PyObject *value")
            )
        ]
        self.assertIn("spec->groups[i] < spec->groups[i - 1]", parser)
        self.assertNotIn("spec->groups[i] <= spec->groups[i - 1]", parser)
        self.assertIn("item >= UINT32_MAX", parser)
        ordinary = source[
            source.index("case_identity_is_ordinary(const child_spec *spec)") : source.index(
                "static int\nverify_child_identity",
                source.index("case_identity_is_ordinary(const child_spec *spec)"),
            )
        ]
        self.assertIn("spec->groups[index] == 0", ordinary)

    @unittest.skipUnless(
        os.environ.get("LH_Q2_NAMESPACE_NATIVE_FIXTURE") == "1",
        "NOT_RUN: no explicit isolated root cgroup fixture was supplied",
    )
    def test_real_clone_into_cgroup_requires_separately_admitted_fixture(self):
        self.fail("fixture harness must replace this sentinel only with exact F0 plan inputs")


if __name__ == "__main__":
    unittest.main()

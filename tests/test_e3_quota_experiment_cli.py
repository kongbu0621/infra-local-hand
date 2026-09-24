"""LOGIC_ONLY CLI routing/transport checks in real isolated Python processes.

The experiment callable is replaced before its repository module can load.
No systemd, quota, real journal, account change, or host admission is exercised.
Simulated platform/UID values are control-flow checks, not platform acceptance.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "tools" / "run_q1_experiment.py"
INPUT = "/synthetic/private/q1-experiment.json"
DIGEST = "a" * 64
COMMIT = "b" * 40


REFUSAL_SCRIPT = """
import argparse, builtins, json, os, pathlib, runpy, shutil, sys
sys.argv = sys.argv[1:]
original_import = builtins.__import__
def guard_import(name, *args, **kwargs):
    if name == 'admin' or name.startswith('admin.'):
        raise AssertionError('refused CLI imported repository runtime')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard_import
{setup}
runpy.run_path(sys.argv[0], run_name='__main__')
"""


MOCK_EXPERIMENT_SCRIPT = """
import argparse, builtins, json, os, pathlib, runpy, sys, types
from unittest.mock import Mock
sys.argv = sys.argv[1:]
expected_argv = sys.argv[1:]
original_write = os.write
original_import = builtins.__import__
module_name = 'admin.local_hand_quota_observer.experiment'
for name in ('admin', 'admin.local_hand_quota_observer'):
    package = types.ModuleType(name)
    package.__path__ = []
    sys.modules[name] = package
module = types.ModuleType(module_name)
raw = (json.dumps({{'schema': 'local-hand-quota-q1-experiment/v1',
                   'status': {status!r}, 'evidence_class': 'LOGIC_ONLY',
                   'admission_proven': False, 'real_e3_accepted': False,
                   'production_supported': False, 'padding': 'x' * {padding}}},
                  sort_keys=True, separators=(',', ':')) + '\\n').encode()
execute = Mock(return_value=raw)
module.execute_experiment = execute
sys.modules[module_name] = module
def guard_import(name, *args, **kwargs):
    if (name == 'admin' or name.startswith('admin.')) and name != module_name:
        raise AssertionError('CLI imported a real repository runtime module')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard_import
os.getuid = lambda: 0
os.geteuid = lambda: 0
captured = bytearray()
write_calls = []
{transport}
try:
    runpy.run_path(sys.argv[0], run_name='__main__')
except SystemExit as error:
    code = error.code
else:
    raise AssertionError('CLI did not exit')
execute.assert_called_once_with(expected_argv[1], expected_argv[3], expected_argv[5])
{verify}
"""


@unittest.skipUnless(sys.platform.startswith("linux"), "Q1 experiment CLI is Linux-only")
class ExperimentCLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def arguments(self):
        return ["--input", INPUT, "--sha256", DIGEST, "--source-commit", COMMIT]

    def invoke(self, arguments=None, *, script=None, flags=("-I", "-B")):
        prefix = [str(CLI)] if script is None else ["-c", script, str(CLI)]
        return subprocess.run(
            [sys.executable, *flags, *prefix,
             *(self.arguments() if arguments is None else arguments)],
            cwd=self.directory.name, capture_output=True, text=True,
            timeout=10, check=False)

    def refusal(self, completed, status, returncode, code):
        self.assertEqual(completed.returncode, returncode, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertLess(len(completed.stdout), 2048)
        value = json.loads(completed.stdout)
        self.assertEqual(value["schema"], "local-hand-quota-q1-experiment/v1")
        self.assertEqual((value["status"], value["failure_code"]), (status, code))
        self.assertIs(value["controller_entered"], False)
        for flag in ("admission_proven", "real_e3_accepted", "production_supported"):
            self.assertIs(value[flag], False)
        self.assertNotIn(INPUT, completed.stdout)

    def test_both_interpreter_flags_are_required_before_runtime_import(self):
        script = REFUSAL_SCRIPT.format(setup="")
        for flags in ((), ("-I",), ("-B",)):
            with self.subTest(flags=flags):
                self.refusal(self.invoke(script=script, flags=flags), "REJECTED", 2,
                             "ISOLATED_PYTHON_REQUIRED")

    def test_missing_flags_rejection_precedes_argument_parsing(self):
        self.refusal(self.invoke([], script=REFUSAL_SCRIPT.format(setup=""), flags=("-I",)),
                     "REJECTED", 2, "ISOLATED_PYTHON_REQUIRED")

    def test_missing_required_argument_is_rejected_before_runtime_import(self):
        completed = self.invoke([], script=REFUSAL_SCRIPT.format(setup=""))
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(completed.stdout, "")
        self.assertIn("required", completed.stderr)

    def test_unknown_and_abbreviated_flags_are_rejected_before_runtime_import(self):
        for flag in ("--unexpected", "--inp", "--sha", "--source"):
            with self.subTest(flag=flag):
                completed = self.invoke(self.arguments() + [flag, "ignored"],
                                        script=REFUSAL_SCRIPT.format(setup=""))
                self.assertEqual(completed.returncode, 2, completed.stderr)
                self.assertEqual(completed.stdout, "")
                self.assertIn("unrecognized arguments", completed.stderr)

    def test_nonlinux_refuses_before_uid_lookup_or_runtime_import(self):
        setup = """
sys.platform = 'win32'
def forbidden_uid():
    raise AssertionError('unsupported platform reached UID lookup')
os.getuid = forbidden_uid
os.geteuid = forbidden_uid
"""
        self.refusal(self.invoke(script=REFUSAL_SCRIPT.format(setup=setup)),
                     "UNSUPPORTED", 3, "LINUX_REQUIRED")

    def test_real_and_effective_uid_must_both_be_root_before_runtime_import(self):
        for uid, euid in ((1000, 1000), (0, 1000), (1000, 0)):
            with self.subTest(uid=uid, euid=euid):
                setup = f"os.getuid = lambda: {uid}\nos.geteuid = lambda: {euid}"
                self.refusal(self.invoke(script=REFUSAL_SCRIPT.format(setup=setup)),
                             "REJECTED", 2, "ADMIN_CONTROLLER_REQUIRED")

    def test_mock_experiment_status_routes_to_exact_exit_code_once(self):
        for status, returncode in (("OBSERVED", 0), ("REJECTED", 2),
                                   ("UNSUPPORTED", 3), ("UNKNOWN", 4)):
            with self.subTest(status=status):
                script = MOCK_EXPERIMENT_SCRIPT.format(
                    status=status, padding=0, transport="", verify="raise SystemExit(code)")
                completed = self.invoke(script=script)
                self.assertEqual(completed.returncode, returncode, completed.stderr)
                self.assertEqual(completed.stderr, "")
                value = json.loads(completed.stdout)
                self.assertEqual(value["status"], status)
                self.assertEqual(value["evidence_class"], "LOGIC_ONLY")
                for flag in ("admission_proven", "real_e3_accepted", "production_supported"):
                    self.assertIs(value[flag], False)

    def test_short_stdout_writes_preserve_exact_record_without_reexecuting(self):
        transport = """
def write_short(descriptor, data):
    assert descriptor == 1
    assert 0 < len(data) <= 4096
    write_calls.append(len(data))
    count = min(17, len(data))
    captured.extend(data[:count])
    return count
os.write = write_short
"""
        verify = """
assert code == 0, code
assert len(write_calls) > 2
assert bytes(captured) == raw
original_write(1, b'{"transport":"short-write-complete","calls":1}\\n')
"""
        completed = self.invoke(script=MOCK_EXPERIMENT_SCRIPT.format(
            status="OBSERVED", padding=7000, transport=transport, verify=verify))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(json.loads(completed.stdout),
                         {"transport": "short-write-complete", "calls": 1})

    def test_stdout_oserror_or_zero_after_partial_write_never_reruns(self):
        for failure in ("raise BrokenPipeError('synthetic transport failure')", "return 0"):
            with self.subTest(failure=failure):
                transport = """
def write_then_fail(descriptor, data):
    assert descriptor == 1
    assert 0 < len(data) <= 4096
    write_calls.append(len(data))
    if len(write_calls) == 1:
        captured.extend(data[:7])
        return 7
    {failure}
os.write = write_then_fail
""".format(failure=failure)
                verify = """
assert code == 74, code
assert len(write_calls) == 2
assert bytes(captured) == raw[:7]
original_write(1, b'{"transport":"failed","exit_code":74,"calls":1}\\n')
"""
                completed = self.invoke(script=MOCK_EXPERIMENT_SCRIPT.format(
                    status="OBSERVED", padding=0, transport=transport, verify=verify))
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stderr, "")
                self.assertEqual(json.loads(completed.stdout),
                                 {"transport": "failed", "exit_code": 74, "calls": 1})


if __name__ == "__main__":
    unittest.main()

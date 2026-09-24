"""Real isolated CLI processes with LOGIC_ONLY launcher/import/UID doubles.

No real launcher, systemd, quota, journal or host provisioning is executed.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "tools" / "launch_q1_experiment.py"
INPUT = "/synthetic/protected/launch.json"
ARGS = ["--input", INPUT, "--sha256", "a" * 64, "--source-commit", "b" * 40]

REFUSE = """import argparse, builtins, json, os, pathlib, re, runpy, shutil, sys
sys.argv = sys.argv[1:]
original = builtins.__import__
def guard(name, *args, **kwargs):
    if name == 'admin' or name.startswith('admin.'):
        raise AssertionError('refused CLI loaded repository runtime')
    return original(name, *args, **kwargs)
builtins.__import__ = guard
{setup}
runpy.run_path(sys.argv[0], run_name='__main__')
"""

ROUTE = """import argparse, builtins, json, os, pathlib, re, runpy, sys, types
sys.argv = sys.argv[1:]
class Rejected(ValueError): pass
for name in ('admin', 'admin.local_hand_quota_observer'):
    package = types.ModuleType(name); package.__path__ = []; sys.modules[name] = package
admission = types.ModuleType('admin.local_hand_quota_observer.admission')
admission.Rejected = Rejected; sys.modules[admission.__name__] = admission
launcher = types.ModuleType('admin.local_hand_quota_observer.launcher')
count = 0
def launch(*args, **kwargs):
    global count
    count += 1
    assert count == 1
    assert args == ({input!r}, 'a'*64, 'b'*40)
    assert kwargs == {{'launcher_path': os.path.abspath(sys.argv[0])}}
    {behavior}
launcher.launch_experiment = launch; sys.modules[launcher.__name__] = launcher
os.getuid = lambda: 0
os.geteuid = lambda: 0
{transport}
runpy.run_path(sys.argv[0], run_name='__main__')
"""


class LaunchCLITests(unittest.TestCase):
    def invoke(self, *, script=None, flags=("-I", "-B"), args=None):
        with tempfile.TemporaryDirectory() as folder:
            prefix = [str(CLI)] if script is None else ["-c", script, str(CLI)]
            return subprocess.run([sys.executable, *flags, *prefix, *(ARGS if args is None else args)],
                                  cwd=folder, capture_output=True, text=True, timeout=10)

    def refusal(self, completed, status, reason, code):
        self.assertEqual(completed.returncode, code, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertLess(len(completed.stdout), 1024)
        output = json.loads(completed.stdout)
        self.assertEqual(output["schema"], "local-hand-quota-q1-launch/v1")
        self.assertEqual((output["status"], output["failure_code"]), (status, reason))
        for field in ("admission_proven", "real_e3_accepted", "production_supported"):
            self.assertFalse(output[field])
        self.assertNotIn(INPUT, completed.stdout)

    def test_required_flags_platform_and_root_refuse_before_runtime_import(self):
        for flags in ((), ("-I",), ("-B",)):
            self.refusal(self.invoke(script=REFUSE.format(setup=""), flags=flags), "REJECTED",
                         "ISOLATED_PYTHON_REQUIRED", 2)
        self.refusal(self.invoke(script=REFUSE.format(setup="sys.platform = 'win32'")),
                     "UNSUPPORTED", "LINUX_REQUIRED", 3)
        self.refusal(self.invoke(script=REFUSE.format(setup="sys.platform = 'linux'\nos.getuid = lambda: 1000\nos.geteuid = lambda: 1000")),
                     "REJECTED", "ADMIN_CONTROLLER_REQUIRED", 2)

    def test_required_arguments_no_abbreviations_or_extra_fields(self):
        for args in ([], ARGS + ["--inp", "ignored"], ARGS + ["--force"]):
            completed = self.invoke(script=REFUSE.format(setup=""), args=args)
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertEqual(completed.stdout, "")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux-only launcher routing")
    def test_fixed_arguments_and_sanitized_rejection_or_io_failure(self):
        for behavior, status, reason, code in (
            ("raise Rejected('CONTROLLER_UNIT_CHANGED')", "REJECTED", "CONTROLLER_UNIT_CHANGED", 2),
            ("raise Rejected('/private/leak')", "REJECTED", "LAUNCH_REJECTED", 2),
            ("raise OSError('/private/leak')", "UNKNOWN", "LAUNCH_IO_OR_EXEC_UNCERTAIN", 4),
            ("raise KeyboardInterrupt()", "UNKNOWN", "LAUNCH_IO_OR_EXEC_UNCERTAIN", 4),
            ("return None", "UNKNOWN", "EXEC_RETURNED", 4),
        ):
            with self.subTest(reason=reason):
                completed = self.invoke(script=ROUTE.format(input=INPUT, behavior=behavior, transport=""))
                self.refusal(completed, status, reason, code)
                self.assertNotIn("/private/leak", completed.stdout + completed.stderr)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux-only launcher output routing")
    def test_short_writes_complete_and_broken_pipe_returns_74_without_second_launch(self):
        transport = "original_write = os.write\nos.write = lambda fd, data: original_write(fd, data[:5])"
        script = ROUTE.format(input=INPUT, behavior="raise OSError('private')", transport=transport)
        self.refusal(self.invoke(script=script), "UNKNOWN", "LAUNCH_IO_OR_EXEC_UNCERTAIN", 4)
        for transport in ("os.write = lambda fd, data: 0", "def fail(fd, data): raise BrokenPipeError()\nos.write = fail"):
            completed = self.invoke(script=ROUTE.format(input=INPUT, behavior="raise OSError('private')", transport=transport))
            self.assertEqual(completed.returncode, 74, completed.stderr)
            self.assertEqual(completed.stdout, "")


if __name__ == "__main__":
    unittest.main()

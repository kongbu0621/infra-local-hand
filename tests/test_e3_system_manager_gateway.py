"""Fixed command/intent models and real pipe EOF, not host qualification."""
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

if sys.platform.startswith("linux"):
    from admin.local_hand_system_manager import server
    from local_hand_jobs import budget, quota_contract as q, runner, result_reader
    from q2_fixtures import BOOT, SECOND, make_grant


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux fixed system gateway")
class GatewayTests(unittest.TestCase):
    def gateway(self):
        # OS admission is intentionally not modeled as a real supported host.
        gateway = server.Gateway.__new__(server.Gateway)
        gateway.binding = dict(schema="local-hand-manager-binding/v1", manager_kind="system", authority_id="fixture",
            boot_id=BOOT, parent=dict(path="/fixture.slice/fixture-ordinary.slice", device=4, inode=81))
        gateway.uid = gateway.gid = 1234
        gateway.configuration = dict(uid=1234, gid=1234, slice="fixture-ordinary.slice",
            cgroup="/sys/fs/cgroup/fixture.slice/fixture-ordinary.slice", manager_binding=gateway.binding)
        gateway.core = runner._SystemdExecutionCore(gateway.configuration)
        gateway.python_path = "/usr/bin/python3"; gateway.runner_path = "/synthetic/installed/runner.py"
        gateway.namespace = "mnt:[123]"
        gateway.programs = {"systemd_run": dict(path="/usr/bin/systemd-run", sha256="e" * 64)}
        gateway.lock = threading.RLock(); gateway.closed = False; gateway.failure = None
        gateway.parts = {}; gateway.phases = {}; gateway.closed_phases = []
        gateway.channel = SimpleNamespace(session_id="a" * 64)
        gateway.end = 50 * SECOND
        gateway._time = lambda: 2 * SECOND
        gateway._parent = mock.Mock(return_value=gateway.binding["parent"])
        grant = make_grant(); data = grant.as_dict()
        plan = dict(phase="preflight", execution_id=data["budget"]["execution_id"],
            budget_grant=data["budget"], budgets=data["budget"]["limits"], bootstrap_allocation=data["allocation"],
            supervision_version=3, quota_observation_grant=data, manager_binding=gateway.binding,
            execution=dict(python=gateway.python_path, kind="host.inspect", operation_id=data["budget"]["operation_id"],
                roots=data["allocation"]["source_roots"], readonly=[], storage={}, stages=[]))
        execution = runner._quota_prepared_execution(plan, parent_mount_namespace=gateway.namespace, now_ns=2 * SECOND)
        item = dict(execution=execution, grant=grant, plan=plan)
        gateway.phases["preflight"] = item
        self.clock = mock.patch.object(budget, "current_clock", return_value=dict(boot_id=BOOT, boottime_ns=2 * SECOND))
        self.clock.start(); self.addCleanup(self.clock.stop)
        return gateway, item

    def test_commands_rebuilt_from_exact_grant_and_predecessor_no_input_argv(self):
        gateway, item = self.gateway()
        execution = item["execution"]
        unit, properties, argv = gateway._build(item, "bootstrap")
        self.assertIn("--system", argv); self.assertNotIn("--user", argv)
        self.assertEqual("1234", properties["User"])
        self.assertEqual("1234", properties["Group"])
        for key in ("PrivateUsers", "PrivateNetwork", "PrivateMounts", "PrivateDevices", "NoNewPrivileges"):
            self.assertEqual("yes", properties[key])
        self.assertEqual("", properties["CapabilityBoundingSet"])
        self.assertIn("/run/user/1234", properties["InaccessiblePaths"])
        self.assertNotIn("/run/user/0", properties["InaccessiblePaths"])
        payload = argv[argv.index("--") + 1:]
        self.assertEqual(runner.quota_bootstrap_argv(execution, item["grant"], script=gateway.runner_path,
                                                   now_ns=2 * SECOND), payload)
        helper_unit = server._unit(execution["execution_id"], "helper")
        gateway.parts["preflight", "helper"] = dict(unit=helper_unit, invocation_id="b" * 32,
                                                     terminal=dict(ExecMainStatus="7"))
        reader_unit, _, argv = gateway._build(item, "result_reader")
        decoded = result_reader.decode_payload(argv[-1])
        self.assertEqual("b" * 32, decoded["helper_identity"]["invocation_id"])
        self.assertEqual(7, decoded["helper_identity"]["exit_code"])
        self.assertEqual(reader_unit, decoded["reader_unit"])
        result_reader._validate_payload(decoded)

    def test_extra_argv_and_wrong_or_future_refs_never_reach_command(self):
        gateway, item = self.gateway(); gateway._command = mock.Mock()
        valid = dict(execution_id=item["execution"]["execution_id"], phase="preflight", stage="bootstrap")
        for body in (dict(ref=valid, bindings={}, argv=["forbidden"]),
                     dict(ref=dict(valid, phase="business"), bindings=dict(allocation_digest="c" * 64, grant_digest="d" * 64))):
            with self.assertRaises(q.QuotaError): gateway.dispatch("launch", body)
        gateway._command.assert_not_called()

    def test_real_pipe_eof_requires_writer_exit_and_every_original_byte_drained(self):
        read, write = os.pipe(); duplicate = os.dup(read)
        try:
            self.assertFalse(server._drained(read))
            os.write(write, b"retained output")
            self.assertFalse(server._drained(read))
            os.close(write); write = -1
            self.assertFalse(server._drained(read))
            self.assertEqual(b"retained output", os.read(duplicate, 4096))
            self.assertTrue(server._drained(read))
            self.assertEqual(b"", os.read(duplicate, 1))
        finally:
            os.close(read); os.close(duplicate)
            if write >= 0: os.close(write)

    def test_create_only_intent_survives_popen_failure_and_forbids_second_delivery(self):
        gateway, item = self.gateway()
        with tempfile.TemporaryDirectory() as directory:
            gateway.directory = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                gateway._predecessor = mock.Mock()
                unit = server._unit(item["execution"]["execution_id"], "bootstrap")
                gateway._command = mock.Mock(return_value=dict(returncode=0, stdout=f"Id={unit}\nLoadState=not-found\nJob=\n", stderr=""))
                body = dict(ref=dict(execution_id=item["execution"]["execution_id"], phase="preflight", stage="bootstrap"),
                    bindings=dict(allocation_digest=item["execution"]["bootstrap_allocation"]["grant_digest"], grant_digest=item["grant"].digest))
                with mock.patch.object(server.subprocess, "Popen", side_effect=OSError("delivery outcome unknown")) as launch:
                    with self.assertRaises(OSError): gateway._launch(body)
                    with self.assertRaisesRegex(q.QuotaError, "SYSTEM_DELIVERY_REPLAY"): gateway._launch(body)
                    self.assertEqual(1, launch.call_count)
                files = list(Path(directory).iterdir()); self.assertEqual(1, len(files))
                self.assertLess(files[0].stat().st_size, 8192)
                self.assertNotIn(b"argv", files[0].read_bytes())
                self.assertIn(b"command_template_digest", files[0].read_bytes())
            finally:
                os.close(gateway.directory)

    def test_unknown_inventory_and_unsealed_predecessor_fail_closed(self):
        gateway, item = self.gateway()
        gateway._command = mock.Mock(return_value=dict(returncode=0,
            stdout="lhj-" + "f" * 64 + ".service loaded failed failed unknown\n", stderr=""))
        with self.assertRaisesRegex(q.QuotaError, "SYSTEM_INVENTORY_UNKNOWN"):
            gateway.dispatch("inventory", {})
        gateway._journal = mock.Mock(return_value=dict(status="RESULT"))
        with self.assertRaisesRegex(q.QuotaError, "SYSTEM_PREDECESSOR_UNSEALED"):
            gateway._predecessor("preflight", "helper")

    def test_actual_root_client_and_two_pipe_eofs_are_required_for_seal(self):
        gateway, item = self.gateway()
        process = subprocess.Popen([sys.executable, "-c", "import sys;sys.stdout.write('out');sys.stderr.write('err')"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            process.wait(timeout=3)
            terminal = dict(ExecMainCode="1", ExecMainStatus="0")
            part = dict(sealed=False, stop_ok=True, invocation_id="b" * 32, terminal=terminal,
                        process=process, pidfd=os.pidfd_open(os.getpid(), 0))
            after = dict(ActiveState="inactive", Job="")
            gateway._show = mock.Mock(return_value=({}, after))
            with self.assertRaisesRegex(q.QuotaError, "SYSTEM_CLIENT_EOF_UNPROVEN"): gateway._seal(part)
            self.assertFalse(part["sealed"])
            self.assertEqual(b"out", process.stdout.read()); self.assertEqual(b"err", process.stderr.read())
            gateway._seal(part)
            self.assertTrue(part["sealed"])
            self.assertTrue(process.stdout.closed and process.stderr.closed)
        finally:
            process.stdout.close(); process.stderr.close()
            if part["pidfd"] >= 0: os.close(part["pidfd"])

    def test_finite_native_duration_rendering(self):
        self.assertEqual(23999999, server._usec("23.999999s"))
        self.assertEqual(1000, server._usec("1ms"))
        for bad in ("infinity", "23", "1.0000001s", "1s 1min"):
            with self.assertRaises(ValueError): server._usec(bad)

    def test_native_generated_cpu_percent_preserves_omitted_fraction_digits(self):
        for cpu, wall, text, expected in ((1, 10, "10%", 100000), (3, 24, "12.5%", 125000),
                                         (1234, 10000, "12.34%", 123400), (1, 1, "100%", 1000000)):
            actual = runner._cpu_quota(dict(cpu_seconds=cpu, wall_seconds=wall))
            self.assertEqual(text, actual)
            self.assertEqual(expected, server._quota_usec(actual))

    def test_management_output_counts_overflow_byte_even_when_buffer_is_capped(self):
        cap = server._ControlCapture(4)
        cap.start([sys.executable, "-c", "import os;os.write(1,b'12345')"])
        try:
            cap.process.wait(timeout=3)
            cap.pump()
            self.assertEqual(5, cap.received)
            self.assertEqual(4, len(cap.stdout))
            self.assertEqual("SYSTEM_CONTROL_BYTE_LIMIT", cap.error)
            self.assertFalse(cap.done)
        finally:
            cap.close_pipes()

    def test_loaded_unit_checks_native_rate_identity_parent_and_zero_capabilities(self):
        gateway, item = self.gateway()
        unit, properties, _ = gateway._build(item, "bootstrap")
        values = dict.fromkeys(server._ALL_FIELDS, "")
        values.update({key: properties[key] for key in server._EXTRA_FIELDS if key in properties})
        values.update(Id=unit, LoadState="loaded", ActiveState="active", SubState="running",
            ControlGroup=gateway.binding["parent"]["path"] + "/" + unit, InvocationID="a" * 32,
            Job="", Restart="no", KillMode="control-group", Type="exec", ExitType="cgroup", RemainAfterExit="yes",
            RestrictNamespaces="yes", CPUQuotaPerSecUSec="100ms", CPUQuotaPeriodUSec="1ms",
            RuntimeMaxUSec=properties["RuntimeMaxSec"], TimeoutStopUSec="1s")
        part = dict(unit=unit, properties=properties, boot_id=BOOT, quota_parent=gateway.binding["parent"],
                    invocation_id=None, stop_ok=False)
        def observe(data):
            gateway._command = mock.Mock(return_value=dict(returncode=0, stderr="",
                stdout="".join(key + "=" + value + "\n" for key, value in data.items())))
            return gateway._show(part)
        observe(values)
        self.assertEqual("a" * 32, part["invocation_id"])
        observe(dict(values, ReadWritePaths=" ".join('"' + path + '"' for path in properties["ReadWritePaths"].split())))
        for key, value in (("CapabilityBoundingSet", "cap_sys_admin"), ("User", "0"),
                           ("InvocationID", "b" * 32), ("ControlGroup", ""), ("CPUQuotaPerSecUSec", "10ms"),
                           ("ReadWritePaths", "/"), ("InaccessiblePaths", ""), ("ReadOnlyPaths", "/extra"),
                           ("SendSIGKILL", "no"), ("RestrictNamespaces", "true")):
            with self.subTest(key=key), self.assertRaises(q.QuotaError): observe(dict(values, **{key: value}))

    def test_runtime_shrinks_after_intent_io_and_expiry_never_delivers(self):
        for late_ns in (6 * SECOND, 12 * SECOND):
            with self.subTest(late_ns=late_ns):
                gateway, item = self.gateway()
                unit, props, _ = gateway._build(item, "bootstrap")
                original_runtime = int(props["RuntimeMaxSec"][:-2])
                gateway._predecessor = mock.Mock()
                gateway._command = mock.Mock(return_value=dict(returncode=0,
                    stdout=f"Id={unit}\nLoadState=not-found\nJob=\n", stderr=""))
                intents = []
                def persist(phase, stage, value):
                    intents.append(value)
                    self.clock.target.current_clock.return_value = dict(boot_id=BOOT, boottime_ns=late_ns)
                    gateway._time = lambda: late_ns
                gateway._intent = persist
                body = dict(ref=dict(execution_id=item["execution"]["execution_id"], phase="preflight", stage="bootstrap"),
                    bindings=dict(allocation_digest=item["execution"]["bootstrap_allocation"]["grant_digest"],
                                  grant_digest=item["grant"].digest))
                with mock.patch.object(server.subprocess, "Popen", side_effect=OSError("modeled delivery uncertainty")) as launch:
                    with self.assertRaises(Exception): gateway._launch(body)
                    self.assertEqual(1, len(intents))
                    self.assertEqual(item["execution"]["phase_deadline_boottime_ns"], intents[0]["deadline_ns"])
                    if late_ns == 6 * SECOND:
                        argv = launch.call_args.args[0]
                        runtime = next(arg for arg in argv if arg.startswith("--property=RuntimeMaxSec="))
                        self.assertLess(int(runtime.split("=")[-1][:-2]), original_runtime)
                    else:
                        launch.assert_not_called()

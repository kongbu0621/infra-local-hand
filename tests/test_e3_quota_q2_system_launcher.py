"""System launch integration: modeled services, real socket FDs/files/threads.

The old phase driver supplies genuine grant/config contracts. Gateway authority
and child execution remain explicit models; these checks grant no host readiness.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

import test_e3_quota_q2_launcher_chain as chain_tests
from test_local_hand_jobs_quota_resident import resident

launcher = chain_tests.launcher
if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import q2_config
    from admin.local_hand_system_manager import server
    from local_hand_jobs import system_manager, system_manager_protocol
    from q2_fixtures import BOOT
    from test_e3_quota_q2_prepare_assembly import a, system_facts


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux inherited channels and original phase contracts")
class SystemLauncherOrderingTests(unittest.TestCase):
    setUp = chain_tests.ChainLauncherTests.setUp

    def configure(self):
        self.value["schema"] = launcher.SYSTEM_SCHEMA
        ordinary = self.value["resident"]["ordinary"]
        ordinary["manager_binding"] = dict(schema="local-hand-manager-binding/v1", manager_kind="system",
            authority_id="modeled-authority", boot_id=BOOT, parent=copy.deepcopy(ordinary["parent"]))
        self.value["resident"]["schema"] = resident.SYSTEM_SCHEMA
        self.gateway_closed = threading.Event()
        self.gateway_fault = None
        self.spawn_pins = None
        self.channel_arguments = None
        self.gateway_arguments = None

    def on_spawn(self, argv, options):
        # Observe actual descriptors and the bytes persisted before the spawn.
        self.spawn_pins = json.loads((self.root / "declarations/resident.json").read_bytes())
        expected = (self.spawn_pins["bridge"]["fd"], self.spawn_pins["manager_channel"]["fd"])
        self.assertEqual(expected, options["pass_fds"])
        self.assertEqual(2, len(set(expected)))
        for fd in expected:
            with socket.socket(fileno=os.dup(fd)) as inherited:
                self.assertEqual(socket.SOCK_SEQPACKET, inherited.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE))
                self.assertEqual(1, inherited.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED))

    def invoke(self):
        test = self
        class ManagerChannel:
            def __init__(self, sock, **kwargs):
                test.events.append(("manager_channel", test.phase))
                test.channel_arguments = kwargs
                self.sock = sock
            def close(self): self.sock.close()
        class Gateway:
            failure = None
            def __init__(self, channel, **kwargs):
                test.events.append(("gateway", test.phase))
                test.gateway_arguments = kwargs
                test.assertEqual(test.value["resident"]["ordinary"]["manager_binding"], kwargs["manager_binding"])
            def serve(self): test.gateway_closed.wait(3)
            def authorize_phase(self, plan, execution, grant, config):
                phase = grant.request.as_dict()["phase"]
                test.events.append(("authorize", phase))
                test.assertEqual(config.active().as_dict(), grant.as_dict())
                if test.gateway_fault == ("authorize", phase): raise ValueError("MODELED_MANAGER_AUTHORITY")
            def close_phase(self, fence):
                phase = fence["phase"]
                test.events.append(("manager_seal", phase))
                test.assertEqual(test.closed[phase], fence)
                if test.gateway_fault == ("seal", phase): raise ValueError("MODELED_MANAGER_SEAL_UNKNOWN")
            def close(self):
                test.events.append(("manager_close", test.phase))
                test.gateway_closed.set()
            def snapshot(self):
                return dict(schema="explicitly-modeled-gateway-diagnostic", closed=test.gateway_closed.is_set())
        with mock.patch.object(system_manager_protocol, "Channel", ManagerChannel), \
             mock.patch.object(server, "Gateway", Gateway):
            return chain_tests.ChainLauncherTests.invoke(self)

    def test_two_channels_precede_resident_and_each_authorization_precedes_phase(self):
        self.configure()
        result = self.invoke()
        self.assertEqual("CHAIN_CLOSED", result["status"])
        self.assertEqual("local-hand-q2-system-launcher-result/v1", result["schema"])
        bridge = self.spawn_pins["bridge"]; manager = self.spawn_pins["manager_channel"]
        for key in ("pid", "uid", "gid", "start_ticks", "boot_id", "deadline_ns"):
            self.assertEqual(bridge[key], manager[key])
        self.assertEqual(hashlib.sha256((self.value["session"] + ":system-manager").encode("ascii")).hexdigest(),
                         manager["session"])
        self.assertEqual((os.getpid(), 1234, 1234), self.channel_arguments["peer"])
        self.assertEqual(77, self.channel_arguments["peer_start_ticks"])
        self.assertEqual(self.value["controller_envelope"]["deadline_ns"], self.gateway_arguments["deadline_ns"])
        self.assertEqual(1, sum(name == "spawn" for name, _ in self.events))
        for phase in chain_tests.PHASES:
            order = [self.events.index((name, phase)) for name in ("install", "authorize", "phase", "manager_seal", "record_close")]
            self.assertEqual(sorted(order), order)
        self.assertLess(self.events.index(("manager_close", "evidence")), self.events.index(("finish", "evidence")))
        self.assertFalse(result["q3_accepted"]); self.assertFalse(result["production_supported"])

    def test_unknown_manager_seal_retains_evidence_without_advancing(self):
        self.configure(); self.gateway_fault = ("seal", "preflight")
        result = self.invoke()
        self.assertEqual("INCOMPLETE", result["status"])
        self.assertEqual("MODELED_MANAGER_SEAL_UNKNOWN", result["reason"])
        self.assertFalse(any(name in ("advance", "finish") for name, _ in self.events))
        self.assertNotIn(("grant", "business"), self.events)
        self.assertTrue((self.root / "output/reservation.json").is_file())
        self.assertEqual(1, sum(name == "spawn" for name, _ in self.events))

    def test_refused_second_authority_never_starts_second_coordinator(self):
        self.configure(); self.gateway_fault = ("authorize", "business")
        result = self.invoke()
        self.assertEqual("MODELED_MANAGER_AUTHORITY", result["reason"])
        self.assertEqual(["preflight"], [phase for name, phase in self.events if name == "phase"])
        self.assertFalse(any(name == "finish" for name, _ in self.events))
        self.assertNotIn(("grant", "evidence"), self.events)


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux read-only parent pseudo-file boundaries")
class SystemParentAdmissionTests(unittest.TestCase):
    def setUp(self):
        fixture = a.assemble(system_facts())
        self.value = fixture["launcher"]
        self.spec = SimpleNamespace(**self.value["controller_envelope"]["controller"])
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.directories = {}; self.owners = {}
        for role, record in self.value["system_geometry"].items():
            if role == "schema": continue
            path = self.root / role; path.mkdir(mode=0o700)
            for name, content in (("memory.max", str(record["memory_bytes"])), ("memory.swap.max", "0"),
                                  ("pids.max", str(record["tasks_max"])), ("cpu.max", "100000 100000")):
                (path / name).write_text(content + "\n")
            self.directories["/sys/fs/cgroup" + record["parent"]["path"]] = path
            info = path.stat()
            self.owners[info.st_ino] = self.value["resident"]["ordinary"]["uid"] if role == "retained_ordinary_parent" else 0

    def admit(self):
        original = os.fstat
        def ownership(fd):
            info = original(fd)
            return SimpleNamespace(st_uid=self.owners.get(info.st_ino, info.st_uid), st_mode=info.st_mode)
        def pinned(pin):
            return os.open(self.directories[pin["path"]], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        with mock.patch.object(q2_config, "pinned_directory", side_effect=pinned), \
             mock.patch.object(launcher.os, "fstat", side_effect=ownership):
            launcher.system_parent_admission(self.value, self.spec, BOOT)

    def test_exact_declared_limits_are_checked_against_real_finite_file_reads(self):
        self.admit()

    def test_declared_limits_and_live_unbounded_or_reduced_parent_are_rejected(self):
        file = self.root / "ordinary_parent/memory.max"
        for content in ("max\n", str(512 * 1024**2), "x" * 257):
            file.write_text(content)
            with self.subTest(content=content[:20]), self.assertRaises(ValueError): self.admit()
        file.write_text(str(256 * 1024**2))
        (self.root / "ordinary_parent/cpu.max").write_text("50000 100000\n")
        with self.assertRaisesRegex(ValueError, "LAUNCHER_SYSTEM_PARENT_LIMITS"): self.admit()

    def test_parent_owner_and_sibling_geometry_cannot_be_substituted(self):
        ordinary = self.value["resident"]["ordinary"]
        inode = (self.root / "ordinary_parent").stat().st_ino
        self.owners[inode] = ordinary["uid"]
        with self.assertRaisesRegex(ValueError, "LAUNCHER_SYSTEM_PARENT_OWNER"): self.admit()
        self.owners[inode] = 0
        self.spec.cgroup = ordinary["parent"]["path"] + "/wrong.service"
        with self.assertRaisesRegex(ValueError, "LAUNCHER_SYSTEM_GEOMETRY"): self.admit()

    def test_symlink_and_fifo_limit_sources_never_block_or_pass(self):
        file = self.root / "ordinary_parent/pids.max"; file.unlink()
        file.symlink_to(self.root / "controller_parent/pids.max")
        with self.assertRaises(OSError): self.admit()
        file.unlink(); os.mkfifo(file)
        with self.assertRaises(ValueError): self.admit()


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux resident system channel binding")
class SystemResidentChannelTests(unittest.TestCase):
    def setUp(self):
        self.pin = dict(fd=71, pid=333, uid=0, gid=0, start_ticks=91, session="a" * 64,
                        boot_id=BOOT, deadline_ns=1000000000)
        self.value = dict(schema=resident.SYSTEM_SCHEMA, bridge=copy.deepcopy(self.pin),
                          manager_channel=dict(self.pin, fd=72, session="b" * 64))

    def invoke(self, *, manager_failure=False):
        events = []
        quota = mock.Mock(); manager = mock.Mock(); broker = mock.Mock()
        def manager_from_pin(pin):
            events.append("manager")
            if manager_failure: raise ValueError("SYSTEM_PEER_CHANGED")
            return manager
        def compose(value, **kwargs):
            self.assertIs(manager, kwargs["manager_channel"]); events.append("compose"); return broker
        result = dict(schema="local-hand-q2-system-resident-result/v1", status="CHAIN_CLOSED",
                      q3_accepted=False, production_supported=False)
        with mock.patch.object(resident, "bootstrap", return_value=self.value), \
             mock.patch.object(resident, "channel_from_pin", return_value=quota), \
             mock.patch.object(system_manager, "channel_from_pin", side_effect=manager_from_pin), \
             mock.patch.object(resident, "compose", side_effect=compose), \
             mock.patch.object(resident, "run", side_effect=lambda *_: events.append("run") or result), \
             mock.patch("local_hand_jobs.cli.close_service") as close, \
             mock.patch.object(resident.os, "write") as write:
            code = resident.main(["--fixture", "/protected/resident.json", "--sha256", "a" * 64])
        return code, json.loads(write.call_args.args[1]), events, close, quota, manager

    def test_manager_channel_is_admitted_before_broker_composition_and_closed_afterward(self):
        code, result, events, close, quota, manager = self.invoke()
        self.assertEqual(0, code); self.assertEqual(["manager", "compose", "run"], events)
        self.assertEqual("local-hand-q2-system-resident-result/v1", result["schema"])
        self.assertFalse(close.call_args.kwargs["failed"])
        quota.close.assert_called_once(); manager.close.assert_called_once()

    def test_channel_alias_and_cross_controller_metadata_refuse_before_composition(self):
        original = copy.deepcopy(self.value)
        for name, changed in (("fd", 71), ("pid", 334), ("uid", 1), ("gid", 1), ("start_ticks", 92),
                              ("boot_id", "wrong"), ("deadline_ns", self.pin["deadline_ns"] + 1)):
            self.value = copy.deepcopy(original); self.value["manager_channel"][name] = changed
            code, result, events, close, _, _ = self.invoke()
            self.assertEqual(3, code); self.assertEqual([], events); close.assert_not_called()
            self.assertIn(result["reason"], ("RESIDENT_CHANNEL_ALIAS", "RESIDENT_SYSTEM_PEER_BINDING"))

    def test_actual_manager_admission_error_never_constructs_broker(self):
        code, result, events, close, _, _ = self.invoke(manager_failure=True)
        self.assertEqual(3, code); self.assertEqual(["manager"], events)
        self.assertEqual("SYSTEM_PEER_CHANGED", result["reason"]); close.assert_not_called()


@unittest.skipUnless(sys.platform.startswith("linux"), "Explicit system fixture versions")
class SystemFixtureVersionTests(unittest.TestCase):
    def test_launcher_version_requires_geometry_and_old_version_rejects_it(self):
        fixture = a.assemble(system_facts())["launcher"]
        raw = launcher.encoded(fixture, launcher.LIMIT)
        self.assertEqual(fixture, launcher.decode(raw, hashlib.sha256(raw).hexdigest()))
        for mutate in (lambda x: x.pop("system_geometry"),
                       lambda x: x.update(schema=launcher.CHAIN_SCHEMA),
                       lambda x: x.update(purpose="ISOLATED_Q2_PREFLIGHT")):
            candidate = copy.deepcopy(fixture); mutate(candidate)
            raw = launcher.encoded(candidate, launcher.LIMIT)
            with self.assertRaisesRegex(ValueError, "LAUNCHER_SCHEMA"):
                launcher.decode(raw, hashlib.sha256(raw).hexdigest())

    def test_resident_channel_cannot_be_added_to_old_fixture_or_omitted_from_new(self):
        fixture = a.assemble(system_facts())["resident"]
        fixture["bridge"] = {}
        for kind in ("missing", "legacy"):
            candidate = copy.deepcopy(fixture)
            if kind == "legacy":
                candidate["schema"] = resident.CHAIN_SCHEMA
                candidate["manager_channel"] = {}
            raw = json.dumps(candidate).encode()
            with mock.patch.object(resident.sys, "flags", SimpleNamespace(isolated=1)), \
                 mock.patch.object(resident.sys, "dont_write_bytecode", True), \
                 mock.patch.object(resident, "protected", return_value=raw) as read:
                with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "RESIDENT_SCHEMA"):
                    resident.bootstrap("/protected/fixture", hashlib.sha256(raw).hexdigest())
                read.assert_called_once_with("/protected/fixture", resident.LIMIT)


if __name__ == "__main__": unittest.main()

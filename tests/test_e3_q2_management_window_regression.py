"""Synthetic protected 8/7/5-second input under the unchanged Q2 contracts.

These checks exercise the original decoders, command builder and listener loop.
Process identity, sockets, clocks and cgroup files are modeled where indicated;
no guest, systemd unit, quota query or normal-chain success is claimed.
"""
import os
import sys
import unittest
from unittest import mock

from local_hand_jobs import budget, quota_contract as q, quota_grant as g
from q2_fixtures import SECOND

if sys.platform.startswith("linux"):
    from admin.local_hand_quota_observer import q2_listener as listener, q2_runtime as runtime
    from test_e3_quota_q2_runtime import config, declaration


def protected_input(*, legacy=False, issued_lag_ns=SECOND // 10):
    value = declaration()
    grant = next(iter(value["grants"].values()))
    phase = grant["budget"]
    phase["limits"].update(wall_seconds=24, terminate_grace_seconds=1,
        cpu_seconds=10, memory_bytes=64 * 1024**2, processes=8,
        log_bytes=32768, reservation_bytes=8 * 1024**2)
    original = dict(phase["limits"])
    for key in ("wall_seconds", "cpu_seconds", "log_bytes"):
        original[key] *= 3
    phase["budget_digest"] = g.digest(original)
    phase["deadline_boottime_ns"] = phase["started_boottime_ns"] + original["wall_seconds"] * SECOND
    grant["request"]["deadline_ns"] = budget.phase_deadline_ns(phase) - SECOND
    value["service"]["end_ns"] = grant["request"]["deadline_ns"]
    management = grant["management"]
    management.update(issued_ns=phase["reserved_boottime_ns"] + issued_lag_ns,
                      receive_ns=SECOND, stop_ns=SECOND)
    seconds = dict(collector=3, admission=3, query=6) if legacy else dict(collector=8, admission=7, query=5)
    for name, stage in management["stages"].items():
        stage.update(runtime_ns=seconds[name] * SECOND, cpu_ns=2 * SECOND,
                     memory_bytes=64 * 1024**2, pids=8, output_bytes=32768)
    return value


def command_properties(cfg, role, now_ns):
    return {item.split("=", 2)[1]: item.split("=", 2)[2]
            for item in runtime.command(cfg, role, now_ns=now_ns)
            if item.startswith("--property=")}


def duration_ns(text):
    assert text.endswith("us")
    return int(text[:-2]) * 1000


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux administrative runtime")
class ManagementWindowRegressionTests(unittest.TestCase):
    def test_original_decoder_keeps_budget_and_resource_totals(self):
        old = config(protected_input(legacy=True)).active()
        new = config(protected_input()).active()
        self.assertEqual(new, g.decode_grant(new.wire))
        self.assertEqual(old.as_dict()["budget"], new.as_dict()["budget"])
        self.assertEqual(g.totals(old), g.totals(new))
        data = new.as_dict()
        management = data["management"]
        wall = sum(stage["runtime_ns"] for stage in management["stages"].values())
        total = wall + management["receive_ns"] + management["stop_ns"]
        phase_available = data["request"]["deadline_ns"] - data["budget"]["reserved_boottime_ns"]
        self.assertEqual(22 * SECOND, total)
        self.assertEqual(23 * SECOND, phase_available)
        self.assertLess(total, phase_available)
        self.assertLessEqual(management["issued_ns"] + total, data["request"]["deadline_ns"])

    def test_each_original_command_keeps_its_own_stop_and_resource_caps(self):
        cfg = config(protected_input())
        issued = cfg.active().as_dict()["management"]["issued_ns"]
        expected = dict(listener=(7, 22), admission=(6, 25), query=(4, 33))
        for role, (active_seconds, percent) in expected.items():
            with self.subTest(role=role):
                values = command_properties(cfg, role, issued)
                active, stop = duration_ns(values["RuntimeMaxSec"]), duration_ns(values["TimeoutStopSec"])
                self.assertEqual(active_seconds * SECOND, active)
                self.assertEqual(SECOND, stop)
                self.assertLessEqual(active + stop, runtime.limits(cfg, role)["runtime_ns"])
                self.assertEqual(str(percent) + "%", values["CPUQuota"])
                self.assertEqual("2", values["LimitCPU"])
                self.assertEqual(str(64 * 1024**2), values["MemoryMax"])
                self.assertEqual("8", values["TasksMax"])
                self.assertEqual("no", values["Restart"])

    def test_two_point_two_seconds_exceeds_only_the_old_listener_active_window(self):
        elapsed = 2_200_000_000  # Relative timing only; no host IDs or evidence are embedded.
        for legacy in (True, False):
            cfg = config(protected_input(legacy=legacy))
            issued = cfg.active().as_dict()["management"]["issued_ns"]
            values = command_properties(cfg, "listener", issued)
            with self.subTest(legacy=legacy):
                self.assertEqual(legacy, elapsed >= duration_ns(values["RuntimeMaxSec"]))
                self.assertLess(elapsed, runtime.limits(cfg, "listener")["runtime_ns"])

    def test_original_listener_loop_uses_the_longer_protected_collector_window(self):
        class ReachedHotLoop(Exception):
            pass

        for legacy in (True, False):
            cfg = config(protected_input(legacy=legacy))
            start = cfg.active().as_dict()["management"]["issued_ns"] + SECOND
            # At 3.2 seconds, the old Python loop itself has expired as well.
            # Fake sockets/attestation isolate the original loop's clock checks.
            late = start + 3_200_000_000
            private, endpoint, control = mock.Mock(), mock.Mock(), mock.Mock()
            private.accept.return_value = (control, None)
            with self.subTest(legacy=legacy), \
                 mock.patch.object(runtime, "host"), \
                 mock.patch.object(listener, "bind", side_effect=[private, endpoint]), \
                 mock.patch.object(listener.peer, "control"), \
                 mock.patch.object(listener, "boottime_ns", side_effect=[start, start, start, late, late]), \
                 mock.patch.object(listener.select, "select", side_effect=[([private], [], []), ReachedHotLoop]):
                if legacy:
                    with self.assertRaisesRegex(q.QuotaError, "^LISTENER_DEADLINE$"):
                        listener.listener(cfg)
                else:
                    with self.assertRaises(ReachedHotLoop):
                        listener.listener(cfg)
                private.close.assert_called_once()
                endpoint.close.assert_called_once()
                control.close.assert_called_once()

    def test_issued_later_than_one_second_is_still_rejected(self):
        # The exact equality is valid; one nanosecond later cannot renew the phase.
        config(protected_input(issued_lag_ns=SECOND))
        value = protected_input(issued_lag_ns=SECOND + 1)
        grant = next(iter(value["grants"].values()))
        with self.assertRaisesRegex(q.QuotaError, "^MANAGEMENT_DEADLINE$"):
            g.decode_grant(q._canonical(grant, g.GRANT_LIMIT))
        with self.assertRaisesRegex(q.QuotaError, "^MANAGEMENT_DEADLINE$"):
            config(value)

    def test_expired_request_or_missing_stop_grace_cannot_start_a_stage(self):
        cfg = config(protected_input())
        for role in ("listener", "admission", "query"):
            end = runtime.deadline(cfg, role)
            for now in (end - SECOND, end, end + 1):
                with self.subTest(role=role, now=now), \
                     self.assertRaisesRegex(q.QuotaError, "^RUNTIME_DEADLINE$"):
                    runtime.command(cfg, role, now_ns=now)

    def check_modeled_cpu_host(self, cfg, role, period_us, quota_us):
        """Actual host validator; OS identity/cgroup reads are explicitly modeled."""
        stage = runtime.limits(cfg, role)
        grant = cfg.active().as_dict()
        mask = 1 if role == "listener" else (1 << 2) | (1 << 19)
        status = "".join(name + ": " + format(value, "016x") + "\n" for name, value in
            dict(CapInh=0, CapAmb=0, CapPrm=mask, CapEff=mask, CapBnd=mask).items()) + "NoNewPrivs: 1\n"

        def read(path, maximum):
            if path.endswith("/cpu.max"):
                return f"{quota_us} {period_us}\n".encode()
            if path.endswith("/memory.max"):
                return str(stage["memory_bytes"]).encode()
            if path.endswith("/memory.swap.max"):
                return b"0"
            if path.endswith("/pids.max"):
                return str(stage["pids"]).encode()
            self.assertEqual("/proc/self/status", path)
            return status.encode()

        group = runtime.parent(cfg, role)["path"] + "/" + runtime.name(cfg, role)
        with mock.patch.object(runtime.os, "getuid", return_value=0), \
             mock.patch.object(runtime.os, "geteuid", return_value=0), \
             mock.patch.dict(os.environ, INVOCATION_ID="a" * 32), \
             mock.patch.object(runtime, "_boot_id", return_value=grant["request"]["boot_id"]), \
             mock.patch.object(runtime.c, "initial_namespace"), \
             mock.patch.object(runtime.c, "pinned_directory", side_effect=lambda pin: os.open("/", os.O_RDONLY | os.O_DIRECTORY)), \
             mock.patch.object(runtime, "_own_cgroup", return_value=group), \
             mock.patch.object(runtime, "boottime_ns", return_value=grant["management"]["issued_ns"]), \
             mock.patch.object(runtime, "_fixed_read", side_effect=read), \
             mock.patch.object(runtime.worker, "parse_status"):
            return runtime.host(cfg, role)

    def test_original_cpu_validator_keeps_two_second_caps_after_period_clamping(self):
        cfg = config(protected_input())
        issued = cfg.active().as_dict()["management"]["issued_ns"]
        for role in ("listener", "admission", "query"):
            stage = runtime.limits(cfg, role)
            percent = int(command_properties(cfg, role, issued)["CPUQuota"][:-1])
            # Model the requested ratio, not a claim about a particular kernel's
            # period selection. Cover every integer period from 2 through 1000ms.
            for period_ms in range(2, 1001):
                period_us = period_ms * 1000
                quota_us = percent * period_us // 100
                self.assertLessEqual(quota_us * (stage["runtime_ns"] + period_us * 1000),
                                     period_us * 2 * SECOND)
            for period_us in (2000, 5000, 100000, 1_000_000):
                with self.subTest(role=role, period_us=period_us):
                    self.check_modeled_cpu_host(cfg, role, period_us, percent * period_us // 100)
            period_us = 1_000_000
            excessive = stage["cpu_ns"] * period_us // (stage["runtime_ns"] + period_us * 1000) + 1
            with self.subTest(role=role, fault="excessive CPU"), \
                 self.assertRaisesRegex(q.QuotaError, "^RUNTIME_CPU$"):
                self.check_modeled_cpu_host(cfg, role, period_us, excessive)
            with self.subTest(role=role, fault="period above original maximum"), \
                 self.assertRaisesRegex(q.QuotaError, "^RUNTIME_CPU$"):
                self.check_modeled_cpu_host(cfg, role, 1_000_001, percent * 1_000_001 // 100)


if __name__ == "__main__":
    unittest.main()

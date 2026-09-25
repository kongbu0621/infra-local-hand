"""Pure chain capacity admission, with host reads and side effects forbidden.

The real chain decoder and launcher accounting run here. No host controller,
systemd service, resident or quota observation is admitted by these tests.
"""
import contextlib
import copy
import sys
import unittest
from unittest import mock

if sys.platform.startswith("linux"):
    from local_hand_jobs import budget, quota_grant as g
    from admin.local_hand_quota_observer import q2_chain as chain
    from test_e3_quota_controller_guard import controller_value
    from test_e3_quota_q2_chain import PHASES, clock, declaration_chain, decoded
    from test_e3_quota_q2_launcher import launcher
    from q2_fixtures import SECOND


class HostBoundary(Exception):
    """Stop an otherwise admitted accounting check before any host fact read."""


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux administrative chain")
class PrechargeTests(unittest.TestCase):
    def setUp(self):
        self.value, unused = declaration_chain()
        controller = controller_value()
        controller["runtime_max_usec"] = 50_000_000
        self.launch = {
            "schema": launcher.CHAIN_SCHEMA,
            "controller_envelope": {
                "controller": controller, "issued_ns": SECOND,
                "deadline_ns": 51 * SECOND, "output_bytes": 32768,
                "storage_bytes": 1024**2, "storage_inodes": 9,
            },
            "resident": {"ordinary": {
                "uid": 1234, "gid": 1234, "parent": {}, "broker_cgroup": "/synthetic",
                "initial_userns": copy.deepcopy(self.value["installation"]["initial_userns"]),
            }},
        }
        self.phase_output = chain.declared_totals(decoded(self.value))["output_bytes"]

    def contract(self, output_capacity):
        value = copy.deepcopy(self.value)
        capacity = value["installation"]["capacity"]
        capacity["management"]["output_bytes"] = output_capacity
        for phase in PHASES:
            value["phases"][phase]["grant"]["management"]["capacity_digest"] = g.digest(capacity)
        return decoded(value)

    @contextlib.contextmanager
    def before_host(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(budget, "current_clock", return_value=clock("preflight")))
            first_read = stack.enter_context(mock.patch.object(launcher.os, "stat", side_effect=HostBoundary))
            mutations = [stack.enter_context(mock.patch.object(owner, name,
                side_effect=AssertionError("unexpected filesystem or process operation")))
                for owner, name in ((launcher.os, "open"), (launcher.subprocess, "Popen"), (launcher, "save"))]
            yield first_read
            for mutation in mutations:
                mutation.assert_not_called()

    def check(self, contract):
        launcher.controller(self.launch, chain.phase_template(contract, "preflight"),
                            chain.declared_totals(contract))

    def test_one_controller_capture_cannot_fund_three_retained_phase_captures(self):
        for control_output in (1, 4096, 32768):
            self.launch["controller_envelope"]["output_bytes"] = control_output
            # This funds every observer, the resident pipes, summary and one
            # control capture. Business and evidence must also be precharged.
            contract = self.contract(self.phase_output + control_output + 32768 + 4096)
            with self.subTest(control_output=control_output), self.before_host() as first_read:
                with self.assertRaisesRegex(ValueError, "LAUNCHER_CONTROLLER_CAPACITY"):
                    self.check(contract)
                first_read.assert_not_called()

    def test_exact_output_capacity_reaches_host_boundary_but_one_byte_short_does_not(self):
        required = self.phase_output + 3 * 32768 + 32768 + 4096
        for short in (1, 0):
            contract = self.contract(required - short)
            with self.subTest(short=short), self.before_host() as first_read:
                if short:
                    with self.assertRaisesRegex(ValueError, "LAUNCHER_CONTROLLER_CAPACITY"):
                        self.check(contract)
                    first_read.assert_not_called()
                else:
                    with self.assertRaises(HostBoundary):
                        self.check(contract)
                    first_read.assert_called_once_with("/proc/self/ns/user")

    def test_three_phase_result_files_require_nine_controller_inodes_before_host_checks(self):
        contract = self.contract(self.phase_output + 3 * 32768 + 32768 + 4096)
        for inodes in (8, 9):
            self.launch["controller_envelope"]["storage_inodes"] = inodes
            with self.subTest(inodes=inodes), self.before_host() as first_read:
                if inodes == 8:
                    with self.assertRaises(ValueError):
                        self.check(contract)
                    first_read.assert_not_called()
                else:
                    with self.assertRaises(HostBoundary):
                        self.check(contract)
                    first_read.assert_called_once_with("/proc/self/ns/user")


if __name__ == "__main__":
    unittest.main()

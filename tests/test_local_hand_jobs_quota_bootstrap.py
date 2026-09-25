"""Real temporary roots/plan files; modeled UID, quota/namespace/IPC facts.

The executor may map only UID 0. No chown or user-namespace privileges are needed:
inode/device/mode remain real, and only root UID observations are modeled here.
"""
import contextlib
import copy
import json
import os
import stat
import struct
import sys
import unittest
from unittest import mock

from local_hand_jobs import bootstrap, quota_bootstrap as qb, quota_client as client, quota_contract as q, quota_grant as g
from local_hand_jobs.contract import JobError
if sys.platform.startswith("linux"):
    import test_local_hand_jobs_bootstrap_preparation as legacy
from q2_fixtures import SECOND, grant_data, encoded, receipt


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux bootstrap FD/project checks")
class QuotaBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy.BootstrapPreparationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.uid = os.geteuid() or 1234
        for root in self.fixture.slot["roots"].values():
            root["uid"] = self.uid
        self.payload = self.fixture.payload()
        execution = self.payload["execution"]
        issued = execution["budget_grant"]["reserved_boottime_ns"]
        data = grant_data(allocation=self.payload["allocation"], phase_budget=execution["budget_grant"], issued=issued)
        for root in data["roots"]:
            info = os.stat(g.root_paths(data["allocation"])[root["role"]])
            root["gid"] = info.st_gid
            root["mode"] = info.st_mode
        self.grant = g.decode_grant(encoded(data))
        execution["quota_grant_digest"] = self.grant.digest
        self.payload.update(version=2, observation=self.grant.as_dict())
        self.now = issued + SECOND
        self.result = receipt(self.grant, start=self.now, finish=self.now)
        self.calls = 0

    @contextlib.contextmanager
    def host(self, *, response=None, ioctl=None):
        import fcntl
        by_inode = {root["inode"]: root for root in self.grant.as_dict()["roots"]}
        real_stat, real_fstat = os.stat, os.fstat
        def mapped(info):
            if info.st_ino in by_inode:
                fields = list(info)
                fields[4] = self.uid
                return os.stat_result(fields)
            return info
        def local_ioctl(descriptor, command, buffer, mutate):
            self.calls += 1
            self.assertEqual(0x801C581F, command)
            root = by_inode[os.fstat(descriptor).st_ino]
            buffer[:20] = struct.pack("=IIIII", root["xflags"], 0, 0, root["project_id"], 0)
            return 0
        def exchange(*args):
            data = self.result if response is None else response()
            return q.Receipt(encoded(data), 0)  # Must be decoded again, not trusted.
        with self.fixture.simulated_host(quota=mock.Mock(side_effect=AssertionError("ordinary quota fallback"))), \
             mock.patch.object(bootstrap.os, "geteuid", return_value=self.uid), \
             mock.patch.object(os, "stat", side_effect=lambda *a, **kw: mapped(real_stat(*a, **kw))), \
             mock.patch.object(os, "fstat", side_effect=lambda fd: mapped(real_fstat(fd))), \
             mock.patch.object(client, "_boottime_ns", side_effect=lambda: self.now), \
             mock.patch.object(client, "_boot_id", return_value=self.grant.request.as_dict()["boot_id"]), \
             mock.patch.object(client, "observe", side_effect=exchange) as request, \
             mock.patch.object(fcntl, "ioctl", side_effect=ioctl or local_ioctl):
            yield request

    def test_receipt_consumed_after_fd_checks_without_ordinary_quota_call(self):
        original = copy.deepcopy(self.payload)
        with self.host() as request:
            self.assertEqual(0, bootstrap.prepare(self.payload))
        self.assertEqual(original, self.payload)
        self.assertEqual(1, request.call_count)
        self.assertEqual(6, self.calls)
        saved = json.loads(self.fixture.plan_path(self.payload).read_bytes())
        facts = saved["quota_observation"]
        self.assertEqual("local-hand-bootstrap-quota/v1", facts["schema"])
        self.assertEqual(self.grant.digest, facts["grant_digest"])
        self.assertEqual(3*65536, facts["domain_hard_bytes"])
        self.assertTrue(all(path.exists() for path in self.fixture.markers()))

    def test_trusted_payload_binding_is_explicit_detached_and_bounded(self):
        execution = copy.deepcopy(self.payload["execution"])
        execution.pop("quota_grant_digest")
        payload = qb.bind_payload(execution, self.payload["allocation"], self.grant, now_ns=self.now)
        self.assertEqual(self.payload, payload)
        self.assertNotIn("quota_grant_digest", execution)
        payload["allocation"]["slot_id"] = "changed"
        self.assertNotEqual("changed", self.payload["allocation"]["slot_id"])
        execution["padding"] = "x" * 65536
        with self.assertRaises(JobError):
            qb.bind_payload(execution, self.payload["allocation"], self.grant, now_ns=self.now)

    def test_wrong_receipt_root_or_query_parent_prevents_all_writes(self):
        for field in ("root", "parent", "exit"):
            candidate = copy.deepcopy(self.result)
            if field == "root":
                candidate["roots"][0]["inode"] += 1
            elif field == "parent":
                candidate["query"]["cgroup"] = "/foreign.slice/" + self.grant.request.query_unit
            else:
                candidate["exit"]["stderr_eof"] = False
            with self.subTest(field=field), self.host(response=lambda: candidate), self.assertRaises(JobError):
                bootstrap.prepare(self.payload)
            self.assertFalse(any(path.exists() for path in self.fixture.markers()))
            self.assertFalse(self.fixture.plan_path(self.payload).exists())

    def test_unknown_receipt_does_not_fallback_or_publish_plan(self):
        self.result.update(status="UNKNOWN", reason="EXIT_UNPROVEN")
        self.result["exit"]["tree_empty"] = False
        with self.host(), self.assertRaisesRegex(JobError, "OBSERVATION_UNRESOLVED"):
            bootstrap.prepare(self.payload)
        self.assertFalse(any(path.exists() for path in self.fixture.markers()))

    def test_transport_failure_retains_no_new_plan_or_marker(self):
        with self.host(), mock.patch.object(client, "observe", side_effect=q.QuotaError("PARTIAL_FRAME")):
            with self.assertRaisesRegex(JobError, "PARTIAL_FRAME"):
                bootstrap.prepare(self.payload)
        self.assertFalse(any(path.exists() for path in self.fixture.markers()))

    def test_local_project_change_rejected_before_contacting_observer(self):
        def wrong(descriptor, command, buffer, mutate):
            buffer[:20] = struct.pack("=IIIII", 512, 0, 0, 9999, 0)
        with self.host(ioctl=wrong) as request, self.assertRaisesRegex(JobError, "LOCAL_PROJECT"):
            bootstrap.prepare(self.payload)
        request.assert_not_called()
        self.assertFalse(any(path.exists() for path in self.fixture.markers()))

    def test_local_inode_change_after_receipt_is_rejected(self):
        def replace_root():
            path = self.fixture.root / "work"
            path.rename(self.fixture.root / "retained-work")
            path.mkdir(mode=0o700)
            return self.result
        with self.host(response=replace_root), self.assertRaisesRegex(JobError, "LOCAL_ROOT_CHANGED"):
            bootstrap.prepare(self.payload)
        self.assertFalse(any(path.exists() for path in self.fixture.markers()))

    def test_expiry_during_exchange_is_not_renewed(self):
        def expired():
            self.now = self.grant.request.as_dict()["deadline_ns"]
            return self.result
        with self.host(response=expired), self.assertRaisesRegex(JobError, "DEADLINE"):
            bootstrap.prepare(self.payload)
        self.assertFalse(self.fixture.plan_path(self.payload).exists())

    def test_exact_new_envelope_and_binding_required(self):
        for change in ({"version": True}, {"version": 3}, {"additional": "field"}):
            with self.subTest(change=change), self.assertRaises(JobError):
                bootstrap.prepare(dict(self.payload, **change))
        old = {key: self.payload[key] for key in ("execution", "allocation")}
        with self.assertRaisesRegex(JobError, "version and binding"):
            bootstrap.prepare(old)
        bad = copy.deepcopy(self.payload)
        bad["execution"]["quota_grant_digest"] = "0" * 64
        with self.host() as request, self.assertRaisesRegex(JobError, "BOOTSTRAP_BINDING"):
            bootstrap.prepare(bad)
        request.assert_not_called()

    def test_supervision_budget_versions_do_not_gain_management_cpu(self):
        self.payload["execution"]["supervision_version"] = 3
        before = copy.deepcopy(self.payload["execution"]["budget_grant"])
        with self.host():
            bootstrap.prepare(self.payload)
        saved = json.loads(self.fixture.plan_path(self.payload).read_bytes())
        self.assertEqual(before, saved["budget_grant"])

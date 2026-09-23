"""LOGIC_ONLY quota transcripts; no Samba binary, network or actual NAS used."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand_jobs import nas_quota as quota
from local_hand_jobs.contract import JobError

SID = "S-1-5-21-111-222-333-1001"
# Response labels/order follow dump_ntquota in the pinned upstream source.
# These bytes are constructed synthetic fixtures, not captured NAS evidence.
FS_OUTPUT = (b"File System QUOTAS:\nLimits:\n"
             b" Default Soft Limit:            1024\n"
             b" Default Hard Limit:            2048\n"
             b"Quota Flags:\n Quotas Enabled: On\n Deny Disk:      On\n"
             b" Log Soft Limit: Off\n Log Hard Limit: Off\n")
USER_OUTPUT = (b"Quotas for User: S-1-5-21-111-222-333-1001\n"
               b"Used Space:             256\nSoft Limit:            1024\n"
               b"Hard Limit:            2048\n")


def admission():
    return {"provider": quota.PROVIDER, "storage_ref": "synthetic-store", "resource_id": "synthetic-archive",
            "quota_domain": "synthetic-volume-user", "share": "//nas.example.test/synthetic",
            "remote_sid": SID, "archive_root": "/synthetic/archive", "storage_config_digest": "1" * 64,
            "mount": {"type": "cifs", "source": "//nas.example.test/synthetic", "root": "/",
                      "target": "/synthetic/archive", "device": 71, "inode": 91, "mount_id": 14,
                      "namespace": "mnt:[123456]"},
            "tool": {"path": "/synthetic/bin/smbcquotas", "sha256": "2" * 64, "version": "4.23.0",
                     "client_config": "/synthetic/query/smb.conf", "client_config_digest": "3" * 64,
                     "authentication_file": "/synthetic/query/credential", "credential_ref": "synthetic-query",
                     "network_boundary_ref": "synthetic-query-network"}}


def context(phase="preflight"):
    operation = "12345678-1234-4234-8234-123456789abc"
    return {"operation_id": operation, "execution_id": "job-" + operation + "-" + phase,
            "phase": phase, "boot_id": "12345678-1234-1234-1234-123456789abc", "nas_bytes": 4096,
            "not_before_boottime_ns": 100, "deadline_boottime_ns": 30_000_000_100}


def fixture_observations(admitted, scope):
    requests = quota.build_query_requests(admitted, scope)
    fixed_tool = mock.Mock(side_effect=[FS_OUTPUT, USER_OUTPUT])
    results = []
    for index, request in enumerate(requests):
        tick = 110 + index * 10
        results.append({"request_digest": request["request_digest"], "boot_id": scope["boot_id"],
                        "started_boottime_ns": tick + 1, "finished_boottime_ns": tick + 2,
                        "before": {"boottime_ns": tick, "binding": copy.deepcopy(admitted)},
                        "after": {"boottime_ns": tick + 3, "binding": copy.deepcopy(admitted)},
                        "exit_code": 0, "stdout": fixed_tool(request), "stderr": b""})
    return results, fixed_tool


class NasQuotaTests(unittest.TestCase):
    def setUp(self):
        self.admitted, self.scope = admission(), context()
        self.observations, self.tool = fixture_observations(self.admitted, self.scope)
        self.now = {"boot_id": self.scope["boot_id"], "boottime_ns": 130}

    def validate(self, observations=None, **kwargs):
        return quota.validate_responses(kwargs.get("admission", self.admitted), kwargs.get("context", self.scope),
            self.observations if observations is None else observations, now=kwargs.get("now", self.now))

    def rejected(self, operation):
        with self.assertRaises(JobError) as failure:
            operation()
        self.assertEqual("UNSUPPORTED", failure.exception.code)

    def test_fixed_tool_fixture_has_only_two_read_only_operations_and_clean_environment(self):
        with mock.patch.dict(os.environ, {"PASSWD": "do-not-inherit", "USER": "foreign-user"}):
            requests = quota.build_query_requests(self.admitted, self.scope)
        self.assertEqual(["filesystem", "user"], [item["query"] for item in requests])
        for request, option in zip(requests, ["--fs", "--quota-user=" + SID]):
            self.assertEqual(["/synthetic/bin/smbcquotas", "//nas.example.test/synthetic", "--numeric",
                              "--verbose", "--debuglevel=0", "--configfile=/synthetic/query/smb.conf",
                              "--authentication-file=/synthetic/query/credential", "--client-protection=encrypt",
                              "--use-kerberos=off", option], request["argv"])
            self.assertEqual({"LC_ALL": "C", "LANG": "C"}, request["environment"])
            self.assertEqual("DEVNULL", request["stdin"])
            self.assertEqual(4096, request["max_output_bytes"])
            self.assertNotIn("--set", request["argv"])
        self.assertEqual(2, self.tool.call_count)
        result = self.validate()
        self.assertEqual("LOGIC_ONLY", result["coverage"])
        self.assertIs(False, result["business_authorized"])
        self.assertEqual(2048, result["validated_responses"]["user"]["hard_bytes"])
        self.assertEqual(64, len(result["observation_digest"]))
        self.assertNotIn("stdout", result["receipts"][0])

    def test_live_execution_never_accepts_declared_or_validated_quota_proof(self):
        proof = self.validate()
        with mock.patch("builtins.open", side_effect=AssertionError("unexpected file read")), \
             mock.patch("subprocess.Popen", side_effect=AssertionError("unexpected process")), \
             mock.patch("socket.socket", side_effect=AssertionError("unexpected network")):
            for supplied in (self.admitted, proof, {"quota_enforced": True}, None):
                with self.subTest(supplied=type(supplied).__name__):
                    self.rejected(lambda: quota.execute_live_queries(supplied, self.scope))

    def test_exit_zero_unsupported_server_message_is_not_quota_evidence(self):
        self.observations[0]["stdout"] = b"Quotas are not supported by the server.\n"
        self.rejected(self.validate)

    def test_disabled_enforcement_diagnostic_errors_and_unknown_fields_are_rejected(self):
        for value in (FS_OUTPUT.replace(b"Quotas Enabled: On", b"Quotas Enabled: Off"),
                      FS_OUTPUT.replace(b"Deny Disk:      On", b"Deny Disk:      Off")):
            self.rejected(lambda: quota.parse_filesystem_response(value))
        for key, value in (("exit_code", 1), ("exit_code", True), ("stderr", b"warning\n"),
                           ("stderr", ""), ("quota_enforced", True)):
            changed = copy.deepcopy(self.observations)
            changed[0][key] = value
            with self.subTest(key=key, value=value):
                self.rejected(lambda: self.validate(changed))

    def test_zero_unlimited_no_entry_and_huge_limits_are_never_finite_authority(self):
        for value in ("0", str(2**64 - 1), str(2**64 - 2), str(2**53), "NO LIMIT", "-1", "1e3", "02048"):
            raw = USER_OUTPUT.replace(b"Hard Limit:            2048", b"Hard Limit: " + value.encode())
            with self.subTest(value=value):
                self.rejected(lambda: quota.parse_user_response(raw, remote_sid=SID, nas_bytes=4096))
        for value in (b"0", str(2**64 - 1).encode(), str(2**64 - 2).encode()):
            raw = FS_OUTPUT.replace(b"Default Hard Limit:            2048", b"Default Hard Limit: " + value)
            self.rejected(lambda: quota.parse_filesystem_response(raw))

    def test_domain_absolute_limit_not_free_bytes_must_fit_budget(self):
        # Remaining 1024 fits 4096, but the total 8192-byte domain does not.
        raw = USER_OUTPUT.replace(b"256", b"7168").replace(b"2048", b"8192")
        self.rejected(lambda: quota.parse_user_response(raw, remote_sid=SID, nas_bytes=4096))
        for raw in (USER_OUTPUT.replace(b"256", b"4096"), USER_OUTPUT.replace(b"1024", b"4096")):
            self.rejected(lambda: quota.parse_user_response(raw, remote_sid=SID, nas_bytes=4096))
        parsed = quota.parse_user_response(USER_OUTPUT, remote_sid=SID, nas_bytes=2048)
        self.assertEqual(2048, parsed["hard_bytes"])

    def test_wrong_sid_duplicates_missing_lines_extra_bytes_and_truncation_fail(self):
        for raw in (USER_OUTPUT.replace(b"1001", b"1002"), USER_OUTPUT * 2, USER_OUTPUT[:-1],
                    USER_OUTPUT + b"\n", USER_OUTPUT.replace(b"Soft Limit:", b"Hard Limit:"),
                    USER_OUTPUT + b"\x00", USER_OUTPUT + b"\xff", b"x" * 4097, "not bytes"):
            with self.subTest(raw=str(raw)[:70]):
                self.rejected(lambda: quota.parse_user_response(raw, remote_sid=SID, nas_bytes=4096))
        for raw in (FS_OUTPUT * 2, FS_OUTPUT.replace(b"Limits:\n", b""), FS_OUTPUT + b"comment"):
            self.rejected(lambda: quota.parse_filesystem_response(raw))

    def test_all_identity_and_mount_observations_must_remain_bound_before_and_after(self):
        mutations = [("storage_config_digest", "4" * 64), ("quota_domain", "other-domain"),
                     ("resource_id", "other-resource"), ("remote_sid", SID + "-1")]
        for point in ("before", "after"):
            for key, value in mutations:
                changed = copy.deepcopy(self.observations)
                changed[1][point]["binding"][key] = value
                with self.subTest(point=point, key=key):
                    self.rejected(lambda: self.validate(changed))
            for key, value in (("inode", 92), ("device", 72), ("mount_id", 15),
                               ("namespace", "mnt:[456789]"), ("root", "/other"), ("inode", True)):
                changed = copy.deepcopy(self.observations)
                changed[1][point]["binding"]["mount"][key] = value
                self.rejected(lambda: self.validate(changed))
            for key, value in (("sha256", "4" * 64), ("client_config_digest", "4" * 64),
                               ("credential_ref", "other-credential"), ("network_boundary_ref", "other-network")):
                changed = copy.deepcopy(self.observations)
                changed[1][point]["binding"]["tool"][key] = value
                self.rejected(lambda: self.validate(changed))

    def test_query_order_cardinality_and_execution_replay_are_rejected(self):
        for observations in ([], self.observations[:1], self.observations * 2, self.observations[::-1]):
            self.rejected(lambda: self.validate(observations))
        self.rejected(lambda: self.validate(context=context("business")))
        other = context()
        other["operation_id"] = "22345678-1234-4234-8234-123456789abc"
        other["execution_id"] = "job-" + other["operation_id"] + "-preflight"
        self.rejected(lambda: self.validate(context=other))

    def test_stale_future_reordered_expired_and_cross_boot_observations_fail(self):
        for now in ({"boot_id": self.now["boot_id"], "boottime_ns": 122},
                    {"boot_id": self.now["boot_id"], "boottime_ns": 2_000_000_000},
                    {"boot_id": self.now["boot_id"], "boottime_ns": self.scope["deadline_boottime_ns"] + 1},
                    {"boot_id": "22345678-1234-1234-1234-123456789abc", "boottime_ns": 130}):
            self.rejected(lambda: self.validate(now=now))
        for key, value in (("started_boottime_ns", 109), ("finished_boottime_ns", 114),
                           ("finished_boottime_ns", True), ("boot_id", "wrong-boot")):
            changed = copy.deepcopy(self.observations)
            changed[0][key] = value
            self.rejected(lambda: self.validate(changed))
        changed = copy.deepcopy(self.observations)
        changed[1]["before"]["boottime_ns"] = 112
        self.rejected(lambda: self.validate(changed))

    def test_admission_rejects_protocol_share_path_sid_and_tool_ambiguity(self):
        mutations = [("provider", "nfs-rquota"), ("share", "//other.example.test/synthetic"),
                     ("share", "//nas.example.test/synthetic/other"), ("share", "//nas.example.test/IPC$"),
                     ("remote_sid", "DOMAIN/user"), ("remote_sid", "S-1-5-4294967296"),
                     ("remote_sid", "S-1-5-01"), ("archive_root", "/synthetic/../archive"),
                     ("quota_enforced", True), ("args", ["--set=FSQFLAGS:QUOTA_ENABLED"])]
        for key, value in mutations:
            changed = admission()
            changed[key] = value
            self.rejected(lambda: quota.build_query_requests(changed, self.scope))
        for key, value in (("version", "4.24.0"), ("path", "/usr/bin/%n"), ("path", "/bin/$USER"),
                           ("path", "/synthetic/archive/tool"), ("authentication_file", "/synthetic/query/smb.conf")):
            changed = admission()
            changed["tool"][key] = value
            self.rejected(lambda: quota.build_query_requests(changed, self.scope))
        changed = admission()
        changed["mount"]["type"] = "nfs4"
        self.rejected(lambda: quota.build_query_requests(changed, self.scope))

    def test_context_has_finite_nonboolean_budget_and_exact_execution_phase(self):
        for key, value in (("nas_bytes", True), ("nas_bytes", 0), ("phase", "reconcile"),
                           ("execution_id", "arbitrary"), ("deadline_boottime_ns", 100),
                           ("deadline_boottime_ns", 30_000_000_101), ("not_before_boottime_ns", True)):
            changed = context()
            changed[key] = value
            self.rejected(lambda: quota.build_query_requests(self.admitted, changed))

    def test_mutating_inputs_or_returned_requests_does_not_rebind_existing_request(self):
        admitted, scope = admission(), context()
        requests = quota.build_query_requests(admitted, scope)
        before = copy.deepcopy(requests[0])
        admitted["tool"]["path"] = "/other/tool"
        scope["nas_bytes"] = 8192
        requests[1]["context"]["nas_bytes"] = 9000
        self.assertEqual(before, requests[0])


if __name__ == "__main__":
    unittest.main()

"""Real protected host files/pipes; guest and systemd observations are synthetic."""
from __future__ import annotations

import base64
import copy
import gzip
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from e3_host import q2_startup_retry_entry as e


@unittest.skipUnless(sys.platform.startswith("linux") and hasattr(os,"O_NOATIME"),"Linux protected noatime reads")
class StartupRetryPrivateEntry(unittest.TestCase):
    def setUp(self):
        # Production still validates the complete '/' ancestry. The test uses a
        # protected home, not an alternate trust-root escape through world-writable /tmp.
        try:
            fd=e.protected_directory(Path.home());os.close(fd)
        except (OSError,ValueError):
            self.skipTest("test home has no fully protected ancestry")
        self.tmp=tempfile.TemporaryDirectory(prefix="q2-startup-entry-",dir=Path.home())
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.old=[]
        for index in range(2):
            path=self.root/("old"+str(index)+".json");raw=e.encoded({"historical_failure":index})
            path.write_bytes(raw);path.chmod(0o600);os.utime(path,ns=(1000000000,2000000000))
            self.old.append(dict(path=str(path),sha256=e.sha(raw)))
        self.wrapper=self.root/"ssh-wrapper"
        self.guest=dict(hostname="synthetic-guest",boot_id="12345678-1234-1234-1234-123456789abc",
                        initial_userns=dict(device=1,inode=2))
        self.config=dict(schema=e.SCHEMA,attempt_id="startupretry01",source_commit="a"*40,source_tree="b"*40,
            candidate=e.CANDIDATE,wheel_sha256=e.WHEEL_SHA256,host_result_directory=str(self.root/"new-result"),
            old_host_files=self.old,guest_pin=self.guest,ssh_wrapper=str(self.wrapper),
            guest_python="/usr/bin/python3.12",guest_stage="/root/synthetic-startup-retry",guest_outer_unit="syntheticstartup01.service")
        self.write_wrapper()

    def write_wrapper(self, *, probe_extra=None, collector_status="COLLECTED"):
        sample={**self.guest,"boottime_ns":900*10**9}
        if probe_extra:sample.update(probe_extra)
        code = ("#!"+sys.executable+"\nimport json,sys,shlex\ncommand=sys.argv[1]\n"
            "if 'q2_startup_retry_collect.py' in command:\n"
            " args=shlex.split(command)\n"
            " result="+repr(dict(schema=e.COLLECTION_SCHEMA,status=collector_status,q2_accepted=False,q3_accepted=False,
                        production_supported=False,scope="LH-Q2-SUPERVISOR-STARTUP-RETRY-v1",attempt_id=self.config["attempt_id"]))+"\n"
            " result.update(retry_sha256=args[args.index('--sha256')+1],delivery_sha256=args[args.index('--delivery-sha256')+1],clock_anchor_sha256=args[args.index('--clock-anchor-sha256')+1])\n"
            " print(json.dumps(result))\n"
            "elif 'systemd-run' in command:\n"
            " source=sys.stdin.buffer.read();exec(compile(source,'<synthetic-guest>','exec'))\n"
            "else:\n print("+repr(json.dumps(sample))+")\n")
        self.wrapper.write_text(code);self.wrapper.chmod(0o700)

    def guest_input(self,anchor,*,exit_code=0,ready_change=None,duplicate=False,prepared=False):
        ready=dict(schema=e.READY_SCHEMA,status="STARTUP_RETRY_BOOTSTRAP_READY",attempt_id=self.config["attempt_id"],
                   retry_sha256="c"*64,delivery_sha256="d"*64,clock_anchor_sha256=e.sha(e.encoded(anchor)),
                   q2_accepted=False,q3_accepted=False,production_supported=False)
        if ready_change:ready.update(ready_change)
        values=[ready,ready] if duplicate else [ready]
        if prepared:
            values.append(dict(schema="local-hand-q2-supervisor-startup-retry-driver-result/v1",status="STARTUP_RETRY_PREPARED",
                attempt_id=self.config["attempt_id"],source_commit=e.CANDIDATE,
                orchestration_source=dict(commit=self.config["source_commit"]),
                runtime_candidate=dict(commit=e.CANDIDATE,wheel_sha256=e.WHEEL_SHA256),
                new_request_issuance=dict(schema="local-hand-q2-new-request-issuance/v1",attempt_id=self.config["attempt_id"],
                                         original_owners_issued=True,original_verdicts_retained=True)))
        values.append(dict(schema="local-hand-q2-handoff-result/v1",status="SUPERVISOR_CLOSED" if exit_code==0 else "INCOMPLETE",
                           sealed=exit_code==0,q2_accepted=False))
        return ("import sys\n"+"".join("print("+repr(json.dumps(v))+")\n" for v in values)+"sys.exit("+str(exit_code)+")\n").encode()

    def test_real_noatime_old_evidence_identity_and_digest_stay_exact(self):
        before=[e.identity(Path(pin["path"]).stat()) for pin in self.old]
        first=e.read_history(self.config,lambda:None)
        second=e.read_history(self.config,lambda:None)
        self.assertEqual(first,second)
        self.assertEqual(before,[e.identity(Path(pin["path"]).stat()) for pin in self.old])

    def test_noatime_denial_has_no_unprotected_retry(self):
        original=os.open;attempts=[]
        def opened(path,flags,*args,**kwargs):
            if str(path)==Path(self.old[0]["path"]).name:
                attempts.append(flags)
                raise PermissionError(1,"denied")
            return original(path,flags,*args,**kwargs)
        with patch.object(e.os,"open",side_effect=opened),self.assertRaises(PermissionError):
            e.read_pinned(self.old[0],lambda:None)
        self.assertEqual(len(attempts),1);self.assertTrue(attempts[0]&os.O_NOATIME)

    def test_symlink_hardlink_writable_file_and_changed_leaf_rejected(self):
        path=Path(self.old[0]["path"]);raw=path.read_bytes();path.unlink()
        path.symlink_to(Path(self.old[1]["path"]))
        with self.assertRaises((OSError,ValueError)):e.read_pinned(self.old[0],lambda:None)
        path.unlink();path.write_bytes(raw);path.chmod(0o622)
        with self.assertRaises(ValueError):e.read_pinned(self.old[0],lambda:None)
        path.chmod(0o600);os.link(path,self.root/"alias")
        with self.assertRaises(ValueError):e.read_pinned(self.old[0],lambda:None)

    def test_real_host_pipeline_is_retained_once_but_does_not_accept_q2(self):
        result=e.run_host(self.config,guest_input_builder=lambda anchor:self.guest_input(anchor,prepared=True))
        self.assertEqual(result["status"],"RUN_RECORDED")
        self.assertTrue(result["transport"]["original_clients_capture_complete"])
        self.assertTrue(result["old_host_preserved"]);self.assertTrue(result["wrapper_unchanged"])
        self.assertTrue(result["owner_request_issuance_observed"]);self.assertTrue(result["owner_report_observed"])
        self.assertTrue(result["within_original_deadline"])
        for key in ("q2_accepted","q3_accepted","production_supported","independent_stop_proven","runtime_tree_empty_proven"):
            self.assertFalse(result[key])
        out=Path(self.config["host_result_directory"])
        packed=json.loads(gzip.decompress(Path(result["upload_path"]).read_bytes()))
        core=e.encoded(dict(schema=e.BUNDLE_SCHEMA,files=packed["files"]))
        self.assertEqual(e.sha(core),packed["core_sha256"])
        self.assertEqual(packed["completion"]["core_sha256"],e.sha(core))
        self.assertTrue(packed["completion"]["core_within_original_deadline"])
        raw_files={name:base64.b64decode(meta["data"]) for name,meta in packed["files"].items()}
        self.assertEqual(json.loads(raw_files["guest-capture.json"])["returncode"],0)
        before={p.name:p.read_bytes() for p in out.iterdir()}
        with self.assertRaises(FileExistsError):e.run_host(self.config,guest_input_builder=lambda _:b"raise RuntimeError()")
        self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir()})

    def test_nonzero_guest_keeps_complete_streams_and_unknown_owner_issuance(self):
        result=e.run_host(self.config,guest_input_builder=lambda anchor:self.guest_input(anchor,exit_code=3))
        self.assertEqual(result["status"],"INCOMPLETE")
        self.assertTrue(result["transport"]["guest_capture"]["complete"])
        self.assertEqual(result["transport"]["guest_capture"]["returncode"],3)
        self.assertIsNone(result["owner_request_issued"])
        self.assertTrue(result["old_host_preserved"])

    def test_host_suspend_before_guest_issuance_keeps_original_window_and_blocks_delivery(self):
        real_builder=self.guest_input;real_clock=e.time.clock_gettime_ns;paused=[]
        def builder(anchor):
            source=real_builder(anchor)
            paused.append(True)
            return source
        def clock(clock_id):
            return real_clock(clock_id)+(200*10**9 if paused else 0)
        with patch.object(e.time,"clock_gettime_ns",side_effect=clock):
            result=e.run_host(self.config,guest_input_builder=builder)
        self.assertEqual(result["status"],"INCOMPLETE")
        self.assertEqual(result["error"]["reason"],"STARTUP_RETRY_DELIVERY_HOST_CLOCK_DIVERGED")
        self.assertFalse(result["batch_delivery_issued"])
        self.assertIsNone(result["transport"]["guest_capture"])
        self.assertEqual(result["deadline_ns"]-result["issued_ns"],300*10**9)
        self.assertTrue(Path(result["upload_path"]).exists())

    def test_wrong_boot_probe_never_issues_guest_and_still_consumes_reservation(self):
        self.write_wrapper(probe_extra={"boot_id":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"})
        called=[]
        result=e.run_host(self.config,guest_input_builder=lambda anchor:called.append(anchor))
        self.assertEqual(result["status"],"INCOMPLETE");self.assertFalse(result["batch_delivery_issued"])
        self.assertEqual(called,[]);self.assertIsNone(result["transport"]["guest_capture"])
        self.assertTrue(Path(result["upload_path"]).exists())
        with self.assertRaises(FileExistsError):e.run_host(self.config,guest_input_builder=lambda _:b"pass")

    def test_ready_schema_extra_fields_or_attempt_drift_are_not_collected(self):
        result=e.run_host(self.config,guest_input_builder=lambda anchor:self.guest_input(anchor,ready_change={"attempt_id":"otherattempt01"}))
        self.assertEqual(result["status"],"INCOMPLETE")
        self.assertEqual(result["error"]["reason"],"STARTUP_ENTRY_READY_BINDING")
        self.assertIsNone(result["transport"]["collect_capture"])

    def test_duplicate_ready_cannot_start_second_collection(self):
        result=e.run_host(self.config,guest_input_builder=lambda anchor:self.guest_input(anchor,duplicate=True))
        self.assertEqual(result["error"]["reason"],"STARTUP_ENTRY_DUPLICATE_READY")
        self.assertIsNone(result["transport"]["collect_capture"])

    def test_original_failure_hash_mismatch_retains_create_only_failure_record(self):
        self.config["old_host_files"][1]["sha256"]="e"*64
        result=e.run_host(self.config,guest_input_builder=lambda _:b"pass")
        self.assertEqual(result["error"]["reason"],"STARTUP_ENTRY_OLD_HOST_CHANGED")
        self.assertIsNone(result["transport"]["probe_capture"])
        self.assertTrue(Path(result["upload_path"]).exists())

    def test_strict_config_rejects_old_schema_mutable_candidate_aliases_and_shell_unit(self):
        for changed in ({"schema":"local-hand-q2-private-cpuquota-retry/v1"},{"candidate":"main"},
                        {"guest_python":"/bin/sh"},{"guest_outer_unit":"synthetic;id.service"},
                        {"host_result_directory":self.old[0]["path"]},{"arbitrary_command":"id"}):
            with self.subTest(changed=changed),self.assertRaises(ValueError):e.validate_config({**self.config,**changed})
        self.assertFalse(Path(self.config["host_result_directory"]).exists())


class InertStartupRetryEntry(unittest.TestCase):
    def test_no_argument_entry_is_inert_on_every_platform(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,"-I","-B",e.__file__],cwd=directory,capture_output=True,timeout=5)
            self.assertEqual(result.returncode,3)
            self.assertEqual(json.loads(result.stdout)["status"],"BLOCKED")
            self.assertEqual(list(Path(directory).iterdir()),[])


if __name__=="__main__":unittest.main()

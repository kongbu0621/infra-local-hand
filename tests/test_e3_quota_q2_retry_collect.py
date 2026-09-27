"""Read-only files/pipe collection; systemd observations are explicitly modeled."""
import base64
import copy
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from e3_host import q2_retry_collect as c
from e3_host import q2_retry_delivery as d


@unittest.skipUnless(os.name=="posix","POSIX no-follow read-only collector")
class Files(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.guard=lambda:None
        self.reader=c.Reader(self.guard,uids=(os.geteuid(),),root=str(self.root))
        self.addCleanup(self.reader.close)

    def write(self,name,raw):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);path.chmod(0o600);return path

    def test_real_tree_archive_metadata_bytes_and_atime_remain_unchanged(self):
        path=self.write("capture/child/result.json",b'{"status":"INCOMPLETE"}\n')
        os.utime(path,ns=(1230000000000000000,1240000000000000000))
        before=path.stat();rows=self.reader.tree(str(self.root/"capture"));self.reader.stable();after=path.stat()
        file=next(row for row in rows if row["kind"]=="file")
        self.assertEqual(base64.b64decode(file["content_base64"]),path.read_bytes())
        self.assertEqual(file["sha256"],c.sha(b'{"status":"INCOMPLETE"}\n'))
        for key in ("st_atime_ns","st_mtime_ns","st_ctime_ns","st_ino","st_mode","st_size"):
            self.assertEqual(getattr(before,key),getattr(after,key),key)
        self.assertEqual({p.relative_to(self.root).as_posix() for p in self.root.rglob("*")},
                         {"capture","capture/child","capture/child/result.json"})

    def test_symlink_hardlink_fifo_permission_and_outside_root_rejected(self):
        original=self.write("capture/result.json",b"keep")
        for kind in ("symlink","hardlink","fifo","writable"):
            target=self.root/(kind+".json")
            if kind=="symlink":target.symlink_to(original)
            elif kind=="hardlink":os.link(original,target)
            elif kind=="fifo":os.mkfifo(target)
            else:target.write_bytes(b"changed");target.chmod(0o666)
            with self.subTest(kind=kind),self.assertRaises((OSError,ValueError)):self.reader.read(str(target))
            target.unlink()
        linked=self.root/"linked";linked.symlink_to(self.root/"capture",target_is_directory=True)
        with self.assertRaises(OSError):self.reader.read(str(linked/"result.json"))
        with self.assertRaises(ValueError):self.reader.read("/etc/passwd")

    def test_read_set_replacement_detected_without_modifying_evidence(self):
        path=self.write("capture/result.json",b"one")
        self.reader.read(str(path));path.rename(path.with_suffix(".old"));path.write_bytes(b"one")
        with self.assertRaisesRegex(ValueError,"CHANGED"):self.reader.stable()

    def test_total_file_entry_limits_are_actual_read_bounds(self):
        path=self.write("capture/result.json",b"x"*1025)
        with self.assertRaisesRegex(ValueError,"FILE_LIMIT"):self.reader.read(str(path),limit=1024)
        small=c.Reader(self.guard,uids=(os.geteuid(),),root=str(self.root),max_raw=1024)
        try:
            with self.assertRaisesRegex(ValueError,"TOTAL_LIMIT"):small.read(str(path),limit=2048)
        finally:small.close()
        limited=c.Reader(self.guard,uids=(os.geteuid(),),root=str(self.root),max_entries=1)
        try:
            with self.assertRaisesRegex(ValueError,"ENTRY_LIMIT"):limited.tree(str(self.root/"capture"))
        finally:limited.close()

    def fixture(self):
        old=self.write("old/result.json",b'{"old":"INCOMPLETE"}\n')
        ledger=self.write("old/jobs.sqlite",b"retained sqlite bytes");info=ledger.stat()
        directories={role:dict(path=str(self.root/("new-"+role))) for role in
                     ("reservation","authority","state","capture","declarations","journal")}
        for item in directories.values():Path(item["path"]).mkdir(mode=0o700)
        retry=dict(attempt_id="syntheticretry01",source={"commit":"a"*40},candidate={"commit":"b"*40},
                   old_files={str(old):c.sha(old.read_bytes())},old_prepared=str(old),directories=directories,
                   old_ledger=dict(path=str(ledger),device=info.st_dev,inode=info.st_ino,uid=info.st_uid,mode=0o600))
        attest=dict(ledger=dict(sha256=c.sha(ledger.read_bytes())),old_prepared_sha256=c.sha(old.read_bytes()),
                    original_owner_issued=True,unused_roots=True,unused_ledger=True)
        receipt=dict(schema="local-hand-q2-cpuquota-retry-preparation/v1",status="RETRY_RESOURCES_PREPARED",
                     attempt_id=retry["attempt_id"],retry_sha256=c.sha(c.encoded(retry)),q2_accepted=False,q3_accepted=False,
                     production_supported=False,fixture_generated=False,
                     retry=dict(attestation=attest,attestation_sha256=c.sha(c.encoded(attest))),facts={})
        p=Path(directories["reservation"]["path"])/"retry-preparation.json";p.write_bytes(c.encoded(receipt));p.chmod(0o600)
        root=self.root/"quota";root.mkdir(mode=0o700)
        original=dict(roots=[dict(path=str(root),project_id=123)],parents={})
        return retry,original,old,ledger

    def collect(self,retry,original):
        return c.collect(retry,original,{},{},guard=self.guard,reader=self.reader,deadline_ns=1,
            runtime_observer=lambda *args:dict(parent_trees_empty=True,new_runtime_services_stopped=True),
            preservation_observer=lambda *args:dict(old_trees_preserved=True,q1_records_preserved=True))

    def test_model_observations_actual_bytes_collection_keeps_old_verdict(self):
        retry,original,old,ledger=self.fixture();before={str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        value=self.collect(retry,original)
        self.assertTrue(value["complete"]);self.assertTrue(value["old_files_preserved"])
        self.assertTrue(value["old_ledger_preserved"]);self.assertFalse(value["q2_accepted"])
        report=c.bundle_report(value,output_limit=65536)
        raw=gzip.decompress(base64.b64decode(report["bundle"]["data"],validate=True))
        self.assertEqual(c.sha(raw),report["bundle"]["raw_sha256"])
        self.assertEqual(json.loads(raw)["old_files"][0]["preserved"],True)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertFalse(report["original_eof_proven"]);self.assertFalse(report["remote_stop_proven"])

    def test_changed_old_bytes_or_ledger_identity_preserves_incomplete(self):
        retry,original,old,ledger=self.fixture();old.write_bytes(b"changed old result")
        ledger.rename(ledger.with_suffix(".retained"));ledger.write_bytes(b"retained sqlite bytes");ledger.chmod(0o600)
        value=self.collect(retry,original)
        self.assertFalse(value["old_files_preserved"]);self.assertFalse(value["old_ledger_preserved"])
        self.assertFalse(value["complete"])
        self.assertEqual(c.bundle_report(value,output_limit=65536)["status"],"INCOMPLETE")

    def test_receipt_cannot_substitute_a_new_old_ledger_digest(self):
        retry,original,old,ledger=self.fixture()
        path=Path(retry["directories"]["reservation"]["path"])/"retry-preparation.json"
        receipt=json.loads(path.read_bytes());receipt["retry"]["attestation"]["ledger"]["sha256"]="f"*64
        path.write_bytes(c.encoded(receipt))
        value=self.collect(retry,original)
        self.assertFalse(value["complete"])
        self.assertFalse(value["old_ledger_preserved"])
        self.assertTrue(any(error["reason"]=="COLLECT_ATTESTATION_BINDING" for error in value["errors"]))

    def test_actual_snapshot_formats_match_without_changing_retained_files(self):
        backend=c.helper("q2_retry")
        old=self.write("old-install/pinned.py",b"old source\n")
        q1=self.write("q1-retained/payload",b"retained Q1 payload")
        q1root=q1.parent.stat()
        original=dict(retained=[dict(path=str(q1.parent),device=q1root.st_dev,inode=q1root.st_ino)],
                      budgets=dict(retained_scan_entries=100,retained_scan_bytes=4096))
        def opened(path,*,directory=False,owner=0,noatime=False):
            return self.reader.opened(str(path),directory=directory)
        with patch.object(backend.p,"opened",side_effect=opened):
            # Only path ancestry is modeled around this real temporary fixture.
            # Both snapshot implementations read/hash the actual same bytes.
            expected_old=backend.snapshot_tree(str(old.parent),self.guard)
            model=object.__new__(backend.p.LinuxBackend);model.plan=original;model.guard=self.guard
            expected_q1=model.snapshot()
            receipt=dict(retry=dict(attestation=dict(old_snapshots=[expected_old])),facts=dict(retained_before=expected_q1))
            before={str(p):c.identity(p.stat()) for p in (old,old.parent,q1,q1.parent)}
            with patch.object(c,"helper",return_value=backend):
                observed=c.preserve_snapshots(original,receipt,self.guard)
            self.assertTrue(observed["old_trees_preserved"])
            self.assertTrue(observed["q1_records_preserved"])
            self.assertEqual(before,{str(p):c.identity(p.stat()) for p in (old,old.parent,q1,q1.parent)})

    def test_no_argument_entry_is_blocked_and_creates_nothing(self):
        result=subprocess.run([sys.executable,"-I","-B",c.__file__],cwd=self.root,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,3);self.assertEqual(json.loads(result.stdout)["status"],"BLOCKED")
        self.assertEqual(list(self.root.iterdir()),[])


class ClocksAndPacking(unittest.TestCase):
    boot="12345678-1234-1234-1234-123456789abc"
    def window(self):
        anchor=d.make_clock_anchor(host_issued_ns=100*d.NS,host_deadline_ns=400*d.NS,host_probe_send_ns=103*d.NS,
            host_probe_receive_ns=107*d.NS,guest_boot_id=self.boot,guest_sample_ns=900*d.NS,expected_boot_id=self.boot)
        envelope=d.guest_envelope(anchor,attempt_id="syntheticretry01",guest_boot_id=self.boot,guest_now_ns=901*d.NS)
        return anchor,envelope

    def test_collection_uses_original_outer_bound_after_preparation_finished(self):
        anchor,envelope=self.window();now=1173*d.NS
        self.assertEqual(c.fixed_envelope(anchor,envelope,"syntheticretry01",boot_id=self.boot,now_ns=now),1189*d.NS)
        self.assertEqual(c.fixed_envelope(None,envelope,"syntheticretry01",boot_id=self.boot,now_ns=now,
            anchor_sha256=d.sha(d.encoded(anchor))),1189*d.NS)
        for bad in (1189*d.NS,1192*d.NS):
            with self.assertRaisesRegex(ValueError,"WINDOW_EXPIRED"):
                c.fixed_envelope(anchor,envelope,"syntheticretry01",boot_id=self.boot,now_ns=bad)
        with self.assertRaisesRegex(ValueError,"ANCHOR_DIGEST"):
            c.fixed_envelope(None,envelope,"syntheticretry01",boot_id=self.boot,now_ns=now,anchor_sha256="f"*64)
        for field in ("deadline_ns","preparation_deadline_ns","guest_outer_deadline_ns","stop_ns"):
            changed={**envelope,field:envelope[field]+d.NS}
            with self.subTest(field=field),self.assertRaises(ValueError):
                c.fixed_envelope(anchor,changed,"syntheticretry01",boot_id=self.boot,now_ns=now)

    def test_oversize_wire_preserves_hashes_and_explicitly_omits_content(self):
        raw=os.urandom(100000)
        value=dict(complete=True,attempt_id="syntheticretry01",files=[dict(path="/synthetic/result",kind="file",
            sha256=c.sha(raw),content_base64=base64.b64encode(raw).decode())])
        report=c.bundle_report(value,output_limit=16384)
        self.assertLessEqual(len(c.encoded(report)),16384);self.assertEqual(report["status"],"INCOMPLETE")
        retained=json.loads(gzip.decompress(base64.b64decode(report["bundle"]["data"])))
        self.assertEqual(retained["files"][0]["sha256"],c.sha(raw))
        self.assertEqual(retained["files"][0]["content_omitted"],"WIRE_OUTPUT_LIMIT")
        self.assertNotIn("content_base64",retained["files"][0])
        self.assertFalse(report["q2_accepted"])

    def test_service_parse_preserves_actual_nonzero_capture_and_duplicates_fail(self):
        value=dict(complete=True,returncode=0,stderr_base64="",stdout_base64=base64.b64encode(
            b"Id=one.service\nMainPID=0\n\nId=two.slice\nActiveState=active\n").decode())
        self.assertEqual(set(c.rows(value)),{"one.service","two.slice"})
        changed={**value,"returncode":1}
        with self.assertRaisesRegex(ValueError,"SERVICE_CAPTURE"):c.rows(changed)
        value["stdout_base64"]=base64.b64encode(b"Id=one.service\nId=two.service\n").decode()
        with self.assertRaisesRegex(ValueError,"SERVICE_PROPERTIES"):c.rows(value)

    @unittest.skipUnless(os.name=="posix","POSIX finite client")
    def test_actual_read_command_nonzero_exit_and_two_eofs_retained(self):
        end=time.clock_gettime_ns(time.CLOCK_BOOTTIME)+3*d.NS
        value=c.command([sys.executable,"-I","-B","-c","import os;os.write(2,b'diagnostic failure');os._exit(2)"],
                        guard=lambda:None,deadline_ns=end)
        self.assertTrue(value["complete"]);self.assertEqual(value["returncode"],2)
        self.assertEqual(value["eof"],["stderr","stdout"])
        self.assertEqual(base64.b64decode(value["stderr_base64"]),b"diagnostic failure")


if __name__=="__main__":unittest.main()

"""Selected read-only host export: real local files, modeled guest admission.

No test provisions host identities, quota, mounts or systemd objects.
"""
import copy
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

PATH = Path(__file__).parent / "e3_host/q2_host_export.py"
spec = importlib.util.spec_from_file_location("_q2_host_export_tests", PATH)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
REVISION = "a" * 40
BOOT = "11111111-2222-3333-4444-555555555555"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def configuration(base):
    authority = encoded(dict(schema="fixture-test", note="selected source only"))
    install = {}
    for role in m.ROLES:
        install[role + "_path"] = "/synthetic/bin/" + ("worker.py" if role == "worker" else role)
        install[role + "_sha256"] = "f" * 64
    install["package_files"] = dict.fromkeys(("admission.py", "protected_inputs.py", "supervision.py"), "e"*64)
    manifest = dict(schema="local-hand-quota-q1-manifest/v1", authority_digest=m.sha(authority),
        installation_digest=m.sha(encoded(install)), source_commit=REVISION, boot_id=BOOT, epoch="b"*32,
        query_uid=0, query_euid=0, abi=dict(fsxattr_bytes=28, dqblk_bytes=72, qstatv_bytes=160),
        cgroup_parent="/lhqtest.slice", max_query_ns=1000000,
        slots=[dict(ref="sample", generation="c"*32, path="/synthetic/retained", filesystem="ext4",
            filesystem_uuid=BOOT, root=dict(device=7, inode=17, uid=12001, gid=12002, mode=stat.S_IFDIR|0o700),
            project_id=31001, xflags=512, hard_bytes=1048576)])
    manifest_raw = encoded(manifest)
    runtime = dict(schema="local-hand-quota-runtime/v1", **install, manifest_path=base + "/manifest.json",
        manifest_digest=m.sha(manifest_raw), query_slice="lhqtest.slice", cgroup_parent_device=7,
        cgroup_parent_inode=22, initial_userns_device=4, initial_userns_inode=1)
    storage = {role: dict(path="/synthetic/"+role, device=7, inode=30+index, owner_uid=0)
               for index, role in enumerate(("journal", "evidence"))}
    files = {"authority.json": authority, "manifest.json": manifest_raw, "runtime.json": encoded(runtime),
             "storage.json": encoded(storage)}
    # Original Q1 seal does not need to list authority separately: manifest binds it.
    files["SHA256SUMS"] = b"".join((m.sha(raw) + "  " + base + "/" + name + "\n").encode()
                                    for name, raw in files.items() if name != "authority.json")
    return {base + "/" + name: raw for name, raw in files.items()}


class DefaultTests(unittest.TestCase):
    def test_missing_explicit_input_is_blocked_before_host_access(self):
        proc = subprocess.run([sys.executable, "-I", "-B", str(PATH)], capture_output=True, timeout=10)
        self.assertEqual(3, proc.returncode); self.assertEqual(b"", proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual("EXPLICIT_PRIVATE_INPUTS_REQUIRED", result["reason"])
        self.assertFalse(result["q2_accepted"]); self.assertFalse(result["fixture_generated"])

    def test_host_rejection_never_reads_q1_configuration(self):
        reader = mock.Mock()
        with mock.patch.object(m, "host", side_effect=ValueError("HOSTNAME_MISMATCH")):
            result = m.export("/synthetic/q1", REVISION, "fixture-guest", reader)
        reader.read.assert_not_called(); reader.directory.assert_not_called()
        self.assertEqual("BLOCKED", result["status"])

    def test_json_duplicate_floats_complexity_and_boolean_numbers_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":1.0}', b'{"a":NaN}',
                    b'{"a":' + b'['*14 + b'0' + b']'*14 + b'}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): m.document(raw)
        with self.assertRaises(ValueError): m.number(True)

    def test_source_head_is_metadata_only_and_never_resolves_refs(self):
        reader = mock.Mock(); reader.read.return_value = REVISION.encode() + b"\n"
        result = m.source_head(reader, "/synthetic/source", REVISION)
        self.assertFalse(result["source_bytes_verified"]); self.assertFalse(result["clean_tree_verified"])
        reader.read.return_value = b"ref: refs/heads/main\n"
        with self.assertRaises(ValueError): m.source_head(reader, "/synthetic/source", REVISION)
        self.assertTrue(all(call.args[0].endswith("/.git/HEAD") for call in reader.read.call_args_list))

    def test_config_reads_only_fixed_members_ignoring_unselected_seal_path(self):
        base = "/synthetic/config"; files = configuration(base)
        files[base + "/SHA256SUMS"] += ("d"*64 + "  /private/unrelated\n").encode()
        reader = mock.Mock(); reader.read.side_effect = lambda name, limit: files[name]
        values, summary = m.config(reader, base, REVISION)
        self.assertEqual("Q1_CONFIG_BYTES_LINKED_ONLY", summary["status"])
        self.assertFalse(summary["q2_reusable_allocation"])
        self.assertEqual(set(files), {call.args[0] for call in reader.read.call_args_list})
        self.assertEqual("sample", values["manifest.json"]["slots"][0]["ref"])

    def test_config_checksum_revision_and_authority_mismatches_fail(self):
        base = "/synthetic/config"
        for fault in ("checksum", "revision", "authority"):
            files = configuration(base)
            if fault == "checksum": files[base+"/storage.json"] += b" "
            if fault == "authority": files[base+"/authority.json"] = b"{}"
            reader = mock.Mock(); reader.read.side_effect = lambda name, limit: files[name]
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                m.config(reader, base, "b"*40 if fault == "revision" else REVISION)

    def test_mount_selection_longest_device_match_and_ambiguity(self):
        device = os.makedev(8, 1) if hasattr(os, "makedev") else None
        if device is None: self.skipTest("POSIX device encoding")
        rows = m.mounts(b"1 0 8:1 / / rw - ext4 /dev/fake rw\n2 1 8:1 / /synthetic rw - ext4 /dev/fake rw\n")
        self.assertEqual("/synthetic", m.selected_mount(rows, "/synthetic/retained", device)["mountpoint"])
        with self.assertRaisesRegex(ValueError, "MOUNT_AMBIGUOUS"):
            m.selected_mount(rows + [rows[1]], "/synthetic/retained", device)
        with self.assertRaisesRegex(ValueError, "MOUNT_DEVICE_MISMATCH"):
            m.selected_mount(rows, "/synthetic/retained", os.makedev(8, 2))

    def test_accounts_export_only_selected_identity_without_password_or_home(self):
        reader = mock.Mock(); reader.read.return_value = b"guest:x:12001:12002:Private person:/private/home:/bin/false\nother:x:99:99::/:/bin/false\n"
        self.assertEqual([dict(name="guest", uid=12001, gid=12002)], m.accounts(reader, {12001}))
        with self.assertRaisesRegex(ValueError, "ACCOUNT_MISSING_OR_ALIAS"): m.accounts(reader, {7})

    def test_missing_config_groups_are_aggregated_without_replay(self):
        reader = mock.Mock(); reader.used = 0
        reader.directory.return_value = dict(device=7, inode=1, uid=0, gid=0, mode=stat.S_IFDIR|0o700)
        reader.kernel.return_value = b"1 0 8:1 / / rw - ext4 /dev/fake rw\n"
        reader.read.side_effect = FileNotFoundError("private path must not echo")
        with mock.patch.object(m, "host", return_value=dict(boot_id=BOOT)):
            result = m.export("/synthetic/q1", REVISION, "fixture-guest", reader)
        checks = {row["check"]: row for row in result["checks"]}
        self.assertEqual("BLOCKED", checks["original_config"]["status"])
        self.assertEqual("BLOCKED", checks["revision_config"]["status"])
        self.assertEqual("PARTIAL", result["status"])
        self.assertEqual({"NOT_DELIVERED"}, set(result["q2_input_groups"].values()))
        self.assertNotIn("private path", json.dumps(result))
        self.assertFalse(result["complete_q1_domain_inventory"])

    def test_full_selected_export_keeps_q2_missing_and_does_not_publish_config_payloads(self):
        root = "/synthetic/q1"; revised = root + "/revisions/" + REVISION
        files = {**configuration(root+"/config"), **configuration(revised+"/config")}
        reader = mock.Mock(); reader.used = 512
        reader.directory.return_value = dict(device=7, inode=1, uid=0, gid=0, mode=stat.S_IFDIR|0o700)
        reader.kernel.return_value = b"1 0 8:1 / / rw - ext4 /dev/fake rw\n"
        reader.read.side_effect = lambda name, limit: files[name]
        with mock.patch.object(m, "host", return_value=dict(boot_id=BOOT)), \
             mock.patch.object(m, "source_head", return_value=dict(clean_tree_verified=False)), \
             mock.patch.object(m, "program", return_value=dict(executed=False)), \
             mock.patch.object(m, "cgroup", return_value=dict(q2_parent_admitted=False)), \
             mock.patch.object(m, "root_fact", return_value=dict(path="/synthetic/retained")), \
             mock.patch.object(m, "accounts", return_value=[dict(uid=12001, gid=12002, name="sample")]):
            result = m.export(root, REVISION, "fixture-guest", reader)
        self.assertEqual("EXPORTED", result["status"])
        self.assertEqual("Q1_EVIDENCE_ONLY", result["source_config_status"])
        self.assertEqual({"NOT_DELIVERED"}, set(result["q2_input_groups"].values()))
        self.assertNotIn("selected source only", json.dumps(result))
        self.assertNotIn("manifest_path", json.dumps(result))
        self.assertFalse(result["q2_accepted"]); self.assertFalse(result["q3_accepted"])

    def test_output_limit_fails_cleanly_without_partial_large_payload(self):
        result = m.report(); result.update(status="EXPORTED", unexpected="x"*m.OUTPUT_LIMIT)
        output = io.StringIO()
        with mock.patch.object(m, "export", return_value=result), mock.patch.object(m.sys, "stdout", output), \
             mock.patch.object(m.sys, "flags", SimpleNamespace(isolated=True)), \
             mock.patch.object(m.sys, "dont_write_bytecode", True):
            rc = m.main(["--q1-root", "/synthetic/q1", "--q1-revision", REVISION, "--expected-hostname", "fixture-guest"])
        self.assertEqual(3, rc)
        self.assertLess(len(output.getvalue().encode()), m.OUTPUT_LIMIT)
        self.assertEqual("OUTPUT_LIMIT", json.loads(output.getvalue())["reason"])


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux descriptor and guest guards")
class LocalReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.reader = m.Reader()

    @staticmethod
    def local_open(name, *, directory=False, owner=0):
        return os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
                       | (os.O_DIRECTORY if directory else 0))

    def test_fifo_symlink_oversize_are_rejected_without_blocking(self):
        fifo = self.root/"fifo"; os.mkfifo(fifo)
        file = self.root/"plain"; file.write_bytes(b"abcd")
        link = self.root/"link"; link.symlink_to(file)
        with mock.patch.object(self.reader, "opened", self.local_open):
            with self.assertRaises(ValueError): self.reader.read(str(fifo), 32)
            with self.assertRaises(OSError): self.reader.read(str(link), 32)
            with self.assertRaises(ValueError): self.reader.read(str(file), 3)
        self.assertEqual(b"abcd", file.read_bytes())

    def test_hardlinked_and_setid_files_cannot_supply_export_data(self):
        file = self.root/"plain"; file.write_bytes(b"abcd")
        alias = self.root/"alias"; os.link(file, alias)
        with mock.patch.object(self.reader, "opened", self.local_open):
            with self.assertRaises(ValueError): self.reader.read(str(file), 32)
            alias.unlink(); file.chmod(0o4644)
            with self.assertRaises(ValueError): self.reader.read(str(file), 32)

    def test_guest_hints_accept_qemu_standard_pc_without_claiming_host_authority(self):
        data = {"/proc/1/comm": b"systemd\n", "/sys/class/dmi/id/sys_vendor": b"QEMU\n",
                "/sys/class/dmi/id/product_name": b"Standard PC (Q35 + ICH9, 2009)\n",
                "/proc/sys/kernel/random/boot_id": BOOT.encode(), "/proc/sys/kernel/osrelease": b"test-kernel\n"}
        reader = mock.Mock(); reader.kernel.side_effect = lambda name: data[name]
        with mock.patch.object(m.os, "getuid", return_value=0), mock.patch.object(m.os, "geteuid", return_value=0), \
             mock.patch.object(m.os, "getgid", return_value=0), mock.patch.object(m.os, "getegid", return_value=0), \
             mock.patch.object(m.socket, "gethostname", return_value="fixture-guest"), \
             mock.patch.object(m.os, "stat", return_value=SimpleNamespace(st_dev=4, st_ino=1)):
            value = m.host(reader, "fixture-guest")
            self.assertEqual("MATCHING_DECLARED_GUEST_HINTS_ONLY", value["guest_identity"])
            data["/sys/class/dmi/id/sys_vendor"] = b"physical-machine\n"
            with self.assertRaisesRegex(ValueError, "ISOLATED_GUEST_HINT_REQUIRED"): m.host(reader, "fixture-guest")

    def test_protected_reader_refuses_unprotected_temporary_path(self):
        file = self.root/"plain"; file.write_bytes(b"x")
        # A non-root CI runner cannot open root-owned '/' with O_NOATIME.
        # Root instead reaches and rejects the writable temporary ancestry.
        with self.assertRaises((ValueError, PermissionError)) as raised:
            self.reader.read(str(file), 8)
        if isinstance(raised.exception, PermissionError):
            self.assertEqual(errno.EPERM, raised.exception.errno)
        else:
            self.assertEqual("UNPROTECTED_OBJECT", str(raised.exception))
        self.assertEqual(0, self.reader.used)

    def test_protected_reader_refuses_modeled_root_owned_writable_ancestor(self):
        ancestor = SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o777)
        with mock.patch.object(m.os, "open", side_effect=[100, 101]) as opened, \
             mock.patch.object(m.os, "close") as closed, \
             mock.patch.object(m.os, "fstat", return_value=ancestor), \
             mock.patch.object(self.reader, "read_fd") as read:
            with self.assertRaisesRegex(ValueError, "^UNPROTECTED_OBJECT$"):
                self.reader.read("/writable/secret", 8)
        self.assertEqual(2, opened.call_count)
        self.assertEqual("/", opened.call_args_list[0].args[0])
        self.assertEqual("writable", opened.call_args_list[1].args[0])
        self.assertEqual([mock.call(100), mock.call(101)], closed.call_args_list)
        read.assert_not_called()

    def test_protected_reader_does_not_retry_without_noatime_permission(self):
        denied = PermissionError(errno.EPERM, "synthetic no-atime denial")
        with mock.patch.object(m.os, "open", side_effect=denied) as opened, \
             mock.patch.object(self.reader, "read_fd") as read:
            with self.assertRaises(PermissionError) as raised:
                self.reader.read("/synthetic/secret", 8)
        self.assertIs(denied, raised.exception)
        opened.assert_called_once()
        self.assertTrue(opened.call_args.args[1] & os.O_NOATIME)
        read.assert_not_called()

    def test_noncanonical_path_is_rejected_before_open(self):
        for name in ("relative", "//path", "/tmp/../etc/passwd", "/"):
            with self.subTest(path=name), mock.patch.object(m.os, "open") as opened:
                with self.assertRaises(ValueError): self.reader.opened(name)
                opened.assert_not_called()

    def test_program_hash_streams_large_binary_and_accepts_source_role(self):
        binary = self.root/"program"; raw = b"\x7fELF" + b"x"*(3*1024*1024)
        binary.write_bytes(raw); binary.chmod(0o755)
        script = self.root/"worker.py"; script.write_bytes(b"# never execute\n")
        runtime = dict(python_path=str(binary), python_sha256=m.sha(raw), worker_path=str(script),
                       worker_sha256=m.sha(script.read_bytes()))
        before = {name: p.stat().st_mtime_ns for name, p in (("binary", binary), ("script", script))}
        with mock.patch.object(self.reader, "opened", self.local_open):
            result = m.program(self.reader, runtime, "python")
            self.assertEqual(len(raw), result["size"]); self.assertFalse(result["executed"])
            self.assertFalse(m.program(self.reader, runtime, "worker")["executed"])
        self.assertEqual(before["binary"], binary.stat().st_mtime_ns)
        self.assertEqual(before["script"], script.stat().st_mtime_ns)

    def test_aggregate_limit_and_changed_file_fingerprint_refuse(self):
        file = self.root/"plain"; file.write_bytes(b"abcd")
        with mock.patch.object(self.reader, "opened", self.local_open), mock.patch.object(m, "READ_LIMIT", 3):
            with self.assertRaisesRegex(ValueError, "AGGREGATE_READ_LIMIT"): self.reader.read(str(file), 8)
        self.reader.used = 0
        fd = self.local_open(str(file)); self.addCleanup(os.close, fd)
        before = os.fstat(fd); after = SimpleNamespace(**{key: getattr(before, key) for key in
            ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")})
        after.st_ino += 1
        with mock.patch.object(m.os, "fstat", side_effect=[before, after]):
            with self.assertRaisesRegex(ValueError, "FILE_LIMIT_OR_CHANGED"): self.reader.read_fd(fd, 8)

    def test_guest_guard_rejects_wrong_hostname_before_any_file_read(self):
        reader = mock.Mock()
        with mock.patch.object(m.os, "getuid", return_value=0), mock.patch.object(m.os, "geteuid", return_value=0), \
             mock.patch.object(m.os, "getgid", return_value=0), mock.patch.object(m.os, "getegid", return_value=0), \
             mock.patch.object(m.socket, "gethostname", return_value="another-machine"):
            with self.assertRaisesRegex(ValueError, "HOSTNAME_MISMATCH"): m.host(reader, "fixture-guest")
        reader.kernel.assert_not_called()


if __name__ == "__main__":
    unittest.main()

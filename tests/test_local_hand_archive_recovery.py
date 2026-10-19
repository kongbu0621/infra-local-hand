"""Consumer recovery through installed public Ledger snapshot/export interfaces."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid
from unittest import mock

import test_local_hand_artifact_archive as fixtures
from local_hand_jobs import artifact_archive as consumer


@unittest.skipUnless(sys.platform == 'linux' and fixtures.HAS_LEDGER, 'Linux and installed Ledger required')
class ArchiveRecoveryTests(fixtures.BundleFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        import infra_artifact_ledger
        self.api = infra_artifact_ledger
        self.store = self.root / 'archive'
        self.status = dict(operation_id=fixtures.OP, request_digest='a'*64,
                           lifecycle='TERMINAL', phase='EXITED', outcome='SUCCEEDED', evidence='SEALED',
                           observed_at=1.5, seal_refs=[{k:self.descriptor[k] for k in ('seal_id','seal_sha256')}])
        self.status_path = self.root/'status.json'
        self.save_status()
    save_status = fixtures.ArchiveTests.save_status
    archive = fixtures.ArchiveTests.archive
    resume = fixtures.ArchiveTests.resume
    read = fixtures.ArchiveTests.read
    verification = fixtures.ArchiveTests.verification

    def tree(self, root=None):
        return {str(p.relative_to(root or self.store)): p.read_bytes()
                for p in (root or self.store).rglob('*') if p.is_file()}

    def prepare(self):
        from infra_artifact_ledger import recovery
        self.original_result = self.archive()
        self.original_store = self.store
        self.original_files = self.tree()
        self.checkpoint = consumer.recovery_checkpoint(self.store)
        self.assertEqual(self.tree(), self.original_files)
        self.checkpoint_file = self.root / 'checkpoint.json'
        self.checkpoint_file.write_bytes(consumer._json(self.checkpoint))
        snapshots = self.root / 'snapshots'; snapshots.mkdir(mode=0o700)
        scratch = self.root / 'scratch'; scratch.mkdir(mode=0o700)
        snapshot = recovery.create(db=self.store/'ledger.sqlite', output_root=snapshots,
                                   snapshot_id=uuid.uuid4().hex, source_commit='1'*40)['data']
        target = self.root / 'restored-ledger'
        restored = recovery.restore(snapshot=Path(snapshot['snapshot_path']), target_dir=target,
                                    expected_manifest_sha256=snapshot['manifest_sha256'], scratch_parent=scratch)
        self.database_digest = restored['data']['database_sha256']
        self.store = self.root / 'restored-archive'
        shutil.copytree(self.original_store, self.store)
        (self.store/'ledger.sqlite').unlink()
        shutil.copy2(target/'ledger.sqlite', self.store/'ledger.sqlite')
        self.before_binding = self.tree()

    def bind(self, **overrides):
        values = dict(checkpoint_path=self.checkpoint_file,
                      expected_checkpoint_sha256=self.checkpoint['checkpoint_sha256'],
                      expected_database_sha256=self.database_digest)
        values.update(overrides)
        return consumer.bind_restored(self.store, **values)

    def test_snapshot_restore_old_receipt_and_new_task(self):
        self.prepare()
        with self.assertRaises(consumer.ArchiveError): self.resume()
        with self.assertRaises(consumer.ArchiveError): self.read(self.original_result)
        with self.api.open(self.store/'ledger.sqlite') as ledger:
            ledger_type = type(ledger)
        with mock.patch.object(ledger_type, 'execute', side_effect=AssertionError('binding must not execute')):
            result = self.bind()
            self.assertFalse(result['reused'])
            self.assertTrue(self.bind()['reused'])
        after = self.tree()
        self.assertEqual({p: after[p] for p in self.before_binding}, self.before_binding)
        self.assertEqual(len(set(after)-set(self.before_binding)), 1)
        resumed = self.resume()
        self.assertTrue(resumed['reused'])
        self.assertEqual(resumed['recorded_at'], self.original_result['recorded_at'])
        self.assertEqual(resumed['version_id'], self.original_result['version_id'])
        self.assertEqual(self.tree(), after)
        self.assertTrue(self.read(resumed)['content_verified'])
        self.assertTrue(self.archive()['reused'])
        # A distinct producer represents a separate synthetic completed source.
        new = consumer.archive_result(self.store, producer='test:next-source', status_path=self.status_path,
                                      status_sha256=self.digest, evidence_dir=self.evidence)
        self.assertNotEqual(new['version_id'], resumed['version_id'])
        self.assertTrue(self.read(new, 'new-read')['content_verified'])
        self.assertEqual(self.verification()['counts']['versions'], 2)
        self.assertEqual(self.tree(self.original_store), self.original_files)

    def test_bad_checkpoint_database_and_metadata_never_publish_binding(self):
        self.prepare()
        for changes in ({'expected_checkpoint_sha256':'0'*64}, {'expected_database_sha256':'0'*64}):
            with self.subTest(changes=changes):
                with self.assertRaises(consumer.ArchiveError): self.bind(**changes)
                self.assertEqual(self.tree(), self.before_binding)
        task = next(self.store.glob('task-*'))
        original = (task/'create.json').read_bytes()
        (task/'create.json').write_bytes(original+b' ')
        changed = self.tree()
        with self.assertRaises(consumer.ArchiveError): self.bind()
        self.assertEqual(self.tree(), changed)
        (task/'create.json').write_bytes(original)
        # A well-formed but wrong Ledger is not accepted even with its actual hash.
        wrong = self.root/'wrong.sqlite'
        with self.api.initialize(wrong): pass
        original_db = (self.store/'ledger.sqlite').read_bytes()
        (self.store/'ledger.sqlite').write_bytes(wrong.read_bytes())
        changed = self.tree()
        with self.assertRaises(consumer.ArchiveError):
            self.bind(expected_database_sha256=hashlib.sha256(wrong.read_bytes()).hexdigest())
        self.assertEqual(self.tree(), changed)
        (self.store/'ledger.sqlite').write_bytes(original_db)
        self.assertEqual(self.bind()['status'], 'RESTORED_BOUND')

    def test_binding_publication_and_response_loss_are_retryable(self):
        self.prepare()
        original = consumer._publish_files
        def publish_then_fail(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError('response lost after publication')
        with mock.patch.object(consumer, '_publish_files', side_effect=publish_then_fail):
            with self.assertRaises(OSError): self.bind()
        preserved = self.tree()
        self.assertTrue(self.bind()['reused'])
        self.assertEqual(self.tree(), preserved)
        self.assertTrue(self.resume()['reused'])

    def test_partial_archive_checkpoint_preserves_pending_original_operation(self):
        self.archive()
        with self.api.open(self.store/'ledger.sqlite') as ledger:
            ledger_type = type(ledger)
        original = ledger_type.execute
        def lose_append(handle, raw, **kwargs):
            if json.loads(raw)['operation_kind'] == 'append_version':
                raise OSError('append not started')
            return original(handle, raw, **kwargs)
        with mock.patch.object(ledger_type, 'execute', new=lose_append):
            with self.assertRaises(OSError):
                consumer.archive_result(self.store, producer='test:partial', status_path=self.status_path,
                                        status_sha256=self.digest, evidence_dir=self.evidence)
        before = self.tree()
        with mock.patch.object(ledger_type, 'execute', side_effect=AssertionError('checkpoint must not complete tasks')):
            checkpoint = consumer.recovery_checkpoint(self.store)
        self.assertEqual(self.tree(), before)
        copied = self.root/'copy';shutil.copytree(self.store,copied)
        path = self.root/'partial-checkpoint.json';path.write_bytes(consumer._json(checkpoint))
        consumer.bind_restored(copied, checkpoint_path=path, expected_checkpoint_sha256=checkpoint['checkpoint_sha256'],
                               expected_database_sha256=hashlib.sha256((copied/'ledger.sqlite').read_bytes()).hexdigest())
        result = consumer.resume_archive(copied, producer='test:partial', operation_id=fixtures.OP)
        self.assertFalse(result['reused'])
        self.assertTrue(consumer.resume_archive(copied, producer='test:partial', operation_id=fixtures.OP)['reused'])
        self.assertEqual(self.tree(), before)

    def test_missing_lock_sidecars_and_replaced_binding_are_not_bypassed(self):
        self.prepare()
        for suffix in ('-journal','-wal','-shm'):
            path = Path(str(self.store/'ledger.sqlite')+suffix);path.write_bytes(b'kept')
            with self.subTest(suffix=suffix):
                before = self.tree()
                with self.assertRaises(consumer.ArchiveError): self.bind()
                self.assertEqual(self.tree(),before)
            path.unlink()
        self.bind()
        lock = self.store/'.archive.lock';lock.rename(self.store/'retained-lock')
        with self.assertRaises(FileNotFoundError): self.read(self.original_result)
        self.assertFalse(lock.exists())
        (self.store/'retained-lock').rename(lock)
        bound_db = self.store/'ledger.sqlite';old = self.store/'kept-db'
        bound_db.rename(old);shutil.copy2(old,bound_db)
        with self.assertRaises(consumer.ArchiveError): self.resume()
        bound_db.unlink();old.rename(bound_db)
        self.assertTrue(self.resume()['reused'])

    def test_second_restoration_preserves_prior_bindings(self):
        self.prepare();self.bind();self.resume()
        checkpoint = consumer.recovery_checkpoint(self.store)
        path = self.root/'next-checkpoint.json';path.write_bytes(consumer._json(checkpoint))
        copied = self.root/'second-restore';shutil.copytree(self.store,copied)
        before = self.tree(copied)
        consumer.bind_restored(copied, checkpoint_path=path, expected_checkpoint_sha256=checkpoint['checkpoint_sha256'],
                               expected_database_sha256=hashlib.sha256((copied/'ledger.sqlite').read_bytes()).hexdigest())
        after = self.tree(copied)
        self.assertEqual({p:after[p] for p in before},before)
        self.assertEqual(len(set(after)-set(before)),1)
        self.assertTrue(consumer.resume_archive(copied,producer='test:local-hand',operation_id=fixtures.OP)['reused'])

    def test_read_only_lock_and_real_cli_checkpoint(self):
        original = self.archive()
        lock = self.store/'.archive.lock';lock.chmod(0o400)
        before = self.tree()
        script = 'import sys;sys.path.insert(0,sys.argv.pop(1));from local_hand_jobs.artifact_archive import main;raise SystemExit(main())'
        base = [sys.executable,'-I','-B','-c',script,str(Path(consumer.__file__).parents[1])]
        response = subprocess.run(base+['recovery-checkpoint','--store',str(self.store)],capture_output=True,timeout=20)
        self.assertEqual(response.returncode,0,response.stdout+response.stderr)
        self.assertEqual(json.loads(response.stdout)['status'],'RECOVERY_CHECKPOINT')
        response = subprocess.run(base+['read','--store',str(self.store),'--artifact-id',original['artifact_id'],
                                       '--version-id',original['version_id'],'--output',str(self.root/'cli-read')],capture_output=True,timeout=20)
        self.assertEqual(response.returncode,0,response.stdout+response.stderr)
        self.assertEqual(self.tree(),before)
        import fcntl
        with lock.open('rb') as held:
            fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(consumer.ArchiveError) as rejected:
                consumer.recovery_checkpoint(self.store)
            self.assertEqual(rejected.exception.code,'BUSY')
        lock.chmod(0o600)
        self.assertTrue(self.resume()['reused'])

    def test_binding_before_publication_failure_can_continue(self):
        self.prepare()
        with mock.patch.object(consumer,'_publish_files',side_effect=OSError('not published')):
            with self.assertRaises(OSError):self.bind()
        self.assertEqual(self.tree(),self.before_binding)
        self.assertFalse(self.bind()['reused'])

    def test_checkpoint_rejects_confirmed_history_loss(self):
        self.archive()
        reservation = next(self.store.glob('request-task-*'))
        with self.api.open(self.store/'ledger.sqlite') as ledger:ledger_type=type(ledger)
        original = ledger_type.get_operation
        def missing_create(handle, scope, kind, key):
            if kind=='create_artifact':raise self.api.LedgerError('NOT_FOUND','synthetic lost operation')
            return original(handle,scope,kind,key)
        # Even if both confirmations are lost, a committed append implies its
        # original create operation must exist; checkpoint must not bless loss.
        shutil.rmtree(reservation/'create_artifact');shutil.rmtree(reservation/'append_version')
        before=self.tree()
        with mock.patch.object(ledger_type,'get_operation',new=missing_create):
            with self.assertRaises(consumer.ArchiveError):consumer.recovery_checkpoint(self.store)
        self.assertEqual(self.tree(),before)


if __name__ == '__main__': unittest.main()

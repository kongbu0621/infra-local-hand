"""Real retained ledger/evidence checks with synthetic mount observations."""
import copy
from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from admin.local_hand_system_manager import retained_reader as reader
from local_hand_jobs import evidence as evidence_module
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES
from local_hand_jobs.evidence import EvidenceStore, EvidenceError
from local_hand_jobs.policy import Policy
from local_hand_jobs.state import StateStore
from test_local_hand_jobs_policy import policy_fixture
from test_local_hand_jobs_evidence import EvidenceFixture, OP


class RetainedFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = EvidenceFixture(self.root)
        self.store = self.root / 'store'
        info = self.store.stat()
        self.old = dict(device=info.st_dev + 1, inode=info.st_ino, uid=info.st_uid)
        self.fs = dict(mountpoint=str(self.root), uuid='12345678-1234-1234-1234-123456789abc',
                       backing_file='/var/lib/synthetic/volume.ext4')

    def rebound(self):
        return reader.RetainedEvidenceStore(self.store, original_identity=self.old, filesystem=self.fs,
            snapshot_provider=Mock(side_effect=AssertionError('No writer')),
            register_seal=Mock(side_effect=AssertionError('No registration')),
            is_registered=lambda sid, digest: self.fixture.registered.get(sid) == digest,
            authorize=self.fixture.authorize)

    def seal_on_previous_device(self, device=None):
        # Record the pre-reboot device in the authenticated seal as well as the
        # admitted root. Changing only the root pin misses retained-file reads.
        device = self.old['device'] if device is None else device
        original = evidence_module._same
        def previous(info):
            return (device, *original(info)[1:])
        with patch.object(evidence_module, '_same', side_effect=previous):
            return self.fixture.sealed()

    def test_sealed_file_devices_rebind_without_rewriting_original_seals(self):
        self.seal_on_previous_device()
        before = {str(p): p.read_bytes() for p in self.store.rglob('*') if p.is_file()}
        with patch.object(reader, 'observe_filesystem'):
            rebound = self.rebound()
            artifacts = rebound.manifest(OP, principal='reader')['artifacts']
            for artifact in artifacts:
                with self.subTest(role=artifact['role']):
                    result = rebound.read_chunk(artifact['artifact_id'],
                        expected_sha256=artifact['sha256'], principal='reader')
                    raw = base64.b64decode(result['data_base64'])
                    self.assertTrue(result['eof'])
                    self.assertEqual(artifact['size'], len(raw))
                    self.assertEqual(artifact['sha256'], hashlib.sha256(raw).hexdigest())
                    if artifact['role'] == 'seal':
                        identities = json.loads(raw)['artifact_identities']
                        self.assertTrue(all(value[0] == self.old['device'] for value in identities.values()))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.store.rglob('*') if p.is_file()})

    def test_rebound_file_still_rejects_changed_content(self):
        artifact = self.seal_on_previous_device()
        with patch.object(reader, 'observe_filesystem'):
            rebound = self.rebound()
            path = self.store / artifact['seal_id'] / 'evidence.zip'
            raw = path.read_bytes()
            path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            with self.assertRaises((JobError, EvidenceError)):
                rebound.read_chunk(artifact['artifact_id'], expected_sha256=artifact['sha256'], principal='reader')

    def test_rebinding_preserves_each_other_sealed_file_identity_field(self):
        artifact = self.seal_on_previous_device()
        original_record = EvidenceStore._record
        with patch.object(reader, 'observe_filesystem'):
            rebound = self.rebound()
            for field in range(1, 8):
                def changed(store, seal_id):
                    value = original_record(store, seal_id)
                    value['artifact_identities']['zip'][field] += 1
                    return value
                with self.subTest(field=field), \
                     patch.object(EvidenceStore, '_record', autospec=True, side_effect=changed):
                    with self.assertRaisesRegex(EvidenceError, 'sealed evidence identity changed'):
                        rebound.read_chunk(artifact['artifact_id'],
                            expected_sha256=artifact['sha256'], principal='reader')

    def test_failed_mount_observation_allows_same_read_retry_without_publication(self):
        artifact = self.seal_on_previous_device()
        before = {str(p): p.read_bytes() for p in self.store.rglob('*') if p.is_file()}
        with patch.object(reader, 'observe_filesystem'):
            rebound = self.rebound()
        with patch.object(reader, 'observe_filesystem', side_effect=OSError('temporary observation failure')):
            with self.assertRaises((JobError, EvidenceError, OSError)):
                rebound.read_chunk(artifact['artifact_id'], expected_sha256=artifact['sha256'], principal='reader')
        with patch.object(reader, 'observe_filesystem'):
            result = rebound.read_chunk(artifact['artifact_id'], expected_sha256=artifact['sha256'], principal='reader')
            self.assertEqual(artifact['sha256'], hashlib.sha256(base64.b64decode(result['data_base64'])).hexdigest())
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.store.rglob('*') if p.is_file()})

    def test_foreign_seal_device_cannot_be_rebound(self):
        artifact = self.seal_on_previous_device(self.old['device'] + 2)
        with patch.object(reader, 'observe_filesystem'):
            rebound = self.rebound()
            with self.assertRaises((JobError, EvidenceError)):
                rebound.read_chunk(artifact['artifact_id'], expected_sha256=artifact['sha256'], principal='reader')

    def test_unchanged_device_keeps_original_file_identity(self):
        self.old['device'] = self.store.stat().st_dev
        artifact = self.fixture.sealed()
        with patch.object(reader, 'observe_filesystem'):
            result = self.rebound().read_chunk(artifact['artifact_id'],
                expected_sha256=artifact['sha256'], principal='reader')
        self.assertEqual(artifact['sha256'], hashlib.sha256(base64.b64decode(result['data_base64'])).hexdigest())

    def test_exact_retained_bytes_after_device_change_and_no_original_mutation(self):
        artifact = self.seal_on_previous_device()
        before = {str(p): p.read_bytes() for p in self.store.rglob('*') if p.is_file()}
        with self.assertRaises(EvidenceError):
            EvidenceStore(self.store, root_identity=self.old,
                snapshot_provider=Mock(), register_seal=Mock(), is_registered=Mock())
        with patch.object(reader, 'observe_filesystem') as observe:
            rebound = self.rebound()
            page = rebound.manifest(OP, principal='reader')
            self.assertEqual(artifact, page['artifacts'][0])
            actual = rebound.read_chunk(artifact['artifact_id'], expected_sha256=artifact['sha256'], principal='reader')
            raw = (self.store / artifact['seal_id'] / 'evidence.zip').read_bytes()
            self.assertEqual(raw, base64.b64decode(actual['data_base64']))
            self.assertEqual(artifact['sha256'], actual['sha256'])
            self.assertGreater(observe.call_count, 3)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.store.rglob('*') if p.is_file()})

    def test_readonly_binding_never_publishes(self):
        with patch.object(reader, 'observe_filesystem'):
            rebound = self.rebound()
            for call in (lambda: rebound.seal(OP), lambda: rebound.publish_only(self.fixture.snapshot)):
                with self.assertRaises(JobError) as failure:
                    call()
                self.assertEqual('UNSUPPORTED', failure.exception.code)
        self.assertEqual([], list(self.store.iterdir()))

    def test_identity_change_rejected_before_mount_probe(self):
        for changed in ('inode', 'uid'):
            with self.subTest(changed), patch.object(reader, 'observe_filesystem') as probe:
                value = dict(self.old)
                value[changed] += 1
                with self.assertRaises((JobError, EvidenceError)):
                    reader.current_pin(self.store, value, self.fs)
                probe.assert_not_called()

    def test_symlink_permissions_missing_and_foreign_replacement_rejected(self):
        with patch.object(reader, 'observe_filesystem'):
            rebound = self.rebound()
            self.store.rename(self.root / 'original')
            for kind in ('missing', 'symlink', 'new-directory', 'public-directory'):
                with self.subTest(kind):
                    if kind == 'symlink':
                        self.store.symlink_to(self.root / 'original', target_is_directory=True)
                    elif kind in ('new-directory', 'public-directory'):
                        self.store.mkdir(mode=0o700 if kind == 'new-directory' else 0o755)
                    with self.assertRaises((JobError, EvidenceError, OSError)):
                        rebound.manifest(OP, principal='reader')
                    if self.store.is_symlink():
                        self.store.unlink()
                    elif self.store.exists():
                        self.store.rmdir()

    def test_mount_is_checked_after_evidence_access(self):
        with patch.object(reader, 'observe_filesystem'):
            rebound = self.rebound()
        original = reader.current_pin
        count = 0
        def change(*args):
            nonlocal count
            count += 1
            value = original(*args)
            if count == 2:
                value['device'] += 1
            return value
        with patch.object(reader, 'observe_filesystem'), patch.object(reader, 'current_pin', side_effect=change):
            with self.assertRaises(JobError):
                with rebound._open_store():
                    pass

    def mount_row(self):
        device = self.store.stat().st_dev
        return dict(source='/dev/loop22', target=self.fs['mountpoint'], fstype='ext4',
                    options='rw,nosuid,nodev,noexec', uuid=self.fs['uuid'],
                    **{'maj:min': f'{os.major(device)}:{os.minor(device)}'})

    def observe_mount(self, row=None, metadata=None):
        row = self.mount_row() if row is None else row
        metadata = [self.fs['backing_file'], '0', '0'] if metadata is None else metadata
        with patch.object(reader, 'protected_backing_parent'), \
             patch.object(reader, 'mount_output', return_value=json.dumps({'filesystems': [row]}).encode()), \
             patch.object(reader, 'small_read', side_effect=metadata):
            return reader.observe_filesystem(self.fs, self.store.stat().st_dev)

    def test_uuid_device_target_type_and_protection_are_all_required(self):
        self.observe_mount()
        for field, value in (('uuid', 'other'), ('maj:min', '7:99'), ('target', '/other'),
                             ('fstype', 'nfs'), ('source', '/dev/sda'),
                             ('options', 'rw,nosuid,nodev'), ('options', None)):
            with self.subTest(field=field, value=value), self.assertRaises(JobError):
                self.observe_mount(dict(self.mount_row(), **{field: value}))

    def test_duplicate_uuid_on_another_image_and_image_ranges_are_rejected(self):
        for metadata in (['/var/lib/other.ext4', '0', '0'], [self.fs['backing_file'], '4096', '0'],
                         [self.fs['backing_file'], '0', '4096']):
            with self.subTest(metadata), self.assertRaises(JobError):
                self.observe_mount(metadata=metadata)

    def test_unprotected_image_parent_rejected(self):
        with self.assertRaises(JobError):
            reader.protected_backing_parent(str(self.root / 'image.ext4'))

    def policy_and_binding(self):
        config = policy_fixture(self.root)
        profile = config['profiles']['fixture']
        profile['bootstrap_slots'] = [dict(slot_id='slot', roots={
            role: dict(path=str(self.root / name / 'a'), device=self.old['device'],
                       inode=200 + index, uid=os.geteuid())
            for index, (role, name) in enumerate((('work', 'work'), ('evidence', 'evidence'), ('temporary', 'temporary')))})]
        profile['bootstrap_evidence_store'] = dict(path=str(self.store), **self.old)
        path = self.root / 'policy.json'
        raw = json.dumps(config).encode()
        path.write_bytes(raw)
        path.chmod(0o600)
        binding = dict(schema=reader.SCHEMA, policy_path=str(path), policy_sha256=hashlib.sha256(raw).hexdigest(),
                       original_root=copy.deepcopy(profile['bootstrap_evidence_store']), filesystem=self.fs)
        return config, path, binding

    def test_binding_to_another_policy_directory_or_admission_is_rejected(self):
        config, path, binding = self.policy_and_binding()
        policy = Policy(config)
        reader.validate(binding, str(path), policy)
        for changed in ('path', 'inode', 'device', 'uid', 'schema', 'extra', 'mountpoint'):
            bad = copy.deepcopy(binding)
            if changed == 'path': bad['policy_path'] += '-other'
            elif changed in ('inode', 'device', 'uid'): bad['original_root'][changed] += 1
            elif changed == 'schema': bad['schema'] += '-other'
            elif changed == 'extra': bad['writable'] = True
            else: bad['filesystem']['mountpoint'] = str(self.store)
            with self.subTest(changed), self.assertRaises(JobError):
                reader.validate(bad, str(path), policy)

    def prepare_ledger(self):
        config, path, binding = self.policy_and_binding()
        for name in ('work', 'evidence', 'temporary', 'source', 'cache'):
            (self.root / name).mkdir(mode=0o700, exist_ok=True)
        for name in ('python', 'broker.py'):
            (self.root / name).write_bytes(b'fixture')
            (self.root / name).chmod(0o600)
        broker_root = Path(config['broker_root']); broker_root.mkdir(mode=0o700)
        authority_root = Path(config['authority_root']); authority_root.mkdir(mode=0o700)
        (authority_root / 'authority.json').write_text(json.dumps(dict(
            authority_id=config['authority_id'], ledger_id='retained-ledger', state_root=str(broker_root))))
        (authority_root / 'authority.json').chmod(0o600)
        state = StateStore(broker_root / 'jobs.sqlite', config['authority_id'], 'retained-ledger', initialize=True)
        with state.transaction() as tx:
            request = dict(kind='host.inspect', profile_ref='fixture', inputs={}, expected=Policy(config).expected('fixture'))
            state.insert(tx, 'job', OP, OP, 'owner', 'original-digest', request, {}, 10)
        state.close()
        return config, path, binding

    def test_real_original_ledger_and_policy_unchanged_repeated_open_and_write_rejection(self):
        config, path, binding = self.prepare_ledger()
        raw = path.read_bytes()
        dbpath = Path(config['broker_root']) / 'jobs.sqlite'
        before = dbpath.read_bytes()
        owner = Principal('owner', frozenset(TOOL_SCOPES.values()))
        with patch.object(reader, 'read_descriptor', return_value=binding), \
             patch.object(reader, 'verify_release') as release, \
             patch.object(reader, 'observe_filesystem'):
            for _ in range(2):
                broker = reader.open_reader(path, '/root/synthetic-binding')
                try:
                    broker.start()
                    self.assertIsNone(broker._thread)
                    self.assertTrue(broker.read_only)
                    self.assertEqual('original-digest', broker.state.get('job', OP)['digest'])
                    observed = broker.call('lh_job_status', {'operation_id': OP}, owner)
                    self.assertEqual('original-digest', observed['request_digest'])
                    self.assertEqual(OP, observed['operation_id'])
                    with self.assertRaises(JobError) as denied:
                        broker.call('lh_job_status', {'operation_id': OP}, Principal('other', owner.scopes))
                    self.assertEqual('UNAUTHORIZED', denied.exception.code)
                    with self.assertRaises(JobError):
                        broker.call('lh_job_submit', {}, owner)
                    with self.assertRaises(JobError):
                        with broker.state.transaction() as tx:
                            tx.execute('DELETE FROM events')
                finally:
                    reader.cli.close_service(broker, None)
            self.assertEqual(2, release.call_count)
        self.assertEqual(raw, path.read_bytes())
        self.assertEqual(before, dbpath.read_bytes())

    def test_policy_byte_change_rejected_before_release_and_ledger(self):
        config, path, binding = self.prepare_ledger()
        path.write_bytes(path.read_bytes() + b'\n')
        with patch.object(reader, 'read_descriptor', return_value=binding), \
             patch.object(reader, 'verify_release') as release, \
             patch.object(reader, 'StateStore') as state:
            with self.assertRaises(JobError):
                reader.open_reader(path, '/root/synthetic-binding')
            release.assert_not_called(); state.assert_not_called()

    def test_failed_evidence_construction_releases_real_authority_for_retry(self):
        _, path, binding = self.prepare_ledger()
        with patch.object(reader, 'read_descriptor', return_value=binding), \
             patch.object(reader, 'verify_release'), patch.object(reader, 'observe_filesystem'):
            with patch.object(reader, 'RetainedEvidenceStore', side_effect=OSError('injected')):
                with self.assertRaises(OSError):
                    reader.open_reader(path, '/root/synthetic-binding')
            broker = reader.open_reader(path, '/root/synthetic-binding')
            reader.cli.close_service(broker, None)

    def test_invalid_anchor_keeps_original_error_when_close_fails_then_retries(self):
        config, path, binding = self.prepare_ledger()
        anchor = Path(config['authority_root']) / 'authority.json'
        original = anchor.read_bytes()
        anchor.write_bytes(b'{invalid')
        inode = anchor.stat().st_ino
        real_close = os.close
        injected = False

        def close(fd):
            nonlocal injected
            chosen = os.fstat(fd).st_ino == inode and not injected
            real_close(fd)
            if chosen:
                injected = True
                raise OSError('anchor close failed after release')

        with patch.object(reader, 'read_descriptor', return_value=binding), \
             patch.object(reader, 'verify_release'), patch.object(reader, 'observe_filesystem'):
            with patch.object(reader, 'AuthorityLock') as lock, \
                 patch.object(reader.os, 'close', side_effect=close):
                with self.assertRaises(JobError) as failed:
                    reader.open_reader(path, '/root/synthetic-binding')
                self.assertTrue(failed.exception.__notes__)
                lock.assert_not_called()
            self.assertTrue(injected)
            anchor.write_bytes(original)
            broker = reader.open_reader(path, '/root/synthetic-binding')
            reader.cli.close_service(broker, None)


class RetainedObservationFailureTests(unittest.TestCase):
    @contextmanager
    def process_source(self, code):
        launch = subprocess.Popen
        children = []
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / 'observation.py'
            script.write_text(code)

            def child(_command, **kwargs):
                process = launch([sys.executable, '-I', '-B', str(script)], **kwargs)
                children.append(process)
                return process

            with patch.object(reader.subprocess, 'Popen', side_effect=child):
                try:
                    yield children
                finally:
                    self.assertTrue(all(process.poll() is not None for process in children))
                    self.assertTrue(all(process.stdout.closed for process in children))

    def close_fault(self, *, reuse=False, invalid=False):
        real_open, real_close = os.open, os.close
        owned, replaced = set(), []
        calls = []

        def opened(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            owned.add(fd)
            return fd

        def closed(fd):
            calls.append(fd)
            real_close(fd)
            owned.discard(fd)
            # In the invalid branch, fail while unwinding the rejected child.
            if len(calls) == (2 if invalid else 1):
                if reuse:
                    replacement = opened('/dev/null', os.O_RDONLY)
                    self.assertEqual(fd, replacement)
                    replaced.append(replacement)
                raise OSError('injected close failure after release')

        try:
            with patch.object(reader.os, 'open', side_effect=opened), \
                 patch.object(reader.os, 'close', side_effect=closed):
                if invalid:
                    with patch.object(reader.os, 'fstat', return_value=SimpleNamespace(st_uid=1, st_mode=0o40777)):
                        with self.assertRaises(JobError) as failed:
                            reader.protected_backing_parent('/usr/share/image.ext4')
                    self.assertEqual('CONFLICT', failed.exception.code)
                    self.assertTrue(failed.exception.__notes__)
                else:
                    with self.assertRaises((OSError, JobError)):
                        reader.protected_backing_parent('/usr/share/image.ext4')
            self.assertEqual(set(replaced), owned, 'new child leaked or reused descriptor closed')
            for fd in replaced:
                os.fstat(fd)
            self.assertEqual(len(calls), len(set(calls)), 'a released descriptor number was closed twice')
        finally:
            for fd in owned:
                real_close(fd)

    def test_ancestor_close_failure_releases_new_child(self):
        self.close_fault()

    def test_ancestor_close_failure_never_closes_reused_descriptor(self):
        self.close_fault(reuse=True)

    def test_ancestor_validation_error_survives_close_failure(self):
        self.close_fault(invalid=True)

    def test_mount_output_limit_stops_capture_before_child_finishes(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed = Path(temporary) / 'all-output-consumed'
            code = ('import os,pathlib; '
                    '[os.write(1,b"x"*4096) for _ in range(256)]; '
                    'pathlib.Path(' + repr(str(completed)) + ').write_text("done")')
            launch = subprocess.Popen
            children = []

            def child(_command, **kwargs):
                process = launch([sys.executable, '-I', '-B', '-c', code], **kwargs)
                children.append(process)
                return process

            with patch.object(reader, 'protected_backing_parent'), \
                 patch.object(reader.subprocess, 'Popen', side_effect=child):
                with self.assertRaises(JobError):
                    reader.observe_filesystem({'mountpoint': temporary, 'backing_file': '/protected/image'}, 1)
            self.assertFalse(completed.exists(), 'the whole oversized output was consumed before rejection')
            self.assertTrue(all(process.poll() is not None for process in children))
            self.assertTrue(all(process.stdout.closed for process in children))

    def test_mount_capture_exact_limit_overflow_and_stderr_flood(self):
        for size in (0, 1, reader.MOUNT_OUTPUT_LIMIT, reader.MOUNT_OUTPUT_LIMIT + 1):
            with self.subTest(size=size):
                code = f'import os; os.write(2,b"e"*1048576); os.write(1,b"x"*{size})'
                with self.process_source(code) as children:
                    if size > reader.MOUNT_OUTPUT_LIMIT:
                        with self.assertRaises(JobError) as failed:
                            reader.mount_output('/synthetic')
                        self.assertEqual('LIMIT_EXCEEDED', failed.exception.code)
                    else:
                        self.assertEqual(b'x' * size, reader.mount_output('/synthetic'))
                    self.assertIsNone(children[0].stderr, 'stderr must not be accumulated')

    def test_escaped_long_mount_target_fits_and_keeps_exact_identity(self):
        fixture = RetainedFilesystemTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        # Valid Linux component/path lengths; JSON control escaping expands 6x.
        target = '/' + '/'.join(['\x01' * 240] * 16)
        row = dict(fixture.mount_row(), target=target)
        data = json.dumps({'filesystems': [row]}).encode()
        self.assertLess(len(target.encode()), 4096)
        self.assertGreater(len(data), 16384)
        self.assertLess(len(data), reader.MOUNT_OUTPUT_LIMIT)
        with self.process_source('import os; os.write(1,' + repr(data) + ')'), \
             patch.object(reader, 'protected_backing_parent'), \
             patch.object(reader, 'small_read', side_effect=[fixture.fs['backing_file'], '0', '0']):
            observed = reader.observe_filesystem(dict(fixture.fs, mountpoint=target),
                                                fixture.store.stat().st_dev)
        self.assertEqual(target, observed[2])

    def test_mount_nonzero_and_both_timeout_windows_release_child_and_allow_retry(self):
        cases = (
            ('raise SystemExit(7)', 'CONFLICT'),
            ('import time; time.sleep(60)', 'IO_UNCERTAIN'),
            ('import os,time; os.close(1); time.sleep(60)', 'IO_UNCERTAIN'),
        )
        for code, expected in cases:
            with self.subTest(code=code), self.process_source(code), patch.object(reader, 'MOUNT_TIMEOUT', 0.1):
                with self.assertRaises(JobError) as failed:
                    reader.mount_output('/synthetic')
                self.assertEqual(expected, failed.exception.code)
            with self.process_source('import os; os.write(1,b"ok")'):
                self.assertEqual(b'ok', reader.mount_output('/synthetic'))

    def test_mount_launch_and_pipe_failures_release_resources(self):
        before = set(os.listdir('/proc/self/fd'))
        with patch.object(reader.subprocess, 'Popen', side_effect=OSError('launch failed')):
            with self.assertRaises(JobError):
                reader.mount_output('/synthetic')
        self.assertEqual(before, set(os.listdir('/proc/self/fd')))
        with self.process_source('import os,time; os.write(1,b"ready"); time.sleep(60)') as children:
            real_read = os.read

            def failed_read(fd, size):
                if children and fd == children[0].stdout.fileno():
                    raise OSError('pipe read failed')
                return real_read(fd, size)

            with patch.object(reader.os, 'read', side_effect=failed_read):
                with self.assertRaises(JobError) as failed:
                    reader.mount_output('/synthetic')
                self.assertEqual('IO_UNCERTAIN', failed.exception.code)
        self.assertEqual(before, set(os.listdir('/proc/self/fd')))

    def test_selector_failure_after_launch_still_reaps_child(self):
        original = reader.selectors.DefaultSelector
        with self.process_source('import time; time.sleep(60)'):
            selector = original()
            with patch.object(reader.selectors, 'DefaultSelector', return_value=selector), \
                 patch.object(selector, 'register', side_effect=OSError('registration failed')):
                with self.assertRaises(JobError):
                    reader.mount_output('/synthetic')
            self.assertIsNone(selector.get_map())

    def test_cleanup_failure_cannot_mask_primary_or_report_success(self):
        original = reader.selectors.DefaultSelector
        for code, expected in (('raise SystemExit(7)', 'CONFLICT'), ('print("ok")', 'IO_UNCERTAIN')):
            with self.subTest(code=code), self.process_source(code):
                selector = original()
                close = selector.close

                def close_failed():
                    close()
                    raise OSError('selector close failed after release')

                with patch.object(reader.selectors, 'DefaultSelector', return_value=selector), \
                     patch.object(selector, 'close', side_effect=close_failed):
                    with self.assertRaises(JobError) as failed:
                        reader.mount_output('/synthetic')
                    self.assertEqual(expected, failed.exception.code)
                    if expected == 'CONFLICT':
                        self.assertTrue(failed.exception.__notes__)

    def test_actual_capture_and_filesystem_validation_then_same_reader_retry(self):
        fixture = RetainedFilesystemTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        row = fixture.mount_row()
        valid = json.dumps({'filesystems': [row]}).encode()
        exact = valid + b' ' * (reader.MOUNT_OUTPUT_LIMIT - len(valid))
        for data, accepted in ((exact, True), (exact + b' ', False), (b'{', False),
                               (b'{"filesystems":[],"filesystems":[]}', False),
                               (b'{"filesystems":[NaN]}', False), (valid, True)):
            with self.subTest(accepted=accepted, size=len(data)), \
                 self.process_source('import os; os.write(1,' + repr(data) + ')'), \
                 patch.object(reader, 'protected_backing_parent'), \
                 patch.object(reader, 'small_read', side_effect=[fixture.fs['backing_file'], '0', '0']):
                if accepted:
                    observed = reader.observe_filesystem(fixture.fs, fixture.store.stat().st_dev)
                    self.assertEqual(fixture.fs['uuid'], observed[1])
                else:
                    with self.assertRaises(JobError):
                        reader.observe_filesystem(fixture.fs, fixture.store.stat().st_dev)

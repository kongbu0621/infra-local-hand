"""Migration uses the same protected recovery declaration offline and in MCP."""
import copy
import hashlib
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from local_hand_jobs import cli, retained_filesystem, retained_offline, retained_probe
from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES
from local_hand_jobs.evidence import EvidenceError
from local_hand_mcp.resident import ResidentBroker
import test_retained_filesystem_reader as fixtures


class MigrationRoutesTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.RetainedFilesystemTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.config, self.path, self.binding = self.f.registered_ledger()
        self.bindings = {str(self.path): self.binding}
        self.identity = {'source_commit': 'f'*40, 'installed_payload_digest': 'e'*64,
                         'execution_entrypoint': cli.__file__}
        self.release = patch('local_hand_jobs.deployment.verify_release', return_value=self.identity)
        self.release.start(); self.addCleanup(self.release.stop)
        self.mount = patch.object(retained_filesystem, 'observe_filesystem')
        self.mount.start(); self.addCleanup(self.mount.stop)
        self.originals = {p: p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}

    def open(self, bindings=None):
        return cli.create_retained_broker(self.path, actual_entrypoint=cli.__file__,
            reader_identity=self.identity, filesystem_bindings=bindings)

    def assert_originals(self):
        for p, raw in self.originals.items():
            self.assertEqual(raw, p.read_bytes(), str(p))

    def test_actual_offline_path_reproduces_old_device_refusal_then_reads_original_bytes(self):
        spec = {'mode': 'policies', 'inputs': {'policies': [str(self.path), str(self.path)]},
                'reader_identity': self.identity, 'seconds': 10}
        with self.assertRaisesRegex((JobError, EvidenceError), 'admitted identity'):
            retained_offline.readback(spec)
        self.assert_originals()
        result = retained_offline.readback(dict(spec, filesystem_bindings=self.bindings))
        self.assertEqual(1, len(result['tasks']))
        self.assertEqual(3, len(result['tasks'][0]['artifacts']))
        self.assertGreater(result['bytes_verified'], 0)
        self.assertEqual(result, retained_offline.readback(dict(spec, filesystem_bindings=self.bindings)))
        self.assert_originals()

    def test_original_policy_hash_and_directory_still_required_and_retry_is_readonly(self):
        for field in ('policy_sha256', 'inode', 'device', 'uid', 'policy_path'):
            bindings = copy.deepcopy(self.bindings)
            if field == 'policy_sha256': bindings[str(self.path)][field] = '0'*64
            elif field == 'policy_path': bindings[str(self.path)][field] += '.other'
            else: bindings[str(self.path)]['original_root'][field] += 1
            with self.subTest(field=field), self.assertRaises(JobError):
                self.open(bindings)
            self.assert_originals()
        broker = self.open(self.bindings)
        try:
            self.assertEqual(self.identity, broker.reader_identity)
            self.assertNotEqual(self.identity['source_commit'], broker.policy.source_commit)
            self.assertIsNone(broker.runner)
            self.assertTrue(broker.read_only)
            with self.assertRaises(JobError):
                broker.call('lh_job_submit', {}, Principal('owner', frozenset(TOOL_SCOPES.values())))
        finally:
            cli.close_service(broker, None)
        self.assert_originals()

    def test_resident_catalog_anchor_reuses_lock_and_same_bound_read_route(self):
        broker = self.open(self.bindings)
        self.addCleanup(cli.close_service, broker, None)
        catalog = self.f.root / 'catalog'; catalog.mkdir(mode=0o700)
        op = fixtures.OP
        (catalog / (op+'.json')).write_text(json.dumps({'operation_id': op, 'state': 'READY',
                                                      'policy_path': str(self.path), 'principal_id': 'owner'}))
        descriptor = {'schema': 'local-hand-resident-adapter/v1', 'service': {}, 'catalog': str(catalog),
                      'profile_ref': 'fixture', 'authority_id': broker.policy.authority_id,
                      'budgets': {}, 'retained': [str(self.path)]}
        with patch('local_hand_mcp.resident.read_descriptor', return_value=descriptor), \
             patch('local_hand_mcp.resident.ServiceClient'):
            resident = ResidentBroker.open(broker, '/protected/resident.json')
        self.addCleanup(resident.close)
        resident.service.call.return_value = {'state': 'EXITED'}
        self.assertIs(broker, resident._reader(str(self.path)))
        with patch('local_hand_jobs.retained_probe.read_descriptor',
                   side_effect=lambda p: json.loads(Path(p).read_bytes())), \
             patch('local_hand_mcp.resident.read_descriptor', side_effect=lambda p: json.loads(Path(p).read_bytes())):
            result = retained_probe.collect(lambda r: retained_probe.handle(resident, r), deadline=time.monotonic()+10)
        self.assertEqual(3, len(result['tasks'][0]['artifacts']))
        self.assertEqual({}, resident.readers)
        # Catalog readers for other policies receive the same selected map;
        # unknown routes still require their own original admission.
        with patch.object(cli, 'create_retained_broker') as create:
            resident.reader_factory('/protected/another-policy')
            self.assertEqual(self.bindings, create.call_args.kwargs['filesystem_bindings'])
        self.assert_originals()

    def test_bindings_snapshot_cannot_be_retargeted_by_caller_mutation(self):
        broker = self.open(self.bindings)
        try:
            original = copy.deepcopy(broker.filesystem_bindings)
            self.bindings[str(self.path)]['filesystem']['uuid'] = '0'*36
            self.assertEqual(original, broker.filesystem_bindings)
        finally:
            cli.close_service(broker, None)

    def test_current_payload_must_be_admitted_before_original_ledger_open(self):
        with patch('local_hand_jobs.deployment.verify_release', side_effect=JobError('PROVENANCE_MISMATCH', 'wrong reader')), \
             patch.object(retained_filesystem, 'StateStore') as store, self.assertRaises(JobError):
            self.open(self.bindings)
        store.assert_not_called()
        self.assert_originals()

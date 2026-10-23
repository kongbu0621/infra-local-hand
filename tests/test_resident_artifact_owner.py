"""Cold artifact routing preserves task ownership across retained policies."""
import base64
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES, request_digest
from local_hand_jobs.evidence import EvidenceError
from local_hand_jobs.policy import Policy
from local_hand_jobs.state import StateStore
from local_hand_mcp.resident import ResidentBroker
from test_local_hand_jobs_broker import RegistryFixture
from test_local_hand_jobs_evidence import EvidenceFixture, OP
from test_local_hand_jobs_policy import policy_fixture


class ResidentArtifactOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.other = Principal('other', frozenset(TOOL_SCOPES.values()))
        self.entry, _ = self.broker('entry')
        self.legacy, self.legacy_files = self.broker('legacy', include_other=False)
        self.owned, self.owned_files = self.broker('owned')
        self.admit(self.owned, self.other)
        self.owned_files.store.seal(OP)
        self.artifact = self.owned.call('lh_evidence_manifest', {'operation_id': OP}, self.other)['artifacts'][0]
        self.args = dict(artifact_id=self.artifact['artifact_id'],
                         expected_sha256=self.artifact['sha256'], offset=0)
        catalog = self.root / 'catalog'
        catalog.mkdir()
        self.record = dict(operation_id=OP, principal_id='other', state='READY', policy_path='/owned-policy')
        (catalog / (OP + '.json')).write_text(json.dumps(self.record))
        self.service = Mock()
        self.service.call.return_value = {'state': 'EXITED'}
        self.factory = Mock(side_effect=lambda path: {
            '/legacy-policy': self.legacy, '/owned-policy': self.owned}[path])
        self.adapter = ResidentBroker(self.entry, {'catalog': str(catalog), 'retained': ['/legacy-policy']},
                                      self.service, self.factory)
        # Only administrator-owned descriptor loading is modeled; authorization,
        # SQLite ownership, exact seal lookup and evidence bytes use real code.
        self.addCleanup(patch.stopall)
        patch('local_hand_mcp.resident.read_descriptor', return_value=self.record).start()
        patch('local_hand_mcp.resident.Policy.from_file', return_value=self.owned.policy).start()

    def broker(self, name, *, include_other=True):
        root = self.root / name
        root.mkdir(mode=0o700)
        config = policy_fixture(root)
        if not include_other:
            del config['principals']['other']
        state = StateStore(root / 'jobs.sqlite', 'fixture-authority', name, initialize=True)
        self.addCleanup(state.close)
        broker = Broker(state, Policy(config), RegistryFixture(), None)
        self.addCleanup(broker.close)
        broker.authority_lock = None
        files = EvidenceFixture(root)
        def authorize(principal, operation):
            with state.transaction() as tx:
                broker._row(tx, 'job', operation, principal, 'lh:evidence')
        files.store.authorize = authorize
        broker.evidence = files.store
        return broker, files

    @staticmethod
    def admit(broker, principal):
        request = dict(schema_version='lh-job-v1', operation_id=OP, kind='host.inspect', profile_ref='fixture',
                       expected=broker.policy.expected('fixture'), inputs={}, expires_at=int(time.time()) + 300)
        request['request_digest'] = request_digest(request)
        broker.submit(request, principal)

    def test_new_principal_reads_own_artifact_without_a_warm_manifest_route(self):
        self.assertNotIn('other', self.legacy.policy.principals)
        self.assertFalse(self.adapter.artifact_routes)
        with patch.object(self.owned, 'call', wraps=self.owned.call) as selected:
            result = self.adapter.call('lh_evidence_read_chunk', self.args, self.other)
        self.assertEqual(self.artifact['artifact_id'], result['artifact_id'])
        self.assertTrue(base64.b64decode(result['data_base64']))
        selected.assert_called_once_with('lh_evidence_read_chunk', self.args, self.other)
        self.assertEqual(['status'], [call.args[0] for call in self.service.call.call_args_list])

    def test_new_principal_recovers_owned_history_after_an_unrelated_old_policy(self):
        self.adapter.config['retained'].append('/owned-policy')
        before = self.owned.state.events('job', OP)
        with patch.object(self.adapter, '_record', return_value=None):
            for name in ('lh_job_status', 'lh_evidence_manifest'):
                with self.subTest(name=name):
                    result = self.adapter.call(name, {'operation_id': OP}, self.other)
                    self.assertEqual(OP, result['operation_id'])
        self.service.call.assert_not_called()
        self.assertEqual(before, self.owned.state.events('job', OP))

    def test_exact_foreign_task_refusal_cannot_fall_through_to_same_id(self):
        self.adapter.config['retained'].append('/owned-policy')
        self.legacy.policy = Policy(policy_fixture(self.root / 'legacy'))
        self.admit(self.legacy, Principal('owner', self.other.scopes))
        before = self.legacy.state.events('job', OP)
        with patch.object(self.adapter, '_record', return_value=None), \
             patch.object(self.owned, 'call', wraps=self.owned.call) as selected:
            for name in ('lh_job_status', 'lh_evidence_manifest'):
                with self.subTest(name=name), self.assertRaises(JobError) as caught:
                    self.adapter.call(name, {'operation_id': OP}, self.other)
                self.assertEqual('UNAUTHORIZED', caught.exception.code)
        selected.assert_not_called()
        self.service.call.assert_not_called()
        self.assertEqual(before, self.legacy.state.events('job', OP))

    def test_uncertain_task_lookup_does_not_fall_through(self):
        self.adapter.config['retained'].append('/owned-policy')
        with patch.object(self.adapter, '_record', return_value=None), \
             patch.object(self.legacy.state, 'get', side_effect=JobError('IO_UNCERTAIN', 'synthetic lookup failure')), \
             patch.object(self.owned, 'call', wraps=self.owned.call) as selected:
            for name in ('lh_job_status', 'lh_evidence_manifest'):
                with self.subTest(name=name), self.assertRaises(JobError) as caught:
                    self.adapter.call(name, {'operation_id': OP}, self.other)
                self.assertEqual('IO_UNCERTAIN', caught.exception.code)
        selected.assert_not_called()
        self.service.call.assert_not_called()

    def test_exact_foreign_artifact_refusal_cannot_fall_through_to_same_id(self):
        # Both identities have identical project grants in this retained policy.
        self.legacy.policy = Policy(policy_fixture(self.root / 'legacy'))
        owner = Principal('owner', self.other.scopes)
        self.admit(self.legacy, owner)
        seal_id = self.artifact['seal_id']
        shutil.copytree(self.owned_files.store.root / seal_id, self.legacy_files.store.root / seal_id)
        self.legacy_files.registered.update(self.owned_files.registered)
        before = self.legacy.state.events('job', OP)
        with patch.object(self.owned, 'call', wraps=self.owned.call) as selected:
            with self.assertRaises(JobError) as caught:
                self.adapter.call('lh_evidence_read_chunk', self.args, self.other)
        self.assertEqual('UNAUTHORIZED', caught.exception.code)
        selected.assert_not_called()
        self.service.call.assert_not_called()
        self.assertEqual(before, self.legacy.state.events('job', OP))

    def test_exact_lookup_uncertainty_or_unsealed_evidence_does_not_fall_through(self):
        for code in ('IO_UNCERTAIN', 'NOT_SEALED', 'CONFLICT'):
            with self.subTest(code=code), \
                 patch.object(self.legacy.evidence, 'owner_of', side_effect=EvidenceError(code, 'synthetic refusal')), \
                 patch.object(self.owned, 'call', wraps=self.owned.call) as selected:
                with self.assertRaises(EvidenceError) as caught:
                    self.adapter.call('lh_evidence_read_chunk', self.args, self.other)
                self.assertEqual(code, caught.exception.code)
                selected.assert_not_called()
        self.service.call.assert_not_called()


if __name__ == '__main__':
    unittest.main()

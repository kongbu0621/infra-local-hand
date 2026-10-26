"""A reconstructed coordinator can read the original gateway proof first."""
from pathlib import Path
import unittest

from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.runtime import ConcreteEnvironment
import test_local_hand_deploy_gateway_removal as fixtures


class FreshProofTests(unittest.TestCase):
    def test_new_coordinator_resume_reads_retained_creation_without_saved_observation(self):
        case=fixtures.AdoptedGatewayCreationTests('runTest')
        self.addCleanup(case.doCleanups);case.setUp()
        op=case.applied;record=case.original_creation()
        original=record['attempts'][-1]['effect_identity'].copy()
        receipt=Path(record['attempts'][-1]['binding']['result_directory'])/'result.json'
        raw=receipt.read_bytes();requests=case.http.requests.read_bytes()
        record['observation']=None
        with case.store.locked():case.store.save(op,'ORIGINAL_EFFECT_WITHOUT_SAVED_OBSERVATION')
        coordinator=Coordinator(case.store,case.f.gate,ConcreteEnvironment(op['plan'],case.store,case.f.gate))
        final=coordinator.resume(op['id'])
        self.assertEqual('COMMITTED',final['decision'],final['waiting'])
        self.assertTrue(final['released'])
        restored=next(value for step,value in zip(final['plan']['steps'],final['steps'])
                      if step['action'].get('kind')=='gateway_create')
        self.assertEqual(original,restored['attempts'][-1]['effect_identity'])
        self.assertEqual(1,len(restored['attempts']))
        self.assertEqual(raw,receipt.read_bytes());self.assertEqual(requests,case.http.requests.read_bytes())


if __name__=='__main__':unittest.main()

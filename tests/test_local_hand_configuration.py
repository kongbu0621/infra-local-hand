"""Behavioral checks of configuration admission and provenance boundaries."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from config_fixtures import profile_v2, transport
from local_hand import config, worker, provenance
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError
from local_hand_connect import controller


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.data=profile_v2({"node_id":"fixture-node","projects_root":str(self.root/'projects'),
                              "repositories":{"demo":{"path":"demo","single_writer":True,"validations":{
                                  "echo":{"argv":[sys.executable,"-c","print('fixture')"],"timeout_seconds":2,"replay_safe":True}}}}})

    def write(self,data=None,name='profile.json'):
        path=self.root/name;path.write_text(json.dumps(self.data if data is None else data));return path

    def test_two_independent_deployments_need_no_source_changes(self):
        for i,remote in enumerate(('git@example.invalid:team-a/queue.git','ssh://worker@git.example.invalid:2222/team-b/mailbox.git')):
            data=copy.deepcopy(self.data);data['node_id']=f'fixture-node-{i}'
            data['projects_root']=str(self.root/f'projects-{i}')
            data['transport_policy']=transport(f'queue/node-{i}',remote)
            path=self.write(data,f'profile-{i}.json');p=load_profile(path)
            self.assertEqual(p.transport_policy.remote_url,remote)
            self.assertEqual(p.transport_policy.branch,f'queue/node-{i}')
            self.assertEqual(p.profile_sha256,hashlib.sha256(path.read_bytes()).hexdigest())

    def test_profile_digest_includes_transport_and_raw_formatting(self):
        path=self.write();a=load_profile(path)
        path.write_text(json.dumps(self.data,indent=2));b=load_profile(path)
        self.assertNotEqual(a.profile_sha256,b.profile_sha256)
        self.assertEqual(a.transport_policy.digest,b.transport_policy.digest)
        self.data['transport_policy']['branch']='other/mailbox'
        c=load_profile(self.write());self.assertNotEqual(b.profile_sha256,c.profile_sha256)
        self.assertNotEqual(b.transport_policy.digest,c.transport_policy.digest)

    def test_configuration_rejects_missing_unknown_null_and_legacy(self):
        cases=[]
        for name in self.data:
            a=copy.deepcopy(self.data);del a[name];cases.append(a)
            a=copy.deepcopy(self.data);a[name]=None;cases.append(a)
        a=copy.deepcopy(self.data);a['unknown']=True;cases.append(a)
        a=copy.deepcopy(self.data);a['repositories']['demo']['unknown']=1;cases.append(a)
        a=copy.deepcopy(self.data);a['repositories']['demo']['validations']['echo']['extra']=1;cases.append(a)
        for i,data in enumerate(cases):
            with self.subTest(i=i),self.assertRaises(LocalHandError):load_profile(self.write(data))

    def test_duplicate_keys_nonfinite_and_boolean_timeouts_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}',b'{"a":NaN}',b'{"a":Infinity}',b'{"a":-Infinity}'):
            with self.subTest(raw=raw),self.assertRaises(LocalHandError):config.strict_json(raw)
        for value in (True,False,0,-1,3601,float('inf'),float('nan'),10**1000,'2',None):
            a=copy.deepcopy(self.data);a['repositories']['demo']['validations']['echo']['timeout_seconds']=value
            with self.subTest(value=type(value).__name__),self.assertRaises(LocalHandError):load_profile(self.write(a))

    def test_transport_spellings_are_explicit_and_same_target(self):
        a=transport();a['allowed_remote_urls'].append('ssh://git@example.invalid/fixtures/mailbox.git')
        self.assertEqual(len(config.parse_transport(a).allowed_remote_urls),2)
        for bad in ('git@example.invalid:other/mailbox.git','git@elsewhere.invalid:fixtures/mailbox.git','other@example.invalid:fixtures/mailbox.git'):
            b=copy.deepcopy(a);b['allowed_remote_urls'].append(bad)
            with self.subTest(bad=bad),self.assertRaises(LocalHandError):config.parse_transport(b)
        for b in ({**a,'remote_url':'ssh://git@example.invalid:22/fixtures/mailbox.git'},
                  {**a,'allowed_remote_urls':[a['remote_url'],a['remote_url']]},
                  {**a,'extra':True}):
            with self.assertRaises(LocalHandError):config.parse_transport(b)

    def test_remote_and_branch_injection_boundaries(self):
        remotes=('file:///tmp/mailbox.git','/tmp/mailbox.git','https://example.invalid/a.git',
                 'ext::touch /tmp/nope','git@-oProxyCommand=x:a.git','git@example.invalid:../x.git',
                 'git@example.invalid:foo//bar.git','ssh://git@example.invalid:0/a.git',
                 'git@example.invalid:foo.git\n','git@example.invalid:foo;bar.git','ssh://git@example.invalid/a.git?x',
                 'git@EXAMPLE.invalid:foo.git','git@example..invalid:foo.git')
        for value in remotes:
            with self.subTest(remote=value),self.assertRaises(LocalHandError):config.parse_transport(transport(remote=value))
        for branch in ('','--upload-pack=x','../main','a..b','x//y','x/.secret','x/foo.lock','x/','x.','x%y','x\ny','x@{y}','x y','x:y'):
            with self.subTest(branch=branch),self.assertRaises(LocalHandError):config.parse_transport(transport(branch))

    def test_worker_cli_rejects_branch_drift_before_runtime_or_state(self):
        state=self.root/'state'
        with mock.patch.object(worker,'validate_runtime_bindings') as bindings:
            result=worker.main(['--profile',str(self.write()),'--mailbox-repo',str(self.root/'mailbox'),
                                '--state-root',str(state),'--mailbox-branch','other/mailbox','--once'])
        self.assertEqual(result,2);bindings.assert_not_called();self.assertFalse(state.exists())

    def test_worker_remote_drift_rejected_without_git_network(self):
        mailbox=self.root/'mailbox';mailbox.mkdir()
        subprocess.run(['git','init','-q',str(mailbox)],check=True)
        allowed=self.data['transport_policy']['remote_url']
        subprocess.run(['git','-C',str(mailbox),'remote','add','origin',allowed],check=True)
        profile=load_profile(self.write())
        worker.validate_worker_mailbox(mailbox,profile.transport_policy.branch,profile)
        subprocess.run(['git','-C',str(mailbox),'remote','set-url','--push','origin','git@example.invalid:wrong/mailbox.git'],check=True)
        with self.assertRaises(LocalHandError):worker.validate_worker_mailbox(mailbox,profile.transport_policy.branch,profile)
        self.assertFalse((self.root/'state').exists())

    def test_controller_marker_policy_digest_and_explicit_expectation(self):
        mailbox=self.root/'controller';(mailbox/'.git').mkdir(parents=True)
        policy=config.parse_transport(transport())
        marker={'schema_version':controller.CONNECT_MARKER_SCHEMA,'mailbox_root':str(mailbox),
                'branch':policy.branch,'remote_url':policy.remote_url,'push_url':policy.remote_url,
                'transport_policy':policy.as_dict(),'transport_policy_digest':policy.digest}
        path=mailbox/'.git'/controller.CONNECT_MARKER_NAME;path.write_text(json.dumps(marker))
        with mock.patch.object(controller,'validate_controller_bindings'),mock.patch.object(controller,'_assert_exact_toplevel',return_value=mailbox),mock.patch.object(controller,'_read_remote_urls',return_value=(policy.remote_url,policy.remote_url)):
            controller.validate_controller_mailbox(mailbox,policy.branch,expected_policy=policy)
            wrong=config.parse_transport(transport('changed/branch'))
            with self.assertRaises(LocalHandError):controller.validate_controller_mailbox(mailbox,policy.branch,expected_policy=wrong)
            marker['transport_policy']['branch']='changed/branch';path.write_text(json.dumps(marker))
            with self.assertRaises(LocalHandError):controller.validate_controller_mailbox(mailbox,policy.branch)

    @unittest.skipUnless(shutil.which('bash'),'Bash unavailable')
    def test_linux_bootstrap_rejects_bad_profile_before_filesystem_mutation(self):
        self.data['transport_policy']['remote_url']='https://example.invalid/rejected.git'
        state=self.root/'new-state'
        script=Path(__file__).resolve().parents[1]/'tools/local_hand/bootstrap_linux.sh'
        result=subprocess.run(['bash',str(script),'--profile',str(self.write()),'--repository-name','demo',
                               '--run-user','fixture','--state-root',str(state)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('invalid_profile',result.stderr)
        self.assertFalse(state.exists())

    def test_environment_commit_cannot_override_checkout(self):
        with mock.patch.dict(os.environ,{'LOCAL_HAND_IMPLEMENTATION_COMMIT':'0'*40}):
            with self.assertRaises(LocalHandError):provenance.implementation_commit()

    def test_build_requires_clean_source_and_exact_payload(self):
        target=self.root/'payload';(target/'local_hand').mkdir(parents=True)
        (target/'local_hand/worker.py').write_text('changed\n')
        with mock.patch.object(provenance,'source_commit',return_value='a'*40) as clean:
            with self.assertRaises(LocalHandError):provenance.write_build_metadata(target,artifact_kind='wheel')
        clean.assert_called_once_with(require_clean=True)
        self.assertFalse((target/'local_hand/_build_metadata.json').exists())


if __name__=='__main__':unittest.main()

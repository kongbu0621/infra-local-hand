"""Project edit uses real Git/CAS/validation and preserves its source snapshot."""
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
from unittest.mock import patch

from local_hand_jobs import workspace_jobs as workspace
from local_hand_jobs.contract import (JobError, Principal, MAX_CANONICAL_BYTES, MAX_INPUT_BYTES,
    MAX_WORKSPACE_TEXT_BYTES, canonical_bytes, request_digest, validate_tool_args)
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs.registry import Registry
from test_local_hand_jobs_contract import submit_fixture
from test_local_hand_jobs_policy import policy_fixture


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'source';self.source.mkdir(mode=0o700)
        (self.source/'tests').mkdir(mode=0o700)
        self.original=b'VALUE = 1\n'
        files={'sample.py':self.original,'tests/test_sample.py':
            b'import unittest\nimport sample\nclass Sample(unittest.TestCase):\n def test_value(self): self.assertEqual(sample.VALUE, 2)\n'}
        blobs={}
        for name,raw in files.items():
            path=self.source/name;path.write_bytes(raw);path.chmod(0o600)
            blobs[name]=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        self.config=policy_fixture(self.root)
        profile=self.config['profiles']['fixture'];profile['python']=sys.executable
        profile['sources']['source']=dict(root=str(self.source),commit='a'*40,blobs=blobs,validations={'core':['test_sample']})
        git=str(Path(shutil.which('git')).resolve())
        profile['workspace_git']=dict(path=git,sha256=hashlib.sha256(Path(git).read_bytes()).hexdigest())
        profile['budgets']['workspace.edit'].update(log_bytes=65536,reservation_bytes=512*1024)
        self.policy=Policy(self.config)
        self.inputs=dict(source_ref='source',relative_path='sample.py',expected_sha256=hashlib.sha256(self.original).hexdigest(),
                         content='VALUE = 2\n',validation_ref='core')
        self.request=submit_fixture('workspace.edit',**self.inputs)
        self.request['expected']=self.policy.expected('fixture');self.request['request_digest']=request_digest(self.request)
        self.principal=Principal('owner',frozenset({'lh:submit'}))
        self.plan=thaw(Registry().resolve(self.request,self.policy,principal=self.principal))['execution']
        for path in self.plan['roots'].values():Path(path).mkdir(parents=True,mode=0o700)
        self.directory=Path(self.plan['roots']['evidence'])
        self.environment=patch.dict(os.environ);self.environment.start();self.addCleanup(self.environment.stop)

    def test_real_edit_git_diff_and_fixed_validation_preserve_original(self):
        result=workspace.prepare_edit(self.plan,self.directory)
        stage=self.plan['stages'][0]
        # The test file imports the project root, as ordinary repository tests
        # do. The installed helper explicitly admits this task-owned root.
        process=subprocess.run(stage['argv'],cwd=stage['cwd'],env=stage['env'],capture_output=True,timeout=10)
        self.assertEqual(0,process.returncode,process.stderr.decode())
        finished=workspace.finish_edit(self.plan,self.directory,result,True)
        self.assertTrue(finished['validation_succeeded']);self.assertTrue(finished['edited_file_unchanged_by_validation'])
        self.assertFalse(finished['original_modified']);self.assertEqual(self.original,(self.source/'sample.py').read_bytes())
        diff=(self.directory/'workspace-final.patch').read_text()
        self.assertIn('-VALUE = 1',diff);self.assertIn('+VALUE = 2',diff)
        self.assertEqual('TASK_OWNED_COPY',finished['scope'])

    def test_stale_hash_or_changed_git_fails_before_copy_or_write(self):
        for key in ('expected_sha256','git'):
            plan=copy.deepcopy(self.plan)
            if key=='git':plan['workspace_git']['sha256']='0'*64
            else:plan['inputs']['expected_sha256']='0'*64
            with self.subTest(key=key),self.assertRaises((JobError,ValueError)):
                workspace.prepare_edit(plan,self.directory)
            self.assertFalse((Path(plan['roots']['work'])/'source').exists())
        self.assertEqual(self.original,(self.source/'sample.py').read_bytes())

    def test_second_execution_refuses_existing_copy(self):
        workspace.prepare_edit(self.plan,self.directory)
        with self.assertRaises(ValueError):workspace.prepare_edit(self.plan,self.directory)
        self.assertEqual('VALUE = 2\n',(Path(self.plan['roots']['work'])/'source/sample.py').read_text())

    def test_validation_mutation_is_reported_in_final_diff(self):
        result=workspace.prepare_edit(self.plan,self.directory)
        (Path(self.plan['roots']['work'])/'source/sample.py').write_text('VALUE = 3\n')
        finished=workspace.finish_edit(self.plan,self.directory,result,False)
        self.assertFalse(finished['edited_file_unchanged_by_validation']);self.assertFalse(finished['validation_succeeded'])
        self.assertIn('+VALUE = 3',(self.directory/'workspace-final.patch').read_text())

    def test_public_request_rejects_escape_metadata_and_oversized_edit(self):
        args=dict(operation_id=self.request['operation_id'],kind='workspace.edit',profile_ref='fixture',inputs=self.inputs)
        for relative in ('../sample.py','/sample.py','.git/config','folder/../sample.py','./sample.py','sample.py\x00'):
            with self.subTest(relative=relative),self.assertRaises(JobError):
                validate_tool_args('lh_job_prepare',dict(args,inputs=dict(self.inputs,relative_path=relative)))
        with self.assertRaises(JobError):
            validate_tool_args('lh_job_prepare',dict(args,inputs=dict(self.inputs,content='x'*(MAX_WORKSPACE_TEXT_BYTES+1))))

    def test_input_byte_boundary_includes_unicode_and_json_escapes(self):
        empty=dict(self.inputs,content='')
        available=MAX_INPUT_BYTES-len(canonical_bytes(empty))
        for character in ('x','中','😀','"','\\','\n','\x00'):
            width=len(canonical_bytes(dict(text=character)))-len(canonical_bytes(dict(text='')))
            content=character*(available//width)+'x'*(available%width)
            inputs=dict(empty,content=content)
            with self.subTest(character=repr(character)):
                self.assertEqual(MAX_INPUT_BYTES,len(canonical_bytes(inputs)))
                request=submit_fixture('workspace.edit',**inputs)
                self.assertLess(len(canonical_bytes(request)),MAX_CANONICAL_BYTES)
                self.assertEqual(request,validate_tool_args('lh_job_submit',request))
                args=dict(operation_id=request['operation_id'],kind='workspace.edit',profile_ref='fixture',inputs=inputs)
                self.assertEqual(args,validate_tool_args('lh_job_prepare',args))
                with self.assertRaises(JobError) as caught:
                    validate_tool_args('lh_job_prepare',dict(args,inputs=dict(inputs,content=content+'x')))
                self.assertEqual('LIMIT_EXCEEDED',caught.exception.code)

    def test_large_real_edit_keeps_complete_diff_and_fixed_validation(self):
        content='VALUE = 2\n# '+('x'*110000)+'\n'
        request=dict(self.request,inputs=dict(self.inputs,content=content))
        request['request_digest']=request_digest(request)
        self.plan['inputs']=validate_tool_args('lh_job_submit',request)['inputs']
        self.plan['budgets']['log_bytes']=512*1024
        result=workspace.prepare_edit(self.plan,self.directory)
        stage=self.plan['stages'][0]
        process=subprocess.run(stage['argv'],cwd=stage['cwd'],env=stage['env'],capture_output=True,timeout=10)
        self.assertEqual(0,process.returncode,process.stderr.decode())
        finished=workspace.finish_edit(self.plan,self.directory,result,True)
        self.assertTrue(finished['edited_file_unchanged_by_validation'])
        self.assertEqual(content,(self.directory/'workspace-after.txt').read_text())
        self.assertIn('+# '+('x'*110000),(self.directory/'workspace-final.patch').read_text())
        self.assertEqual(self.original,(self.source/'sample.py').read_bytes())

    def test_isolated_runner_script_loads_workspace_executor(self):
        from local_hand_jobs import runner
        code=('import runpy,sys; namespace=runpy.run_path(sys.argv[1]); '
              'assert namespace["workspace_jobs"].KIND == "workspace.edit"')
        result=subprocess.run([sys.executable,'-I','-B','-c',code,runner.__file__],
            capture_output=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stderr.decode())

    def test_source_and_validation_are_server_granted(self):
        for field,value in (('source_ref','foreign'),('relative_path','unknown.py'),('validation_ref','shell')):
            request=dict(self.request,inputs=dict(self.inputs,**{field:value}))
            request['request_digest']=request_digest(request)
            with self.subTest(field=field),self.assertRaises(JobError):
                Registry().resolve(request,self.policy,principal=self.principal)

    def test_legacy_policy_bytes_do_not_gain_workspace_budget_or_grant(self):
        config=copy.deepcopy(self.config)
        del config['profiles']['fixture']['budgets']['workspace.edit']
        for grant in config['principals'].values():grant['profiles']['fixture']['kinds'].remove('workspace.edit')
        original=json.dumps(config,sort_keys=True)
        retained=Policy(config)
        self.assertEqual(original,json.dumps(thaw(retained.config),sort_keys=True))
        with self.assertRaises(JobError):retained.authorize(self.principal,'lh:submit',request=self.request)

    def test_local_completion_never_accepts_external_writable_paths(self):
        plan=dict(kind='workspace.edit',execution=self.plan)
        self.assertTrue(workspace.local_effects_only(plan))
        changed=copy.deepcopy(plan);changed['execution']['writable'].append(str(self.source))
        self.assertFalse(workspace.local_effects_only(changed))

    def test_full_source_inventory_is_digest_bound_without_expanding_helper_transport(self):
        config=copy.deepcopy(self.config);source=config['profiles']['fixture']['sources']['source']
        raw=canonical_bytes(dict(commit=source['commit'],blobs=source['blobs']))
        path=self.root/'inventory.json';path.write_bytes(raw);path.chmod(0o600)
        source['manifest']=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest())
        policy=Policy(config);request=dict(self.request,expected=policy.expected('fixture'))
        request['request_digest']=request_digest(request)
        plan=thaw(Registry().resolve(request,policy,principal=self.principal))['execution']
        self.assertNotIn('blobs',plan['source']);self.assertTrue(workspace.verify_inputs(plan)['inputs_stable'])
        path.write_bytes(raw+b' ')
        with self.assertRaises(ValueError):workspace.verify_inputs(plan)

    def test_project_assembly_keeps_same_uuid_and_three_phase_quota_chain(self):
        from test_e3_quota_q2_prepare_assembly import a,system_facts
        from test_local_hand_jobs_quota_resident import resident
        from unittest.mock import Mock
        facts=system_facts()
        selected=dict(sources=self.config['profiles']['fixture']['sources'],
                      git=self.config['profiles']['fixture']['workspace_git'],inputs=self.inputs)
        assembled=a.assemble(facts,workspace=selected)
        self.assertEqual('workspace.edit',assembled['resident']['request']['kind'])
        self.assertEqual(facts['identity']['operation_id'],assembled['resident']['request']['operation_id'])
        self.assertEqual({'preflight','business','evidence'},set(assembled['chain']['phases']))
        self.assertEqual(self.inputs,assembled['resident']['request']['inputs'])
        broker=Mock()
        broker.state.get.return_value={'plan':assembled['resident']['plan']}
        identity,principal=resident.prepare_request(assembled['resident'],broker)
        self.assertEqual(facts['identity']['operation_id'],identity)
        broker.submit.assert_called_once_with(assembled['resident']['request'],principal)

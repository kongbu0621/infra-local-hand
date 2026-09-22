"""Installed-wheel acceptance using isolated local fixtures, never a live node.

Run with the new runtime venv's ``python -I`` from outside the source checkout.
Every fixture and command log is retained under a fresh --run-root.
POSIX Git transport uses an explicitly named local SSH shim; it proves the Git
mailbox/CLI chain, not SSH authentication, network security or physical service.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid


def _entry_exists_strict(path: Path) -> bool:
    """Return whether a directory entry exists without hiding lookup errors."""
    path = Path(path)
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise AssertionError(
            f"cannot determine directory-entry state: {path}; errno={exc.errno}"
        ) from exc
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--wheel',required=True,type=Path)
    parser.add_argument('--run-root',required=True,type=Path)
    args=parser.parse_args()
    root=args.run_root.absolute();root.mkdir()
    logs=root/'commands';logs.mkdir()
    env=os.environ.copy()
    for key in list(env):
        if key.startswith(('GIT_','SSH_','LOCAL_HAND_')) or key in ('PYTHONPATH','PYTHONHOME'):
            env.pop(key)
            os.environ.pop(key, None)
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['GIT_CONFIG_NOSYSTEM']='1';env['GIT_CONFIG_GLOBAL']=os.devnull
    records=[];checks=[]

    def run(argv, *, cwd=root, expected=0, override=None):
        n=len(records)+1; folder=logs/f'{n:03}';folder.mkdir()
        command=[str(x) for x in argv];start=time.monotonic()
        entry={'argv':command,'cwd':str(cwd),'start_utc':datetime.now(timezone.utc).isoformat()}
        child=subprocess.Popen(command,cwd=cwd,env={**env,**(override or {})},stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=os.name!='nt')
        captures={name: {'data':bytearray(),'observed':0,'error':None} for name in ('stdout.log','stderr.log')}
        def drain(pipe, capture):
            try:
                with pipe:
                    while block:=pipe.read(65536):
                        capture['observed']+=len(block)
                        remaining=32*1024*1024-len(capture['data'])
                        capture['data'].extend(block[:remaining])
            except Exception as exc:capture['error']=repr(exc)
        threads=[threading.Thread(target=drain,args=(pipe,captures[name]),daemon=True)
                 for name,pipe in (('stdout.log',child.stdout),('stderr.log',child.stderr))]
        for thread in threads:thread.start()
        if hasattr(os,'wait4'):
            while True:
                pid,status,usage=os.wait4(child.pid,os.WNOHANG)
                if pid:
                    code=os.waitstatus_to_exitcode(status);child.returncode=code
                    entry['max_rss_kib']=usage.ru_maxrss;entry['rss_method']='Linux wait4 ru_maxrss';break
                if time.monotonic()-start>90:
                    os.killpg(child.pid,signal.SIGKILL)
                    _,status,usage=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status)
                    code=124;entry['timed_out']=True;entry['max_rss_kib']=usage.ru_maxrss;break
                time.sleep(.02)
        else:
            try:code=child.wait(timeout=90)
            except subprocess.TimeoutExpired:child.kill();child.wait();code=124
            entry['max_rss_kib']=None;entry['rss_method']='UNAVAILABLE on this platform in this fixture harness'
        for thread in threads:thread.join(5)
        incomplete=any(thread.is_alive() for thread in threads)
        entry['capture_complete']=not incomplete and all(c['error'] is None and c['observed']==len(c['data']) for c in captures.values())
        entry['capture_method']='parent drains both pipes with 32 MiB per-stream bound; create-only fsynced logs'
        for name,capture in captures.items():
            with (folder/name).open('xb') as stream:
                stream.write(bytes(capture['data']));stream.flush();os.fsync(stream.fileno())
        entry.update(exit_code=code,expected_exit_code=expected,elapsed_seconds=time.monotonic()-start,
                     end_utc=datetime.now(timezone.utc).isoformat(),
                     logs={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ('stdout.log','stderr.log')})
        with (folder/'command.json').open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(entry,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
        records.append(entry)
        if not entry['capture_complete']:raise AssertionError(f'command {n} output capture incomplete')
        if code!=expected:
            raise AssertionError(f'command {n} exit {code} != {expected}: {command!r}\n'+(folder/'stderr.log').read_text(errors='replace')[-4000:])
        return (folder/'stdout.log').read_text(encoding='utf-8')

    def save(name,value):
        path=root/name;path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n');return path

    report={'status':'RUNNING','fixture_only':True,'physical_node_tested':False,'checks':checks,'commands':records}
    try:
        import local_hand
        import local_hand_connect
        from local_hand.config import PROFILE_SCHEMA,TRANSPORT_SCHEMA
        from local_hand.provenance import implementation_commit,core_digest,build_metadata
        from local_hand.paths import load_profile
        from local_hand.protocol import LocalHandError, conflict_filename, result_error, task_digest
        from local_hand.worker import execute_task
        from local_hand_connect.controller import build_task
        assert sys.prefix!=sys.base_prefix,'runtime must be a dedicated venv'
        for module in (local_hand,local_hand_connect):
            assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()),module.__file__
        metadata=build_metadata();assert metadata and metadata['artifact_kind']=='wheel'
        report.update(python=sys.version,executable=sys.executable,module_paths=[local_hand.__file__,local_hand_connect.__file__],
                      implementation_commit=implementation_commit(),package_digest=core_digest(),
                      wheel_sha256=hashlib.sha256(args.wheel.read_bytes()).hexdigest())
        installed=json.loads(run([sys.executable,'-I','-m','pip','list','--format=json']))
        assert {p['name'].lower() for p in installed}=={'pip','infra-local-hand'},installed
        entry_root=Path(sys.executable).parent
        entries=[entry_root/(name+('.exe' if os.name=='nt' else '')) for name in ('local-hand-worker','local-hand-connect')]
        report['console_entries']=[str(p) for p in entries]
        for entry in entries:
            assert entry.is_file(),entry
            run([entry,'--help'])
        run([sys.executable,'-I','-m','local_hand.worker','--help'])
        run([sys.executable,'-I','-m','local_hand_connect.cli','--help'])
        git=shutil.which('git');assert git,'Git required'
        project=root/'projects'/'demo';project.mkdir(parents=True)
        run([git,'init','-q',str(project)])
        run([git,'-C',project,'config','user.name','fixture'])
        run([git,'-C',project,'config','user.email','fixture@example.invalid'])
        (project/'sample.txt').write_bytes(b'before\n')
        run([git,'-C',project,'add','.']);run([git,'-C',project,'commit','-qm','fixture'])
        policy={'schema_version':TRANSPORT_SCHEMA,'remote_url':'git@example.invalid:fixtures/mailbox.git',
                'allowed_remote_urls':['git@example.invalid:fixtures/mailbox.git'],'branch':'fixture/mailbox-v1'}
        policy_path=save('transport.json',policy)
        profile_data={'profile_schema':PROFILE_SCHEMA,'node_id':'fixture-installed-node','projects_root':str(project.parent),
                      'transport_policy':policy,'repositories':{'demo':{'path':'demo','single_writer':True,'validations':{
                          'echo':{'argv':[sys.executable,'-I','-c','print("INSTALLED_VALIDATION_OK")'],'timeout_seconds':5,'replay_safe':True},
                          'fail':{'argv':[sys.executable,'-I','-c','raise SystemExit(7)'],'timeout_seconds':5,'replay_safe':True}}}}}
        if os.name != 'nt':
            # A finite descendant outlives its launcher and inherits both pipes.
            # Bind the fixed profile before installation; never modify it later.
            heartbeat=root/'lifetime-heartbeat'
            launches=root/'lifetime-launches'
            child_code=('import time\nfrom pathlib import Path\nend=time.monotonic()+12\n'
                        f'with Path({str(heartbeat)!r}).open("ab",buffering=0) as out:\n'
                        ' while time.monotonic()<end:\n  out.write(b"x");time.sleep(.03)\n')
            parent_code=('import subprocess,sys,time\nfrom pathlib import Path\n'
                         f'with Path({str(launches)!r}).open("ab") as out:out.write(b"x")\n'
                         f'subprocess.Popen([sys.executable,"-I","-c",{child_code!r}])\n'
                         'end=time.monotonic()+2\n'
                         f'while not Path({str(heartbeat)!r}).exists() and time.monotonic()<end:time.sleep(.01)\n')
            profile_data['repositories']['demo']['validations']['early-parent']={
                'argv':[sys.executable,'-I','-c',parent_code],'timeout_seconds':1,'replay_safe':True}
            for label, exit_code in (('failed',7),('succeeded',0)):
                launches_path=root/f'budget-{label}-launches'
                code=('import sys\nfrom pathlib import Path\n'
                      f'with Path({str(launches_path)!r}).open("ab") as out:out.write(b"x")\n'
                      'sys.stdout.buffer.write(bytes(1024*1024));sys.stdout.flush()\n'
                      'sys.stderr.buffer.write(bytes(1024*1024));sys.stderr.flush()\n'
                      f'raise SystemExit({exit_code})\n')
                profile_data['repositories']['demo']['validations']['budget-'+label]={
                    'argv':[sys.executable,'-I','-c',code],'timeout_seconds':5,'replay_safe':True}
        profile_path=save('profile.json',profile_data);profile=load_profile(profile_path)
        identity={'implementation_commit':implementation_commit(),'package_digest':core_digest(),'profile_digest':profile.profile_sha256}
        expected_path=save('expected-provenance.json',identity)
        for index,(action,params) in enumerate([
            ('node.status',{}),('repo.audit',{'repository':'demo'}),('fs.list',{'repository':'demo'}),
            ('fs.read_text',{'repository':'demo','relative_path':'sample.txt'}),('git.status',{'repository':'demo'}),
            ('git.diff',{'repository':'demo'}),('validation.run_profile',{'repository':'demo','profile':'echo'}),
            ('fs.write_text_cas',{'repository':'demo','relative_path':'sample.txt','expected_sha256':hashlib.sha256(b'before\n').hexdigest(),'content':'after\n'})]):
            result=execute_task(build_task(profile.node_id,action,params,task_id=f'LH{8000+index}'),profile,root/'direct-state')
            assert result['status']=='succeeded' and all(result[k]==v for k,v in identity.items()),result
            checks.append({'case':'installed-direct-'+action,'status':'PASS'})
        assert (project/'sample.txt').read_bytes()==b'after\n'
        if os.name=='nt':
            checks.append({'case':'CLI Git transport with POSIX SSH fixture','status':'SKIP','reason':'POSIX-specific fixture; Windows service/transport needs its own platform evidence'})
        else:
            bare=root/'mailbox.git';seed=root/'seed';controller=root/'controller';worker_box=root/'worker-mailbox';state=root/'state'
            run([git,'init','--bare','-q',str(bare)])
            run([git,'clone','-q',str(bare),str(seed)])
            run([git,'-C',seed,'config','user.name','fixture']);run([git,'-C',seed,'config','user.email','fixture@example.invalid'])
            for name in ('tasks','results','conflicts'):
                folder=seed/'_executor_spike'/name;folder.mkdir(parents=True);(folder/'.keep').write_text('fixture\n')
            run([git,'-C',seed,'add','.']);run([git,'-C',seed,'commit','-qm','fixture mailbox'])
            run([git,'-C',seed,'branch','-M',policy['branch']]);run([git,'-C',seed,'push','-q','origin',policy['branch']])
            for box in (controller,worker_box):
                run([git,'clone','-q','--branch',policy['branch'],str(bare),str(box)])
                run([git,'-C',box,'remote','set-url','origin',policy['remote_url']])
            shim_code=root/'ssh-fixture.py'
            delayed_push=root/'ssh-fixture-delay-next-push'
            delivered_push=root/'ssh-fixture-delivered'
            shim_code.write_text('import os,shlex,sys,subprocess,time\nfrom pathlib import Path\n'
                'if "-G" in sys.argv: raise SystemExit(0)\n'
                'command=shlex.split(sys.argv[-1])\n'
                'if "git@example.invalid" not in sys.argv or len(command)!=2 or command[0] not in ("git-upload-pack","git-receive-pack") or command[1]!="fixtures/mailbox.git": raise SystemExit(91)\n'
                f'argv=[{git!r},command[0].removeprefix("git-"),{str(bare)!r}]\n'
                f'flag=Path({str(delayed_push)!r})\n'
                'if command[0]=="git-receive-pack" and flag.exists():\n'
                ' flag.unlink()\n code=subprocess.call(argv)\n'
                ' if code: raise SystemExit(code)\n'
                f' Path({str(delivered_push)!r}).write_text("remote accepted push\\n")\n'
                ' time.sleep(15)\n raise SystemExit(0)\n'
                f'os.execv({git!r},argv)\n')
            shim=root/'ssh-fixture';shim.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(shim_code))+' "$@"\n');shim.chmod(0o700)
            key=root/'fixture-key';known=root/'fixture-known-hosts';key.write_text('fixture, not a credential\n');known.write_text('fixture, no network used\n')
            instance=str(uuid.uuid4());record=root/'install-record.json'
            env.update(LOCAL_HAND_GIT_EXECUTABLE=git,LOCAL_HAND_SSH_EXECUTABLE=str(shim),LOCAL_HAND_MAILBOX_SSH_KEY=str(key),
                       LOCAL_HAND_KNOWN_HOSTS=str(known),LOCAL_HAND_MAILBOX_USES_SSH='1',LOCAL_HAND_INSTALL_INSTANCE_ID=instance,
                       LOCAL_HAND_IMPLEMENTATION_COMMIT=identity['implementation_commit'],LOCAL_HAND_INSTALL_RECORD=str(record))
            install_cmd=[sys.executable,'-I','-m','local_hand.installation','--profile',profile_path,'--output',record,
                         '--install-instance-id',instance,'--git',git,'--ssh',shim,'--mailbox-key',key,'--known-hosts',known,
                         '--state-root',state,'--mailbox-root',worker_box,'--wheel',args.wheel.absolute()]
            run(install_cmd);run(install_cmd,expected=2)
            checks.append({'case':'installation record create-only','status':'PASS'})
            connect=[sys.executable,'-I','-m','local_hand_connect.cli']
            common=['--mailbox-repo',controller,'--policy',policy_path]
            # Both installed create-only entry points must remain retryable
            # after a partial write; inject only while their writer is active.
            controller_write_failure_code = '''import errno, os, sys
from unittest import mock
from local_hand_connect import cli, controller
owner = controller if sys.argv[1] == 'marker' else cli
original_writer = owner._write_create_only
def injected_writer(*args, **kwargs):
    original_write = os.write
    calls = 0
    def partial_then_full(fd, data):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original_write(fd, data[:3])
        raise OSError(errno.ENOSPC, 'synthetic controller partial write then disk full')
    with mock.patch.object(os, 'write', side_effect=partial_then_full):
        return original_writer(*args, **kwargs)
with mock.patch.object(owner, '_write_create_only', side_effect=injected_writer):
    raise SystemExit(cli.main(sys.argv[2:]))
'''
            publication_evidence=[]
            controller_marker=controller/'.git/local-hand-connect.json'
            init_args=['init']+common
            assert not _entry_exists_strict(controller_marker)
            failed_stdout=run([sys.executable,'-I','-c',controller_write_failure_code,'marker']+init_args,expected=3)
            failed_command=len(records)
            failure=json.loads((logs/f'{failed_command:03}'/'stderr.log').read_text())
            assert not failed_stdout and failure['error_code']=='controller_file_write_failed' and failure['status']=='indeterminate',failure
            assert 'errno=28' in failure['error'],failure
            failed_target_absent=not _entry_exists_strict(controller_marker)
            assert failed_target_absent
            admitted=json.loads(run(connect+init_args));healthy_command=len(records)
            marker_bytes=controller_marker.read_bytes()
            assert json.loads(marker_bytes)==admitted
            assert admitted['mailbox_root']==str(controller) and admitted['transport_policy']==policy
            assert not run(connect+init_args,expected=2)
            duplicate_command=len(records)
            repeated=json.loads((logs/f'{duplicate_command:03}'/'stderr.log').read_text())
            assert repeated['error_code']=='controller_mailbox_already_initialized',repeated
            assert controller_marker.read_bytes()==marker_bytes
            publication_evidence.append({'case':'marker','path':str(controller_marker),
                'failed_command':failed_command,'healthy_command':healthy_command,'duplicate_command':duplicate_command,
                'failed_target_absent':failed_target_absent,'failure':failure,'duplicate':repeated,
                'bytes':len(marker_bytes),'sha256':hashlib.sha256(marker_bytes).hexdigest(),
                'content':marker_bytes.decode('utf-8')})
            checks.append({'case':'installed controller init partial-write failure retries without overwriting admission','status':'PASS'})

            controller_output=root/'controller-output-task.json'
            build_args=['build','--target-node',profile.node_id,'--action','node.status',
                        '--task-id','LH9850','--output',controller_output]
            assert not _entry_exists_strict(controller_output)
            failed_stdout=run([sys.executable,'-I','-c',controller_write_failure_code,'output']+build_args,expected=3)
            failed_command=len(records)
            failure=json.loads((logs/f'{failed_command:03}'/'stderr.log').read_text())
            assert not failed_stdout and failure['error_code']=='controller_file_write_failed' and failure['status']=='indeterminate',failure
            assert 'errno=28' in failure['error'],failure
            failed_target_absent=not _entry_exists_strict(controller_output)
            assert failed_target_absent
            assert not run(connect+build_args)
            healthy_command=len(records)
            output_bytes=controller_output.read_bytes()
            from local_hand.worker import validate_task
            output_task=validate_task(json.loads(output_bytes))
            assert output_task['task_id']=='LH9850' and output_task['target_node']==profile.node_id
            assert output_task['action']=='node.status' and output_task['params']=={}
            assert not run(connect+build_args,expected=2)
            duplicate_command=len(records)
            repeated=json.loads((logs/f'{duplicate_command:03}'/'stderr.log').read_text())
            assert repeated['error_code']=='controller_output_exists',repeated
            assert controller_output.read_bytes()==output_bytes
            publication_evidence.append({'case':'output','path':str(controller_output),
                'failed_command':failed_command,'healthy_command':healthy_command,'duplicate_command':duplicate_command,
                'failed_target_absent':failed_target_absent,'failure':failure,'duplicate':repeated,
                'bytes':len(output_bytes),'sha256':hashlib.sha256(output_bytes).hexdigest(),
                'content':output_bytes.decode('utf-8'),'task':output_task,'submitted':False})
            checks.append({'case':'installed CLI build partial-write failure retries without overwriting Task output','status':'PASS'})
            save('controller-publication-evidence.json',publication_evidence)
            maintenance_code='''import json,sys
from pathlib import Path
from unittest import mock
from local_hand import git_safety,worker
root=Path(sys.argv[1]);branch=sys.argv[2];original=git_safety.sanitized_git_env;results=[]
for box in (root/'controller',root/'worker-mailbox'):
 for key,value in (('maintenance.auto','true'),('maintenance.autoDetach','false'),('gc.autoPackLimit','1')):
  worker.run_git(['config','--local',key,value],box)
 trace=root/(box.name+'-maintenance-trace.jsonl')
 def environment(**kwargs):return {**original(**kwargs),'GIT_TRACE2_EVENT':str(trace)}
 with mock.patch.object(git_safety,'sanitized_git_env',side_effect=environment):
  worker.sync_mailbox(box,branch)
 events=[json.loads(line) for line in trace.read_text().splitlines()]
 assert any(e.get('event')=='start' and 'fetch' in e.get('argv',[]) for e in events)
 unwanted=[e['argv'] for e in events if e.get('event')=='child_start' and any(v in e.get('argv',[]) for v in ('maintenance','gc'))]
 assert not unwanted,unwanted
 assert worker.run_git(['config','--local','--get','maintenance.auto'],box).stdout.strip()=='true'
 results.append({'mailbox':str(box),'trace':str(trace),'events':len(events),'unwanted_children':unwanted,'local_auto_remains_true':True})
print(json.dumps(results))
'''
            maintenance=json.loads(run([sys.executable,'-I','-c',maintenance_code,root,policy['branch']]))
            save('maintenance-evidence.json',maintenance)
            checks.append({'case':'installed Git operations suppress implicit maintenance without changing local policy','status':'PASS'})
            # The complete installed chain must work without a configured
            # tracking mapping or an origin/<branch> reference.
            for box in (controller,worker_box):
                run([git,'-C',box,'config','--unset-all','remote.origin.fetch'])
                run([git,'-C',box,'update-ref','-d','refs/remotes/origin/'+policy['branch']])
            checks.append({'case':'installed transport fixtures have no tracking mapping or reference','status':'PASS'})
            worker_cmd=[sys.executable,'-I','-m','local_hand.worker','--profile',profile_path,'--mailbox-repo',worker_box,'--state-root',state,'--once']
            outbox_recovery_evidence=[]
            def outbox_recovery_snapshot(task_id,business_file,phase):
                def file_state(path):
                    present=_entry_exists_strict(path)
                    if not present:return {'present':False}
                    raw=path.read_bytes()
                    return {'present':True,'relative_path':str(path.relative_to(root)),
                            'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                return {'task_id':task_id,'phase':phase,'after_command':len(records),
                    'business_file':file_state(business_file),
                    'receipt':file_state(state/'receipts'/f'{task_id}.json'),
                    'remote_result':file_state(worker_box/'_executor_spike/results'/f'{task_id}.json'),
                    'pending':file_state(state/'outbox'/f'{task_id}.json')}
            actions=[('node.status',{},'succeeded'),('repo.audit',{'repository':'demo'},'succeeded'),
                     ('fs.list',{'repository':'demo'},'succeeded'),('fs.read_text',{'repository':'demo','relative_path':'sample.txt'},'succeeded'),
                     ('git.status',{'repository':'demo'},'succeeded'),('git.diff',{'repository':'demo'},'succeeded'),
                     ('validation.run_profile',{'repository':'demo','profile':'echo'},'succeeded'),
                     ('validation.run_profile',{'repository':'demo','profile':'fail'},'failed'),
                     ('fs.write_text_cas',{'repository':'demo','relative_path':'sample.txt','expected_sha256':hashlib.sha256(b'after\n').hexdigest(),'content':'roundtrip\n'},'succeeded'),
                     ('fs.write_text_cas',{'repository':'demo','relative_path':'sample.txt','expected_sha256':'0'*64,'content':'must-not-write'},'stale')]
            for i,(action,params,status) in enumerate(actions):
                task_path=save(f'task-{i}.json',build_task(profile.node_id,action,params,task_id=f'LH{9000+i}'))
                run(connect+['submit']+common+['--task-file',task_path]);run(worker_cmd)
                result=json.loads(run(connect+['wait']+common+['--task-file',task_path,'--timeout-seconds','0','--expected-provenance-file',expected_path]))
                assert result['status']==status,result
                checks.append({'case':'CLI roundtrip '+action+' '+status,'status':'PASS'})
            assert (project/'sample.txt').read_bytes()==b'roundtrip\n'
            (project/'sample.txt').write_bytes(b'after-controller-result\n')
            run(connect+['submit']+common+['--task-file',root/'task-8.json']);run(worker_cmd)
            assert (project/'sample.txt').read_bytes()==b'after-controller-result\n'
            checks.append({'case':'restart and duplicate task do not replay CAS','status':'PASS'})
            wrong=save('wrong-target.json',build_task('other-node','node.status',{},task_id='LH9998'))
            run(connect+['submit']+common+['--task-file',wrong]);run(worker_cmd)
            run(connect+['wait']+common+['--task-file',wrong,'--timeout-seconds','0',
                                        '--expected-provenance-file',expected_path],expected=3)
            assert not _entry_exists_strict(state/'receipts'/'LH9998.json')
            checks.append({'case':'wrong target ignored; timeout remains indeterminate','status':'PASS'})
            invalid_call=save('invalid-call.json',build_task(profile.node_id,'fs.write_text_cas',{
                'repository':'demo','relative_path':'sample.txt',
                'expected_sha256':hashlib.sha256(b'after-controller-result\n').hexdigest(),
                'content':'must-not-publish'},task_id='LH9997'))
            run(connect+['call']+common+['--task-file',invalid_call,'--timeout-seconds','nan',
                                        '--expected-provenance-file',expected_path],expected=2)
            assert not run([git,'--git-dir',bare,'ls-tree','--name-only',policy['branch'],'--',
                            '_executor_spike/tasks/LH9997.json']).strip()
            assert (project/'sample.txt').read_bytes()==b'after-controller-result\n'
            checks.append({'case':'invalid call timing rejected before task publication','status':'PASS'})

            # Publish a synthetic conflict next to the already successful first
            # task. A real installed controller must not hide that uncertainty.
            first_task=json.loads((root/'task-0.json').read_text())
            conflict=result_error(first_task,profile.node_id,
                                  LocalHandError('remote_result_content_conflict','synthetic collision','indeterminate'),identity)
            run([git,'-C',seed,'fetch','origin',policy['branch']])
            run([git,'-C',seed,'reset','--hard','FETCH_HEAD'])
            conflict_path=seed/'_executor_spike/conflicts'/conflict_filename(task_digest(first_task))
            with conflict_path.open('x',encoding='utf-8') as stream:
                stream.write(json.dumps(conflict,sort_keys=True)+'\n')
            run([git,'-C',seed,'add','--',conflict_path.relative_to(seed).as_posix()])
            run([git,'-C',seed,'commit','-qm','synthetic result conflict'])
            run([git,'-C',seed,'push','origin',policy['branch']])
            actual=json.loads(run(connect+['wait']+common+['--task-file',root/'task-0.json',
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert actual==conflict,actual
            checks.append({'case':'matching conflict takes precedence over canonical success','status':'PASS'})
            # A conflict with no local receipt must stop the real installed
            # worker before CAS, and become a durable recovery barrier.
            blocked_task=build_task(profile.node_id,'fs.write_text_cas',{
                'repository':'demo','relative_path':'sample.txt',
                'expected_sha256':hashlib.sha256(b'after-controller-result\n').hexdigest(),
                'content':'must-not-replay'},task_id='LH9996')
            blocked_path=save('remote-conflict-cas-task.json',blocked_task)
            blocked=result_error(blocked_task,profile.node_id,
                LocalHandError('outcome_unknown','synthetic prior uncertainty','indeterminate'),identity)
            run(connect+['submit']+common+['--task-file',blocked_path])
            run([git,'-C',seed,'fetch','origin',policy['branch']])
            run([git,'-C',seed,'reset','--hard','FETCH_HEAD'])
            rel='_executor_spike/conflicts/'+conflict_filename(task_digest(blocked_task))
            remote_path=seed/rel
            remote_path.write_text(json.dumps(blocked,sort_keys=True)+'\n')
            run([git,'-C',seed,'add','--',rel]);run([git,'-C',seed,'commit','-qm','synthetic CAS conflict'])
            run([git,'-C',seed,'push','origin',policy['branch']])
            run(worker_cmd)
            received=json.loads(run(connect+['wait']+common+['--task-file',blocked_path,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert received==blocked,received
            assert (project/'sample.txt').read_bytes()==b'after-controller-result\n'
            assert not _entry_exists_strict(state/'receipts/LH9996.json')
            assert not _entry_exists_strict(worker_box/'_executor_spike/results/LH9996.json')
            marker=state/'conflicts'/remote_path.name;marker_bytes=marker.read_bytes()
            assert json.loads(marker_bytes)==blocked
            checks.append({'case':'remote conflict blocks installed CAS without a local receipt','status':'PASS'})

            run([git,'-C',seed,'rm','--',rel]);run([git,'-C',seed,'commit','-qm','synthetic conflict loss'])
            run([git,'-C',seed,'push','origin',policy['branch']]);run(worker_cmd)
            received=json.loads(run(connect+['wait']+common+['--task-file',blocked_path,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert received==blocked and marker.read_bytes()==marker_bytes
            assert (worker_box/rel).read_bytes()==marker_bytes
            assert (project/'sample.txt').read_bytes()==b'after-controller-result\n'
            checks.append({'case':'restart republishes lost remote conflict without CAS replay','status':'PASS'})

            run([git,'-C',seed,'fetch','origin',policy['branch']])
            run([git,'-C',seed,'reset','--hard','FETCH_HEAD'])
            remote_bytes=remote_path.read_bytes()
            remote_path.write_text(json.dumps({**blocked,'details':{'changed':True}})+'\n')
            run([git,'-C',seed,'add','--',rel]);run([git,'-C',seed,'commit','-qm','synthetic conflict drift'])
            run([git,'-C',seed,'push','origin',policy['branch']]);run(worker_cmd,expected=3)
            assert marker.read_bytes()==marker_bytes
            assert (worker_box/rel).read_bytes()==remote_path.read_bytes()
            assert (project/'sample.txt').read_bytes()==b'after-controller-result\n'
            checks.append({'case':'installed worker reports indeterminate for remote conflict drift','status':'PASS'})
            remote_path.write_bytes(remote_bytes)
            run([git,'-C',seed,'add','--',rel]);run([git,'-C',seed,'commit','-qm','restore synthetic conflict'])
            run([git,'-C',seed,'push','origin',policy['branch']]);run(worker_cmd)
            assert marker.read_bytes()==marker_bytes
            checks.append({'case':'restored conflict resumes clean polling without replay','status':'PASS'})
            # Real local Git accepts the push; the fixture then delays SSH
            # completion past the admitted Git timeout. No product mocks.
            uncertain_task=build_task(profile.node_id,'fs.write_text_cas',{
                'repository':'demo','relative_path':'sample.txt',
                'expected_sha256':hashlib.sha256(b'after-controller-result\n').hexdigest(),
                'content':'delivered-once\n'},task_id='LH9995')
            uncertain_path=save('lost-ack-cas-task.json',uncertain_task)
            delayed_push.write_text('delay exactly the next synthetic receive-pack\n')
            run(connect+['submit']+common+['--task-file',uncertain_path],expected=3,
                override={'LOCAL_HAND_GIT_TIMEOUT_SECONDS':'2'})
            stderr=(logs/f'{len(records):03}'/'stderr.log').read_text()
            assert 'controller_publish_failed' in stderr and 'git_timeout' in stderr,stderr
            assert delivered_push.is_file() and not _entry_exists_strict(delayed_push)
            delivered_push.rename(root/'controller-push-delivered.txt')
            remote_task=json.loads(run([git,'--git-dir',bare,'show',policy['branch']+':_executor_spike/tasks/LH9995.json']))
            assert remote_task==uncertain_task
            checks.append({'case':'installed controller reports indeterminate after delivered push times out','status':'PASS'})

            delayed_push.write_text('delay exactly the next synthetic receive-pack\n')
            run(worker_cmd,expected=3,override={'LOCAL_HAND_GIT_TIMEOUT_SECONDS':'2'})
            stderr=(logs/f'{len(records):03}'/'stderr.log').read_text()
            assert 'mailbox_publish_failed' in stderr and 'git_timeout' in stderr,stderr
            assert delivered_push.is_file() and not _entry_exists_strict(delayed_push)
            delivered_push.rename(root/'worker-push-delivered.txt')
            assert (project/'sample.txt').read_bytes()==b'delivered-once\n'
            receipt_path=state/'receipts/LH9995.json';receipt_bytes=receipt_path.read_bytes()
            saved=json.loads(receipt_bytes)['result']
            assert saved['status']=='succeeded'
            assert json.loads((state/'outbox/LH9995.json').read_text())==saved
            remote_result=json.loads(run([git,'--git-dir',bare,'show',policy['branch']+':_executor_spike/results/LH9995.json']))
            assert remote_result==saved
            lost_ack_before=outbox_recovery_snapshot('LH9995',project/'sample.txt','delivered-timeout')
            assert lost_ack_before['pending']['present']
            checks.append({'case':'installed worker retains successful result and outbox after delivered push timeout','status':'PASS'})

            (project/'sample.txt').write_bytes(b'recovery-sentinel\n')
            run(worker_cmd)
            actual=json.loads(run(connect+['wait']+common+['--task-file',uncertain_path,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert actual==saved and receipt_path.read_bytes()==receipt_bytes
            assert not _entry_exists_strict(state/'outbox/LH9995.json')
            lost_ack_recovered=outbox_recovery_snapshot('LH9995',project/'sample.txt','first-recovery')
            run(connect+['submit']+common+['--task-file',uncertain_path]);run(worker_cmd)
            assert (project/'sample.txt').read_bytes()==b'recovery-sentinel\n'
            lost_ack_repeated=outbox_recovery_snapshot('LH9995',project/'sample.txt','repeat-submit-worker')
            for field in ('receipt','remote_result'):
                assert lost_ack_before[field]['sha256']==lost_ack_recovered[field]['sha256']==lost_ack_repeated[field]['sha256']
            assert lost_ack_recovered['business_file']['sha256']==lost_ack_repeated['business_file']['sha256']
            assert not lost_ack_recovered['pending']['present'] and not lost_ack_repeated['pending']['present']
            outbox_recovery_evidence.append({'case':'delivered-push-timeout','task_id':'LH9995',
                'snapshots':[lost_ack_before,lost_ack_recovered,lost_ack_repeated]})
            checks.append({'case':'restart and same-task reconciliation preserve delivery result without replay','status':'PASS'})

            broken_task=build_task(profile.node_id,'fs.write_text_cas',{
                'repository':'demo','relative_path':'sample.txt',
                'expected_sha256':hashlib.sha256(b'recovery-sentinel\n').hexdigest(),
                'content':'must-not-replay'},task_id='LH9994')
            broken_path=save('broken-receipt-cas-task.json',broken_task)
            broken_receipt=state/'receipts/LH9994.json';missing_receipt=state/'absent-receipt-payload.json'
            broken_receipt.symlink_to(missing_receipt)
            run(connect+['submit']+common+['--task-file',broken_path]);run(worker_cmd)
            actual=json.loads(run(connect+['wait']+common+['--task-file',broken_path,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert actual['status']=='indeterminate' and actual['error_code']=='local_receipt_invalid',actual
            assert broken_receipt.is_symlink() and broken_receipt.readlink()==missing_receipt
            assert not _entry_exists_strict(missing_receipt) and (project/'sample.txt').read_bytes()==b'recovery-sentinel\n'
            assert not _entry_exists_strict(worker_box/'_executor_spike/results/LH9994.json')
            checks.append({'case':'installed worker preserves dangling receipt and rejects CAS replay','status':'PASS'})
            lifetime_task=save('lifetime-task.json',build_task(profile.node_id,'validation.run_profile',{
                'repository':'demo','profile':'early-parent'},task_id='LH9993'))
            run(connect+['submit']+common+['--task-file',lifetime_task]);run(worker_cmd)
            actual=json.loads(run(connect+['wait']+common+['--task-file',lifetime_task,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert actual['status']=='failed' and actual['error_code']=='validation_timeout',actual
            details=actual['details']
            assert details['timed_out'] and details['termination_confirmed'] and details['pipes_closed'],details
            assert details['termination_scope']=='process_tree' and details['duration_seconds']<8,details
            pulse=heartbeat.read_bytes();time.sleep(.15)
            assert pulse and heartbeat.read_bytes()==pulse and launches.read_bytes()==b'x'
            lifetime_receipt=state/'receipts/LH9993.json';receipt_bytes=lifetime_receipt.read_bytes()
            assert json.loads(receipt_bytes)['result']==actual
            checks.append({'case':'installed parent exit remains subject to timeout and descendant cleanup','status':'PASS'})
            run(connect+['submit']+common+['--task-file',lifetime_task]);run(worker_cmd)
            again=json.loads(run(connect+['wait']+common+['--task-file',lifetime_task,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert again==actual and lifetime_receipt.read_bytes()==receipt_bytes
            assert launches.read_bytes()==b'x' and heartbeat.read_bytes()==pulse
            checks.append({'case':'failed validation receipt reconciles without relaunching descendant','status':'PASS'})
            for label, task_id, status in (('failed','LH9992','failed'),('succeeded','LH9991','indeterminate')):
                budget_task=save(f'budget-{label}-task.json',build_task(profile.node_id,'validation.run_profile',{
                    'repository':'demo','profile':'budget-'+label},task_id=task_id))
                run(connect+['submit']+common+['--task-file',budget_task]);run(worker_cmd)
                actual=json.loads(run(connect+['wait']+common+['--task-file',budget_task,
                    '--timeout-seconds','0','--expected-provenance-file',expected_path]))
                assert actual['status']==status and actual['error_code']=='result_too_large',actual
                summary=actual['details']
                assert summary['original_status']==label and summary['original_details_omitted']
                assert summary['original_error_code']==('validation_failed' if label=='failed' else None)
                assert summary['original_result_json_bytes']>summary['result_limit_bytes']
                assert len(summary['original_result_sha256'])==64 and 'stdout' not in summary
                budget_receipt=state/'receipts'/f'{task_id}.json';receipt_bytes=budget_receipt.read_bytes()
                assert json.loads(receipt_bytes)['result']==actual
                assert (root/f'budget-{label}-launches').read_bytes()==b'x'
                checks.append({'case':f'installed {label} validation JSON expansion produces a bounded durable result','status':'PASS'})
                run(connect+['submit']+common+['--task-file',budget_task]);run(worker_cmd)
                again=json.loads(run(connect+['wait']+common+['--task-file',budget_task,
                    '--timeout-seconds','0','--expected-provenance-file',expected_path]))
                assert again==actual and budget_receipt.read_bytes()==receipt_bytes
                assert (root/f'budget-{label}-launches').read_bytes()==b'x'
                checks.append({'case':f'installed {label} validation size failure recovers without replay','status':'PASS'})
            # Real committed mailbox state must win over interrupted local
            # creation. Preserve these files as evidence, then resume normally.
            interrupted=build_task(profile.node_id,'fs.write_text_cas',{
                'repository':'demo','relative_path':'sample.txt',
                'expected_sha256':hashlib.sha256(b'recovery-sentinel\n').hexdigest(),
                'content':'precommit-applied\n'},task_id='LH9990')
            interrupted_path=save('precommit-task.json',interrupted)
            (controller/'_executor_spike/tasks/LH9990.json').write_bytes(interrupted_path.read_bytes())
            submission=json.loads(run(connect+['submit']+common+['--task-file',interrupted_path]))
            assert submission['status']=='submitted',submission
            assert json.loads(run([git,'--git-dir',bare,'show',policy['branch']+':_executor_spike/tasks/LH9990.json']))==interrupted
            checks.append({'case':'installed controller resumes local precommit task and really publishes it','status':'PASS'})
            from local_hand.worker import _persist_result
            completed=execute_task(interrupted,profile,state)
            _persist_result(outbox=state/'outbox',receipts=state/'receipts',task=interrupted,result=completed)
            receipt_bytes=(state/'receipts/LH9990.json').read_bytes()
            interrupted_result=(state/'outbox/LH9990.json').read_bytes()
            (worker_box/'_executor_spike/results/LH9990.json').write_bytes(interrupted_result)
            local_only=build_task(profile.node_id,'fs.write_text_cas',{
                'repository':'demo','relative_path':'sample.txt',
                'expected_sha256':hashlib.sha256(b'recovery-sentinel\n').hexdigest(),
                'content':'must-not-execute-local-task'},task_id='LH9989')
            local_only_path=save('uncommitted-local-task.json',local_only)
            (worker_box/'_executor_spike/tasks/LH9989.json').write_bytes(local_only_path.read_bytes())
            (project/'sample.txt').write_bytes(b'recovery-sentinel\n')
            run(worker_cmd)
            received=json.loads(run(connect+['wait']+common+['--task-file',interrupted_path,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert received==completed and (state/'receipts/LH9990.json').read_bytes()==receipt_bytes
            assert not _entry_exists_strict(state/'outbox/LH9990.json')
            checks.append({'case':'installed worker publishes retained precommit result without replay','status':'PASS'})
            assert not _entry_exists_strict(state/'receipts/LH9989.json')
            assert (project/'sample.txt').read_bytes()==b'recovery-sentinel\n'
            checks.append({'case':'installed worker does not execute uncommitted local task','status':'PASS'})
            from local_hand.protocol import result_success
            fake_task=build_task(profile.node_id,'node.status',{},task_id='LH9988')
            fake_task_path=save('uncommitted-result-task.json',fake_task)
            fake_result=save('uncommitted-result.json',result_success(fake_task,profile.node_id,{'local_only':True},identity))
            (controller/'_executor_spike/results/LH9988.json').write_bytes(fake_result.read_bytes())
            run(connect+['wait']+common+['--task-file',fake_task_path,'--timeout-seconds','0',
                '--expected-provenance-file',expected_path],expected=3)
            assert 'controller_wait_timeout' in (logs/f'{len(records):03}'/'stderr.log').read_text()
            assert not run([git,'--git-dir',bare,'ls-tree','--name-only',policy['branch'],'--',
                '_executor_spike/tasks/LH9989.json','_executor_spike/results/LH9989.json',
                '_executor_spike/results/LH9988.json']).strip()
            checks.append({'case':'installed controller rejects uncommitted local result as delivery evidence','status':'PASS'})
            expected_archives={
                (controller,'_executor_spike/tasks/LH9990.json'):interrupted_path.read_bytes(),
                (controller,'_executor_spike/results/LH9988.json'):fake_result.read_bytes(),
                (worker_box,'_executor_spike/tasks/LH9989.json'):local_only_path.read_bytes(),
                (worker_box,'_executor_spike/results/LH9990.json'):interrupted_result,
            }
            for (box,relative),raw in expected_archives.items():
                found=[]
                for record_path in (box/'.git/local-hand-untracked').glob('*/record.json'):
                    item=json.loads(record_path.read_text())
                    if item['relative_path']==relative:
                        assert item['sha256']==hashlib.sha256(raw).hexdigest() and item['bytes']==len(raw)
                        assert (record_path.parent/'payload').read_bytes()==raw
                        found.append(record_path)
                assert len(found)==1,(relative,found)
            checks.append({'case':'installed untracked control evidence retains exact bytes and path manifest','status':'PASS'})
            fault_code='''import errno,json,os,stat,sys
from pathlib import Path
from unittest import mock
from local_hand import mailbox_safety
from local_hand.protocol import LocalHandError
root=Path(sys.argv[1]);(root/'_executor_spike/tasks').mkdir(parents=True)
events=[]
for index,operation in enumerate(('write','fsync')):
 target=root/'_executor_spike/tasks'/f'LH{7100+index}.json'
 with mock.patch.object(mailbox_safety.os,operation,side_effect=OSError(errno.EIO,'synthetic I/O fault')):
  try:mailbox_safety.atomic_create_control_file(root,target,b'payload')
  except LocalHandError as exc:
   assert exc.status=='indeterminate';events.append({'fault':operation,'code':exc.code,'status':exc.status})
  else:raise AssertionError('fault was hidden')
 assert not target.exists() and not list(target.parent.glob('.lh-*.tmp'))
 mailbox_safety.atomic_create_control_file(root,target,b'payload')
 assert target.read_bytes()==b'payload'
original=os.fsync
def fail_directory(fd):
 if stat.S_ISDIR(os.fstat(fd).st_mode):raise OSError(errno.EIO,'synthetic directory sync fault')
 return original(fd)
target=root/'_executor_spike/tasks/LH7102.json'
with mock.patch.object(mailbox_safety.os,'fsync',side_effect=fail_directory):
 try:mailbox_safety.atomic_create_control_file(root,target,b'payload')
 except LocalHandError as exc:
  assert exc.status=='indeterminate';events.append({'fault':'directory-fsync','code':exc.code,'status':exc.status})
 else:raise AssertionError('directory sync failure was hidden')
assert target.read_bytes()==b'payload' and not list(target.parent.glob('.lh-*.tmp'))
from local_hand import worker
outbox=root/'outbox';outbox.mkdir()
with mock.patch.object(os,'scandir',side_effect=OSError(errno.EIO,'synthetic outbox scan fault')),mock.patch.object(os,'listdir',side_effect=OSError(errno.EIO,'synthetic outbox scan fault')):
 try:worker.publish_outbox(root,'fixture/mailbox-v1',outbox)
 except LocalHandError as exc:
  assert exc.code=='local_outbox_unreadable' and exc.status=='indeterminate'
  events.append({'fault':'outbox-scan','code':exc.code,'status':exc.status})
 else:raise AssertionError('unreadable outbox was mistaken for an empty queue')
worker.publish_outbox(root,'fixture/mailbox-v1',outbox)
import hashlib
pending=outbox/'LH7103.json';pending.write_bytes(b'new invalid evidence')
quarantine=root/'quarantine';quarantine.mkdir()
reason='synthetic invalid record'
prior=quarantine/(pending.name+'.'+hashlib.sha256(reason.encode()).hexdigest()[:12]+'.invalid')
prior.write_bytes(b'prior invalid evidence')
original_lstat=os.lstat
def unreadable_prior(path,*args,**kwargs):
 if not isinstance(path,int) and Path(path)==prior:raise OSError(errno.EIO,'synthetic metadata fault')
 return original_lstat(path,*args,**kwargs)
with mock.patch.object(os,'lstat',side_effect=unreadable_prior):
 try:worker._quarantine_local_outbox_file(outbox,pending,reason)
 except LocalHandError as exc:
  assert exc.code=='path_state_unavailable' and exc.status=='indeterminate'
  events.append({'fault':'quarantine-lookup','code':exc.code,'status':exc.status})
 else:raise AssertionError('unreadable prior evidence was overwritten')
assert prior.read_bytes()==b'prior invalid evidence' and pending.read_bytes()==b'new invalid evidence'
worker._quarantine_local_outbox_file(outbox,pending,reason)
assert prior.read_bytes()==b'prior invalid evidence'
assert prior.with_name(prior.stem+'.1.invalid').read_bytes()==b'new invalid evidence'
print(json.dumps(events))
'''
            fault_events=json.loads(run([sys.executable,'-I','-c',fault_code,root/'atomic-retry-fixture']))
            assert len(fault_events)==5
            for event in fault_events:
                checks.append({'case':'installed atomic publication fault '+event['fault'],'status':'PASS'})
            # Inject only filesystem metadata errors. The installed entry point,
            # installation binding, Git transport, receipt and recovery are real.
            lookup_code='''import errno,os,sys
from pathlib import Path
from unittest import mock
target=Path(sys.argv[1]);mode=sys.argv[2];original=os.lstat
if mode=='worker':
 from local_hand.worker import main
else:
 from local_hand_connect.cli import main
def lookup(path,*args,**kwargs):
 if not isinstance(path,int) and Path(path)==target:raise OSError(errno.EIO,'synthetic metadata lookup fault',os.fspath(path))
 return original(path,*args,**kwargs)
with mock.patch.object(os,'lstat',side_effect=lookup):
 raise SystemExit(main(sys.argv[3:]))
'''
            def lookup_rejected(target,mode,argv):
                output=run([sys.executable,'-I','-c',lookup_code,target,mode]+argv,expected=3)
                error=(logs/f'{len(records):03}'/'stderr.log').read_text()
                assert 'path_state_unavailable' in error and 'errno=5' in error
                if mode=='worker':assert not output
            receipt_path=state/'receipts/LH9995.json';receipt_before=receipt_path.read_bytes()
            receipt_result=json.loads(receipt_before)['result']
            run([git,'-C',seed,'fetch','origin',policy['branch']])
            run([git,'-C',seed,'reset','--hard','FETCH_HEAD'])
            run([git,'-C',seed,'rm','--','_executor_spike/results/LH9995.json'])
            run([git,'-C',seed,'commit','-qm','synthetic canonical result loss'])
            run([git,'-C',seed,'push','origin',policy['branch']])
            lookup_rejected(receipt_path,'worker',worker_cmd[4:])
            assert receipt_path.read_bytes()==receipt_before
            assert (project/'sample.txt').read_bytes()==b'recovery-sentinel\n'
            assert not _entry_exists_strict(state/'outbox/LH9995.json')
            run(worker_cmd)
            actual=json.loads(run(connect+['wait']+common+['--task-file',root/'lost-ack-cas-task.json',
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert actual==receipt_result and receipt_path.read_bytes()==receipt_before
            assert (project/'sample.txt').read_bytes()==b'recovery-sentinel\n'
            checks.append({'case':'installed unreadable receipt stops and later republishes without CAS replay','status':'PASS'})
            conflict_name=conflict_filename(task_digest(blocked_task))
            marker_path=state/'conflicts'/conflict_name;marker_before=marker_path.read_bytes()
            run([git,'-C',seed,'fetch','origin',policy['branch']])
            run([git,'-C',seed,'reset','--hard','FETCH_HEAD'])
            run([git,'-C',seed,'rm','--','_executor_spike/conflicts/'+conflict_name])
            run([git,'-C',seed,'commit','-qm','synthetic conflict loss before metadata fault'])
            run([git,'-C',seed,'push','origin',policy['branch']])
            lookup_rejected(marker_path,'worker',worker_cmd[4:])
            assert marker_path.read_bytes()==marker_before and not _entry_exists_strict(state/'receipts/LH9996.json')
            assert (project/'sample.txt').read_bytes()==b'recovery-sentinel\n'
            residue_code='''import json,sys
from pathlib import Path
from unittest import mock
from local_hand import worker
marker=Path(sys.argv[1]);original=worker.run_git;events=[]
def run(args,cwd,**kwargs):
 result=original(args,cwd,**kwargs)
 if args[:2]==['reset','--hard'] and args[2]!='HEAD' and not events:
  target=cwd/'_executor_spike/conflicts'/marker.name
  target.write_bytes(marker.read_bytes());events.append(str(target))
 return result
with mock.patch.object(worker,'run_git',side_effect=run):
 code=worker.main(sys.argv[2:])
assert len(events)==1
raise SystemExit(code)
'''
            run([sys.executable,'-I','-c',residue_code,marker_path]+worker_cmd[4:])
            residue_archives=[p for p in (worker_box/'.git/local-hand-untracked').glob('*/record.json')
                if json.loads(p.read_text())['relative_path']=='_executor_spike/conflicts/'+conflict_name]
            assert len(residue_archives)==1
            assert (residue_archives[0].parent/'payload').read_bytes()==marker_before
            save('reset-residue-evidence.json',{'archive':str(residue_archives[0]),
                'sha256':hashlib.sha256(marker_before).hexdigest(),'task_id':'LH9996'})
            actual=json.loads(run(connect+['wait']+common+['--task-file',blocked_path,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert actual==json.loads(marker_before)
            checks.append({'case':'installed conflict recovery ignores untracked reset residue','status':'PASS'})
            assert marker_path.read_bytes()==marker_before and not _entry_exists_strict(state/'receipts/LH9996.json')
            assert (project/'sample.txt').read_bytes()==b'recovery-sentinel\n'
            checks.append({'case':'installed unreadable conflict stops and later restores the replay barrier','status':'PASS'})
            first_marker=controller/'_executor_spike/conflicts'/conflict_filename(task_digest(first_task))
            first_wait=['wait']+common+['--task-file',root/'task-0.json',
                '--timeout-seconds','0','--expected-provenance-file',expected_path]
            lookup_rejected(first_marker,'controller',first_wait)
            assert json.loads(run(connect+first_wait))==conflict
            checks.append({'case':'installed controller does not accept success through an unreadable conflict','status':'PASS'})
            persistence_code='''import errno,os,sys
from pathlib import Path
from unittest import mock
from local_hand import worker
task_id,stage,phase=sys.argv[1:4];original=worker.write_json_atomic
def injected(path,value,**kwargs):
 selected=path.name==task_id+'.json' and ((stage=='intent' and path.parent.name=='receipts' and 'result' not in value) or (stage=='outbox' and path.parent.name=='outbox') or (stage=='receipt' and path.parent.name=='receipts' and 'result' in value))
 if selected:
  owner,method=(worker,'_fsync_parent') if phase=='after-replace' else (os,'write')
  with mock.patch.object(owner,method,side_effect=OSError(errno.ENOSPC,'synthetic persistence failure')):
   return original(path,value,**kwargs)
 return original(path,value,**kwargs)
with mock.patch.object(worker,'write_json_atomic',side_effect=injected):
 raise SystemExit(worker.main(sys.argv[4:]))
'''
            persistence_cases=[('intent','before-replace'),('outbox','before-replace'),
                ('receipt','before-replace'),('outbox','after-replace'),('receipt','after-replace')]
            persistence_evidence=[]
            for index,(stage,phase) in enumerate(persistence_cases):
                task_id=f'LH{9600+index}'
                relative=f'persistence-{task_id}.txt';target=project/relative;target.write_bytes(b'before\n')
                task=build_task(profile.node_id,'fs.write_text_cas',{'repository':'demo','relative_path':relative,
                    'expected_sha256':hashlib.sha256(b'before\n').hexdigest(),'content':'after\n'},task_id=task_id)
                task_path=save(f'persistence-{task_id}-task.json',task)
                run(connect+['submit']+common+['--task-file',task_path])
                output=run([sys.executable,'-I','-c',persistence_code,task_id,stage,phase]+worker_cmd[4:],expected=3)
                error=(logs/f'{len(records):03}'/'stderr.log').read_text()
                expected_code='local_state_durability_unconfirmed' if phase=='after-replace' else 'local_state_write_failed'
                assert not output and expected_code in error and 'errno=28' in error
                receipt=state/'receipts'/f'{task_id}.json';pending=state/'outbox'/f'{task_id}.json'
                assert target.read_bytes()==(b'before\n' if stage=='intent' else b'after\n')
                assert _entry_exists_strict(receipt)==(stage!='intent')
                retained=stage=='receipt' or phase=='after-replace'
                assert _entry_exists_strict(pending)==retained
                item={'task_id':task_id,'stage':stage,'phase':phase,'error_code':expected_code,
                    'failed_command':len(records),'file_after_failure_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                    'receipt_after_failure':json.loads(receipt.read_text()) if _entry_exists_strict(receipt) else None,
                    'outbox_after_failure':json.loads(pending.read_text()) if _entry_exists_strict(pending) else None}
                if retained:assert item['outbox_after_failure']['status']=='succeeded'
                if stage!='intent':target.write_bytes(b'recovery-sentinel\n')
                run(worker_cmd)
                result=json.loads(run(connect+['wait']+common+['--task-file',task_path,
                    '--timeout-seconds','0','--expected-provenance-file',expected_path]))
                expected_status='indeterminate' if stage=='outbox' and phase=='before-replace' else 'succeeded'
                assert result['status']==expected_status
                if expected_status=='indeterminate':assert result['error_code']=='outcome_unknown'
                assert json.loads(receipt.read_text())['result']==result and not _entry_exists_strict(pending)
                assert target.read_bytes()==(b'after\n' if stage=='intent' else b'recovery-sentinel\n')
                item.update(result=result,file_after_recovery_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
                persistence_evidence.append(item)
                checks.append({'case':f'installed state persistence recovery {stage} {phase}','status':'PASS'})
            save('persistence-recovery-evidence.json',persistence_evidence)
            read_code='''import errno,os,sys
from pathlib import Path
from unittest import mock
from local_hand import worker
target=Path(sys.argv[1]);mode=sys.argv[2];original=worker.read_regular_file_bounded
def read(path,*args,**kwargs):
 if path==target:
  with mock.patch.object(os,'read',side_effect=OSError(errno.EIO,'synthetic payload read failure')):
   return original(path,*args,**kwargs)
 return original(path,*args,**kwargs)
if mode=='worker':main=worker.main
else:
 from local_hand_connect.cli import main
with mock.patch.object(worker,'read_regular_file_bounded',side_effect=read):
 raise SystemExit(main(sys.argv[3:]))
'''
            def state_view():
                view={}
                for namespace in ('receipts','outbox','conflicts','quarantine'):
                    for path in (state/namespace).rglob('*'):
                        relative=path.relative_to(state).as_posix()
                        if path.is_symlink():view[relative]={'link':str(path.readlink())}
                        elif path.is_file():
                            raw=path.read_bytes();view[relative]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
                return view
            def rejected_read(target,mode,argv,task_id,kind,file_path):
                before=state_view();file_before=file_path.read_bytes()
                head_before=run([git,'--git-dir',bare,'rev-parse','refs/heads/'+policy['branch']]).strip()
                stdout=run([sys.executable,'-I','-c',read_code,target,mode]+argv,expected=3)
                failed_command=len(records)
                error=(logs/f'{failed_command:03}'/'stderr.log').read_text()
                assert not stdout and 'json_read_unavailable' in error and 'errno=5' in error
                head_after=run([git,'--git-dir',bare,'rev-parse','refs/heads/'+policy['branch']]).strip()
                after=state_view()
                assert before==after and file_path.read_bytes()==file_before and head_before==head_after
                return {'task_id':task_id,'case':kind,'mode':mode,'target':str(target),
                    'failed_command':failed_command,'state_before':before,'state_after':after,
                    'remote_before':head_before,'remote_after':head_after,
                    'file_before_sha256':hashlib.sha256(file_before).hexdigest(),
                    'file_after_failure_sha256':hashlib.sha256(file_path.read_bytes()).hexdigest()}
            read_evidence=[]
            for index,kind in enumerate(('task','receipt','outbox','remote-result','remote-ack')):
                task_id=f'LH{9800+index}';target_file=project/f'read-{task_id}.txt';target_file.write_bytes(b'before\n')
                task=build_task(profile.node_id,'fs.write_text_cas',{'repository':'demo','relative_path':target_file.name,
                    'expected_sha256':hashlib.sha256(b'before\n').hexdigest(),'content':'after\n'},task_id=task_id)
                task_path=save(f'read-{task_id}-task.json',task)
                run(connect+['submit']+common+['--task-file',task_path])
                receipt=state/'receipts'/f'{task_id}.json';pending=state/'outbox'/f'{task_id}.json'
                canonical=worker_box/'_executor_spike/results'/f'{task_id}.json'
                if kind=='outbox':
                    run([sys.executable,'-I','-c',persistence_code,task_id,'receipt','before-replace']+worker_cmd[4:],expected=3)
                    error=(logs/f'{len(records):03}'/'stderr.log').read_text()
                    assert 'local_state_write_failed' in error and 'errno=28' in error
                    assert json.loads(receipt.read_text())['source']=='local_execution_started'
                    assert json.loads(pending.read_text())['status']=='succeeded'
                elif kind!='task':run(worker_cmd)
                if kind!='task':
                    assert target_file.read_bytes()==b'after\n';target_file.write_bytes(b'recovery-sentinel\n')
                if kind=='remote-result':
                    (root/f'read-{task_id}-receipt-before-removal.json').write_bytes(receipt.read_bytes())
                    receipt.unlink()
                elif kind=='remote-ack':pending.write_bytes(canonical.read_bytes())
                target={'task':worker_box/'_executor_spike/tasks'/f'{task_id}.json','receipt':receipt,
                    'outbox':pending,'remote-result':canonical,'remote-ack':canonical}[kind]
                item=rejected_read(target,'worker',worker_cmd[4:],task_id,kind,target_file)
                run(worker_cmd)
                result=json.loads(run(connect+['wait']+common+['--task-file',task_path,
                    '--timeout-seconds','0','--expected-provenance-file',expected_path]))
                assert result['status']=='succeeded' and json.loads(receipt.read_text())['result']==result
                assert not _entry_exists_strict(pending)
                assert not _entry_exists_strict(state/'conflicts'/conflict_filename(task_digest(task)))
                assert target_file.read_bytes()==(b'after\n' if kind=='task' else b'recovery-sentinel\n')
                item.update(result=result,file_after_recovery_sha256=hashlib.sha256(target_file.read_bytes()).hexdigest())
                if kind=='remote-ack':
                    remote_ack_recovered=outbox_recovery_snapshot(task_id,target_file,'first-recovery')
                    run(worker_cmd)
                    remote_ack_repeated=outbox_recovery_snapshot(task_id,target_file,'repeat-worker')
                    for field in ('business_file','receipt','remote_result'):
                        assert remote_ack_recovered[field]['sha256']==remote_ack_repeated[field]['sha256']
                    assert not remote_ack_recovered['pending']['present'] and not remote_ack_repeated['pending']['present']
                    item['repeat_worker_command']=len(records)
                    outbox_recovery_evidence.append({'case':'remote-ack-read-failure','task_id':task_id,
                        'snapshots':[remote_ack_recovered,remote_ack_repeated]})
                    checks.append({'case':'installed remote-ack recovery repeat poll preserves all barriers','status':'PASS'})
                read_evidence.append(item)
                checks.append({'case':'installed payload read failure recovery '+kind,'status':'PASS'})
            save('outbox-recovery-evidence.json',{'cases':outbox_recovery_evidence})
            for operation in ('wait','submit'):
                target=controller/'_executor_spike'/('results' if operation=='wait' else 'tasks')/f'{task_id}.json'
                argv=[operation]+common+['--task-file',task_path]
                if operation=='wait':argv+=['--timeout-seconds','0','--expected-provenance-file',expected_path]
                item=rejected_read(target,'controller',argv,task_id,'controller-'+operation,target_file)
                response=json.loads(run(connect+argv))
                assert response==result if operation=='wait' else response['status']=='already_present'
                item.update(response=response,file_after_recovery_sha256=hashlib.sha256(target_file.read_bytes()).hexdigest())
                read_evidence.append(item)
                checks.append({'case':'installed controller payload read failure '+operation,'status':'PASS'})
            save('read-failure-evidence.json',read_evidence)
            # Invalid action identities stay byte-for-byte in the committed
            # mailbox; they cannot manufacture Result v1 identities or block CAS.
            admission_start=len(records)
            admission_target=project/'admission-cas.txt';admission_target.write_bytes(b'before\n')
            admission_tasks=[];admission_invalid=[];admission_originals={}
            for index,action in enumerate(('',None,[],{},0,42,False)):
                item=build_task(profile.node_id,'node.status',{},task_id=f'LH{1000+index}')
                item['action']=action;admission_tasks.append(item);admission_invalid.append(item['task_id'])
            item=build_task(profile.node_id,'node.status',{},task_id='LH1007');del item['action']
            admission_tasks.append(item);admission_invalid.append(item['task_id'])
            admission_unknown=build_task(profile.node_id,'node.status',{},task_id='LH1008')
            admission_unknown['action']='unsupported.fixture.action';admission_tasks.append(admission_unknown)
            admission_valid=build_task(profile.node_id,'fs.write_text_cas',{
                'repository':'demo','relative_path':admission_target.name,
                'expected_sha256':hashlib.sha256(b'before\n').hexdigest(),'content':'after\n'},task_id='LH1009')
            admission_tasks.append(admission_valid)
            run([git,'-C',seed,'fetch','origin',policy['branch']])
            run([git,'-C',seed,'reset','--hard','FETCH_HEAD'])
            for item in admission_tasks:
                item_path=save(f"admission-{item['task_id']}-task.json",item)
                item_raw=item_path.read_bytes();relative=f"_executor_spike/tasks/{item['task_id']}.json"
                (seed/relative).write_bytes(item_raw)
                admission_originals[item['task_id']]={'task':item,'source_file':item_path.name,
                    'relative_path':relative,'bytes':len(item_raw),'sha256':hashlib.sha256(item_raw).hexdigest(),
                    'task_digest':task_digest(item)}
            run([git,'-C',seed,'add','--','_executor_spike/tasks'])
            run([git,'-C',seed,'commit','-qm','fixture unrepresentable action identities and later CAS'])
            run([git,'-C',seed,'push','origin','HEAD:refs/heads/'+policy['branch']])
            run(worker_cmd);admission_worker_command=len(records)
            assert admission_target.read_bytes()==b'after\n'
            admission_result=json.loads(run(connect+['wait']+common+['--task-file',root/'admission-LH1009-task.json',
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            admission_wait_command=len(records)
            assert admission_result['status']=='succeeded' and admission_result['task_digest']==task_digest(admission_valid)
            admission_completed={}
            for item in (admission_unknown,admission_valid):
                name=item['task_id']+'.json';receipt_path=state/'receipts'/name
                result_path=worker_box/'_executor_spike/results'/name
                receipt_raw=receipt_path.read_bytes();result_raw=result_path.read_bytes()
                receipt_value=json.loads(receipt_raw);result_value=json.loads(result_raw)
                assert receipt_value['result']==result_value
                assert receipt_value['task_id']==item['task_id'] and receipt_value['task_digest']==task_digest(item)
                assert result_value['task_id']==item['task_id'] and result_value['task_digest']==task_digest(item)
                assert result_value['action']==item['action'] and result_value['target_node']==profile.node_id
                assert all(result_value[k]==v for k,v in identity.items())
                if item['task_id']=='LH1008':
                    assert result_value['status']=='rejected' and result_value['error_code']=='action_not_allowlisted'
                else:assert result_value==admission_result
                assert not _entry_exists_strict(state/'outbox'/name)
                admission_completed[item['task_id']]={'result':result_value,
                    'receipt_before_sha256':hashlib.sha256(receipt_raw).hexdigest(),
                    'result_before_sha256':hashlib.sha256(result_raw).hexdigest()}
            def admission_unchanged():
                for item in admission_tasks:
                    saved=admission_originals[item['task_id']]
                    raw=(root/saved['source_file']).read_bytes()
                    assert hashlib.sha256(raw).hexdigest()==saved['sha256']
                    assert (worker_box/saved['relative_path']).read_bytes()==raw
                    assert (controller/saved['relative_path']).read_bytes()==raw
                    name=item['task_id']+'.json';conflict=conflict_filename(task_digest(item))
                    assert not _entry_exists_strict(state/'conflicts'/conflict)
                    for box in (worker_box,controller):
                        assert not _entry_exists_strict(box/'_executor_spike/conflicts'/conflict)
                    if item['task_id'] in admission_invalid:
                        for location in (state/'receipts'/name,state/'outbox'/name,
                                         worker_box/'_executor_spike/results'/name,controller/'_executor_spike/results'/name):
                            assert not _entry_exists_strict(location),(item['task_id'],str(location))
            admission_unchanged()
            # A second CAS would turn this sentinel back into after\n.
            admission_target.write_bytes(b'before\n')
            run(worker_cmd);admission_repeat_command=len(records)
            assert admission_target.read_bytes()==b'before\n'
            admission_unchanged()
            for item in (admission_unknown,admission_valid):
                name=item['task_id']+'.json';saved=admission_completed[item['task_id']]
                saved['receipt_after_sha256']=hashlib.sha256((state/'receipts'/name).read_bytes()).hexdigest()
                saved['result_after_sha256']=hashlib.sha256((worker_box/'_executor_spike/results'/name).read_bytes()).hexdigest()
                assert saved['receipt_before_sha256']==saved['receipt_after_sha256']
                assert saved['result_before_sha256']==saved['result_after_sha256']
                assert not _entry_exists_strict(state/'outbox'/name)
            assert len(records)-admission_start==8
            save('admission-evidence.json',{'tasks':admission_originals,'invalid_task_ids':admission_invalid,
                'completed':admission_completed,'valid_result':admission_result,
                'unknown_result':admission_completed['LH1008']['result'],
                'target_relative_path':str(admission_target.relative_to(root)),
                'target_after_execution_sha256':hashlib.sha256(b'after\n').hexdigest(),
                'target_after_repeat_sha256':hashlib.sha256(admission_target.read_bytes()).hexdigest(),
                'command_numbers':list(range(admission_start+1,len(records)+1)),
                'worker_command':admission_worker_command,'wait_command':admission_wait_command,
                'repeat_worker_command':admission_repeat_command})
            checks.append({'case':'installed malformed action isolation and later CAS without replay','status':'PASS'})
            digest_start=len(records)
            digest_target=project/'unicode-digest-cas.txt'
            digest_before=b'before\n';digest_after='完成😀\n'.encode('utf-8')
            with digest_target.open('xb') as stream:stream.write(digest_before)
            digest_tasks=[];digest_originals={}
            digest_high=build_task(profile.node_id,'node.status',{},task_id='LH1010')
            digest_high['params']={'invalid':'\ud800'};digest_tasks.append(digest_high)
            digest_low=build_task(profile.node_id,'node.status',{},task_id='LH1011')
            digest_low['action']='\udfff';digest_tasks.append(digest_low)
            digest_valid=build_task(profile.node_id,'fs.write_text_cas',{
                'repository':'demo','relative_path':digest_target.name,
                'expected_sha256':hashlib.sha256(digest_before).hexdigest(),
                'content':digest_after.decode('utf-8')},task_id='LH1012')
            digest_tasks.append(digest_valid)
            digest_invalid_ids=['LH1010','LH1011']
            for item in digest_tasks[:-1]:
                try:task_digest(item)
                except LocalHandError as exc:assert exc.code=='task_digest_invalid'
                else:raise AssertionError('lone surrogate gained a canonical UTF-8 identity')
            def digest_conflict_snapshot():
                snapshot={}
                for directory in (state/'conflicts',state/'outbox',
                                  worker_box/'_executor_spike/conflicts',controller/'_executor_spike/conflicts'):
                    for path in sorted(directory.glob('CONFLICT-*.json')):
                        snapshot[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
                return snapshot
            digest_conflicts_before=digest_conflict_snapshot()
            run([git,'-C',seed,'fetch','origin',policy['branch']])
            run([git,'-C',seed,'reset','--hard','FETCH_HEAD'])
            for item in digest_tasks:
                # ASCII JSON escapes retain the exact invalid decoded values;
                # save() never invents a replacement canonical task digest.
                source=save(f"digest-{item['task_id']}-task.json",item)
                raw=source.read_bytes();relative=f"_executor_spike/tasks/{item['task_id']}.json"
                (seed/relative).write_bytes(raw)
                digest_originals[item['task_id']]={'task':item,'source_file':source.name,
                    'relative_path':relative,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                    'task_digest':None if item['task_id'] in digest_invalid_ids else task_digest(item),
                    'identity_error':'task_digest_invalid' if item['task_id'] in digest_invalid_ids else None}
            run([git,'-C',seed,'add','--','_executor_spike/tasks'])
            run([git,'-C',seed,'commit','-qm','fixture invalid UTF-8 task identities and valid Unicode CAS'])
            run([git,'-C',seed,'push','origin','HEAD:refs/heads/'+policy['branch']])
            run(worker_cmd);digest_worker_command=len(records)
            assert digest_target.read_bytes()==digest_after
            digest_result=json.loads(run(connect+['wait']+common+['--task-file',root/'digest-LH1012-task.json',
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            digest_wait_command=len(records)
            assert digest_result['status']=='succeeded' and digest_result['task_digest']==task_digest(digest_valid)
            assert digest_result['task_id']=='LH1012' and digest_result['action']=='fs.write_text_cas'
            assert digest_result['target_node']==profile.node_id
            assert all(digest_result[k]==v for k,v in identity.items())
            digest_receipt=state/'receipts/LH1012.json'
            digest_remote_result=worker_box/'_executor_spike/results/LH1012.json'
            digest_receipt_before=digest_receipt.read_bytes();digest_result_before=digest_remote_result.read_bytes()
            assert json.loads(digest_receipt_before)['result']==digest_result==json.loads(digest_result_before)
            def digest_unchanged():
                for item in digest_tasks:
                    saved=digest_originals[item['task_id']];raw=(root/saved['source_file']).read_bytes()
                    assert hashlib.sha256(raw).hexdigest()==saved['sha256']
                    for box in (worker_box,controller):assert (box/saved['relative_path']).read_bytes()==raw
                    if item['task_id'] in digest_invalid_ids:
                        name=item['task_id']+'.json'
                        for location in (state/'receipts'/name,state/'outbox'/name,
                                         worker_box/'_executor_spike/results'/name,controller/'_executor_spike/results'/name):
                            assert not _entry_exists_strict(location),(item['task_id'],str(location))
                assert digest_conflict_snapshot()==digest_conflicts_before
            digest_unchanged()
            digest_target.write_bytes(digest_before)
            run(worker_cmd);digest_repeat_command=len(records)
            assert digest_target.read_bytes()==digest_before
            assert digest_receipt.read_bytes()==digest_receipt_before
            assert digest_remote_result.read_bytes()==digest_result_before
            assert not _entry_exists_strict(state/'outbox/LH1012.json')
            digest_unchanged()
            digest_committed_head=run([git,'--git-dir',bare,'rev-parse','refs/heads/'+policy['branch']]).strip()
            digest_head_command=len(records)
            for item in digest_tasks:
                saved=digest_originals[item['task_id']]
                raw=run([git,'--git-dir',bare,'show',digest_committed_head+':'+saved['relative_path']]).encode('utf-8')
                assert raw==(root/saved['source_file']).read_bytes()
                saved['committed_blob_read_command']=len(records)
            assert len(records)-digest_start==12
            save('digest-admission-evidence.json',{'tasks':digest_originals,'invalid_task_ids':digest_invalid_ids,
                'valid_result':digest_result,'receipt':json.loads(digest_receipt_before),
                'receipt_before_sha256':hashlib.sha256(digest_receipt_before).hexdigest(),
                'receipt_after_sha256':hashlib.sha256(digest_receipt.read_bytes()).hexdigest(),
                'result_before_sha256':hashlib.sha256(digest_result_before).hexdigest(),
                'result_after_sha256':hashlib.sha256(digest_remote_result.read_bytes()).hexdigest(),
                'conflicts_before':digest_conflicts_before,'conflicts_after':digest_conflict_snapshot(),
                'target_relative_path':str(digest_target.relative_to(root)),
                'target_after_execution_sha256':hashlib.sha256(digest_after).hexdigest(),
                'target_after_repeat_sha256':hashlib.sha256(digest_target.read_bytes()).hexdigest(),
                'committed_head':digest_committed_head,'head_command':digest_head_command,
                'worker_command':digest_worker_command,'wait_command':digest_wait_command,
                'repeat_worker_command':digest_repeat_command,
                'command_numbers':list(range(digest_start+1,len(records)+1))})
            checks.append({'case':'installed invalid UTF-8 task identity isolation and valid Unicode CAS without replay','status':'PASS'})
            # Escaped surrogate text is valid input JSON but cannot be emitted
            # as a Result's UTF-8 bytes. Exercise all persisted ingress routes
            # with the installed worker, retaining the original malformed data.
            from local_hand.protocol import result_success
            encoding_start=len(records)
            encoding_tasks=[];encoding_originals={};encoding_targets=[]
            for task_id in ('LH1020','LH1021','LH1022'):
                target=project/f'result-encoding-{task_id}.txt'
                with target.open('xb') as stream:stream.write(b'before\n')
                task=build_task(profile.node_id,'fs.write_text_cas',{
                    'repository':'demo','relative_path':target.name,
                    'expected_sha256':hashlib.sha256(b'before\n').hexdigest(),
                    'content':'完成😀\n'},task_id=task_id)
                encoding_tasks.append(task);encoding_targets.append(target)
                save(f'encoding-{task_id}-task.json',task)
            bad_remote=result_success(encoding_tasks[0],profile.node_id,{'value':'\ud800'},identity)
            bad_saved=result_success(encoding_tasks[1],profile.node_id,{'nested':['\udfff']},identity)
            bad_pending=result_success(encoding_tasks[0],profile.node_id,{'\udfff':'invalid key'},identity)
            remote_raw=(json.dumps(bad_remote,ensure_ascii=True)+'\n').encode('ascii')
            receipt_raw=(json.dumps({'task_id':'LH1021','task_digest':task_digest(encoding_tasks[1]),
                                    'result':bad_saved},ensure_ascii=True)+'\n').encode('ascii')
            pending_raw=(json.dumps(bad_pending,ensure_ascii=True)+'\n').encode('ascii')
            invalid_receipt_path=state/'receipts/LH1021.json'
            invalid_outbox_path=state/'outbox/LH1020.json'
            with invalid_receipt_path.open('xb') as stream:stream.write(receipt_raw)
            with invalid_outbox_path.open('xb') as stream:stream.write(pending_raw)
            run([git,'-C',seed,'fetch','origin',policy['branch']])
            run([git,'-C',seed,'reset','--hard','FETCH_HEAD'])
            for task in encoding_tasks:
                relative=f"_executor_spike/tasks/{task['task_id']}.json"
                raw=(root/f"encoding-{task['task_id']}-task.json").read_bytes()
                (seed/relative).write_bytes(raw);encoding_originals[relative]=hashlib.sha256(raw).hexdigest()
            invalid_remote_relative='_executor_spike/results/LH1020.json'
            with (seed/invalid_remote_relative).open('xb') as stream:stream.write(remote_raw)
            run([git,'-C',seed,'add','--','_executor_spike/tasks',invalid_remote_relative])
            run([git,'-C',seed,'commit','-qm','fixture invalid Result encoding and healthy CAS'])
            run([git,'-C',seed,'push','origin','HEAD:refs/heads/'+policy['branch']])
            run(connect+['wait']+common+['--task-file',root/'encoding-LH1020-task.json',
                '--timeout-seconds','0','--expected-provenance-file',expected_path],expected=3)
            encoding_reject_command=len(records)
            rejection=(logs/f'{len(records):03}'/'stderr.log').read_text()
            assert 'remote_result_invalid' in rejection and 'Traceback' not in rejection
            run(worker_cmd);encoding_worker_command=len(records)
            encoding_results={}
            for task in encoding_tasks:
                result=json.loads(run(connect+['wait']+common+['--task-file',root/f"encoding-{task['task_id']}-task.json",
                    '--timeout-seconds','0','--expected-provenance-file',expected_path]))
                assert result['task_digest']==task_digest(task) and result['task_id']==task['task_id']
                assert all(result[k]==v for k,v in identity.items())
                encoding_results[task['task_id']]=result
            assert encoding_results['LH1020']['status']=='indeterminate'
            assert encoding_results['LH1020']['error_code']=='remote_result_invalid'
            assert encoding_results['LH1021']['status']=='indeterminate'
            assert encoding_results['LH1021']['error_code']=='local_receipt_invalid'
            assert encoding_results['LH1022']['status']=='succeeded'
            assert encoding_results['LH1022']['details']['already_applied'] is False
            assert [p.read_bytes() for p in encoding_targets]==[b'before\n',b'before\n','完成😀\n'.encode('utf-8')]
            assert (worker_box/invalid_remote_relative).read_bytes()==remote_raw
            assert invalid_receipt_path.read_bytes()==receipt_raw
            preserved_pending=[p for p in (state/'quarantine').iterdir()
                               if p.name.startswith('LH1020.json.') and p.name.endswith('.invalid')]
            assert len(preserved_pending)==1 and preserved_pending[0].read_bytes()==pending_raw
            for task in encoding_tasks:assert not _entry_exists_strict(state/'outbox'/f"{task['task_id']}.json")
            encoding_barriers={}
            for task in encoding_tasks[:2]:
                path=state/'conflicts'/conflict_filename(task_digest(task))
                encoding_barriers[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
            good_receipt=state/'receipts/LH1022.json';good_result=worker_box/'_executor_spike/results/LH1022.json'
            for path in (good_receipt,good_result):
                encoding_barriers[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
            encoding_targets[2].write_bytes(b'before\n')
            run(worker_cmd);encoding_repeat_command=len(records)
            assert all(p.read_bytes()==b'before\n' for p in encoding_targets)
            assert invalid_receipt_path.read_bytes()==receipt_raw
            assert (worker_box/invalid_remote_relative).read_bytes()==remote_raw
            assert preserved_pending[0].read_bytes()==pending_raw
            assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in encoding_barriers.items())
            assert all(hashlib.sha256((worker_box/p).read_bytes()).hexdigest()==h for p,h in encoding_originals.items())
            save('result-encoding-evidence.json',{'results':encoding_results,'task_blob_sha256':encoding_originals,
                'remote_result_sha256':hashlib.sha256(remote_raw).hexdigest(),
                'invalid_receipt_sha256':hashlib.sha256(receipt_raw).hexdigest(),
                'quarantined_outbox':str(preserved_pending[0].relative_to(root)),
                'quarantined_outbox_sha256':hashlib.sha256(pending_raw).hexdigest(),
                'barriers_before_and_after_sha256':encoding_barriers,
                'target_paths':[str(p.relative_to(root)) for p in encoding_targets],
                'target_after_repeat_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in encoding_targets],
                'controller_rejection_command':encoding_reject_command,
                'worker_command':encoding_worker_command,'repeat_command':encoding_repeat_command,
                'command_numbers':list(range(encoding_start+1,len(records)+1))})
            for label in ('typed controller rejection','remote malformed Result barrier',
                          'invalid outbox preservation','invalid receipt and later CAS without replay'):
                checks.append({'case':'installed Result encoding '+label,'status':'PASS'})
            # Command exit zero means a valid business Result was retrieved;
            # its rejected/indeterminate status remains a separate assertion.
            contract_evidence=[]
            cas_file=project/'contract-cas.txt'
            with cas_file.open('xb') as stream:stream.write(b'before\n')
            invalid_receipt=None
            for task_id,label,expected_digest,content,status in (
                ('LH9860','invalid-cas-digest','+'+'0'*63,'before\n','rejected'),
                ('LH9861','uppercase-cas-digest',hashlib.sha256(b'before\n').hexdigest().upper(),'after\n','succeeded'),
            ):
                task=build_task(profile.node_id,'fs.write_text_cas',{
                    'repository':'demo','relative_path':cas_file.name,
                    'expected_sha256':expected_digest,'content':content},task_id=task_id)
                task_path=save(f'contract-{task_id}-task.json',task)
                receipt=state/'receipts'/f'{task_id}.json'
                assert not _entry_exists_strict(receipt)
                before=cas_file.read_bytes();commands={}
                response=json.loads(run(connect+['submit']+common+['--task-file',task_path]))
                commands['submit']=len(records);assert response['status']=='submitted'
                run(worker_cmd);commands['worker']=len(records)
                result=json.loads(run(connect+['wait']+common+['--task-file',task_path,
                    '--timeout-seconds','0','--expected-provenance-file',expected_path]))
                commands['wait']=len(records)
                raw=receipt.read_bytes();saved_receipt=json.loads(raw)
                assert saved_receipt['result']==result and result['status']==status
                assert result['task_id']==task_id and result['task_digest']==task_digest(task)
                assert all(result[key]==value for key,value in identity.items())
                if label=='invalid-cas-digest':
                    assert result['error_code']=='invalid_expected_sha256'
                    assert cas_file.read_bytes()==before==b'before\n'
                    invalid_receipt=raw
                else:
                    assert result['error_code'] is None and result['details']['already_applied'] is False
                    assert cas_file.read_bytes()==b'after\n'
                    assert (state/'receipts/LH9860.json').read_bytes()==invalid_receipt
                contract_evidence.append({'case':label,'task':task,'result':result,'commands':commands,
                    'file':str(cas_file),'file_before_sha256':hashlib.sha256(before).hexdigest(),
                    'file_after_sha256':hashlib.sha256(cas_file.read_bytes()).hexdigest(),
                    'receipt_before':None,'receipt_after':saved_receipt,
                    'receipt_after_sha256':hashlib.sha256(raw).hexdigest()})
                checks.append({'case':'installed action contract '+label,'status':'PASS'})
            contract_evidence[0]['receipt_after_healthy_cas_sha256']=hashlib.sha256(
                (state/'receipts/LH9860.json').read_bytes()).hexdigest()
            list_fault_code='''import errno,sys
from pathlib import Path
from unittest import mock
from local_hand import observe,worker
target=Path(sys.argv[1]);original=observe.list_directory_bounded
class FaultEntry:
 def __init__(self,entry):self.entry=entry;self.name=entry.name
 def is_symlink(self):return self.entry.is_symlink()
 def is_dir(self,**kwargs):raise OSError(errno.EIO,'synthetic directory entry metadata failure')
 def is_file(self,**kwargs):return self.entry.is_file(**kwargs)
def listing(path,*args,**kwargs):
 entries=original(path,*args,**kwargs)
 return [FaultEntry(entry) if Path(entry.path)==target else entry for entry in entries]
with mock.patch.object(observe,'list_directory_bounded',side_effect=listing):
 raise SystemExit(worker.main(sys.argv[2:]))
'''
            uncertain_receipt=None
            for task_id,label in (('LH9862','directory-entry-io'),('LH9863','directory-entry-healthy')):
                if label=='directory-entry-healthy':os.mkfifo(project/'observation-channel')
                task=build_task(profile.node_id,'fs.list',{'repository':'demo'},task_id=task_id)
                task_path=save(f'contract-{task_id}-task.json',task)
                receipt=state/'receipts'/f'{task_id}.json';assert not _entry_exists_strict(receipt)
                before=cas_file.read_bytes();commands={}
                response=json.loads(run(connect+['submit']+common+['--task-file',task_path]))
                commands['submit']=len(records);assert response['status']=='submitted'
                if label=='directory-entry-io':
                    run([sys.executable,'-I','-c',list_fault_code,cas_file]+worker_cmd[4:])
                else:run(worker_cmd)
                commands['worker']=len(records)
                result=json.loads(run(connect+['wait']+common+['--task-file',task_path,
                    '--timeout-seconds','0','--expected-provenance-file',expected_path]))
                commands['wait']=len(records)
                raw=receipt.read_bytes();saved_receipt=json.loads(raw)
                assert saved_receipt['result']==result and cas_file.read_bytes()==before==b'after\n'
                assert result['task_id']==task_id and result['task_digest']==task_digest(task)
                assert all(result[key]==value for key,value in identity.items())
                if label=='directory-entry-io':
                    assert result['status']=='indeterminate' and result['error_code']=='directory_entry_unavailable'
                    assert 'errno=5' in result['error'];uncertain_receipt=raw
                else:
                    assert result['status']=='succeeded' and result['error_code'] is None
                    observed={entry['name']:entry['kind'] for entry in result['details']['entries']}
                    assert observed['contract-cas.txt']=='file' and observed['observation-channel']=='other'
                    assert (state/'receipts/LH9862.json').read_bytes()==uncertain_receipt
                    assert (state/'receipts/LH9860.json').read_bytes()==invalid_receipt
                contract_evidence.append({'case':label,'task':task,'result':result,'commands':commands,
                    'file':str(cas_file),'file_before_sha256':hashlib.sha256(before).hexdigest(),
                    'file_after_sha256':hashlib.sha256(cas_file.read_bytes()).hexdigest(),
                    'receipt_before':None,'receipt_after':saved_receipt,
                    'receipt_after_sha256':hashlib.sha256(raw).hexdigest()})
                checks.append({'case':'installed action contract '+label,'status':'PASS'})
            contract_evidence[2]['receipt_after_healthy_observation_sha256']=hashlib.sha256(
                (state/'receipts/LH9862.json').read_bytes()).hexdigest()
            save('contract-boundary-evidence.json',contract_evidence)
            fifo_code='''import os,signal,sys
from pathlib import Path
from unittest import mock
from local_hand import worker
target=Path(sys.argv[1]);original=os.open;swapped=False
class ReaderDeadline(Exception):pass
def deadline(*_):raise ReaderDeadline('bounded reader blocked in FIFO open')
def race(path,*args,**kwargs):
 global swapped
 if not isinstance(path,int) and Path(path)==target and not swapped:
  target.unlink();os.mkfifo(target);swapped=True
 return original(path,*args,**kwargs)
signal.signal(signal.SIGALRM,deadline);signal.alarm(5)
try:
 with mock.patch.object(os,'open',side_effect=race):code=worker.main(sys.argv[2:])
 assert swapped and target.is_fifo()
finally:signal.alarm(0)
raise SystemExit(code)
'''
            reader_race_evidence=[]
            for offset,action in enumerate(('fs.read_text','fs.write_text_cas')):
                task_id=f'LH{9864+offset}';healthy_id=f'LH{9866+offset}'
                target_file=project/f'fifo-{task_id}.txt';target_file.write_bytes(b'before\n')
                params={'repository':'demo','relative_path':target_file.name}
                if action=='fs.write_text_cas':params.update(expected_sha256=hashlib.sha256(b'before\n').hexdigest(),content='after\n')
                task=build_task(profile.node_id,action,params,task_id=task_id)
                task_path=save(f'fifo-{task_id}-task.json',task)
                run(connect+['submit']+common+['--task-file',task_path])
                run([sys.executable,'-I','-c',fifo_code,target_file]+worker_cmd[4:]);fault_command=len(records)
                assert target_file.is_fifo(),'reader replaced the raced FIFO'
                result=json.loads(run(connect+['wait']+common+['--task-file',task_path,'--timeout-seconds','0',
                    '--expected-provenance-file',expected_path]))
                assert result['status']=='indeterminate' and 'not a regular file' in result['error'],result
                assert result['error_code']==('write_source_invalid' if action=='fs.write_text_cas' else 'read_too_large')
                receipt=state/'receipts'/f'{task_id}.json';saved_receipt=receipt.read_bytes()
                assert json.loads(saved_receipt)['result']==result
                # Only replace this synthetic FIFO after recording its rejection.
                target_file.unlink();target_file.write_bytes(b'before\n')
                healthy=build_task(profile.node_id,action,params,task_id=healthy_id)
                healthy_path=save(f'fifo-{healthy_id}-task.json',healthy)
                run(connect+['submit']+common+['--task-file',healthy_path]);run(worker_cmd)
                recovered=json.loads(run(connect+['wait']+common+['--task-file',healthy_path,'--timeout-seconds','0',
                    '--expected-provenance-file',expected_path]))
                assert recovered['status']=='succeeded'
                assert target_file.read_bytes()==(b'after\n' if action=='fs.write_text_cas' else b'before\n')
                assert receipt.read_bytes()==saved_receipt
                assert json.loads((state/'receipts'/f'{healthy_id}.json').read_bytes())['result']==recovered
                reader_race_evidence.append({'case':action,'fault_task':task,'fault_result':result,'healthy_task':healthy,
                    'healthy_result':recovered,'fault_command':fault_command,'fifo_preserved_after_failure':True,
                    'fault_receipt_before_sha256':hashlib.sha256(saved_receipt).hexdigest(),
                    'fault_receipt_after_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),
                    'final_file_sha256':hashlib.sha256(target_file.read_bytes()).hexdigest()})
                checks.append({'case':'installed FIFO replacement refusal and new-task recovery '+action,'status':'PASS'})
            save('reader-race-evidence.json',reader_race_evidence)
            capture_start_program='"""Installed-only capture startup fault chain. Invoke: python -I FILE NEW_ROOT."""\nimport hashlib\nimport json\nimport os\nfrom pathlib import Path\nimport signal\nimport subprocess\nimport sys\nimport threading\nimport time\nfrom unittest import mock\n\nfrom local_hand import bounded_io, validate\nfrom local_hand.paths import load_profile\nfrom local_hand.protocol import LocalHandError\n\nroot = Path(sys.argv[1])\nroot.mkdir(parents=True, exist_ok=False)\nevidence = []\nfor runner in ("generic", "validation"):\n    for fail_at in (1, 2):\n        case_root = root / (runner + "-reader-" + str(fail_at))\n        repo = case_root / "projects/demo"\n        repo.mkdir(parents=True)\n        subprocess.run([os.environ.get("LOCAL_HAND_GIT_EXECUTABLE", "git"), "init", "-q", str(repo)], check=True)\n        child_script = repo / "finite-child.py"\n        child_script.write_text(\n            "from pathlib import Path\\nimport time\\n"\n            "end=time.monotonic()+5\\n"\n            "with Path(\'heartbeat\').open(\'ab\',buffering=0) as out:\\n"\n            " while time.monotonic()<end:\\n"\n            "  out.write(b\'x\');time.sleep(.02)\\n"\n        )\n        healthy_argv = [sys.executable, "-I", "-c", "print(\'capture-recovered\')"]\n        profile_path = case_root / "profile.json"\n        profile_path.write_text(json.dumps({\n            "profile_schema": "local-hand-profile/v2",\n            "node_id": "capture-start-fixture", "projects_root": str(repo.parent),\n            "transport_policy": {"schema_version": "local-hand-git-mailbox/v1",\n                "remote_url": "git@example.invalid:fixtures/mailbox.git",\n                "allowed_remote_urls": ["git@example.invalid:fixtures/mailbox.git"],\n                "branch": "fixture/mailbox-v1"},\n            "repositories": {"demo": {"path": "demo", "single_writer": True,\n                "validations": {\n                    "fault": {"argv": [sys.executable, "-I", str(child_script)], "timeout_seconds": 2, "replay_safe": True},\n                    "healthy": {"argv": healthy_argv, "timeout_seconds": 2, "replay_safe": True}}}}}))\n        profile = load_profile(profile_path)\n        children = []\n        real_popen = subprocess.Popen\n        real_start = threading.Thread.start\n        calls = [0]\n\n        def tracked_popen(*args, **kwargs):\n            child = real_popen(*args, **kwargs)\n            children.append(child)\n            return child\n\n        def start(thread):\n            calls[0] += 1\n            if calls[0] == fail_at:\n                deadline = time.monotonic() + 1\n                while not (repo / "heartbeat").exists() and time.monotonic() < deadline:\n                    time.sleep(.01)\n                raise RuntimeError("can\'t start new thread")\n            return real_start(thread)\n\n        started = time.monotonic()\n        fault = None\n        try:\n            with mock.patch.object(subprocess, "Popen", side_effect=tracked_popen), mock.patch.object(threading.Thread, "start", start):\n                try:\n                    if runner == "generic":\n                        bounded_io.run_process_bounded([sys.executable, "-I", str(child_script)], cwd=repo,\n                            env=dict(os.environ), timeout=2, max_stdout=1024, max_stderr=1024,\n                            code_prefix="capture_probe", text=True)\n                    else:\n                        validate.run_profile(profile, "demo", "fault")\n                except LocalHandError as error:\n                    fault = {"code": error.code, "status": error.status, "message": error.message}\n            assert len(children) == 1 and (repo / "heartbeat").exists()\n            child = children[0]\n            prefix = "capture_probe" if runner == "generic" else "validation"\n            assert fault and fault["code"] == prefix + "_capture_start_failed" and fault["status"] == "indeterminate", fault\n            assert child.poll() is not None, "child still running"\n            assert child.stdout.closed and child.stderr.closed\n            before = (repo / "heartbeat").read_bytes()\n            time.sleep(.08)\n            after = (repo / "heartbeat").read_bytes()\n            assert before == after\n            if runner == "generic":\n                healthy = bounded_io.run_process_bounded(healthy_argv, cwd=repo, env=dict(os.environ),\n                    timeout=2, max_stdout=1024, max_stderr=1024, code_prefix="capture_probe", text=True)\n                healthy_result = {"exit_code": healthy.returncode, "stdout": healthy.stdout, "stderr": healthy.stderr}\n            else:\n                healthy_result = validate.run_profile(profile, "demo", "healthy")\n            assert healthy_result["exit_code"] == 0 and healthy_result["stdout"] == "capture-recovered\\n"\n            evidence.append({"runner": runner, "failed_reader": fail_at,\n                "argv": [sys.executable, "-I", str(child_script)], "pid": child.pid,\n                "returncode": child.returncode, "fault": fault,\n                "stdout_closed": child.stdout.closed, "stderr_closed": child.stderr.closed,\n                "heartbeat_path": str(repo / "heartbeat"), "heartbeat_bytes": len(after),\n                "heartbeat_before_sha256": hashlib.sha256(before).hexdigest(),\n                "heartbeat_after_sha256": hashlib.sha256(after).hexdigest(),\n                "healthy_argv": healthy_argv, "healthy_result": healthy_result,\n                "elapsed_seconds": time.monotonic() - started})\n        finally:\n            for child in children:\n                if child.poll() is None:\n                    try:\n                        os.killpg(child.pid, signal.SIGKILL)\n                    except ProcessLookupError:\n                        pass\n                child.wait(timeout=3)\n                for stream in (child.stdout, child.stderr):\n                    if not stream.closed:\n                        stream.close()\n\nassert len(evidence) == 4\nprint(json.dumps({"cases": evidence, "module": bounded_io.__file__, "python": sys.executable}, sort_keys=True))\n'
            capture_start_evidence=json.loads(run([sys.executable,'-I','-c',capture_start_program,root/'capture-start']))
            capture_start_evidence['command']=len(records)
            assert len(capture_start_evidence['cases'])==4
            save('capture-start-evidence.json',capture_start_evidence)
            for item in capture_start_evidence['cases']:
                checks.append({'case':f"installed capture startup cleanup {item['runner']} reader {item['failed_reader']}",'status':'PASS'})
            report_publication_program='import errno,json,os,sys\nfrom pathlib import Path\nfrom unittest import mock\nfrom local_hand.protocol import LocalHandError\nfrom local_hand_connect import controller,live_acceptance\n\nroot=Path(sys.argv[1]);root.mkdir()\noriginal=os.write;value={\'status\':\'partial\',\'message\':\'完整证据\'};evidence=[]\ntarget=root/\'visibility.json\';observations=[]\ndef short(fd,data):\n count=original(fd,data[:3]);observations.append(target.read_bytes().hex() if target.exists() else None);return count\nwith mock.patch.object(os,\'write\',side_effect=short):live_acceptance._write_report(target,value)\nassert len(observations)>1 and all(item is None for item in observations)\nassert json.loads(target.read_bytes())==value\nevidence.append({\'case\':\'partial-output-invisible\',\'file\':target.name,\'observations\':observations,\'result\':json.loads(target.read_bytes())})\ntarget=root/\'winner.json\';winner=b\'{"owner":"concurrent publisher"}\\n\'\ndef failed(fd,data):\n original(fd,data[:3])\n if target.exists():target.unlink()\n target.write_bytes(winner)\n raise OSError(errno.ENOSPC,\'synthetic report disk full\')\ntry:\n with mock.patch.object(os,\'write\',side_effect=failed):live_acceptance._write_report(target,value)\nexcept LocalHandError as exc:\n assert exc.code==\'acceptance_report_write_failed\' and exc.status==\'indeterminate\'\n assert target.read_bytes()==winner\n evidence.append({\'case\':\'concurrent-output-preserved\',\'file\':target.name,\'error_code\':exc.code,\'status\':exc.status,\'result\':json.loads(winner)})\nelse:raise AssertionError(\'partial report write accepted\')\ntarget=root/\'durability.json\'\ntry:\n with mock.patch.object(controller,\'_sync_publication_directory\',side_effect=OSError(errno.EIO,\'synthetic directory sync failure\')):\n  live_acceptance._write_report(target,value)\nexcept LocalHandError as exc:\n assert exc.code==\'acceptance_report_durability_unconfirmed\' and exc.status==\'indeterminate\'\n assert json.loads(target.read_bytes())==value\n evidence.append({\'case\':\'complete-output-durability-unconfirmed\',\'file\':target.name,\'error_code\':exc.code,\'status\':exc.status,\'result\':value})\nelse:raise AssertionError(\'directory durability failure accepted\')\nfor item in evidence:\n path=root/item[\'file\'];raw=path.read_bytes()\n import hashlib\n item.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())\n try:live_acceptance._write_report(path,{\'status\':\'failed\'})\n except LocalHandError as exc:assert exc.code==\'acceptance_report_write_failed\' and exc.status==\'indeterminate\'\n else:raise AssertionError(\'published report overwritten\')\n assert path.read_bytes()==raw\nassert sorted(p.name for p in root.iterdir())==[\'durability.json\',\'visibility.json\',\'winner.json\']\nprint(json.dumps({\'status\':\'PASS\',\'cases\':evidence},ensure_ascii=False))\n'
            report_publication_evidence=json.loads(run([sys.executable,'-I','-c',report_publication_program,root/'report-publication']))
            report_publication_evidence['command']=len(records)
            assert report_publication_evidence['status']=='PASS' and len(report_publication_evidence['cases'])==3
            save('report-publication-evidence.json',report_publication_evidence)
            for item in report_publication_evidence['cases']:
                checks.append({'case':'installed evidence report '+item['case'],'status':'PASS'})
            original=profile_path.read_bytes();profile_path.write_bytes(original+b'\n')
            run(worker_cmd,expected=3);profile_path.write_bytes(original)
            run(worker_cmd,expected=3,override={'LOCAL_HAND_IMPLEMENTATION_COMMIT':'0'*40})
            run(worker_cmd,expected=3,override={'LOCAL_HAND_INSTALL_INSTANCE_ID':str(uuid.uuid4())})
            checks.append({'case':'profile, commit and installation identity drift rejected','status':'PASS'})
            install_original=record.read_bytes();binding=json.loads(install_original);binding['wheel_sha256']='0'*64
            record.write_text(json.dumps(binding));run(worker_cmd,expected=3);record.write_bytes(install_original)
            checks.append({'case':'wheel digest binding mismatch rejected','status':'PASS'})
            from local_hand import observe
            payload=Path(observe.__file__);original=payload.read_bytes()
            try:payload.write_bytes(original+b'\n');run(worker_cmd,expected=3)
            finally:payload.write_bytes(original)
            checks.append({'case':'installed payload tamper rejected','status':'PASS'})
            shadow=payload.parent/'observe'
            retained_shadow=root/'shadow-payload'
            assert not retained_shadow.exists() and not retained_shadow.is_symlink()
            shadow_before=state_view();source_before=payload.read_bytes()
            shadow_evidence={'original_file':str(payload),'shadow_directory':str(shadow),
                'retained_directory':str(retained_shadow),'state_before':shadow_before,
                'original_sha256_before':hashlib.sha256(source_before).hexdigest(),'commands':{}}
            shadow_probe='''import json,sys
from pathlib import Path
from local_hand import observe,provenance
from local_hand.protocol import LocalHandError
loaded=Path(observe.__file__)
assert loaded==Path(sys.argv[1])/'__init__.py',str(loaded)
try:provenance.build_metadata()
except LocalHandError as exc:
 print(json.dumps({'loaded_path':str(loaded),'error_code':exc.code,'status':exc.status,'error':exc.message}))
 raise SystemExit(3)
raise AssertionError('shadow package retained the original payload identity')
'''
            shadow.mkdir()
            try:
                with (shadow/'__init__.py').open('x') as stream:
                    stream.write('def node_status(profile):\n return {"fixture_shadow": True}\n')
                probe=json.loads(run([sys.executable,'-I','-c',shadow_probe,shadow],expected=3))
                shadow_evidence['commands']['probe']=len(records)
                assert probe['status']=='indeterminate' and probe['error_code']=='provenance_mismatch'
                shadow_evidence['probe']=probe
                run(worker_cmd,expected=3);shadow_evidence['commands']['worker']=len(records)
                error=(logs/f'{len(records):03}'/'stderr.log').read_text()
                assert 'provenance_mismatch' in error
                shadow_evidence['worker_error']=error
                shadow_evidence['state_after']=state_view()
                shadow_evidence['original_sha256_after']=hashlib.sha256(payload.read_bytes()).hexdigest()
                assert shadow_evidence['state_after']==shadow_before and payload.read_bytes()==source_before
            finally:
                # Keep all generated shadow bytecode as evidence, while removing
                # only this invocation's newly created package from runtime.
                shadow.rename(retained_shadow)
                save('shadow-evidence.json',shadow_evidence)
            checks.append({'case':'installed same-name import package cannot retain bound payload identity','status':'PASS'})
            run(worker_cmd)
            initial_head=run([git,'--git-dir',bare,'rev-list','--max-parents=0','refs/heads/'+policy['branch']]).strip()
            assert re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',initial_head)
            run([git,'--git-dir',bare,'update-ref','refs/tags/'+policy['branch'],initial_head])
            tagged_task=save('same-name-tag-task.json',build_task(profile.node_id,'node.status',{},task_id='LH9987'))
            submitted=json.loads(run(connect+['submit']+common+['--task-file',tagged_task]))
            assert submitted['status']=='submitted'
            run(worker_cmd)
            tagged_result=json.loads(run(connect+['wait']+common+['--task-file',tagged_task,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert tagged_result['status']=='succeeded' and tagged_result['task_id']=='LH9987'
            assert json.loads((state/'receipts/LH9987.json').read_text())['result']==tagged_result
            checks.append({'case':'installed controller and worker use the branch despite a same-named tag','status':'PASS'})
            admitted_head=run([git,'--git-dir',bare,'rev-parse','refs/heads/'+policy['branch']]).strip()
            assert re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',admitted_head) and admitted_head!=initial_head
            (root/'admitted-head-before-removal.txt').write_text(admitted_head+'\n')
            run([git,'--git-dir',bare,'update-ref','-d','refs/heads/'+policy['branch']])
            run(worker_cmd,expected=2)
            assert "couldn't find remote ref refs/heads/"+policy['branch'] in (logs/f'{len(records):03}'/'stderr.log').read_text()
            run(connect+['wait']+common+['--task-file',tagged_task,'--timeout-seconds','0',
                '--expected-provenance-file',expected_path],expected=2)
            assert "couldn't find remote ref refs/heads/"+policy['branch'] in (logs/f'{len(records):03}'/'stderr.log').read_text()
            checks.append({'case':'installed controller and worker reject a missing branch despite cached results and a same-named tag','status':'PASS'})
        for number, record in enumerate(records, 1):
            for name, digest in record['logs'].items():
                assert hashlib.sha256((logs/f'{number:03}'/name).read_bytes()).hexdigest()==digest, f'command {number} evidence digest changed: {name}'
        checks.append({'case':'all retained command log digests revalidated','status':'PASS'})
        report['status']='PASS'
    except BaseException as exc:
        report.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        with (root/'report.json').open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
        print(json.dumps({'status':report['status'],'checks':len(checks),'commands':len(records),'report':str(root/'report.json')}))


if __name__=='__main__':main()

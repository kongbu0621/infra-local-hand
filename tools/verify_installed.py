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
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid


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
            shim_code.write_text('import os,shlex,sys\n'
                'if "-G" in sys.argv: raise SystemExit(0)\n'
                'command=shlex.split(sys.argv[-1])\n'
                'if "git@example.invalid" not in sys.argv or len(command)!=2 or command[0] not in ("git-upload-pack","git-receive-pack") or command[1]!="fixtures/mailbox.git": raise SystemExit(91)\n'
                f'os.execv({git!r},[{git!r},command[0].removeprefix("git-"),{str(bare)!r}])\n')
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
            run(connect+['init']+common)
            worker_cmd=[sys.executable,'-I','-m','local_hand.worker','--profile',profile_path,'--mailbox-repo',worker_box,'--state-root',state,'--once']
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
            assert not (state/'receipts'/'LH9998.json').exists()
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
            assert not (state/'receipts/LH9996.json').exists()
            assert not (worker_box/'_executor_spike/results/LH9996.json').exists()
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
            run(worker_cmd)
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

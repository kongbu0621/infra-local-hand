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
            assert delivered_push.is_file() and not delayed_push.exists()
            delivered_push.rename(root/'controller-push-delivered.txt')
            remote_task=json.loads(run([git,'--git-dir',bare,'show',policy['branch']+':_executor_spike/tasks/LH9995.json']))
            assert remote_task==uncertain_task
            checks.append({'case':'installed controller reports indeterminate after delivered push times out','status':'PASS'})

            delayed_push.write_text('delay exactly the next synthetic receive-pack\n')
            run(worker_cmd,expected=3,override={'LOCAL_HAND_GIT_TIMEOUT_SECONDS':'2'})
            stderr=(logs/f'{len(records):03}'/'stderr.log').read_text()
            assert 'mailbox_publish_failed' in stderr and 'git_timeout' in stderr,stderr
            assert delivered_push.is_file() and not delayed_push.exists()
            delivered_push.rename(root/'worker-push-delivered.txt')
            assert (project/'sample.txt').read_bytes()==b'delivered-once\n'
            receipt_path=state/'receipts/LH9995.json';receipt_bytes=receipt_path.read_bytes()
            saved=json.loads(receipt_bytes)['result']
            assert saved['status']=='succeeded'
            assert json.loads((state/'outbox/LH9995.json').read_text())==saved
            remote_result=json.loads(run([git,'--git-dir',bare,'show',policy['branch']+':_executor_spike/results/LH9995.json']))
            assert remote_result==saved
            checks.append({'case':'installed worker retains successful result and outbox after delivered push timeout','status':'PASS'})

            (project/'sample.txt').write_bytes(b'recovery-sentinel\n')
            run(worker_cmd)
            actual=json.loads(run(connect+['wait']+common+['--task-file',uncertain_path,
                '--timeout-seconds','0','--expected-provenance-file',expected_path]))
            assert actual==saved and receipt_path.read_bytes()==receipt_bytes
            assert not (state/'outbox/LH9995.json').exists()
            run(connect+['submit']+common+['--task-file',uncertain_path]);run(worker_cmd)
            assert (project/'sample.txt').read_bytes()==b'recovery-sentinel\n'
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
            assert not missing_receipt.exists() and (project/'sample.txt').read_bytes()==b'recovery-sentinel\n'
            assert not (worker_box/'_executor_spike/results/LH9994.json').exists()
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

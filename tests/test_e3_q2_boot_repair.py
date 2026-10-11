"""A repaired VM uses its actual new process; historical evidence stays intact."""
import json

import pytest

from e3_host import q2_host_rebind as r
from guest_resumption_fixture import records


def repair_records(monkeypatch):
    files, identity, failure = records(monkeypatch)
    start = json.loads(files['start/result.json'])
    argv = list(start['argv'])
    argv[0] = '/usr/bin/qemu-system-x86_64'
    argv[argv.index('-pidfile')+1] = '/private/repair/vm.pid'
    process = dict(start['process'],pid=start['process']['pid']+10,
                   starttime=start['process']['starttime']+10)
    cmd = b'\0'.join(w.encode() for w in argv)+b'\0'
    process['argv_sha256'] = r.sha(cmd)
    tail = files['start/pid-stat.raw'].rpartition(b') ')[2].split()
    tail[19] = str(process['starttime']).encode()
    stat = str(process['pid']).encode()+b' (qemu) '+b' '.join(tail)+b'\n'
    names = {'backup-'+n for n in r.ROLES} | {'backup-closed-system','start',
        'root-edit','boot-edit','root-readback','boot-readback','root-check','boot-check'}
    record = dict(state='REPAIRED_VM_STARTED',owner_reply='好，选第一项，我没选错，是我想要的意思。你继续',
        old_vm=start['process'],host=start['host_after'],normal_guest_shutdown=False,
        changed_files=['/etc/default/grub','/boot/grub/grub.cfg'],
        backups={n:dict(source=v['path']) for n,v in start['images_after'].items()},
        steps=[dict(name=n,returncode=0) for n in sorted(names)],new_argv=argv,
        new_vm={k:process[k] for k in ('pid','starttime','argv_sha256','exe')})
    request = files['guest/request.json']
    completion = dict(vm=record['new_vm'],returncode=0,eof=dict(stdout=True,stderr=True),request_sha256=r.sha(request))
    repaired = {'record.json':r.canonical(record),'identity.json':r.canonical(dict(
        argv=argv,process=process,host=start['host_after'],images=start['images_after'])),
        'request.json':request,'completion.json':r.canonical(completion),
        'guest.stdout':files['guest/guest.stdout'],'guest.stderr':b'',
        'pid-cmdline.raw':cmd,'pid-stat.raw':stat,'pidfile.raw':str(process['pid']).encode()+b'\n'}
    for name in r.GUEST_FILES:files.pop('guest/'+name)
    files.update({'repair/'+n:b for n,b in repaired.items()})
    freeze=json.loads(files['continuation-freeze.json'])
    freeze['boot_repair_files']={n:r.pin(b) for n,b in repaired.items()}
    files['continuation-freeze.json']=r.canonical(freeze)
    return files,identity,failure


def test_repair_reuses_successful_read_and_preserves_failed_history(monkeypatch):
    files,identity,failure=repair_records(monkeypatch)
    before={n:b for n,b in files.items() if n.startswith(('start/','failed-guest/'))}
    value,proof,_=r.consume_activation(r.envelope(files,resumed=True,repaired=True),identity,failure)
    assert value['vm']['pid']==json.loads(files['repair/record.json'])['new_vm']['pid']
    assert value['pidfile']=='/private/repair/vm.pid'
    assert {n:files[n] for n in before}==before
    from test_e3_q2_guest_resumption import consumers
    consumers(value,proof)


@pytest.mark.parametrize('fault',['old_pid','wrong_target','incomplete_read','remote_command','image_replaced','failed_repair'])
def test_repair_rejects_wrong_target_or_incomplete_actual_returns(monkeypatch,fault):
    files,identity,failure=repair_records(monkeypatch)
    name='repair/identity.json';value=json.loads(files[name])
    if fault=='old_pid':value['process']['pid']-=10
    elif fault=='image_replaced':value['images']['quota']['metadata']['ino']+=1
    elif fault in ('wrong_target','remote_command'):
        name='repair/request.json';value=json.loads(files[name])
        if fault=='wrong_target':value['ssh_prefix'][-1]='another@host'
        else:value['remote_command']+='; true'
    elif fault=='incomplete_read':
        name='repair/completion.json';value=json.loads(files[name]);value['eof']['stdout']=False
    else:
        name='repair/record.json';value=json.loads(files[name])
        next(s for s in value['steps'] if s['name']=='root-check')['returncode']=4
    files[name]=r.canonical(value)
    freeze=json.loads(files['continuation-freeze.json'])
    freeze['boot_repair_files']={n:r.pin(files['repair/'+n]) for n in r.REPAIR_FILES}
    files['continuation-freeze.json']=r.canonical(freeze)
    with pytest.raises((ValueError,KeyError)):
        r.consume_activation(r.envelope(files,resumed=True,repaired=True),identity,failure)


def test_runtime_sources_ignore_unrelated_head_and_old_document_gates(monkeypatch):
    from test_e3_q2_journal_diagnostic_resume import source_git
    state=source_git.__wrapped__(monkeypatch)
    state.changed_doc='docs/governance/Q2_CORE_GUEST_RESUMPTION_BASELINE.md'
    state.rejected_edge=('anything','anything')
    from e3_host import q2_journal_growth as h
    assert len(h.growth_sources('a'*40))==15
    assert all(args[0]=='show' and ':tests/e3_host/' in args[1] for args in state.calls)


def test_runtime_sources_still_reject_changed_code(monkeypatch):
    from test_e3_q2_journal_diagnostic_resume import source_git
    state=source_git.__wrapped__(monkeypatch)
    state.changed_doc='tests/e3_host/q2_journal_growth.py'
    from e3_host import q2_journal_growth as h
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_SOURCE_DRIFT'):
        h.growth_sources(state.head)

"""Synthetic GR originals, preserving the failed HR attempt as separate input."""
import copy
import json
import shlex
import sys
from pathlib import Path

from e3_host import q2_host_rebind as r, q2_core_prior_attempt as p
from host_rebind_fixture import records as old_records, projection as old_projection
from host_rebind_fixture import source as old_source, completion, DUMP, PIN, USAGE


def projection():
    value = old_projection()
    value.update(schema='local-hand-q2-vm-activation/v4', event=r.GR_EVENT,
        continuation_owner_sha256=r.GR_OWNER_SHA, previous_guest_failure_sha256=r.HR_TERMINAL_SHA)
    return r.validate_gr_activation(value)


def source(activation=None):
    activation = activation or projection()
    value = old_source(activation)
    value.update(schema='local-hand-q2-host-rebind-source/v2', costs=r.gr_costs(),
        continuation_owner=r.GR_OWNER_SHA, previous_guest_failure=r.guest_failure_summary(),
        previous_terminal_sha256=r.HR_TERMINAL_SHA, previous_freeze_sha256=r.HR_FREEZE_SHA)
    return value


def records(monkeypatch):
    files, identity, failure = old_records(monkeypatch)
    old = json.loads(files['hr1-freeze.json'])
    guest = {n: files.pop('guest/' + n) for n in r.GUEST_FILES}
    failed = copy.deepcopy(guest)
    old_result = json.loads(failed['result.json'])
    old_result.update(state='STOP_AND_RETAIN', errors=[dict(type='RebindError', reason='HOST_REBIND_COMMAND_COMPLETION')],
        error=dict(type='RebindError', reason='HOST_REBIND_COMMAND_COMPLETION'))
    for key in ('command','guest_boot_id','host_after','vm_after','images_after'):
        old_result.pop(key)
    failed['guest.stdout'] = b''
    failed['guest.stderr'] = b'kex_exchange_identification: read: Connection reset by peer\r\n'
    completion(failed, old_result['binding'], old_result)
    caller = json.loads(failed['caller-completion.json']); caller['returncode'] = 3
    failed['caller-completion.json'] = DUMP(caller)
    tool = dict(exit_code=3); failed['tool-completion.json'] = DUMP(tool)
    index = DUMP(dict(actual={n: PIN(b) for n,b in failed.items()}, missing=[], phase='guest'))
    terminal = DUMP(dict(state='GUEST_FAILED_STOP_AND_RETAIN', phase='guest', freeze=PIN(files['hr1-freeze.json']),
        originals_index=PIN(index), caller_completion=caller, tool_completion=tool,
        retry_allowed=False, maintenance_consumed=None, HR4='NOT_RUN', H01='NOT_RUN', Q4='NOT_RUN', H11='NOT_RUN'))
    owner = DUMP(dict(R=r.R,A=r.GR_A,scope=r.GR_SCOPE,event=r.GR_EVENT,state='APPROVED',
        previous_hr1_freeze_sha256=r.sha(files['hr1-freeze.json']),previous_terminal_sha256=r.sha(terminal)))
    files.update({'failed-guest/'+n:b for n,b in failed.items()})
    files.update({'failed-guest/index.json':index, 'failed-guest/terminal.json':terminal,
                  'continuation-owner.json':owner})
    for name,raw in (('HR_FREEZE_SHA',files['hr1-freeze.json']),('HR_FAILED_INDEX_SHA',index),
            ('HR_TERMINAL_SHA',terminal),('GR_OWNER_SHA',owner)):
        monkeypatch.setattr(r,name,r.sha(raw))
    if sys.platform.startswith('linux'):
        from e3_host import q2_core_delivery_dispatcher as d
        for target,name in (('HOST_REBIND_FROZEN','HR_FREEZE_SHA'),
                ('HOST_REBIND_FAILED_TERMINAL','HR_TERMINAL_SHA'),('GUEST_RESUMPTION_OWNER','GR_OWNER_SHA')):
            monkeypatch.setattr(d,target,getattr(r,name))
    base, _, _, start, _ = r.gr_baseline(files,identity,failure)
    request = json.loads(guest['request.json'])
    request.update(authority=r.gr_authority(),session=r.GR_GUEST_SESSION,nonce='a'*64,
        costs=r.gr_costs(),retained_freeze_sha256=r.HR_FREEZE_SHA,previous_terminal_sha256=r.HR_TERMINAL_SHA,
        guest_source=r.GUEST_SOURCE_PIN)
    source_raw = Path(r.__file__).with_name('q2_current_guest_verification.py').read_bytes()
    prelude = ('import resource\nfor key,value in ((resource.RLIMIT_AS,268435456),'
        '(resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CPU,120),(resource.RLIMIT_CORE,0)):\n'
        '    resource.setrlimit(key,(value,value))\n')
    request['remote_command'] = shlex.join(['exec','/usr/bin/sudo','-n','--','/usr/bin/env','-i',
        'HOME=/root','PATH=/usr/sbin:/usr/bin:/sbin:/bin','LANG=C','LC_ALL=C','/usr/bin/python3',
        '-I','-B','-c',prelude+source_raw.decode('ascii'),
        DUMP(dict(nonce=request['nonce'],package=base['package'],quota=base['quota'])).decode('ascii')])
    guest['request.json'] = DUMP(request); bound = r.binding(guest['request.json'],resumed=True)
    guest['started.json'] = DUMP(dict(binding=bound,startup=PIN(files['start/result.json'])))
    current = json.loads(guest['guest.stdout']); current['nonce'] = request['nonce']
    guest['guest.stdout'] = DUMP(current)
    result = json.loads(guest['result.json']); result['binding'] = bound
    result['command'].update(argv=base['ssh_prefix']+[request['remote_command']],stdout=PIN(guest['guest.stdout']))
    completion(guest,bound,result)
    freeze = dict(schema='lhq-guest-resumption-freeze/v1',state='FROZEN_GR1_VERIFIED',
        authority=r.gr_authority(),costs=r.gr_costs(),limits=r.limits(),baseline_sha256=r.sha(DUMP(base)),
        retained_files={n:PIN(b) for n,b in files.items()},external=dict(identity=PIN(identity),failure=PIN(failure)),
        requests=dict(guest=PIN(guest['request.json'])),implementation=request['implementation'],
        sources={'q2_current_guest_verification.py':r.GUEST_SOURCE_PIN})
    files.update({'continuation-freeze.json':DUMP(freeze),**{'guest/'+n:b for n,b in guest.items()}})
    return files,identity,failure


def archive(files):
    return r.envelope(files,resumed=True)


def bind(frozen,monkeypatch):
    files,identity,failure = records(monkeypatch); raw=archive(files)
    activation,proof,_ = r.build_gr_activation(raw,identity,failure)
    frozen.update(vm_activation=activation,boot_id=activation['current_boot_id'],
        persistent_raw=identity,runtime_preparation_raw=failure,rebind_raw=raw,
        persistent_predecessor=p.runtime_preparation_maintenance_resume())
    frozen['source_binding'].update(vm_activation=activation,persistent_source=proof)
    frozen['source_binding']['sources'].update(vm_activation_archive=proof['prior']['prior']['archive'],
        runtime_preparation_archive=proof['prior']['archive'],host_rebind_archive=proof['archive'])
    return proof

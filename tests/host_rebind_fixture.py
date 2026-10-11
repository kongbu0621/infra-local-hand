"""Synthetic HR evidence. No private files, subprocesses or field observations."""
import copy
import io
import json
import tarfile

from e3_host import q2_core_prior_attempt as p, q2_host_rebind as r
from runtime_preparation_continuation_fixture import source as prior_source

DUMP = r.canonical
PIN = r.pin
HOST = dict(boot_id='77777777-2222-3333-4444-555555555555',
            namespaces=dict(pid='pid:[1]', mnt='mnt:[2]', net='net:[1]'))
BOOT = '88888888-2222-3333-4444-555555555555'
USAGE = dict(cpu_nanoseconds=1000, rss_peak_bytes=4096, elapsed_nanoseconds=10000)


def projection():
    """Portable projection fixture; full originals are covered separately below."""
    from vm_resumption_fixture import records
    files, index, boot = records()
    value = p.build_vm_resumption(files, index, historical_boot=boot)
    value = {k:value[k] for k in p.ACTIVATION_PROJECTION_FIELDS}
    value.update(schema='local-hand-q2-vm-activation/v3', event=r.EVENT,
        current_boot_id=BOOT, host_boot_id=HOST['boot_id'], serial=None,
        baseline_policy='OWNER_ADOPTED_HB2_BASELINE', historical_filesystem_continuity='UNKNOWN',
        historical_content_continuity='UNKNOWN', owner_decision_sha256=r.OWNER_SHA,
        serial_revision_sha256=r.REVISION_SHA, serial_backend='null',
        serial_capture='NOT_CAPTURED_NULL_BACKEND')
    for k in r.EXTRA_FIELDS - value.keys():
        value[k] = 'a' * 64
    return r.validate_activation(value)


def source(activation=None):
    activation = activation or projection()
    return dict(schema='local-hand-q2-host-rebind-source/v1',
        archive=dict(bytes=655360, sha256='a'*64), index=dict(bytes=20000, sha256='b'*64),
        prior=prior_source(), summary=r.previous_failure(), owner=r.OWNER_SHA,
        revision=r.REVISION_SHA, activation_sha256=r.sha(p.c.canonical(activation)),
        baseline_sha256='c'*64, costs=r.costs())


def meta(ino, *, uid=1000, mode=0o100600):
    return dict(dev=2, ino=ino, mode=mode, uid=uid, gid=uid, nlink=1,
                size=100, blocks=8, mtime_ns=100, ctime_ns=100)


def baseline_records(monkeypatch):
    from runtime_preparation_continuation_fixture import records, archive
    from e3_host import q2_host_reboot_consumer as hb
    old, identity, boot = records()
    failure = archive(old)
    proof, activation_files, _ = p.build_runtime_preparation_source(failure, identity)
    historical = p.build_vm_activation({n:b for n,b in activation_files.items()
        if n != 'execution-return-index-private.json'},
        activation_files['execution-return-index-private.json'], historical_boot=boot)
    sources = {n:b'# synthetic retained source\n' for n in r.SOURCE_ROLES}
    sources['startup'] = activation_files['startup/start-proposal-private.json']
    rp = dict(historical_boot_id=boot, vm_activation=historical,persistent_source=proof,
              callers={n.removeprefix('old-caller-'):r.sha(b) for n,b in sources.items()
                       if n.startswith('old-caller-')})
    sources['rp1-freeze.json'] = DUMP(rp)
    summary = dict(reason=r.previous_failure()['reason'], phase='preflight', exit_code=3,
                   ssh_requests=0, marker_created=False)
    sources['old-return-rp2-caller.stdout'] = sources['old-return-rp2-summary.json'] = DUMP(summary)
    sources['old-return-rp2-caller.stderr'] = b''
    caller = dict(returncode=3, stdout_eof=True, stderr_eof=True,
        stdout=PIN(sources['old-return-rp2-caller.stdout']), stderr=PIN(b''))
    sources['old-return-rp2-caller-completion.json'] = DUMP(caller)
    terminal = dict(rp, rp1_freeze_sha256=r.sha(sources['rp1-freeze.json']),
        state='RP2_INVOKED_FAILED_UNCONSUMED_RP3_NOT_RUN',
        rp2=dict(summary=summary, caller_completion=caller))
    sources['rp2-terminal.json'] = sources['old-release-gate'] = DUMP(terminal)
    all_sources = dict(sources, activation_archive=identity, runtime_preparation_archive=failure)
    start = json.loads(sources['startup'])
    images = {role:dict(path=start['images'][role]['path'], metadata=meta(100+i))
              for i,role in enumerate(sorted(r.ROLES))}
    tools = dict(qemu=meta(10,uid=0,mode=0o100755),listener=meta(11,uid=0,mode=0o100755))
    limits = dict(cpu_seconds=240,wall_seconds=240,aggregate_rss_bytes=1073741824,
        process_as_bytes=536870912,process_fds=256,stream_bytes=65536,record_bytes=131072,
        capture_bytes=2097152,control_commands=1,control_children=1)
    costs = dict(maintenance_obligations=18,old_mib=25283,old_inodes=7364,
        source_preparation_mib=2,source_preparation_inodes=64,read_capture_mib=2,
        read_capture_inodes=64,total_mib=25287,total_inodes=7492)
    request = dict(R=r.R,A='b2a326036b634bb007a6adeec8929084bce3ccbd',
        B='e2858815c3d1d340a69bf2c0d69d37becfd48bb1ce523fd0254cf62fc83861a8',
        C='62d485c499d02744fbf83a8653c1aa7f80be0584',D='d'*40,nonce='synthetic-hb',
        owner_uid=1000,old_host_boot=historical['host_boot_id'],rp2_host_boot=HOST['boot_id'],
        inputs={n:dict(path='/sources/'+n,**PIN(b)) for n,b in all_sources.items()},
        tool_metadata=tools,limits=limits,costs=costs,
        target=dict(images={n:dict(path=v['path'],device=1,inode=v['metadata']['ino'])
            for n,v in images.items()},old_vm=historical['vm'],pidfile=historical['pidfile'],
            serial_metadata_only=historical['serial'],qemu_metadata_path='/usr/bin/qemu-system-x86_64',
            listener_argv=['/usr/bin/ss','-H','-4','-ltn','sport = :22221']))
    request_raw = DUMP(request)
    binding = dict(event='LH-Q2-CORE-HOST-REBOOT-READ-20261011-01',session='lhqhost-20261011a',
                   nonce=request['nonce'],request=PIN(request_raw))
    control = dict(started=True,argv=request['target']['listener_argv'],returncode=0,
                   eof=dict(stdout=True,stderr=True),stdout=PIN(b''),stderr=PIN(b''))
    held = {v['path']:meta(200+i) for i,v in enumerate(request['inputs'].values())}
    held.update({v['path']:v['metadata'] for v in images.values()})
    held.update({'/usr/bin/ss':tools['listener'],'/usr/bin/qemu-system-x86_64':tools['qemu'],
                 historical['serial']:meta(15)})
    measured = dict(cpu_seconds=0.1,peak_rss_bytes=4096,elapsed_seconds=0.1)
    result = dict(binding,state='FIXED_HOST_READ_COMPLETE',stage='COMPLETE',limits=limits,costs=costs,
        partitions=dict(parent_cpu=30,reader_cpu=180,control_cpu=30,parent_as=268435456,
                        reader_as=536870912,control_as=268435456),
        inputs={n:PIN(b) for n,b in all_sources.items()},usage=measured,
        ssh_calls=0,network_requests=0,vm_actions=0,listener_queries=1,
        host_before=HOST,host_after=HOST,pidfile=dict(state='ABSENT'),
        processes=[dict(pid=historical['vm']['pid'],state='ABSENT')],
        processes_after=[dict(pid=historical['vm']['pid'],state='ABSENT')],
        images={n:dict(metadata=v['metadata'],matches_retained=False) for n,v in images.items()},
        tools=tools,listener=dict(state='ABSENT',completion=control),
        serial=dict(state='PRESENT',metadata=meta(15)),held_files=held,held_directories={})
    originals = {n:b'' for n in r.HB_ORIGINALS}
    originals.update({'read-started.json':DUMP(binding),'read-result.json':DUMP(result),
                      'listener-completion.json':DUMP(control)})
    names = ('read-started.json','read-result.json','listener-completion.json',
             'listener.stdout','listener.stderr')
    originals['read-index.json'] = DUMP(dict(binding=binding,state=result['state'],allocated_bytes=65536,
                                            files={n:PIN(originals[n]) for n in names}))
    parent = dict(binding=binding,invocations=1,eof=dict(stdout=True,stderr=True),returncode=0,
                  stdout=PIN(b''),stderr=PIN(b''),usage=measured)
    originals['caller-completion.json'] = DUMP(parent)
    consumed = hb.consume(request_raw,{n:originals[n] for n in (*names,'read-index.json',
                          'caller.stdout','caller.stderr')},all_sources,parent,PIN(request_raw))
    owner = DUMP(dict(R=r.R,A=r.ORIGINAL_A,state='APPROVED',scope=r.SCOPE))
    revision = DUMP(dict(R=r.R,A=r.A,state='APPROVED',scope=r.SCOPE,
        previous_owner_decision_sha256=r.sha(owner),serial_backend='null',
        serial_capture='NOT_CAPTURED_NULL_BACKEND'))
    freeze = DUMP(dict(request=PIN(request_raw)))
    tool = DUMP(dict(exit_code=0))
    terminal_raw = DUMP(dict(state=consumed['state']))
    files = {'owner.json':owner,'revision.json':revision,'hb/request.json':request_raw,
        'hb/freeze.json':freeze,'hb/tool-completion.json':tool,'hb/independent.json':DUMP(consumed),
        'hb/terminal.json':terminal_raw,'hb/index.json':DUMP(dict(
            files={n:PIN(b) for n,b in originals.items()},freeze=PIN(freeze),tool_completion=PIN(tool))),
        **{'hb/'+n:b for n,b in originals.items()},**{'source/'+n:b for n,b in sources.items()}}
    for key,name in (('OWNER_SHA','owner.json'),('REVISION_SHA','revision.json'),
        ('HB_FREEZE_SHA','hb/freeze.json'),('HB_REQUEST_SHA','hb/request.json'),
        ('HB_TERMINAL_SHA','hb/terminal.json'),('RP_FREEZE_SHA','source/rp1-freeze.json')):
        monkeypatch.setattr(r,key,r.sha(files[name]))
    # Both consumers still run their own policy checks against synthetic fixed pins.
    import sys
    if sys.platform.startswith('linux'):
        from e3_host import q2_core_delivery_dispatcher as d
        monkeypatch.setattr(d,'HOST_REBIND_OWNER',r.OWNER_SHA)
        monkeypatch.setattr(d,'HOST_REBIND_REVISION',r.REVISION_SHA)
    return files, identity, failure


def command(argv, stdout=b''):
    return dict(argv=argv,returncode=0,eof=dict(stdout=True,stderr=True),
                stdout=PIN(stdout),stderr=PIN(b''))


def completion(files, bound, result):
    files['result.json'] = DUMP(result)
    files['caller.stdout'] = DUMP(dict(state=result['state'],result=PIN(files['result.json'])))
    files['caller-completion.json'] = DUMP(dict(binding=bound,invocations=1,returncode=0,
        eof=dict(stdout=True,stderr=True),stdout=PIN(files['caller.stdout']),stderr=PIN(b''),usage=USAGE))
    files['tool-completion.json'] = DUMP(dict(exit_code=0))


def records(monkeypatch):
    files, identity, failure = baseline_records(monkeypatch)
    base = r.baseline(files, identity, failure)
    authority = dict(R=r.R,A=r.A,C=r.C,owner=r.OWNER_SHA,revision=r.REVISION_SHA)
    common = dict(authority=authority,implementation=dict(commit='d'*40,tree='e'*40),
        nonce='9'*64,costs=r.costs(),limits=r.limits(),baseline_sha256=r.sha(DUMP(base)))
    start = {n:b'' for n in r.START_FILES}
    argv = r.startup_argv(base['original_argv'],'/rebound/vm.pid')
    request = dict(common,session=r.START_SESSION,pidfile='/rebound/vm.pid',argv=argv,serial_backend='null')
    start['request.json'] = DUMP(request); bound = r.binding(start['request.json'])
    start['started.json'] = DUMP(bound)
    start['launch.json'] = DUMP(dict(binding=bound,argv=argv,host=base['host'],images=base['images']))
    start['pidfile.raw'] = b'234\n'
    start['pid-stat.raw'] = b'234 (qemu) S '+b'0 '*18+b'2\n'
    start['pid-cmdline.raw'] = b'\0'.join(s.encode() for s in argv)+b'\0'
    process = dict(pid=234,starttime=2,argv_sha256=r.sha(start['pid-cmdline.raw']),
        exe='/usr/bin/qemu-system-x86_64',exe_metadata=base['tools']['qemu'],namespaces=HOST['namespaces'])
    listener = ['/usr/bin/ss','-H','-4','-ltn','sport = :22221']
    start['post-listener.stdout'] = b'LISTEN 0 128 127.0.0.1:22221 0.0.0.0:*\n'
    start['qemu-version.stdout'] = b'fixture qemu version\n'
    result = dict(binding=bound,state='STARTED_AND_HOST_ENDPOINT_VERIFIED',errors=[],
        startup_calls=1,ssh_calls=0,listener_queries=2,serial_capture='NOT_CAPTURED_NULL_BACKEND',argv=argv,
        host_before=HOST,host_after=HOST,tools=base['tools'],images_before=base['images'],
        images_after=copy.deepcopy(base['images']),old_pid_absent=True,old_pidfile_absent=True,
        old_serial_before=base['serial_observation'],old_serial_after=base['serial_observation'],
        commands={'pre-listener':command(listener),'qemu':command(argv),
                  'post-listener':command(listener,start['post-listener.stdout']),
                  'qemu-version':command(['/usr/bin/qemu-system-x86_64','--version'],start['qemu-version.stdout'])},
        qemu_content_sha256=base['old_startup']['qemu']['sha256'],process=process,usage=USAGE)
    for role in r.ROLES-{'original_system','seed'}:
        result['images_after'][role]['metadata']['mtime_ns'] += 1
    completion(start,bound,result)
    guest = {n:b'' for n in r.GUEST_FILES}
    request = dict(common,session=r.GUEST_SESSION,package=base['package'],quota=base['quota'],
        ssh_prefix=base['ssh_prefix'],guest_source=PIN(b'# synthetic verifier\n'),remote_command='synthetic-command')
    guest['request.json'] = DUMP(request); bound = r.binding(guest['request.json'])
    guest['started.json'] = DUMP(dict(binding=bound,startup=PIN(start['result.json'])))
    from vm_resumption_fixture import records as old_records
    old,_,_ = old_records()
    current = json.loads(old['guest/guest.stdout']); current.update(boot_id=BOOT,boot_end=BOOT,nonce=bound['nonce'])
    guest['guest.stdout'] = DUMP(current)
    returned = dict(binding=bound,state='CURRENT_GUEST_VERIFIED',startup=PIN(start['result.json']),
        ssh_calls=1,startup_calls=0,package_install_calls=0,module_load_calls=0,retries=0,errors=[],
        host_before=HOST,host_after=HOST,vm_before=process,vm_after=process,
        images_before=result['images_after'],images_after=result['images_after'],guest_boot_id=BOOT,
        command=command(base['ssh_prefix']+[request['remote_command']],guest['guest.stdout']),usage=USAGE)
    completion(guest,bound,returned)
    freeze = dict(schema='lhq-host-rebind-freeze/v1',state='FROZEN_HR1_VERIFIED',authority=authority,
        baseline_sha256=common['baseline_sha256'],costs=r.costs(),limits=r.limits(),
        baseline_files={n:PIN(b) for n,b in files.items()},external=dict(identity=PIN(identity),failure=PIN(failure)),
        requests=dict(start=PIN(start['request.json']),guest=PIN(guest['request.json'])),
        implementation=common['implementation'],sources={'q2_current_guest_verification.py':request['guest_source']})
    files.update({'hr1-freeze.json':DUMP(freeze),**{'start/'+n:b for n,b in start.items()},
                  **{'guest/'+n:b for n,b in guest.items()}})
    return files, identity, failure


def archive(files):
    stored = {n:b for n,b in files.items() if n not in r.REFERENCES}
    stored['index.json'] = DUMP(dict(schema='lhq-host-rebind-envelope/v1',
        files={n:PIN(b) for n,b in stored.items()},references=r.REFERENCES))
    output = io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:',format=tarfile.USTAR_FORMAT) as tar:
        for name,raw in sorted(stored.items()):
            info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600
            tar.addfile(info,io.BytesIO(raw))
    return output.getvalue()


def bind(frozen, monkeypatch):
    files, identity, failure = records(monkeypatch); raw = archive(files)
    activation, proof, _ = r.build_activation(raw,identity,failure)
    frozen.update(vm_activation=activation,boot_id=activation['current_boot_id'],
        persistent_raw=identity,runtime_preparation_raw=failure,rebind_raw=raw,
        persistent_predecessor=p.runtime_preparation_maintenance_resume())
    frozen['source_binding'].update(vm_activation=activation,persistent_source=proof)
    frozen['source_binding']['sources'].update(vm_activation_archive=proof['prior']['prior']['archive'],
        runtime_preparation_archive=proof['prior']['archive'],host_rebind_archive=proof['archive'])
    return proof

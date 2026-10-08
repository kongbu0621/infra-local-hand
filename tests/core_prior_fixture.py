"""Explicitly synthetic old F1 bytes; never private evidence or field PASS."""
import base64
import copy
import struct

from core_writer_fixture import writer
from e3_host import q2_core_delivery_contract as c
from e3_host import q2_core_prior_attempt as p


def raw_files(index=0):
    fixed = p.profile(index)
    name = lambda suffix: p.basename(suffix, index)
    remote = dict(account='q1admin', uid=1000, gid=1000, home='/home/q1admin', login_shell='/bin/bash',
        parser_profile='bash-noninteractive-c-v1', remote_tokens_sha256='a' * 64, remote_command_sha256='b' * 64)
    for program_index, (role, path) in enumerate(dict(shell='/bin/bash', sudo='/usr/bin/sudo', env='/usr/bin/env',
                                            systemd_run='/usr/bin/systemd-run', python='/usr/bin/python3').items()):
        remote[role] = dict(path=path, resolved_path=path, symlink_chain=[], dev=1, ino=program_index + 10,
            mode=0o755, uid=0, gid=0, nlink=1, bytes=100, sha256=str(program_index + 1) * 64)
    hello = dict(schema=c.HELLO_SCHEMA, scope=c.SCOPE, loader_sha256=p.LOADER_SHA,
        bootstrap_sha256=fixed['bootstrap_sha'], guest_boot_id='11111111-2222-3333-4444-555555555555',
        guest_boottime_origin_ns=100, guest_monotonic_origin_ns=200, pid=999,
        uid=0, gid=0, euid=0, egid=0, remote_management=remote,
        python={key: val for key, val in remote['python'].items() if key not in ('resolved_path', 'symlink_chain')},
        carrier_unit=dict(name=fixed['unit'], control_group='/system.slice/' + fixed['unit'], invocation_id=str(4 + index) * 32,
            active_state='active', sub_state='running', runtime_max_usec=800000000, timeout_stop_usec=30000000,
            memory_max=1073741824, memory_swap_max=0, tasks_max=128, cpu_quota_per_sec_usec=1000000,
            restart='no', kill_mode='control-group', exit_type='cgroup'),
        process_limits=dict(cpu_soft=800, cpu_hard=800, nofile_soft=256, nofile_hard=256,
                            fsize_soft=67108864, fsize_hard=67108864, umask=0o077))
    hello_raw = c.canonical(hello, newline=True)
    out = c.HELLO_MAGIC + struct.pack('>Q', len(hello_raw)) + hello_raw
    marker = dict(schema=c.CONSUMPTION_SCHEMA, scope=c.SCOPE, session_id=fixed['session'],
        baseline=copy.deepcopy(c.BASELINE), owner_decision=copy.deepcopy(c.OWNER_DECISION),
        closure=copy.deepcopy(c.CLOSURE), implementation=copy.deepcopy(fixed['implementation']),
        amendment=c.make_amendment(fixed['implementation']), candidate=copy.deepcopy(c.CANDIDATE),
        package=dict(basename=fixed['session'] + '.lhfp', bytes=fixed['package_bytes'],
            sha256=fixed['package_sha'], manifest_sha256=fixed['manifest_sha']),
        approved_inputs_sha256=('c' * 64,
            '5bcbf535f6c8d0d2c974756af6815ba95a03da7fadc31c97a0622cdeeaf4846e',
            '5d227ecbef0eb0b72a3c5ddee998c1505b88ddf70d3c3c506e262144c25198da',
            '169c6e8cef5a3d6ee94d7cf433996016710b5e5613a7158e57875baad09ee793')[index],
        local_management_binding_sha256='d' * 64, writer=writer(),
        carrier_argv_sha256='e' * 64, host_boottime_origin_ns=1, host_monotonic_origin_ns=1,
        host_boottime_deadline_ns=900000000001, host_monotonic_deadline_ns=900000000001,
        state='CONSUMPTION_RECORD_COMPLETE')
    marker_raw = c.canonical(marker, newline=True)
    parts = {'carrier-consumed.json': marker_raw, 'stdout': out,
             'stderr': (b'', b'CORE_ADMIT_SUDO_OUTPUT\n', b'CORE_ADMIT_SSHD_GRAMMAR\n',b'CORE_CAP_INSUFFICIENT\n')[index]}
    rows = [dict(basename=name(role), bytes=len(raw), sha256=c.sha256(raw),
        allocated_bytes=4096 if raw else 0, dev=1, ino=i + 1 + 10 * index, mode=0o600, nlink=1)
        for i, (role, raw) in enumerate(sorted(parts.items()))]
    allocated = sum(row['allocated_bytes'] for row in rows)
    missing = [dict(code='CORE_OUTPUT_MISSING', role='output-package', detail_sha256='a' * 64)]
    if not fixed['sent']:
        missing.append(dict(code='CORE_TRANSPORT_FAILED', role='transport', detail_sha256='b' * 64))
    cap = dict(schema='local-hand-q2-core-capture-manifest/v1', session_id=fixed['session'],
        consumption_sha256=c.sha256(marker_raw),
        **{role: dict(basename=name(role), bytes=len(parts[role]), sha256=c.sha256(parts[role]), eof=fixed['sent'])
           for role in ('stdout', 'stderr')},
        output_package=dict(present=False, frame_bytes=0, manifest_sha256=None, members_sha256=None, valid=False),
        wait=dict(status=fixed['status'], host_deadline_met=fixed['sent']), files=rows, logical_bytes=sum(map(len, parts.values())),
        allocated_bytes=allocated, inodes=3, fsync_complete=True, reread_equal=True, missing=missing)
    parts['capture-manifest.json'] = c.canonical(cap, newline=True)
    receipt = dict(schema='local-hand-q2-core-local-acceptance-receipt/v1', scope=c.SCOPE, session_id=fixed['session'],
        consumption=dict(object_created=True, record_complete=True, basename=name('carrier-consumed.json'),
                         bytes=len(marker_raw), sha256=c.sha256(marker_raw)),
        transport=dict(execve_succeeded=True, hello_valid=True, bind_written=fixed['sent'], package_written=fixed['sent'],
                       stdin_bytes_written=(0, 18150763, 18174538,18194592)[index], stdin_eof=fixed['sent']),
        remote_result=dict(present=False, sha256=None, frame_sha256=None),
        wait=dict(status=fixed['status'], stdout_eof=fixed['sent'], stderr_eof=fixed['sent'], host_deadline_met=fixed['sent']),
        capture=dict(bytes=allocated, inodes=3, manifest_sha256=c.sha256(parts['capture-manifest.json']),
                     fsync_complete=True, reread_equal=True),
        real_task_execution=dict(status='UNKNOWN', evidence_sha256=None),
        result_evidence_collection=dict(status='UNKNOWN', evidence_sha256=None), state='STOP_AND_RETAIN', missing=missing)
    parts['acceptance-receipt.json'] = c.canonical(receipt, newline=True)
    return {name(role): raw for role, raw in parts.items()}


def patch_pins(monkeypatch, files, *dispatchers, index=0):
    fixed = p.profile(index)
    pins = {name[len(fixed['session']) + 2:]: (len(raw), c.sha256(raw)) for name, raw in files.items()}
    total = sum(map(len, files.values()))
    monkeypatch.setattr(p, ('PINS', 'SECOND_PINS', 'THIRD_PINS', 'FOURTH_PINS')[index], pins)
    monkeypatch.setattr(p, ('TOTAL_BYTES', 'SECOND_TOTAL_BYTES', 'THIRD_TOTAL_BYTES', 'FOURTH_TOTAL_BYTES')[index], total)
    for dispatcher in dispatchers:
        monkeypatch.setattr(dispatcher, ('PRIOR_PINS', 'SECOND_PRIOR_PINS', 'THIRD_PRIOR_PINS', 'FOURTH_PRIOR_PINS')[index], copy.deepcopy(pins))
        monkeypatch.setattr(dispatcher, ('PRIOR_TOTAL_BYTES', 'SECOND_PRIOR_TOTAL_BYTES', 'THIRD_PRIOR_TOTAL_BYTES', 'FOURTH_PRIOR_TOTAL_BYTES')[index], total)


def fixture(monkeypatch, *dispatchers):
    files = raw_files()
    patch_pins(monkeypatch, files, *dispatchers)
    patch_pins(monkeypatch, raw_files(1), *dispatchers, index=1)
    patch_pins(monkeypatch, raw_files(2), *dispatchers, index=2)
    patch_pins(monkeypatch,raw_files(3),*dispatchers,index=3)
    return p.build(files), files


def triple_fixture(monkeypatch, *dispatchers):
    _, first = fixture(monkeypatch, *dispatchers)
    files = {**first, **raw_files(1), **raw_files(2), **raw_files(3)}
    return p.build_all(files), files


def envelope():
    """Untrusted synthetic envelope, with no parser or production pins patched."""
    priors, commitments = [], []
    for index in (0, 1, 2, 3):
        fixed = p.profile(index)
        files = raw_files(index)
        prior = dict(schema=p.SCHEMA, scope=c.SCOPE, session_id=fixed['session'],
            implementation=copy.deepcopy(fixed['implementation']), package_sha256=fixed['package_sha'],
            manifest_sha256=fixed['manifest_sha'], files=[dict(basename=name, bytes=len(raw),
                sha256=c.sha256(raw), raw_base64=base64.b64encode(raw).decode('ascii'))
                for name, raw in sorted(files.items())])
        priors.append(prior)
        commitments.append(dict(scope=c.SCOPE, session_id=fixed['session'],
            source_attempt_sha256=c.sha256(c.canonical(prior)), logical_bytes=276 * 1048576,
            logical_inodes=16512, cpu_seconds=2090, host_capture_bytes=64 * 1048576,
            host_capture_inodes=16, released_or_refunded=False))
    return priors, commitments


def embed(value, monkeypatch, *dispatchers):
    prior, files = triple_fixture(monkeypatch, *dispatchers)
    value['reconciliation'].update(schema='local-hand-q2-core-reconciliation/v12', prior_core_attempts=prior,
                                  prior_diagnostic_capture=p.diagnostic_retention(),
                                  journal_transition=journal_transition(value['amendment']['implementation']))
    value['historical_capacity_obligations'].update(schema='local-hand-q2-core-historical-capacity-obligations/v12',
        maintenance=p.maintenance_commitments(),prior_commitments=[p.commitment(value, index=index) for index, value in enumerate(prior)])
    return files


def quiescence(prior, context):
    # Fixture construction does not replace the consumer's strict validation.
    index = [p.profile(i)['session'] for i in (0, 1, 2, 3)].index(prior['session_id'])
    row = next(r for r in prior['files'] if r['basename'] == p.basename('stdout', index))
    hello = c.document(base64.b64decode(row['raw_base64'])[16:], limit=65536, newline=True)
    path = '/sys/fs/cgroup' + hello['carrier_unit']['control_group']
    unit = dict(Id=p.profile(index)['unit'], LoadState='not-found', ActiveState='inactive', SubState='dead', MainPID='0',
                InvocationID='', ControlGroup='', Restart='no', KillMode='control-group', ExitType='main')
    group = dict(path=path, state='ABSENT', parent=dict(path='/sys/fs/cgroup/system.slice', dev=1,
        ino=2, mode=0o755, uid=0, gid=0), identity=None, populated=None, procs_bytes=None)
    return dict(schema='local-hand-q2-core-prior-quiescence/v2', prior_attempt_sha256=c.sha256(c.canonical(prior)),
        boot_id=context['hello']['guest_boot_id'], branch='COLLECTED_ABSENT', current_scope_quiescent=True,
        historical_remote_exit='UNKNOWN', historical_usage='UNKNOWN', released_bytes=0, released_inodes=0,
        observations=[dict(ordinal=i, unit=copy.deepcopy(unit), cgroup=copy.deepcopy(group),
            boottime_ns=context['hello']['guest_boottime_origin_ns'] + 4*i + index,
            monotonic_ns=context['hello']['guest_monotonic_origin_ns'] + 4*i + index) for i in (1, 2)])


def diagnostic_files(monkeypatch):
    """Synthetic opaque stdout: no configuration parser or diagnostic replay."""
    marker = dict(schema='lhq-sshd-source-capture-receipt-v1', session=p.DIAGNOSTIC_SESSION,
        R=c.RULE['commit'], A='f2eb31deb3c52d69ccd2079fb7d88608d1a25a62',
        C='b346cbd44dd4f376d4386f72d7029b1311788229',
        D='bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891',
        reader_sha256='68c594cedbea15768789690b4afd0797bfff1057760a522f931e16a4a7ca3108',
        argv_environment_sha256='1192ec89516a1297bf6c85dd7911cc01db61032bde335db2f631f86845845eca',
        clock_origins_ns=[1, 2])
    parts = {'consumed.json': c.canonical(marker, newline=True),
             'stdout': b'synthetic opaque diagnostic bytes, not a snapshot', 'stderr': b''}
    receipt = dict(marker, state='COMPLETE', reason='SNAPSHOT_VERIFIED', requests_attempted=1,
        marker_creation_attempted=True, marker_created=True, exit=0, stdout_eof=True,
        stderr_eof=True, snapshot_complete=True, remote_supervision_proven=False,
        remote_exit='READER_REPORTED_COMPLETE', complete_host_admission_proven=False,
        exclusive_reservation_proven=False, old_commitments_refunded=False,
        files={role: dict(bytes=len(parts[suffix]), sha256=c.sha256(parts[suffix]))
            for role, suffix in (('marker', 'consumed.json'), ('stdout', 'stdout'), ('stderr', 'stderr'))},
        observed_allocated_peak_before_receipt_bytes=8192, host_deadline_met=True)
    parts['receipt.json'] = c.canonical(receipt, newline=True)
    monkeypatch.setattr(p, 'DIAGNOSTIC_PINS', {suffix: (len(raw), c.sha256(raw))
                                            for suffix, raw in parts.items()})
    return {'.' + p.DIAGNOSTIC_SESSION + '.' + suffix: raw for suffix, raw in parts.items()}


def journal_transition(implementation):
    """Synthetic projection, never substitutes for the host original consumer."""
    return dict(schema='local-hand-q2-core-journal-transition/v8',
        authority=dict(R=c.RULE['commit'],A=c.QI_BASELINE['commit'],C=c.QI_CLOSURE['commit']),
        guest_startup_assurance=dict(mode='TRUSTED_SINGLE_ADMIN',
            indirect_startup_observation='NOT_PERFORMED',
            no_undeclared_business_startup=True,continuous_exclusion_proven=False),
        previous_maintenance=p.maintenance_resume(),implementation=copy.deepcopy(implementation),session=p.JOURNAL_SESSION,nonce='a'*64,
        access_mode='TRUSTED_SINGLE_ADMIN',host_writer_observation='NOT_PERFORMED',
        continuous_exclusion_proven=False,input_sha256='b'*64,manifest_sha256='c'*64,
        source_files={name:dict(bytes=100,sha256='d'*64) for name in p.JOURNAL_SOURCE_NAMES},
        originals=[dict(basename='.'+p.JOURNAL_SESSION+'.'+name,bytes=0,sha256=c.sha256(b''))
            for name in sorted(p.JOURNAL_FILES)],
        old_boot_id='11111111-2222-3333-4444-555555555555',
        new_boot_id='22222222-2222-3333-4444-555555555555',
        old_vm=dict(pid=123,starttime=1,argv_sha256='e'*64),
        new_vm=dict(pid=124,starttime=2,argv_sha256='f'*64),old_pidfd_exited=True,
        image_identities={role:[1,i+10] for i,role in enumerate(('system','quota','journal','evidence','seed'))},
        original_argv_sha256='a'*64,restart_argv_sha256='b'*64,
        backup=dict(bytes=1024,sha256='c'*64),virtual_bytes=dict(before=268435456,after=536870912),
        filesystem=dict(uuid='33333333-2222-3333-4444-555555555555',before_bytes=268435456,
            after_bytes=536870912,available=dict(bytes=419430400,inodes=32768)),
        content=dict(entries=1,content_bytes=10,sha256='d'*64),
        reports={phase:dict(bytes=100,sha256='e'*64) for phase in ('pre','post')},
        completed_steps=['CONSUMED','GUEST_QUIET','POWERED_OFF','BACKED_UP','IMAGE_GROWN','BOOTED','FILESYSTEM_GROWN','VERIFIED'],
        transport_exits=[255,0],image_checks=[0,0],logical_compare_exit=0,resize_exit=0,
        all_streams_eof=True,historical_exit='UNKNOWN',old_commitments_refunded=False)


def previous_journal_files(monkeypatch, *dispatchers):
    """Substitute only fixed byte pins for synthetic old originals; use the real relation parser."""
    dump=lambda value:c.canonical(value,newline=True)
    files={}
    for index in range(7):
        files.update(_previous_journal_generation(monkeypatch,dispatchers,index))
    p.build_previous_maintenance(files)
    return files


def _previous_journal_generation(monkeypatch, dispatchers, index):
    dump=lambda value:c.canonical(value,newline=True)
    fixed=p.previous_journal_profiles()[index]
    session=fixed['session']
    authority=fixed['authority']
    common=dict(D=fixed['D'],nonce='9'*64,access_mode='TRUSTED_SINGLE_ADMIN',
        host_writer_observation='NOT_PERFORMED',continuous_exclusion_proven=False)
    inputs=dict(inventory_sha256='8'*64)
    if index==1:inputs['resume']=p.serial_maintenance_resume()
    if index==2:inputs['resume']=p.systemctl_maintenance_resume()
    if index==3:inputs['resume']=p.template_maintenance_resume()
    if index==4:inputs['resume']=p.names_maintenance_resume()
    if index==5:inputs['resume']=p.exec_maintenance_resume()
    if index==6:inputs['resume']=p.guest_startup_maintenance_resume()
    desc=dict(session=session,nonce=common['nonce'],original_boot_id='11111111-2222-3333-4444-555555555555',
        source_binding_sha256=c.sha256(dump(inputs)),window_seconds=898,change_seconds=778)
    if index==6:
        from q1_binding_fixture import inventory, identity
        assurance=dict(mode='TRUSTED_SINGLE_ADMIN',indirect_startup_observation='NOT_PERFORMED',
            no_undeclared_business_startup=True,continuous_exclusion_proven=False)
        common['guest_startup_assurance']=inputs['guest_startup_assurance']=assurance
        desc.update(inventory(),schema='lhq-journal-growth-input/v2',guest_startup_assurance=assurance,
            source_binding_sha256=c.sha256(dump(inputs)))
    manifest=dict(common,**authority,schema='lhq-journal-growth-manifest/v'+str(fixed['version']),inputs=inputs,
        inventory_sha256='8'*64,window_binding=dict(origins=[10,20]))
    marker=dict(common,session=session,manifest=manifest,manifest_sha256=c.sha256(dump(manifest)),
        clocks=[10,20],pre_description=desc,pre_command_sha256='7'*64)
    failure=dict(schema='lhq-journal-growth-guest/v1',session=session,phase='pre',status='INCOMPLETE',
        stage=fixed['stage'],reason=fixed['reason'],actions_started=[])
    if index==6:
        failure.update(schema='lhq-journal-growth-guest/v2',guest_startup_assurance=assurance,
            diagnostic=dict(context=dict(unit=identity()[0])))
    streams={'pre.stdout':b'','pre.stderr':dump(failure)}
    receipt=dict(common,**authority,schema='lhq-journal-growth-receipt/v'+str(fixed['version']),session=session,
        state='STOP_AND_RETAIN',last_step='STOP_AND_RETAIN',reason='GROWTH_REPORT_MISSING',
        started=['CONSUMED','GUEST_QUIET'],marker_created=True,ssh_requests=1,business_cases=0,
        remote_exit='UNKNOWN',old_commitments_refunded=False,manifest_sha256=marker['manifest_sha256'],
        clock_origins_ns=[10,20],original_boot_id=desc['original_boot_id'],
        transports=[dict(files={name:dict(bytes=len(streams['pre.'+name]),sha256=c.sha256(streams['pre.'+name]))
            for name in ('stdout','stderr')})])
    events=[dict(step='CONSUMED',state='STARTED'),dict(step='CONSUMED',state='RETURNED',
        result=dict(manifest_sha256=marker['manifest_sha256'])),dict(step='GUEST_QUIET',state='STARTED'),
        dict(phase='pre',argv_sha256=marker['pre_command_sha256'],description_sha256=c.sha256(dump(desc)),
            window_seconds=898,change_seconds=778)]
    if index in (1,2,3,4,5,6):
        resume={1:p.serial_maintenance_resume,2:p.systemctl_maintenance_resume,3:p.template_maintenance_resume,4:p.names_maintenance_resume,5:p.exec_maintenance_resume,6:p.guest_startup_maintenance_resume}[index]()
        for row in (manifest,marker,receipt):row['resume']=resume
        marker['manifest_sha256']=receipt['manifest_sha256']=c.sha256(dump(manifest))
        events[1]['result']['manifest_sha256']=marker['manifest_sha256']
    raw={'consumed.json':dump(marker),'events.jsonl':b''.join(dump(row) for row in events),
        **streams,'receipt.json':dump(receipt)}
    pins={name:(len(raw[name]),c.sha256(raw[name])) for name in fixed['pins']}
    for module in (p,*dispatchers):monkeypatch.setattr(module,('PREVIOUS_JOURNAL_PINS','SECOND_JOURNAL_PINS','THIRD_JOURNAL_PINS','FOURTH_JOURNAL_PINS','FIFTH_JOURNAL_PINS','SIXTH_JOURNAL_PINS','SEVENTH_JOURNAL_PINS')[index],pins.copy())
    files={'.'+session+'.'+name:data for name,data in raw.items()}
    return files

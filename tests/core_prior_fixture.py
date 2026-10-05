"""Explicitly synthetic old F1 bytes; never private evidence or field PASS."""
import base64
import copy
import struct

from core_writer_fixture import writer
from e3_host import q2_core_delivery_contract as c
from e3_host import q2_core_prior_attempt as p


def raw_files():
    remote = dict(account='q1admin', uid=1000, gid=1000, home='/home/q1admin', login_shell='/bin/bash',
        parser_profile='bash-noninteractive-c-v1', remote_tokens_sha256='a' * 64, remote_command_sha256='b' * 64)
    for index, (role, path) in enumerate(dict(shell='/bin/bash', sudo='/usr/bin/sudo', env='/usr/bin/env',
                                            systemd_run='/usr/bin/systemd-run', python='/usr/bin/python3').items()):
        remote[role] = dict(path=path, resolved_path=path, symlink_chain=[], dev=1, ino=index + 10,
            mode=0o755, uid=0, gid=0, nlink=1, bytes=100, sha256=str(index + 1) * 64)
    hello = dict(schema=c.HELLO_SCHEMA, scope=c.SCOPE, loader_sha256=p.LOADER_SHA,
        bootstrap_sha256=p.BOOTSTRAP_SHA, guest_boot_id='11111111-2222-3333-4444-555555555555',
        guest_boottime_origin_ns=100, guest_monotonic_origin_ns=200, pid=999,
        uid=0, gid=0, euid=0, egid=0, remote_management=remote,
        python={key: val for key, val in remote['python'].items() if key not in ('resolved_path', 'symlink_chain')},
        carrier_unit=dict(name=p.UNIT, control_group='/system.slice/' + p.UNIT, invocation_id='4' * 32,
            active_state='active', sub_state='running', runtime_max_usec=800000000, timeout_stop_usec=30000000,
            memory_max=1073741824, memory_swap_max=0, tasks_max=128, cpu_quota_per_sec_usec=1000000,
            restart='no', kill_mode='control-group', exit_type='cgroup'),
        process_limits=dict(cpu_soft=800, cpu_hard=800, nofile_soft=256, nofile_hard=256,
                            fsize_soft=67108864, fsize_hard=67108864, umask=0o077))
    hello_raw = c.canonical(hello, newline=True)
    out = c.HELLO_MAGIC + struct.pack('>Q', len(hello_raw)) + hello_raw
    marker = dict(schema=c.CONSUMPTION_SCHEMA, scope=c.SCOPE, session_id=p.SESSION,
        baseline=copy.deepcopy(c.BASELINE), owner_decision=copy.deepcopy(c.OWNER_DECISION),
        closure=copy.deepcopy(c.CLOSURE), implementation=copy.deepcopy(p.IMPLEMENTATION),
        amendment=c.make_amendment(p.IMPLEMENTATION), candidate=copy.deepcopy(c.CANDIDATE),
        package=dict(basename=p.SESSION + '.lhfp', bytes=18111397, sha256=p.PACKAGE_SHA, manifest_sha256=p.MANIFEST_SHA),
        approved_inputs_sha256='c' * 64, local_management_binding_sha256='d' * 64, writer=writer(),
        carrier_argv_sha256='e' * 64, host_boottime_origin_ns=1, host_monotonic_origin_ns=1,
        host_boottime_deadline_ns=900000000001, host_monotonic_deadline_ns=900000000001,
        state='CONSUMPTION_RECORD_COMPLETE')
    marker_raw = c.canonical(marker, newline=True)
    parts = {'carrier-consumed.json': marker_raw, 'stdout': out, 'stderr': b''}
    rows = [dict(basename=p.basename(name), bytes=len(raw), sha256=c.sha256(raw),
        allocated_bytes=4096 if raw else 0, dev=1, ino=i + 1, mode=0o600, nlink=1)
        for i, (name, raw) in enumerate(sorted(parts.items()))]
    missing = [dict(code='CORE_OUTPUT_MISSING', role='output-package', detail_sha256='a' * 64),
               dict(code='CORE_TRANSPORT_FAILED', role='transport', detail_sha256='b' * 64)]
    cap = dict(schema='local-hand-q2-core-capture-manifest/v1', session_id=p.SESSION,
        consumption_sha256=c.sha256(marker_raw),
        **{name: dict(basename=p.basename(name), bytes=len(parts[name]), sha256=c.sha256(parts[name]), eof=False)
           for name in ('stdout', 'stderr')},
        output_package=dict(present=False, frame_bytes=0, manifest_sha256=None, members_sha256=None, valid=False),
        wait=dict(status=255, host_deadline_met=False), files=rows, logical_bytes=sum(map(len, parts.values())),
        allocated_bytes=8192, inodes=3, fsync_complete=True, reread_equal=True, missing=missing)
    parts['capture-manifest.json'] = c.canonical(cap, newline=True)
    receipt = dict(schema='local-hand-q2-core-local-acceptance-receipt/v1', scope=c.SCOPE, session_id=p.SESSION,
        consumption=dict(object_created=True, record_complete=True, basename=p.basename('carrier-consumed.json'),
                         bytes=len(marker_raw), sha256=c.sha256(marker_raw)),
        transport=dict(execve_succeeded=True, hello_valid=True, bind_written=False, package_written=False,
                       stdin_bytes_written=0, stdin_eof=False),
        remote_result=dict(present=False, sha256=None, frame_sha256=None),
        wait=dict(status=255, stdout_eof=False, stderr_eof=False, host_deadline_met=False),
        capture=dict(bytes=8192, inodes=3, manifest_sha256=c.sha256(parts['capture-manifest.json']),
                     fsync_complete=True, reread_equal=True),
        real_task_execution=dict(status='UNKNOWN', evidence_sha256=None),
        result_evidence_collection=dict(status='UNKNOWN', evidence_sha256=None), state='STOP_AND_RETAIN', missing=missing)
    parts['acceptance-receipt.json'] = c.canonical(receipt, newline=True)
    return {p.basename(name): raw for name, raw in parts.items()}


def patch_pins(monkeypatch, files, *dispatchers):
    pins = {name[len(p.SESSION) + 2:]: (len(raw), c.sha256(raw)) for name, raw in files.items()}
    total = sum(map(len, files.values()))
    monkeypatch.setattr(p, 'PINS', pins)
    monkeypatch.setattr(p, 'TOTAL_BYTES', total)
    for dispatcher in dispatchers:
        monkeypatch.setattr(dispatcher, 'PRIOR_PINS', copy.deepcopy(pins))
        monkeypatch.setattr(dispatcher, 'PRIOR_TOTAL_BYTES', total)


def fixture(monkeypatch, *dispatchers):
    files = raw_files()
    patch_pins(monkeypatch, files, *dispatchers)
    return p.build(files), files


def envelope():
    """Untrusted synthetic envelope, with no parser or production pins patched."""
    files = raw_files()
    prior = dict(schema=p.SCHEMA, scope=c.SCOPE, session_id=p.SESSION,
        implementation=copy.deepcopy(p.IMPLEMENTATION), package_sha256=p.PACKAGE_SHA,
        manifest_sha256=p.MANIFEST_SHA, files=[dict(basename=name, bytes=len(raw),
            sha256=c.sha256(raw), raw_base64=base64.b64encode(raw).decode('ascii'))
            for name, raw in sorted(files.items())])
    commitment = dict(scope=c.SCOPE, session_id=p.SESSION,
        source_attempt_sha256=c.sha256(c.canonical(prior)), logical_bytes=276 * 1048576,
        logical_inodes=16512, cpu_seconds=2090, host_capture_bytes=64 * 1048576,
        host_capture_inodes=16, released_or_refunded=False)
    return prior, commitment


def embed(value, monkeypatch, *dispatchers):
    prior, files = fixture(monkeypatch, *dispatchers)
    value['reconciliation'].update(schema='local-hand-q2-core-reconciliation/v2', prior_core_attempt=prior)
    value['historical_capacity_obligations'].update(schema='local-hand-q2-core-historical-capacity-obligations/v2',
        prior_commitment=p.commitment(prior))
    return files


def quiescence(prior, context):
    # Fixture construction does not replace the consumer's strict validation.
    row = next(r for r in prior['files'] if r['basename'] == p.basename('stdout'))
    hello = c.document(base64.b64decode(row['raw_base64'])[16:], limit=65536, newline=True)
    path = '/sys/fs/cgroup' + hello['carrier_unit']['control_group']
    unit = dict(Id=p.UNIT, LoadState='not-found', ActiveState='inactive', SubState='dead', MainPID='0',
                InvocationID='', ControlGroup='', Restart='no', KillMode='control-group', ExitType='main')
    group = dict(path=path, state='ABSENT', parent=dict(path='/sys/fs/cgroup/system.slice', dev=1,
        ino=2, mode=0o755, uid=0, gid=0), identity=None, populated=None, procs_bytes=None)
    return dict(schema='local-hand-q2-core-prior-quiescence/v1', prior_attempt_sha256=c.sha256(c.canonical(prior)),
        boot_id=hello['guest_boot_id'], branch='COLLECTED_ABSENT', current_scope_quiescent=True,
        historical_remote_exit='UNKNOWN', historical_usage='UNKNOWN', released_bytes=0, released_inodes=0,
        observations=[dict(ordinal=i, unit=copy.deepcopy(unit), cgroup=copy.deepcopy(group),
            boottime_ns=context['hello']['guest_boottime_origin_ns'] + i,
            monotonic_ns=context['hello']['guest_monotonic_origin_ns'] + i) for i in (1, 2)])

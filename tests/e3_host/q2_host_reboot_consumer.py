"""Independent offline HB2 consumer; never produces VM activation or release."""
from __future__ import annotations

import hashlib
import json
import re
import stat


class EvidenceError(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise EvidenceError(reason)


def digest(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def document(raw):
    need(type(raw) is bytes and len(raw) <= 131072, 'record bound')
    def pairs(items):
        value = {}
        for k, v in items:
            need(k not in value, 'duplicate key')
            value[k] = v
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'invalid constant'))


def protected(meta, owner=None):
    need(stat.S_ISREG(meta['mode']) and not meta['mode'] & 0o022 and meta['nlink'] == 1,
         'file protection')
    if owner is not None:
        need(meta['uid'] == owner, 'file owner')


def consume(request_raw, originals, sources, parent, expected_request):
    """All arguments are retained bytes/data; no filesystem or process observation."""
    need(digest(request_raw) == expected_request, 'frozen request')
    request = document(request_raw)
    need(request['R'] == '10d2a5c827964989f41ca6e8eeac3d44de6d0f04' and
         request['A'] == 'b2a326036b634bb007a6adeec8929084bce3ccbd' and
         request['C'] == '62d485c499d02744fbf83a8653c1aa7f80be0584' and
         request['B'] == 'e2858815c3d1d340a69bf2c0d69d37becfd48bb1ce523fd0254cf62fc83861a8' and
         re.fullmatch('[0-9a-f]{40}', request['D']), 'authority')
    binding = dict(event='LH-Q2-CORE-HOST-REBOOT-READ-20261011-01', session='lhqhost-20261011a',
                   nonce=request['nonce'], request=expected_request)
    need(parent['binding'] == binding and parent['invocations'] == 1 and
         parent['eof'] == {'stdout': True, 'stderr': True}, 'caller completion')
    need(set(sources) == set(request['inputs']), 'source coverage')
    for role, raw in sources.items():
        need(digest(raw) == {k: request['inputs'][role][k] for k in ('bytes', 'sha256')}, 'source pin')
    need(len(originals) <= 32 and sum(len(v) for v in originals.values()) <= 2097152,
         'capture bounds')
    for stream in ('stdout', 'stderr'):
        raw = originals['caller.' + stream]
        need(len(raw) <= 65536 and parent[stream] == digest(raw), 'caller stream')
    index = document(originals['read-index.json'])
    need(index['binding'] == binding and index['allocated_bytes'] <= 2097152, 'index binding')
    expected_names = set(index['files']) | {'read-index.json', 'caller.stdout', 'caller.stderr'}
    need(set(originals) == expected_names, 'original coverage')
    for name, p in index['files'].items():
        need(digest(originals[name]) == p, 'original digest')
    need(document(originals['read-started.json']) == binding, 'start binding')
    result = document(originals['read-result.json'])
    need(all(result[k] == v for k, v in binding.items()) and result['state'] == index['state'],
         'result binding')
    need(result['limits'] == request['limits'] == dict(cpu_seconds=240, wall_seconds=240,
         aggregate_rss_bytes=1073741824, process_as_bytes=536870912, process_fds=256,
         stream_bytes=65536, record_bytes=131072, capture_bytes=2097152,
         control_commands=1, control_children=1), 'limits')
    need(result['costs'] == request['costs'] == dict(maintenance_obligations=18, old_mib=25283,
         old_inodes=7364, source_preparation_mib=2, source_preparation_inodes=64,
         read_capture_mib=2, read_capture_inodes=64, total_mib=25287, total_inodes=7492), 'costs')
    need(result['partitions'] == dict(parent_cpu=30, reader_cpu=180, control_cpu=30,
         parent_as=268435456, reader_as=536870912, control_as=268435456), 'aggregate partitions')
    if result['state'] == 'INCOMPLETE':
        need(parent['returncode'] == 3 and 'error' in result, 'failure completion')
        return dict(state='CONSUMED_READ_INCOMPLETE', core='NOT_RUN', release=False,
                    failure_stage=result['stage'], error=result['error'])
    need('error' not in parent, 'caller error')
    usage = parent['usage']
    need(0 <= usage['cpu_seconds'] < 240 and 0 < usage['peak_rss_bytes'] <= 1073741824
         and 0 <= usage['elapsed_seconds'] < 240, 'aggregate caller usage')
    need(result['state'] == 'FIXED_HOST_READ_COMPLETE' and parent['returncode'] == 0 and
         result['stage'] == 'COMPLETE' and 'error' not in result, 'read completion')
    need(result['inputs'] == {role: digest(raw) for role, raw in sources.items()}, 'read source pins')
    need(result['ssh_calls'] == result['network_requests'] == result['vm_actions'] == 0 and
         result['listener_queries'] == 1, 'operation scope')
    usage = result['usage']
    need(type(usage) is dict and 0 <= usage['cpu_seconds'] < 240 and
         0 < usage['peak_rss_bytes'] <= 1073741824 and 0 <= usage['elapsed_seconds'] < 240,
         'actual usage')
    need(result['host_before'] == result['host_after'] and
         set(result['host_before']['namespaces']) == {'pid', 'mnt', 'net'}, 'host stability')
    target = request['target']
    pidfile = result['pidfile']
    pids = [target['old_vm']['pid']]
    if pidfile['state'] == 'PRESENT':
        raw = originals['pidfile.raw']
        need(re.fullmatch(rb'[1-9][0-9]{0,9}\n?', raw) is not None and
             1 < int(raw) <= 2147483647 and pidfile['pid'] == int(raw) and
             digest(raw) == {k: pidfile[k] for k in ('bytes', 'sha256')}, 'pidfile')
        pids.append(pidfile['pid'])
    else:
        need(pidfile == {'state': 'ABSENT'} and 'pidfile.raw' not in originals, 'absent pidfile')
    pids = list(dict.fromkeys(pids))
    before, after = result['processes'], result['processes_after']
    projection = lambda rows: [{k: v for k, v in row.items() if k != 'stat_sha256'} for row in rows]
    need([p['pid'] for p in before] == pids and len(pids) <= 2 and
         projection(before) == projection(after), 'process scope/stability')
    matches = []
    for process in before:
        if process['state'] == 'ABSENT':
            need(set(process) == {'pid', 'state'}, 'absent process')
        elif process['state'] == 'OTHER_EXECUTABLE':
            need('argv_sha256' not in process and 'namespaces' not in process and
                 (process['exe'] != '/usr/bin/qemu-system-x86_64' or
                  process['exe_metadata'] != result['tools']['qemu']), 'foreign process')
        else:
            need(process['state'] == 'QEMU' and process['exe'] == '/usr/bin/qemu-system-x86_64' and
                 process['exe_metadata'] == result['tools']['qemu'], 'qemu identity')
            matches.append(dict(pid=process['pid'], argv_matches=process['argv_sha256'] ==
                           target['old_vm']['argv_sha256'], namespace_matches=process['namespaces'] ==
                           result['host_before']['namespaces']))
    roles = {'system', 'original_system', 'quota', 'journal', 'evidence', 'seed'}
    need(set(result['images']) == set(target['images']) == roles, 'image coverage')
    for role, item in result['images'].items():
        current, old = item['metadata'], target['images'][role]
        protected(current, request['owner_uid'])
        need(item['matches_retained'] is ((current['dev'], current['ino']) ==
                                         (old['device'], old['inode'])), 'image relation')
    for role in ('qemu', 'listener'):
        need(result['tools'][role] == request['tool_metadata'][role], 'tool source')
        protected(result['tools'][role], 0)
        need(result['tools'][role]['mode'] & 0o111, 'tool executable')
    control = document(originals['listener-completion.json'])
    need(control == result['listener']['completion'] and control['started'] is True and
         control['argv'] == ['/usr/bin/ss', '-H', '-4', '-ltn', 'sport = :22221'] and
         control['returncode'] == 0 and control['eof'] == {'stdout': True, 'stderr': True} and
         'error' not in control, 'control completion')
    for name in ('stdout', 'stderr'):
        raw = originals['listener.' + name]
        need(len(raw) <= 65536 and digest(raw) == control[name], 'control stream')
    need(not originals['listener.stderr'], 'control stderr')
    rows = [line.split() for line in originals['listener.stdout'].splitlines() if line.strip()]
    need(all(len(row) == 5 and row[0] == b'LISTEN' and row[1].isdigit() and row[2].isdigit()
             and row[3].rsplit(b':', 1)[-1] == b'22221' for row in rows), 'listener data')
    listener = 'PRESENT' if rows else 'ABSENT'
    need(result['listener']['state'] == listener, 'listener relation')
    need(result['serial']['state'] in ('PRESENT', 'ABSENT'), 'serial')
    if result['serial']['state'] == 'PRESENT':
        protected(result['serial']['metadata'])
    expected_paths = {v['path'] for v in request['inputs'].values()} | {
        target['qemu_metadata_path'], target['listener_argv'][0]} | {
        v['path'] for v in target['images'].values()}
    if pidfile['state'] == 'PRESENT': expected_paths.add(target['pidfile'])
    if result['serial']['state'] == 'PRESENT': expected_paths.add(target['serial_metadata_only'])
    need(set(result['held_files']) == expected_paths, 'held input coverage')
    for role, item in result['images'].items():
        need(result['held_files'][target['images'][role]['path']] == item['metadata'], 'held image')
    # Tools are separately bound to source metadata; every held input must retain protection.
    for meta in result['held_files'].values(): protected(meta)
    return dict(state='CONSUMED_FIXED_HOST_READ_COMPLETE', core='NOT_RUN', release=False,
                boot_matches_activation=result['host_before']['boot_id'] == request['old_host_boot'],
                boot_matches_rp2=result['host_before']['boot_id'] == request['rp2_host_boot'],
                pid_states=[p['state'] for p in before], listener=listener,
                image_identities_match=all(i['matches_retained'] for i in result['images'].values()),
                qemu_candidates=matches, guest_identity='UNKNOWN')

"""Source-bound, one-use HR activation proof. All inputs are retained bytes.

No live observation or execution entry point. The old activation and HB2 read
keep their meanings: Owner adopts a new baseline, not historical continuity.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import re
import stat
import tarfile
import shlex

R = '10d2a5c827964989f41ca6e8eeac3d44de6d0f04'
A = '4af01900cfe462cec4762cb04966dab139a0a31c'
C = '4acf0dbfe99d0c7e170b6102f861fa9671d09da2'
ORIGINAL_A = 'ee69dc80db82c3fbf3bd2c5d5c0e0ad0882a84c0'
SCOPE = 'LH-Q2-CORE-HOST-REBIND-CONTINUATION-v1'
EVENT = 'LH-Q2-CORE-HOST-REBIND-CONTINUATION-CLOSURE-20261011-01'
START_SESSION = 'lhqstart-20261011b'
GUEST_SESSION = 'lhqguest-20261011c'
MAINTENANCE_SESSION = 'lhqjgrow-20261011c'
OWNER_SHA = '17fe31a85856c67fa2159e50c3b32c4967c1c755ea8cfde26335a821f6fdbe0e'
REVISION_SHA = 'b1eec1914a2d7a02a1d799673aabe0ff5f204faf70479520292547cbedb3c84b'
HB_FREEZE_SHA = 'bdd83c731ed558b2997aefbe3c16456fae2e42663011fe34739b2b4d6b46b5c9'
HB_REQUEST_SHA = '4849b6104b192202fb953d5acbd48e13ff442abb5ce2e50b5b9bc81cc3e5b8bf'
HB_TERMINAL_SHA = '59bc58e9827ab887230f4a10c41a3982c6f6edce1b485334355eebdcb4170f73'
RP_FREEZE_SHA = '761c478977ac1fb62b5b3061c741305064c215cd169d63fcc9184dac4ee92d48'
ROLES = frozenset(('system', 'original_system', 'quota', 'journal', 'evidence', 'seed'))
IDENTITY_KEYS = ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink')
META_KEYS = frozenset((*IDENTITY_KEYS, 'size', 'blocks', 'mtime_ns', 'ctime_ns'))
HB_ORIGINALS = ('caller-completion.json', 'caller-started.json', 'caller.stderr',
    'caller.stdout', 'listener-completion.json', 'listener.stderr', 'listener.stdout',
    'parent.stderr', 'parent.stdout', 'read-index.json', 'read-result.json', 'read-started.json')
BASE_FILES = ('owner.json', 'revision.json', 'hb/request.json', 'hb/freeze.json',
    'hb/index.json', 'hb/tool-completion.json', 'hb/independent.json', 'hb/terminal.json',
    *('hb/' + n for n in HB_ORIGINALS))
EXTERNAL_ROLES = {'activation_archive', 'runtime_preparation_archive'}
SOURCE_ROLES = ('approval-question', 'approval-request', 'approved-review-proposal',
    *('old-caller-' + n + '.py' for n in ('accept_maintenance', 'core_bounds', 'core_once',
    'freeze_rp1', 'lifecycle_bounds', 'maintenance_once', 'offline_maintenance', 'prepare_archive',
    'prepare_binding', 'prepare_sources', 'retain_rp2_failure', 'run_once', 'runtime_bounds',
    'static_inputs', 'test_private_callers')),
    'old-release-gate', *('old-return-' + n for n in ('rp2-caller-completion.json',
    'rp2-caller-started.json', 'rp2-caller.stderr', 'rp2-caller.stdout', 'rp2-parent-launch.json',
    'rp2-parent.stderr', 'rp2-parent.stdout', 'rp2-preflight.stderr', 'rp2-summary.json')),
    'owner-decision', 'rp1-freeze.json', 'rp2-local-returns-index-private.json',
    'rp2-preflight.stdout', 'rp2-terminal.json', 'startup')
BASE_MEMBERS = (*BASE_FILES, *('source/' + n for n in SOURCE_ROLES))
REFERENCES = {'source/old-release-gate': 'source/rp2-terminal.json',
              'source/old-return-rp2-summary.json': 'source/old-return-rp2-caller.stdout'}
START_FILES = ('request.json', 'started.json', 'launch.json', 'result.json', 'caller.stdout',
    'caller.stderr', 'caller-completion.json', 'tool-completion.json', 'qemu.stdout', 'qemu.stderr',
    'pre-listener.stdout', 'pre-listener.stderr', 'post-listener.stdout', 'post-listener.stderr',
    'pidfile.raw', 'pid-stat.raw', 'pid-cmdline.raw', 'qemu-version.stdout', 'qemu-version.stderr')
GUEST_FILES = ('request.json', 'started.json', 'result.json', 'guest.stdout', 'guest.stderr',
    'caller.stdout', 'caller.stderr', 'caller-completion.json', 'tool-completion.json')
FINAL_MEMBERS = (*BASE_MEMBERS, 'hr1-freeze.json',
    *('start/' + n for n in START_FILES), *('guest/' + n for n in GUEST_FILES))
EXTRA_FIELDS = frozenset(('baseline_policy', 'historical_filesystem_continuity',
    'historical_content_continuity', 'owner_decision_sha256', 'serial_revision_sha256',
    'hb2_evidence_sha256', 'rp2_evidence_sha256', 'historical_activation_sha256',
    'startup_evidence_sha256', 'guest_evidence_sha256', 'serial_backend', 'serial_capture'))


class RebindError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise RebindError('HOST_REBIND_' + reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode() + b'\n'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(raw):
    return dict(bytes=len(raw), sha256=sha(raw))


def document(raw, cap=131072):
    require(type(raw) is bytes and len(raw) <= cap, 'DOCUMENT_BOUND')
    def pairs(items):
        require(len(dict(items)) == len(items), 'DUPLICATE_KEY')
        return dict(items)
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: require(False, 'JSON_CONSTANT'))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise RebindError('HOST_REBIND_DOCUMENT') from error
    require(type(value) is dict, 'DOCUMENT_TYPE')
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        require(depth <= 64, 'DOCUMENT_DEPTH')
        if type(item) is float:
            require(math.isfinite(item), 'JSON_FINITE')
        elif type(item) in (dict, list):
            pending.extend((v, depth + 1) for v in
                           (item.values() if type(item) is dict else item))
    return value


def costs():
    return dict(old_mib=25287, old_inodes=7492, maintenance_mib=2200, maintenance_inodes=402,
        preparation_mib=4, preparation_inodes=128, startup_mib=4, startup_inodes=128,
        guest_mib=2, guest_inodes=64, total_mib=27497, total_inodes=8214,
        maintenance_admission_mib=27369, maintenance_admission_inodes=8182,
        maintenance_obligations=19, core_capture_counted_once=True, refunded=False)


def previous_failure():
    return dict(session='lhqjgrow-20261011b', D='934122fab56f1a78f43dbc773e0de9598ea63078',
        state='INVOKED_FAILED_UNCONSUMED', reason='GROWTH_ACTIVATION_HOST_BOOT',
        phase='preflight', ssh_requests=0, marker_created=False, execute='NOT_CALLED',
        caller_returncode=3, coordinator_completion=None, core='NOT_RUN',
        old_commitments_refunded=False)


def envelope(files, *, final=True, resumed=False, repaired=False):
    require(not repaired or (final and resumed), 'REPAIR_ENVELOPE_MODE')
    expected = set(REPAIR_MEMBERS if repaired else (GR_FINAL_MEMBERS if final else GR_BASE_MEMBERS) if resumed else
                   (FINAL_MEMBERS if final else BASE_MEMBERS))
    require(set(files) == expected and all(type(b) is bytes and len(b) <= 131072
            for b in files.values()), 'ENVELOPE_COVERAGE')
    for name, target in REFERENCES.items():
        require(files[name] == files[target], 'ENVELOPE_REFERENCE')
    stored = {n:b for n,b in files.items() if n not in REFERENCES}
    stored['index.json'] = canonical(dict(schema='lhq-host-rebind-envelope/v3' if repaired else 'lhq-host-rebind-envelope/v2' if resumed else 'lhq-host-rebind-envelope/v1',
        files={n:pin(b) for n,b in stored.items()}, references=REFERENCES))
    require(len(stored['index.json']) <= 65536, 'ENVELOPE_INDEX_BOUND')
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(stored.items()):
            member = tarfile.TarInfo(name); member.size = len(data); member.mode = 0o600
            archive.addfile(member, io.BytesIO(data))
    raw = output.getvalue()
    require(len(raw) <= 1048576, 'ENVELOPE_BOUND')
    return raw


def read_envelope(raw, *, final=True, resumed=False, repaired=False):
    require(type(raw) is bytes and 0 < len(raw) <= 1048576 and len(raw) % 512 == 0,
            'ENVELOPE_BOUND')
    require(not repaired or (final and resumed), 'REPAIR_ENVELOPE_MODE')
    expected = set(REPAIR_MEMBERS if repaired else (GR_FINAL_MEMBERS if final else GR_BASE_MEMBERS) if resumed else
                   (FINAL_MEMBERS if final else BASE_MEMBERS)) - REFERENCES.keys()
    expected.add('index.json')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            require(member.name in expected and member.name not in files and
                member.isfile() and member.type == tarfile.REGTYPE and not member.pax_headers
                and member.mode == 0o600 and member.uid == member.gid == 0 and
                0 <= member.size <= 131072, 'ENVELOPE_MEMBER')
            stream = archive.extractfile(member)
            require(stream is not None, 'ENVELOPE_STREAM')
            with stream:
                data = stream.read(131073)
            require(len(data) == member.size, 'ENVELOPE_MEMBER_SIZE')
            files[member.name] = data
    require(set(files) == expected, 'ENVELOPE_COVERAGE')
    index_raw = files.pop('index.json'); index = document(index_raw)
    require(set(index) == {'schema', 'files', 'references'} and
        index['schema'] == ('lhq-host-rebind-envelope/v3' if repaired else 'lhq-host-rebind-envelope/v2' if resumed else 'lhq-host-rebind-envelope/v1') and
        index['files'] == {n: pin(b) for n, b in files.items()} and
        index['references'] == REFERENCES, 'ENVELOPE_INDEX')
    for name, target in REFERENCES.items():
        files[name] = files[target]
    require(raw == envelope(files, final=final, resumed=resumed, repaired=repaired), 'ENVELOPE_ENCODING')
    return files, pin(index_raw)


def baseline(files, identity_raw, failure_raw):
    """Reconsume HB2 and both historical archives; never trust a PASS projection."""
    from . import q2_host_reboot_consumer as hb
    from . import q2_core_prior_attempt as history
    require(set(files) == set(BASE_MEMBERS), 'BASELINE_COVERAGE')
    for name, digest in (('owner.json', OWNER_SHA), ('revision.json', REVISION_SHA),
            ('hb/freeze.json', HB_FREEZE_SHA), ('hb/request.json', HB_REQUEST_SHA),
            ('hb/terminal.json', HB_TERMINAL_SHA), ('source/rp1-freeze.json', RP_FREEZE_SHA)):
        require(sha(files[name]) == digest, 'FROZEN_' + name)
    owner = document(files['owner.json']); revision = document(files['revision.json'])
    require(owner['R'] == revision['R'] == R and owner['A'] == ORIGINAL_A and
        revision['A'] == A and owner['state'] == revision['state'] == 'APPROVED' and
        owner['scope'] == revision['scope'] == SCOPE and
        revision['previous_owner_decision_sha256'] == OWNER_SHA and
        revision['serial_backend'] == 'null' and
        revision['serial_capture'] == 'NOT_CAPTURED_NULL_BACKEND', 'OWNER')
    request = document(files['hb/request.json']); freeze = document(files['hb/freeze.json'])
    sources = {role: files['source/' + role] for role in SOURCE_ROLES}
    sources.update(activation_archive=identity_raw, runtime_preparation_archive=failure_raw)
    require(set(sources) == set(request['inputs']), 'HB_SOURCE_COVERAGE')
    originals_index = document(files['hb/index.json'])
    require(originals_index['files'] == {n: pin(files['hb/' + n]) for n in HB_ORIGINALS} and
        originals_index['freeze'] == pin(files['hb/freeze.json']) and
        originals_index['tool_completion'] == pin(files['hb/tool-completion.json']), 'HB_INDEX')
    require(document(files['hb/tool-completion.json'])['exit_code'] == 0, 'HB_TOOL_COMPLETION')
    parent = document(files['hb/caller-completion.json'])
    names = set(document(files['hb/read-index.json'])['files']) | {
        'read-index.json', 'caller.stdout', 'caller.stderr'}
    result = hb.consume(files['hb/request.json'], {n: files['hb/' + n] for n in names},
                        sources, parent, freeze['request'])
    require(result == document(files['hb/independent.json']) and
        result['state'] == 'CONSUMED_FIXED_HOST_READ_COMPLETE' and
        result['listener'] == 'ABSENT' and result['pid_states'] == ['ABSENT'] and
        result['qemu_candidates'] == [] and result['release'] is False and
        result['boot_matches_rp2'] is True, 'HB_RESULT')
    source, old_files, _ = history.build_runtime_preparation_source(failure_raw, identity_raw)
    rp = document(sources['rp1-freeze.json']); terminal = document(sources['rp2-terminal.json'])
    historical = history.build_vm_activation({n: b for n, b in old_files.items()
        if n != 'execution-return-index-private.json'}, old_files['execution-return-index-private.json'],
        historical_boot=rp['historical_boot_id'])
    require(historical == rp['vm_activation'] == terminal['vm_activation'] and
        rp['persistent_source'] == source and
        terminal['rp1_freeze_sha256'] == RP_FREEZE_SHA and
        terminal['state'] == 'RP2_INVOKED_FAILED_UNCONSUMED_RP3_NOT_RUN' and
        terminal['callers'] == rp['callers'], 'RP_TERMINAL')
    for name, digest in rp['callers'].items():
        require(sha(sources['old-caller-' + name]) == digest, 'RP_CALLER')
    summary = document(sources['old-return-rp2-summary.json'])
    require(summary == terminal['rp2']['summary'] and summary['reason'] == previous_failure()['reason']
        and summary['phase'] == 'preflight' and summary['exit_code'] == 3 and
        summary['ssh_requests'] == 0 and summary['marker_created'] is False, 'RP_FAILURE')
    caller = document(sources['old-return-rp2-caller-completion.json'])
    require(caller == terminal['rp2']['caller_completion'] and caller['returncode'] == 3 and
        caller['stdout_eof'] is caller['stderr_eof'] is True and
        caller['stdout'] == pin(sources['old-return-rp2-caller.stdout']) and
        caller['stderr'] == pin(sources['old-return-rp2-caller.stderr']), 'RP_COMPLETION')
    startup = document(sources['startup'])
    require(sources['startup'] == old_files['startup/start-proposal-private.json'], 'START_SOURCE')
    observed = document(files['hb/read-result.json'])
    require(observed['host_before']['boot_id'] == request['rp2_host_boot'] and
        observed['pidfile']['state'] == 'ABSENT', 'HB_HOST')
    images = {role: dict(path=request['target']['images'][role]['path'],
                        metadata=observed['images'][role]['metadata']) for role in ROLES}
    require(set(images) == set(startup['images']) and all(images[r]['path'] ==
        startup['images'][r]['path'] for r in ROLES), 'IMAGE_PATH_SOURCE')
    return dict(historical=historical, persistent_source=source, host=observed['host_before'],
        images=images, tools=observed['tools'], owner_uid=request['owner_uid'],
        old_vm=request['target']['old_vm'], old_pidfile=request['target']['pidfile'],
        old_serial=request['target']['serial_metadata_only'], serial_observation=observed['serial'],
        original_argv=startup['proposed_argv'], old_startup=startup,
        held_directories=observed['held_directories'],
        hb2_evidence_sha256=sha(canonical({n: pin(files[n]) for n in BASE_FILES if n.startswith('hb/')})),
        rp2_evidence_sha256=sha(canonical({n: pin(sources[n]) for n in SOURCE_ROLES
            if n.startswith('old-') or n.startswith('rp')})), costs=costs(),
        package=document(old_files['activation/activation-proposal-private.json'])['package'],
        quota=document(old_files['guest/proposal.json'])['quota'],
        ssh_prefix=document(old_files['guest/proposal.json'])['ssh_prefix'])


def startup_argv(original, pidfile):
    require(type(original) is list and all(type(x) is str and x.isascii() for x in original)
        and original.count('-pidfile') == original.count('-serial') == 1, 'START_ARGV')
    require(type(pidfile) is str and re.fullmatch(r'/[A-Za-z0-9_./-]+/vm\.pid', pidfile)
        and '..' not in pidfile.split('/'), 'PIDFILE_PATH')
    result = list(original)
    result[result.index('-pidfile') + 1] = pidfile
    result[result.index('-serial') + 1] = 'null'
    return result


def image_transition(before, after, owner):
    require(set(before) == set(after) == ROLES, 'IMAGE_COVERAGE')
    pairs = set()
    for role in ROLES:
        a, b = before[role], after[role]
        require(set(a) == set(b) == {'path', 'metadata'} and a['path'] == b['path'], 'IMAGE_PATH')
        x, y = a['metadata'], b['metadata']
        require(set(x) == set(y) == META_KEYS and all(type(v) is int and v >= 0
            for v in y.values()), 'IMAGE_METADATA')
        require(stat.S_ISREG(y['mode']) and y['uid'] == owner and not y['mode'] & 0o022
            and y['nlink'] == 1 and all(x[k] == y[k] for k in IDENTITY_KEYS), 'IMAGE_IDENTITY')
        if role in ('original_system', 'seed'):
            require(x == y, 'READONLY_IMAGE_CHANGED')
        pairs.add((y['dev'], y['ino']))
    require(len(pairs) == 6, 'IMAGE_ALIAS')


def validate_activation(value):
    from . import q2_core_prior_attempt as history
    fields = history.ACTIVATION_PROJECTION_FIELDS | EXTRA_FIELDS
    require(type(value) is dict and set(value) == fields and
        len(canonical(value)) <= 4096, 'ACTIVATION_FIELDS')
    require(value['schema'] == 'local-hand-q2-vm-activation/v3' and value['event'] == EVENT and
        value['baseline_policy'] == 'OWNER_ADOPTED_HB2_BASELINE' and
        value['historical_filesystem_continuity'] == value['historical_content_continuity'] == 'UNKNOWN'
        and value['owner_decision_sha256'] == OWNER_SHA and value['serial_revision_sha256'] == REVISION_SHA
        and value['serial_backend'] == 'null' and value['serial'] is None and
        value['serial_capture'] == 'NOT_CAPTURED_NULL_BACKEND', 'ACTIVATION_POLICY')
    # Reuse only the old projection's scalar and identity validation. Historical
    # v1/v2 inputs are never converted or accepted as v3 by this check.
    base = {k: copy.deepcopy(value[k]) for k in history.ACTIVATION_PROJECTION_FIELDS}
    base.update(schema='local-hand-q2-vm-activation/v1', event=history.ACTIVATION_EVENT,
                serial=value['pidfile'] + '.unused-null-serial')
    history.validate_vm_activation(base)
    for key in EXTRA_FIELDS - {'baseline_policy', 'historical_filesystem_continuity',
            'historical_content_continuity', 'serial_backend', 'serial_capture'}:
        require(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}', value[key]), 'ACTIVATION_DIGEST')
    return value


def binding(request_raw, *, resumed=False):
    request = document(request_raw)
    expected_authority = gr_authority() if resumed else dict(R=R, A=A, C=C, owner=OWNER_SHA, revision=REVISION_SHA)
    require(request['authority'] == expected_authority,
        'REQUEST_AUTHORITY')
    require(type(request['nonce']) is str and re.fullmatch('[0-9a-f]{64}', request['nonce']),
        'REQUEST_NONCE')
    require(set(request['implementation']) == {'commit', 'tree'} and all(type(v) is str and
        re.fullmatch('[0-9a-f]{40}', v) for v in request['implementation'].values()), 'REQUEST_D')
    require(canonical(request['costs']) == canonical(gr_costs() if resumed else costs()), 'REQUEST_COSTS')
    return dict(authority=request['authority'], implementation=request['implementation'],
                session=request['session'], nonce=request['nonce'], request=pin(request_raw))


def limits():
    return dict(cpu_seconds=240, wall_seconds=240, aggregate_rss_bytes=1073741824,
        process_as_bytes=536870912, process_fds=256, stream_bytes=65536,
        record_bytes=131072, startup_capture_bytes=4194304, guest_capture_bytes=2097152,
        sidecar_bytes=1048576, guest_cpu_seconds=120, guest_rss_bytes=536870912,
        guest_as_bytes=268435456, guest_fds=128)


def usage(value, cpu=240):
    require(type(value) is dict and set(value) == {'cpu_nanoseconds', 'rss_peak_bytes',
        'elapsed_nanoseconds'}, 'USAGE_FIELDS')
    for k, maximum in (('cpu_nanoseconds', cpu * 1000000000), ('rss_peak_bytes', 1073741824),
                        ('elapsed_nanoseconds', 240000000000)):
        require(type(value[k]) is int and 0 < value[k] <= maximum, 'USAGE_LIMIT')


def _completion(files, bound, expected_state):
    value = document(files['caller-completion.json'])
    require(value['binding'] == bound and value['invocations'] == 1 and
        type(value['invocations']) is int and value['returncode'] == 0 and
        type(value['returncode']) is int and value['eof'] == {'stdout': True, 'stderr': True},
        'CALLER_COMPLETION')
    for name in ('stdout', 'stderr'):
        require(len(files['caller.' + name]) <= 65536 and
            value[name] == pin(files['caller.' + name]), 'CALLER_STREAM')
    require(files['caller.stderr'] == b'' and document(files['caller.stdout']) ==
        dict(state=expected_state, result=pin(files['result.json'])), 'CALLER_RESULT')
    tool = document(files['tool-completion.json'])
    require(type(tool['exit_code']) is int and tool['exit_code'] == 0, 'TOOL_COMPLETION')
    usage(value['usage'])
    return value


def _command(row, files, name, argv):
    require(set(row) == {'argv', 'returncode', 'eof', 'stdout', 'stderr'} and
        row['argv'] == argv and type(row['returncode']) is int and row['returncode'] == 0
        and row['eof'] == {'stdout': True, 'stderr': True}, 'COMMAND_COMPLETION')
    for stream in ('stdout', 'stderr'):
        raw = files[name + '.' + stream]
        require(len(raw) <= 65536 and row[stream] == pin(raw), 'COMMAND_STREAM')
    require(files[name + '.stderr'] == b'', 'COMMAND_STDERR')


def verify_start(files, base, freeze):
    from . import q2_core_prior_attempt as history
    require(set(files) == set(START_FILES), 'START_FILES')
    request = document(files['request.json']); bound = binding(files['request.json'])
    require(bound['session'] == START_SESSION and freeze['requests']['start'] == bound['request']
        and request['baseline_sha256'] == sha(canonical(base)) and request['limits'] == limits(),
        'START_REQUEST')
    argv = startup_argv(base['original_argv'], request['pidfile'])
    require(request['argv'] == argv and request['serial_backend'] == 'null', 'START_ARGV_BINDING')
    require(document(files['started.json']) == bound, 'START_MARKER')
    result = document(files['result.json'])
    require(result['binding'] == bound and result['state'] == 'STARTED_AND_HOST_ENDPOINT_VERIFIED'
        and result['errors'] == [] and result['startup_calls'] == 1 and result['ssh_calls'] == 0
        and result['listener_queries'] == 2 and result['serial_capture'] ==
        'NOT_CAPTURED_NULL_BACKEND' and result['argv'] == argv, 'START_RESULT')
    require(all(type(result[k]) is int for k in ('startup_calls', 'ssh_calls', 'listener_queries')),
            'START_COUNTS')
    require(result['host_before'] == result['host_after'] == base['host'] and
        result['tools'] == base['tools'] and result['images_before'] == base['images'],
        'START_SOURCE_BINDING')
    require(result['old_pid_absent'] is result['old_pidfile_absent'] is True and
        result['old_serial_before'] == result['old_serial_after'] == base['serial_observation'],
        'START_OLD_OBJECTS')
    image_transition(base['images'], result['images_after'], base['owner_uid'])
    require(document(files['launch.json']) == dict(binding=bound, argv=argv,
        host=base['host'], images=base['images']), 'LAUNCH_BINDING')
    commands = result['commands']
    require(set(commands) == {'pre-listener', 'qemu', 'post-listener', 'qemu-version'}, 'START_COMMANDS')
    listener = ['/usr/bin/ss', '-H', '-4', '-ltn', 'sport = :22221']
    for name, args in (('pre-listener', listener), ('qemu', argv), ('post-listener', listener),
                       ('qemu-version', ['/usr/bin/qemu-system-x86_64', '--version'])):
        _command(commands[name], files, name, args)
    require(sha(files['qemu-version.stdout'] + files['qemu-version.stderr']) ==
        base['old_startup']['qemu_version_sha256'] and result['qemu_content_sha256'] ==
        base['old_startup']['qemu']['sha256'], 'START_QEMU_SOURCE')
    require(files['pre-listener.stdout'] == files['qemu.stdout'] == b'', 'START_PRE_CONFLICT')
    rows = files['post-listener.stdout'].splitlines()
    require(len(rows) == 1 and len(rows[0].split()) == 5 and rows[0].split()[0] == b'LISTEN'
        and rows[0].split()[3] == b'127.0.0.1:22221', 'START_LISTENER')
    process = result['process']
    require(set(process) == {'pid', 'starttime', 'argv_sha256', 'exe', 'exe_metadata', 'namespaces'}
        and process['exe'] == '/usr/bin/qemu-system-x86_64' and
        process['exe_metadata'] == base['tools']['qemu'] and
        process['namespaces'] == base['host']['namespaces'], 'START_PROCESS')
    vm = history._resume_process(process, argv, files['pid-stat.raw'], files['pid-cmdline.raw'])
    require((vm['pid'], vm['starttime']) != (base['old_vm']['pid'], base['old_vm']['starttime']),
            'START_OLD_PROCESS')
    require(re.fullmatch(rb'[1-9][0-9]{0,9}\n?', files['pidfile.raw']) is not None and
        int(files['pidfile.raw']) == vm['pid'], 'START_PIDFILE')
    usage(result['usage']); _completion(files, bound, result['state'])
    return request, result, vm


def verify_guest(files, base, freeze, start, start_raw, *, resumed=False):
    from . import q2_core_prior_attempt as history
    require(set(files) == set(GUEST_FILES), 'GUEST_FILES')
    request = document(files['request.json']); bound = binding(files['request.json'], resumed=resumed)
    require(bound['session'] == (GR_GUEST_SESSION if resumed else GUEST_SESSION) and freeze['requests']['guest'] == bound['request']
        and request['baseline_sha256'] == sha(canonical(base)) and request['limits'] == limits()
        and request['package'] == base['package'] and request['quota'] == base['quota']
        and request['ssh_prefix'] == base['ssh_prefix'], 'GUEST_REQUEST')
    require(request['guest_source'] == freeze['sources']['q2_current_guest_verification.py'],
            'GUEST_SOURCE')
    require(document(files['started.json']) == dict(binding=bound, startup=pin(start_raw)),
            'GUEST_MARKER')
    result = document(files['result.json'])
    require(result['binding'] == bound and result['state'] == 'CURRENT_GUEST_VERIFIED' and
        result['startup'] == pin(start_raw) and result['ssh_calls'] == 1 and
        result['startup_calls'] == result['package_install_calls'] == result['module_load_calls'] ==
        result['retries'] == 0 and result['errors'] == [], 'GUEST_RESULT')
    require(all(type(result[k]) is int for k in ('ssh_calls', 'startup_calls',
        'package_install_calls', 'module_load_calls', 'retries')), 'GUEST_COUNTS')
    require(result['host_before'] == result['host_after'] == base['host'] and
        result['vm_before'] == result['vm_after'] == start['process'], 'GUEST_IDENTITY')
    image_transition(start['images_after'], result['images_before'], base['owner_uid'])
    image_transition(result['images_before'], result['images_after'], base['owner_uid'])
    command = result['command']
    require(command['argv'][:-1] == base['ssh_prefix'] and
        command['argv'][-1] == request['remote_command'], 'GUEST_SSH_ARGV')
    _command(command, files, 'guest', command['argv'])
    current = history.validate_current_guest(document(files['guest.stdout']),
        package=base['package'], quota=base['quota'], nonce=bound['nonce'])
    require(result['guest_boot_id'] == current['boot_id'] and current['boot_id'] !=
        base['historical']['current_boot_id'], 'GUEST_NEW_BOOT')
    usage(result['usage'], 120)
    require(result['usage']['cpu_nanoseconds'] + current['management_usage']['cpu_nanoseconds']
        <= 240000000000 and result['usage']['rss_peak_bytes'] +
        current['management_usage']['rss_peak_bytes'] <= 1073741824, 'GUEST_AGGREGATE')
    completed = _completion(files, bound, result['state'])
    require(completed['usage']['cpu_nanoseconds'] + current['management_usage']['cpu_nanoseconds']
        <= 240000000000 and completed['usage']['rss_peak_bytes'] +
        current['management_usage']['rss_peak_bytes'] <= 1073741824, 'GUEST_PARENT_AGGREGATE')
    return current, result


def build_activation(raw, identity_raw, failure_raw):
    files, index = read_envelope(raw)
    base = baseline({n: files[n] for n in BASE_MEMBERS}, identity_raw, failure_raw)
    freeze = document(files['hr1-freeze.json'])
    require(freeze['schema'] == 'lhq-host-rebind-freeze/v1' and
        freeze['state'] == 'FROZEN_HR1_VERIFIED' and freeze['authority'] ==
        dict(R=R, A=A, C=C, owner=OWNER_SHA, revision=REVISION_SHA) and
        freeze['baseline_sha256'] == sha(canonical(base)) and freeze['costs'] == costs()
        and freeze['limits'] == limits(), 'FREEZE')
    require(freeze['baseline_files'] == {n: pin(files[n]) for n in BASE_MEMBERS} and
        freeze['external'] == dict(identity=pin(identity_raw), failure=pin(failure_raw)), 'FREEZE_SOURCES')
    groups = {prefix: {n: files[prefix + '/' + n] for n in names}
              for prefix, names in (('start', START_FILES), ('guest', GUEST_FILES))}
    start_request, start, vm = verify_start(groups['start'], base, freeze)
    current, guest = verify_guest(groups['guest'], base, freeze, start, groups['start']['result.json'])
    for prefix in groups:
        require(document(groups[prefix]['request.json'])['implementation'] == freeze['implementation'],
                'IMPLEMENTATION_BINDING')
    historical = base['historical']
    from . import q2_core_prior_attempt as history
    value = {k: copy.deepcopy(historical[k]) for k in history.ACTIVATION_PROJECTION_FIELDS}
    value.update(schema='local-hand-q2-vm-activation/v3', event=EVENT,
        current_boot_id=current['boot_id'], host_boot_id=base['host']['boot_id'], vm=vm,
        image_identities={r: [base['images'][r]['metadata'][k] for k in ('dev', 'ino')]
                          for r in ROLES - {'original_system'}},
        original_system_identity=[base['images']['original_system']['metadata'][k] for k in ('dev', 'ino')],
        system_path=base['images']['system']['path'], pidfile=start_request['pidfile'], serial=None,
        index=index, evidence_sha256=sha(canonical({n: pin(b) for n, b in files.items()})),
        baseline_policy='OWNER_ADOPTED_HB2_BASELINE', historical_filesystem_continuity='UNKNOWN',
        historical_content_continuity='UNKNOWN', owner_decision_sha256=OWNER_SHA,
        serial_revision_sha256=REVISION_SHA, hb2_evidence_sha256=base['hb2_evidence_sha256'],
        rp2_evidence_sha256=base['rp2_evidence_sha256'],
        historical_activation_sha256=sha(history.c.canonical(historical)),
        startup_evidence_sha256=sha(canonical({n: pin(b) for n, b in groups['start'].items()})),
        guest_evidence_sha256=sha(canonical({n: pin(b) for n, b in groups['guest'].items()})),
        serial_backend='null', serial_capture='NOT_CAPTURED_NULL_BACKEND')
    source = dict(schema='local-hand-q2-host-rebind-source/v1', archive=pin(raw), index=index,
        prior=base['persistent_source'], summary=previous_failure(),
        owner=OWNER_SHA, revision=REVISION_SHA, activation_sha256=sha(history.c.canonical(value)),
        baseline_sha256=sha(canonical(base)), costs=costs())
    return validate_activation(value), source, base


# GR adopts only the retained successful start. Its new guest result never
# replaces HR's failed guest bytes or changes the meaning of the old formats.
GR_A = '54036654c399cdab0386a65f53f06283c2a92032'
GR_C = '5692d8c532815d7f741c0f9dc040c4a5a3198058'
GR_SCOPE = 'LH-Q2-CORE-GUEST-RESUMPTION-v1'
GR_EVENT = 'LH-Q2-CORE-GUEST-RESUMPTION-CLOSURE-20261012-01'
GR_OWNER_SHA = '06f6b8c9542a48e360664258d4b4c22e4594c6947d6f2cc543eec5885606a1b9'
GR_GUEST_SESSION = 'lhqguest-20261012a'
HR_FREEZE_SHA = '0d5bb5140b7687dd77714a0ce1f5f30f956e431aadce702e9bc1ab6ba2305d98'
HR_TERMINAL_SHA = 'b602284213c57f1e3a140dff0cfb3b60661d79ba4eadb83ac866722a8182141b'
HR_FAILED_INDEX_SHA = '7ba15c2645a8ed6d9991189f42a950a086f435815d740ff4314678f86defdc5e'
GUEST_SOURCE_PIN = dict(bytes=6674, sha256='fe7591911150090d33db9f2e007da8b3e5aae404d795462161e2435c08b524db')
GR_BASE_MEMBERS = (*BASE_MEMBERS, 'hr1-freeze.json',
    *('start/' + n for n in START_FILES), *('failed-guest/' + n for n in GUEST_FILES),
    'failed-guest/index.json', 'failed-guest/terminal.json', 'continuation-owner.json')
GR_FINAL_MEMBERS = (*GR_BASE_MEMBERS, 'continuation-freeze.json',
                    *('guest/' + n for n in GUEST_FILES))
REPAIR_FILES = ('record.json', 'identity.json', 'request.json', 'completion.json',
                'guest.stdout', 'guest.stderr', 'pid-stat.raw', 'pid-cmdline.raw', 'pidfile.raw')
REPAIR_MEMBERS = (*GR_BASE_MEMBERS, 'continuation-freeze.json',
                  *('repair/' + n for n in REPAIR_FILES))
GR_EXTRA_FIELDS = frozenset(('continuation_owner_sha256', 'previous_guest_failure_sha256'))


def gr_authority():
    return dict(R=R, A=GR_A, C=GR_C, owner=GR_OWNER_SHA)


def gr_costs():
    return dict(old_mib=27497, old_inodes=8214, preparation_mib=4, preparation_inodes=128,
        guest_mib=2, guest_inodes=64, total_mib=27503, total_inodes=8406,
        maintenance_admission_mib=27375, maintenance_admission_inodes=8374,
        maintenance_obligations=19, core_capture_counted_once=True, refunded=False)


def guest_failure_summary():
    return dict(session=GUEST_SESSION, D='0b84bbcf8108522305d1e23c9378f6d0a8f50bcc',
        state='CONSUMED_FAILED_STOP_AND_RETAIN', terminal='GUEST_FAILED_STOP_AND_RETAIN',
        reason='HOST_REBIND_COMMAND_COMPLETION', stage='SSH_KEY_EXCHANGE', ssh_requests=1,
        original_count=9, caller_returncode=3, tool_returncode=3,
        ssh_child_returncode='UNKNOWN', remote_exit='UNKNOWN', guest_report=False,
        maintenance='NOT_ISSUED', core='NOT_RUN', old_commitments_refunded=False)


def gr_baseline(files, identity_raw, failure_raw):
    require(set(files) == set(GR_BASE_MEMBERS), 'GR_BASE_COVERAGE')
    for name, digest in (('hr1-freeze.json', HR_FREEZE_SHA),
            ('failed-guest/index.json', HR_FAILED_INDEX_SHA),
            ('failed-guest/terminal.json', HR_TERMINAL_SHA),
            ('continuation-owner.json', GR_OWNER_SHA)):
        require(sha(files[name]) == digest, 'GR_FROZEN_' + name)
    owner = document(files['continuation-owner.json'])
    require(owner['R'] == R and owner['A'] == GR_A and owner['scope'] == GR_SCOPE
        and owner['event'] == GR_EVENT and owner['state'] == 'APPROVED'
        and owner['previous_hr1_freeze_sha256'] == HR_FREEZE_SHA
        and owner['previous_terminal_sha256'] == HR_TERMINAL_SHA, 'GR_OWNER')
    base = baseline({n: files[n] for n in BASE_MEMBERS}, identity_raw, failure_raw)
    old = document(files['hr1-freeze.json'])
    require(old['schema'] == 'lhq-host-rebind-freeze/v1' and
        old['state'] == 'FROZEN_HR1_VERIFIED' and old['authority'] ==
        dict(R=R, A=A, C=C, owner=OWNER_SHA, revision=REVISION_SHA)
        and old['baseline_sha256'] == sha(canonical(base))
        and old['costs'] == costs() and old['limits'] == limits()
        and old['baseline_files'] == {n: pin(files[n]) for n in BASE_MEMBERS}
        and old['external'] == dict(identity=pin(identity_raw), failure=pin(failure_raw)), 'GR_OLD_FREEZE')
    start = {n: files['start/' + n] for n in START_FILES}
    start_request, started, vm = verify_start(start, base, old)
    failed = {n: files['failed-guest/' + n] for n in GUEST_FILES}
    index = document(files['failed-guest/index.json'])
    require(index == dict(actual={n: pin(b) for n, b in failed.items()}, missing=[], phase='guest'),
            'GR_FAILURE_INDEX')
    bound = binding(failed['request.json'])
    request = document(failed['request.json'])
    require(bound['session'] == GUEST_SESSION and bound['implementation'] == old['implementation']
        == start_request['implementation'] and old['requests']['guest'] == pin(failed['request.json'])
        and request['baseline_sha256'] == sha(canonical(base)), 'GR_FAILURE_REQUEST')
    result = document(failed['result.json']); caller = document(failed['caller-completion.json'])
    tool = document(failed['tool-completion.json']); terminal = document(files['failed-guest/terminal.json'])
    require(document(failed['started.json']) == dict(binding=bound, startup=pin(start['result.json']))
        and result['binding'] == bound and result['startup'] == pin(start['result.json'])
        and result['state'] == 'STOP_AND_RETAIN'
        and result['errors'] == [dict(type='RebindError', reason='HOST_REBIND_COMMAND_COMPLETION')]
        and result['error']['reason'] == 'HOST_REBIND_COMMAND_COMPLETION'
        and result['ssh_calls'] == 1 and type(result['ssh_calls']) is int
        and result['host_before'] == base['host'] and result['vm_before'] == started['process']
        and 'command' not in result and 'guest_boot_id' not in result, 'GR_FAILURE_RESULT')
    for key in ('startup_calls', 'package_install_calls', 'module_load_calls', 'retries'):
        require(type(result[key]) is int and result[key] == 0, 'GR_FAILURE_COUNTS')
    image_transition(started['images_after'], result['images_before'], base['owner_uid'])
    require(failed['guest.stdout'] == b'' and failed['caller.stderr'] == b''
        and b'kex_exchange_identification: read: Connection reset by peer' in failed['guest.stderr']
        and len(failed['guest.stderr']) <= 65536, 'GR_FAILURE_STREAMS')
    require(caller['binding'] == bound and type(caller['returncode']) is int and caller['returncode'] == 3
        and type(caller['invocations']) is int and caller['invocations'] == 1
        and caller['eof'] == dict(stdout=True, stderr=True)
        and all(caller[s] == pin(failed['caller.' + s]) for s in ('stdout', 'stderr'))
        and document(failed['caller.stdout']) == dict(state=result['state'], result=pin(failed['result.json']))
        and type(tool['exit_code']) is int and tool['exit_code'] == 3, 'GR_FAILURE_COMPLETION')
    require(terminal['state'] == 'GUEST_FAILED_STOP_AND_RETAIN' and terminal['phase'] == 'guest'
        and terminal['freeze'] == pin(files['hr1-freeze.json'])
        and terminal['originals_index'] == pin(files['failed-guest/index.json'])
        and terminal['caller_completion'] == caller and terminal['tool_completion'] == tool
        and terminal['retry_allowed'] is False and terminal['maintenance_consumed'] is None
        and all(terminal[n] == 'NOT_RUN' for n in ('HR4', 'H01', 'Q4', 'H11')), 'GR_TERMINAL')
    usage(result['usage'], 120); usage(caller['usage'])
    return base, old, start_request, started, vm


def verify_gr_guest(files, base, freeze, old, start, start_raw):
    request = document(files['request.json'])
    require(request['retained_freeze_sha256'] == HR_FREEZE_SHA
        and request['previous_terminal_sha256'] == HR_TERMINAL_SHA
        and request['guest_source'] == GUEST_SOURCE_PIN
        and request['nonce'] != document(old['guest_request_raw'])['nonce'], 'GR_GUEST_SOURCE')
    # Bind the complete remote program to the original source digest and six
    # command description; a request hash alone must not authorize arbitrary code.
    tokens = shlex.split(request['remote_command'])
    prefix = ['exec', '/usr/bin/sudo', '-n', '--', '/usr/bin/env', '-i', 'HOME=/root',
        'PATH=/usr/sbin:/usr/bin:/sbin:/bin', 'LANG=C', 'LC_ALL=C', '/usr/bin/python3', '-I', '-B', '-c']
    prelude = ('import resource\nfor key,value in ((resource.RLIMIT_AS,268435456),'
        '(resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CPU,120),(resource.RLIMIT_CORE,0)):\n'
        '    resource.setrlimit(key,(value,value))\n')
    require(len(tokens) == len(prefix) + 2 and tokens[:len(prefix)] == prefix
        and tokens[-2].startswith(prelude) and pin(tokens[-2][len(prelude):].encode('ascii')) == GUEST_SOURCE_PIN
        and tokens[-1] == canonical(dict(nonce=request['nonce'], package=base['package'], quota=base['quota'])).decode('ascii')
        and shlex.join(tokens) == request['remote_command'], 'GR_REMOTE_PROGRAM')
    return verify_guest(files, base, freeze, start, start_raw, resumed=True)


def validate_gr_activation(value):
    require(type(value) is dict and set(value) >= GR_EXTRA_FIELDS and len(canonical(value)) <= 4096,
            'GR_ACTIVATION_FIELDS')
    require(value['schema'] == 'local-hand-q2-vm-activation/v4' and value['event'] == GR_EVENT
        and value['continuation_owner_sha256'] == GR_OWNER_SHA
        and value['previous_guest_failure_sha256'] == HR_TERMINAL_SHA, 'GR_ACTIVATION_POLICY')
    old = {k: v for k, v in value.items() if k not in GR_EXTRA_FIELDS}
    old.update(schema='local-hand-q2-vm-activation/v3', event=EVENT)
    validate_activation(old)
    return value


def verify_boot_repair(files, base, freeze, old_start):
    """Adopt an explicitly approved repair from actual restart/read returns.

    Old startup and failed reads stay untouched. This consumes the successful
    read already made after repair instead of requiring another guest probe.
    """
    from . import q2_core_prior_attempt as history
    require(set(files) == set(REPAIR_FILES) and
            freeze['boot_repair_files'] == {n: pin(b) for n,b in files.items()}, 'REPAIR_SOURCES')
    record = document(files['record.json']); observed = document(files['identity.json'])
    request = document(files['request.json']); completed = document(files['completion.json'])
    require(record['state'] == 'REPAIRED_VM_STARTED' and record['owner_reply'] ==
            '好，选第一项，我没选错，是我想要的意思。你继续', 'REPAIR_APPROVAL')
    require(record['old_vm'] == old_start['process'] and record['host'] == base['host']
            and record['normal_guest_shutdown'] is False and record['changed_files'] ==
            ['/etc/default/grub', '/boot/grub/grub.cfg'], 'REPAIR_TARGET')
    require(set(record['backups']) == ROLES and all(
        record['backups'][n]['source'] == base['images'][n]['path'] for n in ROLES), 'REPAIR_BACKUPS')
    required = {'backup-'+n for n in ROLES} | {'backup-closed-system', 'start',
        'root-edit', 'boot-edit', 'root-readback', 'boot-readback', 'root-check', 'boot-check'}
    steps = {row['name']:row['returncode'] for row in record['steps']}
    require(required <= steps.keys() and all(type(steps[n]) is int and steps[n] == 0
            for n in required), 'REPAIR_COMPLETION')
    argv = observed['argv']; pidfile = argv[argv.index('-pidfile')+1]
    expected = startup_argv(base['original_argv'], pidfile)
    if argv[0] == '/usr/bin/qemu-system-x86_64': expected[0] = argv[0]
    require(argv == expected and record['new_argv'][1:] == argv[1:], 'REPAIR_ARGV')
    process = observed['process']
    require(all(process[k] == v for k,v in record['new_vm'].items()) and
            process['exe'] == '/usr/bin/qemu-system-x86_64' and
            process['exe_metadata'] == base['tools']['qemu'] and
            process['namespaces'] == base['host']['namespaces'] and
            observed['host'] == base['host'], 'REPAIR_PROCESS')
    vm = history._resume_process(process, argv, files['pid-stat.raw'], files['pid-cmdline.raw'])
    require((vm['pid'],vm['starttime']) != (old_start['process']['pid'],old_start['process']['starttime'])
            and files['pidfile.raw'].strip() == str(vm['pid']).encode(), 'REPAIR_NEW_PROCESS')
    image_transition(old_start['images_after'], observed['images'], base['owner_uid'])
    require(completed['vm'] == record['new_vm'] and type(completed['returncode']) is int
            and completed['returncode'] == 0 and completed['eof'] == dict(stdout=True,stderr=True)
            and completed['request_sha256'] == sha(files['request.json']) and files['guest.stderr'] == b'',
            'REPAIR_GUEST_COMPLETION')
    require(request['package'] == base['package'] and request['quota'] == base['quota']
            and request['ssh_prefix'] == base['ssh_prefix'] and
            request['guest_source'] == GUEST_SOURCE_PIN, 'REPAIR_GUEST_TARGET')
    # Validate the frozen remote program independently of its request digest.
    tokens = shlex.split(request['remote_command'])
    prefix = ['exec','/usr/bin/sudo','-n','--','/usr/bin/env','-i','HOME=/root',
        'PATH=/usr/sbin:/usr/bin:/sbin:/bin','LANG=C','LC_ALL=C','/usr/bin/python3','-I','-B','-c']
    prelude = ('import resource\nfor key,value in ((resource.RLIMIT_AS,268435456),'
        '(resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CPU,120),(resource.RLIMIT_CORE,0)):\n'
        '    resource.setrlimit(key,(value,value))\n')
    require(len(tokens) == len(prefix)+2 and tokens[:len(prefix)] == prefix and
            tokens[-2].startswith(prelude) and pin(tokens[-2][len(prelude):].encode('ascii')) == GUEST_SOURCE_PIN
            and tokens[-1] == canonical(dict(nonce=request['nonce'],package=base['package'],quota=base['quota'])).decode('ascii')
            and shlex.join(tokens) == request['remote_command'], 'REPAIR_REMOTE_PROGRAM')
    current = history.validate_current_guest(document(files['guest.stdout']),
        package=base['package'],quota=base['quota'],nonce=request['nonce'])
    require(current['boot_id'] != base['historical']['current_boot_id'], 'REPAIR_GUEST_BOOT')
    return current, vm, pidfile


def build_gr_activation(raw, identity_raw, failure_raw, *, repaired=False):
    from . import q2_core_prior_attempt as history
    files, index = read_envelope(raw, resumed=True, repaired=repaired)
    retained = {n: files[n] for n in GR_BASE_MEMBERS}
    base, old, start_request, start, vm = gr_baseline(retained, identity_raw, failure_raw)
    freeze = document(files['continuation-freeze.json'])
    require(freeze['schema'] == 'lhq-guest-resumption-freeze/v1' and freeze['state'] == 'FROZEN_GR1_VERIFIED'
        and freeze['authority'] == gr_authority() and freeze['costs'] == gr_costs()
        and freeze['limits'] == limits() and freeze['baseline_sha256'] == sha(canonical(base))
        and freeze['retained_files'] == {n: pin(b) for n, b in retained.items()}
        and freeze['external'] == dict(identity=pin(identity_raw), failure=pin(failure_raw)), 'GR_FREEZE')
    if repaired:
        guest = {n: files['repair/' + n] for n in REPAIR_FILES}
        current, vm, pidfile = verify_boot_repair(guest, base, freeze, start)
    else:
        guest = {n: files['guest/' + n] for n in GUEST_FILES}
        require(document(guest['request.json'])['implementation'] == freeze['implementation'], 'GR_D')
        old_request = dict(old, guest_request_raw=files['failed-guest/request.json'])
        current, result = verify_gr_guest(guest, base, freeze, old_request, start, files['start/result.json'])
        pidfile = start_request['pidfile']
    historical = base['historical']
    value = {k: copy.deepcopy(historical[k]) for k in history.ACTIVATION_PROJECTION_FIELDS}
    value.update(schema='local-hand-q2-vm-activation/v4', event=GR_EVENT,
        current_boot_id=current['boot_id'], host_boot_id=base['host']['boot_id'], vm=vm,
        image_identities={n: [base['images'][n]['metadata'][k] for k in ('dev', 'ino')]
                          for n in ROLES - {'original_system'}},
        original_system_identity=[base['images']['original_system']['metadata'][k] for k in ('dev', 'ino')],
        system_path=base['images']['system']['path'], pidfile=pidfile, serial=None,
        index=index, evidence_sha256=sha(canonical({n: pin(b) for n, b in files.items()})),
        baseline_policy='OWNER_ADOPTED_HB2_BASELINE', historical_filesystem_continuity='UNKNOWN',
        historical_content_continuity='UNKNOWN', owner_decision_sha256=OWNER_SHA,
        serial_revision_sha256=REVISION_SHA, hb2_evidence_sha256=base['hb2_evidence_sha256'],
        rp2_evidence_sha256=base['rp2_evidence_sha256'],
        historical_activation_sha256=sha(history.c.canonical(historical)),
        startup_evidence_sha256=sha(canonical({n: pin(b) for n,b in guest.items()})) if repaired else
            sha(canonical({n: pin(files['start/' + n]) for n in START_FILES})),
        guest_evidence_sha256=sha(canonical({n: pin(b) for n, b in guest.items()})),
        serial_backend='null', serial_capture='NOT_CAPTURED_NULL_BACKEND',
        continuation_owner_sha256=GR_OWNER_SHA, previous_guest_failure_sha256=HR_TERMINAL_SHA)
    source = dict(schema='local-hand-q2-host-rebind-source/v2', archive=pin(raw), index=index,
        prior=base['persistent_source'], summary=previous_failure(), owner=OWNER_SHA,
        revision=REVISION_SHA, activation_sha256=sha(history.c.canonical(value)),
        baseline_sha256=sha(canonical(base)), costs=gr_costs(), continuation_owner=GR_OWNER_SHA,
        previous_guest_failure=guest_failure_summary(), previous_terminal_sha256=HR_TERMINAL_SHA,
        previous_freeze_sha256=HR_FREEZE_SHA)
    history.validate_host_rebind_source(source)
    return validate_gr_activation(value), source, base


def consume_activation(raw, identity_raw, failure_raw):
    require(type(raw) is bytes and 0 < len(raw) <= 1048576, 'ENVELOPE_BOUND')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        stream = archive.extractfile('index.json')
        require(stream is not None, 'ENVELOPE_INDEX')
        with stream:
            index = document(stream.read(65537), 65536)
    if index['schema'] == 'lhq-host-rebind-envelope/v3':
        return build_gr_activation(raw, identity_raw, failure_raw, repaired=True)
    build = build_gr_activation if index['schema'] == 'lhq-host-rebind-envelope/v2' else build_activation
    return build(raw, identity_raw, failure_raw)

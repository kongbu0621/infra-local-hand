"""Administrator-only completion of a retained, never-dispatched task.

Not a restart/replay interface. The ordinary ledger owner holds the original
authority lock while root rechecks the exited controller and all execution and
management cgroups. The existing TaskSession transaction performs completion;
no manager acknowledgement, result, new budget or quota closure is invented.
Run from a verified installation/explicitly selected maintenance payload.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import ctypes
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import threading
import time

from local_hand_jobs import budget, cli, manager_binding, quota_contract as q, quota_lifecycle
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import strict_loads, validate_submit
from local_hand_jobs.deployment import verify_release
from local_hand_jobs.policy import Policy
from local_hand_jobs.registry import Registry
from local_hand_jobs.resources import AuthorityLock, verify_local_filesystem
from local_hand_jobs.state import StateStore, encoded
from local_hand_jobs.task_session import TaskSession
from admin.local_hand_quota_observer import controller_guard, q2_config
from admin.local_hand_quota_observer.protected_inputs import open_protected, read_protected
from .task_service import save

LIMIT = 2 * 1024**2
TIMEOUT = 25
UNSTARTED = {'ACCEPTED', 'ADMISSION_BOUND', 'BOOTSTRAP_ROOTS_RESERVED',
             'QUOTA_PREPARATION', 'EXECUTION_UNCERTAIN'}
UNIT_FIELDS = (*controller_guard.SHOW_FIELDS, 'ExecStartPre')
EMPTY_EXEC_FIELDS = (*controller_guard.EMPTY_EXEC_FIELDS, 'ExecStartPre')


def load(path):
    # Administrative launch declarations nest more deeply than client requests.
    return q._load(read_protected(str(path), LIMIT), LIMIT, 32)


def same(left, right):
    return encoded(left) == encoded(right)


def retained(current_path, operation, digest, serial):
    """Use the original dynamic controller pin, never a newly observed identity."""
    current = load(current_path)
    request = validate_submit(current['request'])
    q.require(current['operation_id'] == request['operation_id'] == operation
              and request['request_digest'] == digest and type(current['serial']) is int
              and current['serial'] == serial and current['state'] == 'READY', 'RECOVERY_TASK_IDENTITY')
    static = load(current['launch_path'])
    q.require(same(static['request'], request) and static['principal_id'] == current['principal_id'],
              'RECOVERY_REQUEST_CHANGED')
    output = Path(current['output'])
    intent = load(output / 'launch-intent.json')
    q.require(intent['operation_id'] == operation and type(intent['command']) is list
              and len(intent['command']) >= 2, 'RECOVERY_LAUNCH_INTENT')
    dynamic = Path(intent['command'][-1])
    q.require(intent['command'][-2] == current['launch_path'] and dynamic.parent == output
              and dynamic.name.startswith('controller-') and dynamic.suffix == '.json',
              'RECOVERY_CONTROLLER_RECORD')
    launch = load(dynamic)
    # Only the original controller adds these five runtime fields.
    normalized = q._load(encoded(launch).encode(), LIMIT, 32)
    envelope = normalized['controller_envelope']
    for key in ('invocation_id', 'cgroup_device', 'cgroup_inode'):
        envelope['controller'].pop(key)
    for key in ('issued_ns', 'deadline_ns'):
        envelope.pop(key)
    q.require(same(normalized, static), 'RECOVERY_DYNAMIC_CHANGED')
    finished = load(output / 'finished.json')
    q.require(type(finished.get('returncode')) is int and finished['streams_eof'] is True,
              'RECOVERY_CONTROLLER_EOF')
    spec = controller_guard.decode_controller(launch['controller_envelope']['controller'])
    binding = manager_binding.from_configuration(launch['policy']['process_manager'],
                                                authority_id=launch['policy']['authority_id'])
    q.require(binding is not None and current['boot_id'] == binding['boot_id'], 'RECOVERY_BOOT_BINDING')
    manager = load(Path(launch['intents']['path']) / 'manager-final.json')
    q.require(manager['schema'] == 'local-hand-q2-system-manager/v1'
              and same(manager['manager_binding'], binding) and manager['stages'] == []
              and manager['pending_control'] is None and manager['closed_phases'] == [],
              'RECOVERY_MANAGER_NOT_EMPTY')
    return dict(current=current, launch=launch, intent=intent, finished=finished, manager=manager,
                dynamic=str(dynamic), controller=spec.__dict__)


def controller_stopped(values, spec):
    q.require(set(values) == set(UNIT_FIELDS), 'RECOVERY_UNIT_FIELDS')
    q.require(values['Id'] == spec['unit'] and values['LoadState'] == 'loaded'
              and values['InvocationID'] == spec['invocation_id']
              and values['ActiveState'] in ('inactive', 'failed')
              and values['SubState'] in ('dead', 'failed')
              and values['MainPID'] == values['ControlPID'] == '0'
              and values['Job'] in ('', '0') and values['ControlGroup'] in ('', spec['cgroup']),
              'RECOVERY_CONTROLLER_NOT_EXITED')
    required = dict(Restart='no', RestartForceExitStatus='', TriggeredBy='', OnFailure='', OnSuccess='',
                    ExecStartPre='', ExecStartPost='', ExecStop='', ExecStopPost='', ExecReload='',
                    KillMode='control-group', ExitType='cgroup', Type='exec', RemainAfterExit='no')
    q.require(all(values[key] == value for key, value in required.items()), 'RECOVERY_CONTROLLER_RESTARTABLE')


def observe(snapshot):
    launch, spec = snapshot['launch'], snapshot['controller']
    binding = launch['policy']['process_manager']['manager_binding']
    q.require(budget.current_clock()['boot_id'] == binding['boot_id'], 'RECOVERY_BOOT_CHANGED')
    namespace = launch['chain']['installation']['initial_userns']
    for path in ('/proc/self/ns/user', '/proc/1/ns/user'):
        info = os.stat(path)
        q.require(namespace == dict(device=info.st_dev, inode=info.st_ino), 'RECOVERY_USER_NAMESPACE')
    program = launch['chain']['installation']['programs']['systemctl']
    os.close(q2_config.executable(program))
    run = subprocess.run([program['path'], 'show', '--no-pager', '--all',
        '--property=' + ','.join(UNIT_FIELDS), '--', spec['unit']], timeout=5,
        capture_output=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'SYSTEMD_PAGER': ''})
    q.require(run.returncode == 0 and len(run.stdout) <= 32768 and len(run.stderr) <= 4096,
              'RECOVERY_UNIT_QUERY')
    rows = [line.split('=', 1) for line in run.stdout.decode('utf-8', 'strict').splitlines()]
    q.require(all(len(row) == 2 for row in rows) and len({row[0] for row in rows}) == len(rows),
              'RECOVERY_UNIT_PROPERTIES')
    values = dict(rows)
    # systemctl omits empty Exec* arrays even with --all. Normalize only these
    # known array properties; missing scalar identities remain unproven.
    for key in EMPTY_EXEC_FIELDS:
        values.setdefault(key, '')
    controller_stopped(values, spec)
    controller_pin = dict(path=spec['cgroup'], device=spec['cgroup_device'], inode=spec['cgroup_inode'])
    try:
        _, empty = quota_lifecycle.parent('/sys/fs/cgroup' + spec['cgroup'], controller_pin)
    except FileNotFoundError:
        # systemd may have removed the original empty cgroup after exit. An
        # absent child is acceptable only under its real, protected cgroup2 parent.
        parent = str(Path(spec['cgroup']).parent)
        try:
            os.lstat('/sys/fs/cgroup' + spec['cgroup'])
        except FileNotFoundError:
            pass
        else:
            q.require(False, 'RECOVERY_CONTROLLER_CGROUP_UNREADABLE')
        fd = open_protected('/sys/fs/cgroup' + parent, directory=True)
        os.close(fd)
        quota_lifecycle.parent('/sys/fs/cgroup' + parent)
        q.require(values['ControlGroup'] == '', 'RECOVERY_CONTROLLER_CGROUP_MISSING')
    else:
        q.require(empty, 'RECOVERY_CONTROLLER_TREE_BUSY')
    pins = [binding['parent']]
    for phase in launch['chain']['phases'].values():
        pins.extend(phase['grant'][key] for key in ('query_parent', 'management_parent'))
    for pin in pins:
        fd = open_protected('/sys/fs/cgroup' + pin['path'], directory=True)
        os.close(fd)
        _, empty = quota_lifecycle.parent('/sys/fs/cgroup' + pin['path'], pin)
        q.require(empty, 'RECOVERY_EXECUTION_OR_MANAGEMENT_BUSY')
    q.require(budget.current_clock()['boot_id'] == binding['boot_id'], 'RECOVERY_BOOT_CHANGED')
    return dict(controller=values, parents=pins, boot_id=binding['boot_id'])


def check_row(broker, launch):
    """Strictly this pre-dispatch case; missing execution flags are unknown."""
    identity = launch['request']['operation_id']
    with broker.state.transaction() as tx:
        rows = broker.state.all(tx)
        q.require(len(rows) == 1, 'RECOVERY_LEDGER_SCOPE')
        row = rows[0]
        q.require(row['namespace'] == 'job' and row['id'] == row['parent'] == identity
                  and row['digest'] == launch['request']['request_digest']
                  and row['principal'] == launch['principal_id'] and same(row['request'], launch['request']),
                  'RECOVERY_LEDGER_IDENTITY')
        record = row['record']
        q.require(type(record.get('handles')) is dict and not record['handles']
                  and record.get('delivery_intents', []) == []
                  and record.get('business_started') is False and record.get('helper_started') is False
                  and record.get('cancel_requested') is False, 'RECOVERY_DISPATCH_UNCERTAIN')
        q.require(record.get('evidence') == 'STAGING', 'RECOVERY_EVIDENCE_CONFLICT')
        events = list(tx.execute("SELECT seq,kind,data_json FROM events WHERE namespace='job' AND id=? ORDER BY seq",
                                 (identity,)))
        q.require(events and type(record.get('event_seq')) is int
                  and record['event_seq'] == events[-1]['seq'], 'RECOVERY_EVENT_SEQUENCE')
        kinds = [r['kind'] for r in events]
        q.require(kinds and kinds[0] == 'ACCEPTED' and kinds.count('ACCEPTED') == 1
                  and set(kinds) <= UNSTARTED | {'RECOVERED_BEFORE_START'}, 'RECOVERY_HISTORY_UNCERTAIN')
        done = record['lifecycle'] == 'TERMINAL'
        if done:
            expected = dict(lifecycle='TERMINAL', phase='EXITED', outcome='UNKNOWN', recovered=True,
                            execution_resources_released=True, side_effects='NONE', artifacts_retained=True,
                            exit_proof=dict(future_start_blocked=True, tree_exited=True, effects_checked=True))
            q.require(same({key: record.get(key) for key in expected}, expected)
                      and kinds[-1] == 'RECOVERED_BEFORE_START' and kinds.count('RECOVERED_BEFORE_START') == 1
                      and not tx.execute('SELECT 1 FROM leases WHERE owner=?', (identity,)).fetchone(),
                      'RECOVERY_TERMINAL_MISMATCH')
            changes = q._load(events[-1]['data_json'].encode(), LIMIT, 32)
            q.require(type(changes) is dict and same({key: changes.get(key) for key in expected}, expected)
                      and all(key in record and same(record[key], value) for key, value in changes.items()),
                      'RECOVERY_COMPLETION_EVENT_MISMATCH')
        else:
            q.require(record['lifecycle'] == 'RECONCILE_REQUIRED' and record['phase'] == 'QUEUED'
                      and record['outcome'] == 'UNKNOWN' and record.get('exit_proof') is None
                      and record.get('side_effects') == 'UNOBSERVED'
                      and (record.get('execution_resources_released') is None
                           or record.get('execution_resources_released') is False)
                      and 'RECOVERED_BEFORE_START' not in kinds,
                      'RECOVERY_NOT_UNSTARTED')
        return done


def complete(broker, launch):
    """Only called under the authority lock AFTER the root quiescence reply."""
    if check_row(broker, launch):
        return 'ALREADY_COMPLETED'
    session = TaskSession(dict(mode='recover', operation_id=launch['request']['operation_id']), None, None)
    session.broker = broker
    # Reuse release semantics, immutable dispatch-history checks and the atomic
    # event+lease transaction. No tick/recover/start or mock manager is used.
    session._finish_unstarted_recovery()
    q.require(check_row(broker, launch), 'RECOVERY_COMPLETION_UNPROVEN')
    return 'RECOVERED_BEFORE_START'


def drop_privileges(uid, gid, channel_fd):
    # A freshly forked, single-threaded worker inherits code, not root file
    # access. No exec/search path, supplementary group or capability survives.
    for name in os.listdir('/proc/self/fd'):
        fd = int(name)
        if fd == channel_fd:
            continue
        try:
            os.close(fd)
        except OSError:
            pass
    libc = ctypes.CDLL(None, use_errno=True)
    maximum = int(Path('/proc/sys/kernel/cap_last_cap').read_text())
    q.require(0 <= maximum <= 255, 'RECOVERY_CAPABILITY_RANGE')
    for cap in range(maximum + 1):
        q.require(libc.prctl(24, cap, 0, 0, 0) == 0, 'RECOVERY_CAPABILITY_DROP')  # PR_CAPBSET_DROP
    q.require(libc.prctl(38, 1, 0, 0, 0) == 0, 'RECOVERY_NO_NEW_PRIVILEGES')
    os.setgroups([])
    os.setresgid(gid, gid, gid)
    os.setresuid(uid, uid, uid)
    os.chdir('/')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines())
    q.require(os.getresuid() == (uid,) * 3 and os.getresgid() == (gid,) * 3 and not os.getgroups()
              and status['NoNewPrivs'].strip() == '1' and all(int(status[k], 16) == 0 for k in
              ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')), 'RECOVERY_WORKER_PRIVILEGES')


def worker(channel, launch, apply, end):
    policy = Policy(launch['policy'])
    verify_local_filesystem(policy.broker_root)
    verify_local_filesystem(policy.authority_root)
    anchor = Path(policy.authority_root) / 'authority.json'
    # AuthorityLock checks exact registration bytes, owner, mode and stable inode.
    fd = os.open(anchor, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        registration = strict_loads(os.read(fd, 8193))
    finally:
        os.close(fd)
    with ExitStack() as stack:
        stack.enter_context(AuthorityLock(anchor, authority_id=policy.authority_id,
            ledger_id=registration['ledger_id'], state_root=policy.broker_root))
        state = StateStore(Path(policy.broker_root) / 'jobs.sqlite', policy.authority_id,
                           registration['ledger_id'], read_only=not apply)
        stack.callback(state.close)
        broker = Broker(state, policy, Registry(), None, quota_required=True)
        stack.callback(broker.close)
        check_row(broker, launch)
        cli._send_frame(channel, {'locked': True}, deadline=end, limit=4096)
        reply = strict_loads(cli._read_frame(channel, 4096, deadline=end))
        q.require(reply == {'quiescent': True}, 'RECOVERY_ROOT_REPLY')
        q.require(time.monotonic() < end, 'RECOVERY_WINDOW_EXPIRED')
        result = complete(broker, launch) if apply else 'CHECKED_ONLY'
    cli._send_frame(channel, {'result': result}, deadline=end, limit=4096)


def wait_worker(pid, end):
    while time.monotonic() < end:
        waited, status = os.waitpid(pid, os.WNOHANG)
        if waited:
            return os.waitstatus_to_exitcode(status)
        time.sleep(.01)
    return None


def reap_worker(pid):
    # run() requires default SIGCHLD handling and a single thread, so nothing
    # else reaps this child between wait and signal. ECHILD is not permission
    # to act on a possibly reused PID.
    try:
        waited, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return
    if not waited:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # It may have exited between wait and signal; still reap it.
        os.waitpid(pid, 0)


def run(current, operation, digest, serial, archive_parent, *, apply=False):
    q.require(os.getuid() == os.geteuid() == 0, 'RECOVERY_ADMINISTRATOR')
    q.require(threading.active_count() == 1, 'RECOVERY_SINGLE_THREADED_ENTRY')
    # Ignored SIGCHLD auto-reaps children; a caller's handler can reap between
    # waitpid and kill. Refuse both before any host access or ledger writes.
    q.require(signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL, 'RECOVERY_CHILD_REAP_POLICY')
    snapshot = retained(current, operation, digest, serial)
    launch = snapshot['launch']
    policy = Policy(launch['policy'])
    verify_release(expected_source_commit=policy.source_commit,
        expected_payload_digest=policy.installed_payload_digest,
        expected_entrypoint=policy.execution_entrypoint,
        actual_entrypoint=Path(cli.__file__))
    fd = open_protected(str(archive_parent), directory=True)
    os.close(fd)
    archive = Path(tempfile.mkdtemp(prefix='lh-unstarted-recovery-', dir=archive_parent))
    print('PRIVATE_ARCHIVE ' + str(archive), flush=True)
    directory = parent = child = pid = None
    primary = None
    end = time.monotonic() + TIMEOUT
    try:
        directory = os.open(archive, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        parent, child = socket.socketpair()
        save(directory, 'before.json', snapshot)
        pid = os.fork()
        if pid == 0:
            try:
                parent.close()
                config = launch['policy']['process_manager']
                drop_privileges(config['uid'], config['gid'], child.fileno())
                worker(child, launch, apply, end)
            except BaseException as error:
                try:
                    cli._send_frame(child, {'error': type(error).__name__,
                        'code': getattr(error, 'code', None), 'errno': getattr(error, 'errno', None)},
                        deadline=end, limit=4096)
                except BaseException:
                    pass
                os._exit(1)
            os._exit(0)
        child.close()
        ready = strict_loads(cli._read_frame(parent, 4096, deadline=end))
        save(directory, 'worker-ready.json', ready)
        q.require(ready == {'locked': True}, 'RECOVERY_WORKER_NOT_LOCKED')
        before = observe(snapshot)
        q.require(same(retained(current, operation, digest, serial), snapshot), 'RECOVERY_INPUTS_CHANGED')
        after = observe(snapshot)
        q.require(same(before, after), 'RECOVERY_OS_CHANGED')
        save(directory, 'quiescence.json', after)
        cli._send_frame(parent, {'quiescent': True}, deadline=end, limit=4096)
        result = strict_loads(cli._read_frame(parent, 4096, deadline=end))
        save(directory, 'worker-reply.json', result)
        q.require(result.get('result') in ({'RECOVERED_BEFORE_START', 'ALREADY_COMPLETED'} if apply
                                         else {'CHECKED_ONLY'}), 'RECOVERY_WORKER_RESULT')
        exit_code = wait_worker(pid, end)
        if exit_code is not None:
            pid = None  # Reaped: never signal a potentially reused PID.
        q.require(exit_code == 0, 'RECOVERY_WORKER_EXIT')
        save(directory, 'result.json', result)
    except BaseException as error:
        primary = error
        try:
            if directory is not None:
                save(directory, 'failure.json', dict(error_type=type(error).__name__,
                     code=getattr(error, 'code', None), errno=getattr(error, 'errno', None),
                     state='UNCONFIRMED', action='Inspect the same operation; do not submit another task'))
        except BaseException:
            pass  # Keep the original failure; commit may already have happened.
        raise
    finally:
        cleanup = []
        if pid is not None:
            cleanup.append(('worker', lambda: reap_worker(pid)))
        for label, channel in (('parent channel', parent), ('child channel', child)):
            if channel is not None:
                cleanup.append((label, channel.close))
        if directory is not None:
            cleanup.append(('archive', lambda: os.close(directory)))
        failures = []
        for label, action in cleanup:
            try:
                action()
            except BaseException as error:
                failures.append((label, error))
        if failures:
            failure = primary if primary is not None else failures[0][1]
            for label, error in failures:
                failure.add_note('Recovery cleanup ' + label + ': ' + type(error).__name__)
            if primary is None:
                raise failure
    print('FINAL ' + result['result'] + ' (no replay, business success or deployment acceptance)', flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', required=True, type=Path)
    parser.add_argument('--operation-id', required=True)
    parser.add_argument('--request-digest', required=True)
    parser.add_argument('--serial', required=True, type=int)
    parser.add_argument('--archive-parent', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    run(args.current, args.operation_id, args.request_digest, args.serial, args.archive_parent, apply=args.apply)


if __name__ == '__main__':
    main()

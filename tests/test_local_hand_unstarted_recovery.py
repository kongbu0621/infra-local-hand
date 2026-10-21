"""Real ledger completion and modeled OS admission; not live GX10 recovery."""
import copy
import errno
import os
from pathlib import Path
import socket
import sqlite3
import stat
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

if not sys.platform.startswith('linux'):
    raise unittest.SkipTest('Linux administrator recovery')

from admin.local_hand_system_manager import unstarted_recovery as recovery
from local_hand_jobs import cli, quota_contract as q
from local_hand_jobs.contract import strict_loads, JobError
from local_hand_jobs.resources import AuthorityLock
from local_hand_jobs.state import encoded
import test_local_hand_jobs_quota_resident_chain as fixtures


class LedgerCompletionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ResidentChainTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.broker = self.fixture.broker
        self.fixture.prepare('preflight')
        self.identity = self.fixture.identity
        with self.broker.state.transaction() as tx:
            self.broker.state.update(tx, 'job', self.identity, 'EXECUTION_UNCERTAIN', {
                'lifecycle': 'RECONCILE_REQUIRED', 'outcome': 'UNKNOWN'})
        self.launch = dict(request=copy.deepcopy(self.fixture.f.request),
                           principal_id=self.fixture.f.owner.principal_id)

    def snapshot(self):
        with self.broker.state.transaction() as tx:
            return {table: [tuple(row) for row in tx.execute('SELECT * FROM ' + table)]
                    for table in ('operations', 'events', 'leases', 'revocations', 'counters')}

    def mutate(self, changes):
        with self.broker.state.transaction() as tx:
            row = self.broker.state.get('job', self.identity, tx)
            row['record'].update(changes)
            tx.execute('UPDATE operations SET record_json=? WHERE id=?', (encoded(row['record']), self.identity))

    def test_original_five_event_case_completes_once_and_preserves_history(self):
        original = self.broker.state.get('job', self.identity)
        before = self.snapshot()
        self.assertEqual(5, len(before['events']))
        with patch.object(self.broker, '_start', side_effect=AssertionError('replay')):
            self.assertEqual('RECOVERED_BEFORE_START', recovery.complete(self.broker, self.launch))
            after = self.snapshot()
            self.assertEqual('ALREADY_COMPLETED', recovery.complete(self.broker, self.launch))
            self.assertEqual(after, self.snapshot())
        current = self.broker.state.get('job', self.identity)
        for key in ('id', 'request', 'digest', 'principal', 'plan', 'reserved_bytes'):
            self.assertEqual(original[key], current[key])
        for key in ('execution_budget', 'bootstrap_grants', 'quota_preparations', 'quota_bindings', 'gaps'):
            if key != 'gaps':
                self.assertEqual(original['record'].get(key), current['record'].get(key))
        self.assertEqual(before['events'], after['events'][:-1])
        self.assertEqual([lease for lease in before['leases'] if lease[1] != self.identity], after['leases'])
        self.assertEqual('UNKNOWN', current['record']['outcome'])
        self.assertEqual('STAGING', current['record']['evidence'])
        self.assertEqual([], self.fixture.runner.starts)

    def test_identity_mismatch_leaves_every_table_unchanged(self):
        for target, key, value in (('request', 'request_digest', 'f'*64),
                                   ('request', 'operation_id', '00000000-0000-4000-8000-000000000000'),
                                   ('request', 'inputs', {'new': True}), (None, 'principal_id', 'another')):
            launch = copy.deepcopy(self.launch)
            (launch if target is None else launch[target])[key] = value
            before = self.snapshot()
            with self.subTest(key=key), self.assertRaises(ValueError):
                recovery.complete(self.broker, launch)
            self.assertEqual(before, self.snapshot())

    def test_dispatch_unknown_and_incompatible_states_fail_closed(self):
        for key, value in [('handles', {'preflight': {}}), ('handles', []), ('handles', None),
                           ('delivery_intents', None), ('delivery_intents', {}),
                           ('delivery_intents', ['issued']), ('business_started', True),
                           ('business_started', None), ('business_started', 0),
                           ('helper_started', True), ('helper_started', None),
                           ('cancel_requested', True), ('phase', 'PREFLIGHT'),
                           ('outcome', 'SUCCEEDED'), ('exit_proof', {}), ('evidence', 'SEALED'),
                           ('side_effects', 'OBSERVED'), ('execution_resources_released', 0)]:
            old = self.broker.state.get('job', self.identity)['record']
            self.mutate({key: value})
            before = self.snapshot()
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                recovery.complete(self.broker, self.launch)
            self.assertEqual(before, self.snapshot())
            with self.broker.state.transaction() as tx:
                tx.execute('UPDATE operations SET record_json=? WHERE id=?', (encoded(old), self.identity))

    def test_persisted_intent_cannot_be_erased_by_clearing_handles(self):
        for kind in ('EXECUTION_INTENT', 'LAUNCH_ENQUEUED', 'MANAGER_DELIVERY_INTENT', 'UNRECOGNIZED'):
            case = LedgerCompletionTests()
            case.setUp(); self.addCleanup(case.doCleanups)
            with case.broker.state.transaction() as tx:
                case.broker.state.update(tx, 'job', case.identity, kind, {})
            before = case.snapshot()
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'RECOVERY_HISTORY_UNCERTAIN'):
                recovery.complete(case.broker, case.launch)
            self.assertEqual(before, case.snapshot())

    def test_release_or_event_failure_rolls_back(self):
        before = self.snapshot()
        with patch.object(self.broker.state, 'update', side_effect=ValueError('publication failure')):
            with self.assertRaises(ValueError):
                recovery.complete(self.broker, self.launch)
        self.assertEqual(before, self.snapshot())
        with patch.object(self.broker, '_release'):
            with self.assertRaises(JobError):
                recovery.complete(self.broker, self.launch)
        self.assertEqual(before, self.snapshot())

    def test_write_contention_does_not_consume_completion(self):
        before = self.snapshot()
        connection = sqlite3.connect(self.broker.state.path, isolation_level=None)
        try:
            connection.execute('BEGIN IMMEDIATE')
            with self.assertRaises(JobError):
                recovery.complete(self.broker, self.launch)
            connection.execute('ROLLBACK')
        finally:
            connection.close()
        self.assertEqual(before, self.snapshot())
        self.assertEqual('RECOVERED_BEFORE_START', recovery.complete(self.broker, self.launch))

    def test_abrupt_worker_exit_keeps_completion_atomic(self):
        # An abrupt process exit runs no Python rollback/finally callbacks.
        # Exercise actual SQLite recovery, not an injected exception rollback.
        for boundary, expected_exit in (('after_release', 70), ('after_event', 71), ('after_commit', 72)):
            with self.subTest(boundary=boundary):
                case = LedgerCompletionTests()
                case.setUp(); self.addCleanup(case.doCleanups)
                before = case.snapshot()
                self.assertTrue(any(lease[1] == case.identity for lease in before['leases']))
                state = case.broker.state
                registration = dict(authority_id=state.authority_id, ledger_id=state.ledger_id,
                                    state_root=str(state.path.parent))
                anchor = Path(case.fixture.f.temp.name) / 'authority.json'
                anchor.write_text(encoded(registration)); anchor.chmod(0o600)
                # Do not carry an open SQLite connection across fork.
                state.close()
                pid = None
                try:
                    pid = os.fork()
                    if pid == 0:
                        try:
                            child_state = recovery.StateStore(state.path, state.authority_id, state.ledger_id)
                            case.broker.state = child_state
                            original_update = child_state.update
                            def interrupted_update(tx, namespace, identity, event, changes):
                                if event != 'RECOVERED_BEFORE_START':
                                    raise AssertionError('Unexpected completion event')
                                if tx.execute('SELECT 1 FROM leases WHERE owner=?', (identity,)).fetchone():
                                    raise AssertionError('Execution lease was not removed inside transaction')
                                if boundary == 'after_release':
                                    os._exit(expected_exit)
                                value = original_update(tx, namespace, identity, event, changes)
                                if boundary == 'after_event':
                                    os._exit(expected_exit)
                                return value
                            with AuthorityLock(anchor, **registration), \
                                 patch.object(child_state, 'update', side_effect=interrupted_update):
                                if recovery.complete(case.broker, case.launch) != 'RECOVERED_BEFORE_START':
                                    raise AssertionError('Unexpected completion result')
                                if case.fixture.runner.starts:
                                    raise AssertionError('Unexpected execution')
                                os._exit(expected_exit)
                        except BaseException:
                            os._exit(99)  # Must not be mistaken for the selected interruption point.
                    exit_code = recovery.wait_worker(pid, time.monotonic() + 10)
                    if exit_code is not None:
                        pid = None
                    self.assertEqual(expected_exit, exit_code)
                finally:
                    if pid is not None:
                        recovery.reap_worker(pid)
                    case.broker.state = recovery.StateStore(state.path, state.authority_id, state.ledger_id)
                    self.addCleanup(case.broker.state.close)
                after = case.snapshot()
                with AuthorityLock(anchor, **registration):
                    if boundary != 'after_commit':
                        self.assertEqual(before, after)
                        self.assertEqual('RECOVERED_BEFORE_START', recovery.complete(case.broker, case.launch))
                        after = case.snapshot()
                    self.assertEqual(before['events'], after['events'][:-1])
                    self.assertEqual([lease for lease in before['leases'] if lease[1] != case.identity],
                                     after['leases'])
                    self.assertEqual('ALREADY_COMPLETED', recovery.complete(case.broker, case.launch))
                    self.assertEqual(after, case.snapshot())

    def test_terminal_without_original_completion_is_not_accepted(self):
        self.mutate({'lifecycle': 'TERMINAL', 'phase': 'EXITED', 'outcome': 'UNKNOWN'})
        before = self.snapshot()
        with self.assertRaises(ValueError):
            recovery.complete(self.broker, self.launch)
        self.assertEqual(before, self.snapshot())

    def test_completed_record_must_match_typed_original_event(self):
        recovery.complete(self.broker, self.launch)
        original = self.broker.state.get('job', self.identity)['record']
        variants = [dict(exit_proof=dict(original['exit_proof'], tree_exited=1)),
                    dict(artifacts_retained=False), dict(gaps=[]),
                    dict(event_seq=original['event_seq'] - 1),
                    dict(event_seq=float(original['event_seq']))]
        for changes in variants:
            self.mutate(changes)
            before = self.snapshot()
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                recovery.complete(self.broker, self.launch)
            self.assertEqual(before, self.snapshot())
            with self.broker.state.transaction() as tx:
                tx.execute('UPDATE operations SET record_json=? WHERE id=?', (encoded(original), self.identity))

    def test_pending_record_must_match_latest_event_sequence(self):
        self.mutate({'event_seq': 0})
        before = self.snapshot()
        with self.assertRaises(ValueError):
            recovery.complete(self.broker, self.launch)
        self.assertEqual(before, self.snapshot())


class ControllerAdmissionTests(unittest.TestCase):
    def values(self):
        spec = dict(unit='lhqsynthetic.service', invocation_id='a'*32, cgroup='/synthetic.slice/lhqsynthetic.service')
        values = dict.fromkeys(recovery.UNIT_FIELDS, '')
        values.update(Id=spec['unit'], InvocationID=spec['invocation_id'], LoadState='loaded',
                      ActiveState='failed', SubState='failed', MainPID='0', ControlPID='0', Restart='no',
                      KillMode='control-group', ExitType='cgroup', Type='exec', RemainAfterExit='no')
        return spec, values

    def test_exited_original_is_accepted(self):
        spec, values = self.values()
        recovery.controller_stopped(values, spec)
        values.update(ActiveState='inactive', SubState='dead', ControlGroup=spec['cgroup'])
        recovery.controller_stopped(values, spec)

    def test_identity_liveness_and_future_activation_are_required(self):
        for key, value in [('InvocationID', 'b'*32), ('LoadState', 'not-found'), ('ActiveState', 'active'),
                           ('MainPID', '20'), ('ControlPID', '20'), ('Job', '20'),
                           ('Restart', 'on-failure'), ('TriggeredBy', 'a.timer'), ('ExecStartPre', '/bin/true'),
                           ('ExecStopPost', '/bin/true'), ('OnSuccess', 'a.service'), ('ExitType', 'main'),
                           ('ControlGroup', '/wrong'), ('SubState', 'running')]:
            spec, values = self.values()
            values[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                recovery.controller_stopped(values, spec)

    def observation_case(self):
        spec, values = self.values()
        spec.update(cgroup_device=10, cgroup_inode=20)
        pin = dict(path='/synthetic.slice/synthetic-ordinary.slice', device=10, inode=30)
        binding = dict(boot_id='synthetic-boot', parent=pin)
        namespace = os.stat('/proc/self/ns/user')
        launch = dict(policy=dict(process_manager=dict(manager_binding=binding)), chain=dict(
            installation=dict(initial_userns=dict(device=namespace.st_dev, inode=namespace.st_ino),
                              programs=dict(systemctl=dict(path='/synthetic/systemctl'))),
            phases={name: dict(grant=dict(query_parent=dict(pin, inode=31, path='/query.slice'),
                                          management_parent=dict(pin, inode=32, path='/management.slice')))
                    for name in ('preflight', 'business', 'evidence')}))
        snapshot = dict(launch=launch, controller=spec)
        run = SimpleNamespace(returncode=0, stderr=b'', stdout='\n'.join(
            key+'='+value for key, value in values.items()).encode())
        return snapshot, run

    def test_observation_requires_all_seven_parent_checks(self):
        snapshot, result = self.observation_case()
        for busy in range(8):  # Controller plus ordinary, query and management pins.
            count = 0
            def parent(path, expected=None):
                nonlocal count
                empty = count != busy
                count += 1
                return expected, empty
            with self.subTest(busy=busy), \
                 patch.object(recovery.budget, 'current_clock', return_value={'boot_id': 'synthetic-boot'}), \
                 patch.object(recovery.os, 'stat', return_value=os.stat('/proc/self/ns/user')), \
                 patch.object(recovery.q2_config, 'executable', side_effect=lambda _: os.open('/dev/null', os.O_RDONLY)), \
                 patch.object(recovery, 'open_protected', side_effect=lambda *a, **kw: os.open('/dev/null', os.O_RDONLY)), \
                 patch.object(recovery.subprocess, 'run', return_value=result), \
                 patch.object(recovery.quota_lifecycle, 'parent', side_effect=parent), \
                 self.assertRaisesRegex(ValueError, 'RECOVERY_.*BUSY'):
                recovery.observe(snapshot)

    def test_boot_change_rejects_before_unit_query(self):
        snapshot, _ = self.observation_case()
        with patch.object(recovery.budget, 'current_clock', return_value={'boot_id': 'new-boot'}), \
             patch.object(recovery.subprocess, 'run') as command, \
             self.assertRaisesRegex(ValueError, 'RECOVERY_BOOT_CHANGED'):
            recovery.observe(snapshot)
        command.assert_not_called()

    def test_systemctl_omits_only_empty_exec_properties(self):
        # Actual systemctl --all output omits empty Exec* arrays. Scalar
        # identity fields must still be present, and nonempty hooks rejected.
        snapshot, result = self.observation_case()
        hooks = {'ExecStartPre', 'ExecStartPost', 'ExecStop', 'ExecStopPost', 'ExecReload'}
        lines = [line for line in result.stdout.splitlines()
                 if line.split(b'=', 1)[0].decode() not in hooks]
        namespace = os.stat('/proc/self/ns/user')
        for variant, extra, missing in (('empty', b'', None),
                                        ('hook', b'ExecStartPre={ path=/synthetic/hook ; }', None),
                                        ('identity', b'', b'InvocationID='),
                                        ('duplicate', b'Job=\nJob=', b'Job=')):
            stdout = b'\n'.join(line for line in lines if missing is None or not line.startswith(missing))
            if extra:
                stdout += b'\n' + extra
            output = SimpleNamespace(returncode=0, stderr=b'', stdout=stdout)
            with self.subTest(variant=variant), \
                 patch.object(recovery.budget, 'current_clock', return_value={'boot_id': 'synthetic-boot'}), \
                 patch.object(recovery.os, 'stat', return_value=namespace), \
                 patch.object(recovery.q2_config, 'executable', side_effect=lambda _: os.open('/dev/null', os.O_RDONLY)), \
                 patch.object(recovery, 'open_protected', side_effect=lambda *a, **kw: os.open('/dev/null', os.O_RDONLY)), \
                 patch.object(recovery.subprocess, 'run', return_value=output), \
                 patch.object(recovery.quota_lifecycle, 'parent', return_value=(None, True)):
                if variant == 'empty':
                    self.assertEqual('synthetic-boot', recovery.observe(snapshot)['boot_id'])
                else:
                    with self.assertRaises(ValueError):
                        recovery.observe(snapshot)

    def test_absent_controller_group_requires_actual_absence_not_unreadable_events(self):
        snapshot, result = self.observation_case()
        namespace = os.stat('/proc/self/ns/user')
        for absent in (True, False):
            def parent(path, expected=None):
                if path.endswith('.service'):
                    raise FileNotFoundError('controller or events absent')
                return expected, True
            with self.subTest(absent=absent), \
                 patch.object(recovery.budget, 'current_clock', return_value={'boot_id': 'synthetic-boot'}), \
                 patch.object(recovery.os, 'stat', return_value=namespace), \
                 patch.object(recovery.os, 'lstat', side_effect=FileNotFoundError() if absent else None), \
                 patch.object(recovery.q2_config, 'executable', side_effect=lambda _: os.open('/dev/null', os.O_RDONLY)), \
                 patch.object(recovery, 'open_protected', side_effect=lambda *a, **kw: os.open('/dev/null', os.O_RDONLY)), \
                 patch.object(recovery.subprocess, 'run', return_value=result), \
                 patch.object(recovery.quota_lifecycle, 'parent', side_effect=parent):
                if absent:
                    self.assertEqual('synthetic-boot', recovery.observe(snapshot)['boot_id'])
                else:
                    with self.assertRaisesRegex(ValueError, 'RECOVERY_CONTROLLER_CGROUP_UNREADABLE'):
                        recovery.observe(snapshot)


class RetainedInputTests(unittest.TestCase):
    def test_administrator_depth_uses_launch_contract_not_client_request_limit(self):
        nested = {'identity': 'synthetic'}
        for _ in range(15):
            nested = {'nested': nested}
        raw = encoded(nested).encode()
        with patch.object(recovery, 'read_protected', return_value=raw):
            self.assertEqual(nested, recovery.load('/synthetic/launch.json'))

    def test_ambiguous_administrator_record_is_rejected(self):
        with patch.object(recovery, 'read_protected', return_value=b'{"stages":[],"stages":[1]}'), \
             self.assertRaises(ValueError):
            recovery.load('/synthetic/manager-final.json')

    def inputs(self):
        fixture = LedgerCompletionTests()
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        request = fixture.launch['request']
        from admin.local_hand_quota_observer.controller_guard import SCHEMA
        controller = dict(schema=SCHEMA, unit='lhqsynthetic.service', cgroup='/lhqtest.slice/lhqsynthetic.service',
            runtime_max_usec=80000000, timeout_stop_usec=1000000, memory_bytes=64*1024**2, tasks_max=8,
            cpu_quota_per_sec_usec=100000, limit_cpu_seconds=30)
        binding = dict(schema='local-hand-manager-binding/v1', manager_kind='system', authority_id='synthetic',
            boot_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
            parent=dict(path='/lhqtest.slice/lhqtest-ordinary.slice', device=1, inode=2))
        config = dict(uid=1234, gid=1234, slice='lhqtest-ordinary.slice',
                      cgroup='/sys/fs/cgroup'+binding['parent']['path'], manager_binding=binding)
        current = dict(operation_id=request['operation_id'], request=request, serial=3, state='READY',
            principal_id=fixture.launch['principal_id'], launch_path='/synthetic/static.json',
            output='/synthetic/output', boot_id=binding['boot_id'])
        static = dict(request=request, principal_id=current['principal_id'], controller_envelope=dict(controller=controller),
                      policy=dict(authority_id='synthetic', process_manager=config), intents=dict(path='/synthetic/intents'))
        dynamic = copy.deepcopy(static)
        dynamic['controller_envelope'].update(issued_ns=1, deadline_ns=80000000001)
        dynamic['controller_envelope']['controller'].update(invocation_id='b'*32, cgroup_device=1, cgroup_inode=3)
        values = {'/synthetic/current.json': current, current['launch_path']: static,
            '/synthetic/output/launch-intent.json': dict(operation_id=request['operation_id'],
                command=['fixed-launcher', current['launch_path'], '/synthetic/output/controller-1.json']),
            '/synthetic/output/controller-1.json': dynamic,
            '/synthetic/output/finished.json': dict(returncode=1, streams_eof=True),
            '/synthetic/intents/manager-final.json': dict(schema='local-hand-q2-system-manager/v1',
                manager_binding=binding, stages=[], pending_control=None, closed_phases=[])}
        return current, values

    def test_exact_dynamic_original_is_selected(self):
        current, values = self.inputs()
        with patch.object(recovery, 'load', side_effect=lambda path: copy.deepcopy(values[str(path)])):
            result = recovery.retained('/synthetic/current.json', current['operation_id'],
                                       current['request']['request_digest'], 3)
        self.assertEqual('b'*32, result['controller']['invocation_id'])

    def test_identity_and_empty_manager_evidence_cannot_be_substituted(self):
        current, values = self.inputs()
        variants = [('/synthetic/current.json', 'serial', 4),
                    ('/synthetic/output/finished.json', 'streams_eof', False),
                    ('/synthetic/intents/manager-final.json', 'stages', [{}]),
                    ('/synthetic/intents/manager-final.json', 'pending_control', {}),
                    ('/synthetic/output/controller-1.json', 'principal_id', 'other')]
        for path, key, value in variants:
            changed = copy.deepcopy(values); changed[path][key] = value
            with self.subTest(key=key), patch.object(recovery, 'load', side_effect=lambda path: copy.deepcopy(changed[str(path)])), \
                 self.assertRaises(ValueError):
                recovery.retained('/synthetic/current.json', current['operation_id'],
                                  current['request']['request_digest'], 3)


class WorkerProtocolTests(unittest.TestCase):
    setUp = LedgerCompletionTests.setUp
    snapshot = LedgerCompletionTests.snapshot

    def test_worker_uses_original_lock_and_waits_for_root_before_any_completion(self):
        # Real socket/SQLite/authority flock; policy and local filesystem
        # admission are modeled, not production host claims.
        root = Path(self.fixture.f.temp.name)
        anchor = root / 'authority.json'
        registration = dict(authority_id=self.broker.state.authority_id,
                            ledger_id=self.broker.state.ledger_id, state_root=str(self.broker.state.path.parent))
        anchor.write_text(encoded(registration)); anchor.chmod(0o600)
        policy = self.broker.policy
        policy.authority_id = registration['authority_id']
        policy.authority_root = str(root)
        policy.broker_root = str(self.broker.state.path.parent)
        launch = dict(self.launch, policy={})
        before = self.snapshot()
        state_store = recovery.StateStore
        for apply, reply, expected, error_message in (
                (True, {'quiescent': False}, None, 'RECOVERY_ROOT_REPLY'),
                (True, None, None, 'Local transport ended before its response'),
                (False, {'quiescent': True}, 'CHECKED_ONLY', None),
                (True, {'quiescent': True}, 'RECOVERED_BEFORE_START', None)):
            parent, child = socket.socketpair()
            errors = []
            def target():
                try:
                    recovery.worker(child, launch, apply, time.monotonic() + 5)
                except BaseException as error:
                    errors.append(error)
                finally:
                    child.close()
            with patch.object(recovery, 'Policy', return_value=policy), \
                 patch.object(recovery, 'verify_local_filesystem'), \
                 patch.object(recovery, 'StateStore', side_effect=lambda path, *args, **kwargs:
                              state_store(self.broker.state.path, *args, **kwargs)):
                thread = threading.Thread(target=target)
                thread.start()
                try:
                    end = time.monotonic() + 5
                    self.assertEqual({'locked': True}, strict_loads(cli._read_frame(parent, 4096, deadline=end)))
                    self.assertEqual(before, self.snapshot())
                    with self.assertRaises(JobError):
                        AuthorityLock(anchor, **registration)
                    if reply is None:
                        parent.close()  # Root disappeared before authorizing completion.
                    else:
                        cli._send_frame(parent, reply, deadline=end, limit=4096)
                    if expected:
                        self.assertEqual({'result': expected}, strict_loads(cli._read_frame(parent, 4096, deadline=end)))
                    elif reply is not None:
                        # Keep the peer open until rejection finishes. Closing
                        # it immediately can make a broken worker commit and
                        # then fail with BrokenPipeError, masking the missing
                        # authorization check this regression must detect.
                        thread.join(5)
                finally:
                    parent.close(); thread.join(5)
                    if errors and (expected is not None or str(errors[0]) != error_message):
                        raise errors[0]
                self.assertFalse(thread.is_alive())
                if expected != 'RECOVERED_BEFORE_START':
                    self.assertEqual(before, self.snapshot())
                self.assertEqual(expected is None, bool(errors))
                with AuthorityLock(anchor, **registration):
                    pass  # Both rejection and successful completion release the lock.

    def test_real_fork_exchange_and_lost_result_are_idempotent(self):
        self.exercise_fork_exchange(close_inherited=False)

    def test_worker_opens_original_ledger_after_real_inherited_fd_cleanup(self):
        self.exercise_fork_exchange(close_inherited=True)

    def exercise_fork_exchange(self, *, close_inherited):
        # Real fork, Unix frames, authority lock and SQL. Root/cgroup proofs and
        # UID transition are modeled; this does not claim a privileged host run.
        uid, gid, original_pid = os.getuid(), os.getgid(), os.getpid()
        root = Path(self.fixture.f.temp.name)
        registration = dict(authority_id=self.broker.state.authority_id,
                            ledger_id=self.broker.state.ledger_id, state_root=str(self.broker.state.path.parent))
        anchor = root / 'authority.json'
        anchor.write_text(encoded(registration)); anchor.chmod(0o600)
        policy = self.broker.policy
        policy.authority_id = registration['authority_id']
        policy.authority_root = str(root); policy.broker_root = registration['state_root']
        policy.source_commit = 'a'*40; policy.installed_payload_digest = 'b'*64
        policy.execution_entrypoint = cli.__file__
        launch = dict(self.launch, policy=dict(process_manager=dict(uid=uid, gid=gid)))
        snapshot = dict(launch=launch)
        store, save = recovery.StateStore, recovery.save
        drop, read_text = recovery.drop_privileges, Path.read_text
        def modeled_credentials(uid, gid, channel_fd):
            if not close_inherited:
                return
            # Run the actual FD-closing code only in the disposable child.
            # Privileged group/capability changes and their postcondition are
            # modeled. setresuid/gid use the child's unchanged ordinary IDs.
            def status(path, *args, **kwargs):
                if str(path) == '/proc/self/status':
                    return 'NoNewPrivs:\t1\n' + ''.join(key + ':\t0\n' for key in
                        ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'))
                return read_text(path, *args, **kwargs)
            with patch.object(recovery.ctypes, 'CDLL', return_value=SimpleNamespace(prctl=lambda *_: 0)), \
                 patch.object(recovery.os, 'setgroups'), patch.object(recovery.os, 'getgroups', return_value=[]), \
                 patch.object(Path, 'read_text', status):
                drop(uid, gid, channel_fd)
        def selected_save(directory, name, value):
            if name == 'result.json':
                raise OSError('simulated lost final publication')
            return save(directory, name, value)
        options = (root/'current.json', self.identity, self.launch['request']['request_digest'], 3, root)
        def run_recovery():
            if not close_inherited:
                return recovery.run(*options, apply=True)
            # Production's parent never opens SQLite. Finish the fixture's
            # inspection connection before fork: retaining SQLite's inherited
            # connection bookkeeping after closing its FDs is not a valid test
            # of that production path (it produces SQLITE_PROTOCOL).
            state = self.broker.state
            state.close()
            try:
                return recovery.run(*options, apply=True)
            finally:
                with patch.object(recovery.os, 'geteuid', return_value=uid):
                    self.broker.state = store(state.path, state.authority_id, state.ledger_id)
                self.addCleanup(self.broker.state.close)
        with patch.object(recovery.os, 'getuid', side_effect=lambda: 0 if os.getpid() == original_pid else uid), \
             patch.object(recovery.os, 'geteuid', side_effect=lambda: 0 if os.getpid() == original_pid else uid), \
             patch.object(recovery, 'drop_privileges', side_effect=modeled_credentials), \
             patch.object(recovery, 'retained', return_value=snapshot), \
             patch.object(recovery, 'Policy', return_value=policy), \
             patch.object(recovery, 'verify_release'), patch.object(recovery, 'verify_local_filesystem'), \
             patch.object(recovery, 'observe', return_value={'controller': 'verified-fixture'}), \
             patch.object(recovery, 'open_protected', side_effect=lambda path, **kw: os.open(path, os.O_RDONLY)), \
             patch.object(recovery, 'StateStore', side_effect=lambda path, *args, **kwargs:
                          store(self.broker.state.path, *args, **kwargs)):
            before = self.snapshot()
            with patch.object(recovery, 'drop_privileges', side_effect=PermissionError(errno.EPERM, 'denied')), \
                 patch.object(recovery, 'observe') as observation, \
                 self.assertRaisesRegex(ValueError, 'RECOVERY_WORKER_NOT_LOCKED'):
                run_recovery()
            observation.assert_not_called()
            self.assertEqual(before, self.snapshot())
            with patch.object(recovery, 'observe', side_effect=ValueError('busy process tree')), \
                 self.assertRaisesRegex(ValueError, 'busy process tree'):
                run_recovery()
            self.assertEqual(before, self.snapshot())
            # The worker already owns the original authority lock here. Root
            # must not acknowledge if either protected inputs or OS facts drift
            # before its second observation. Exercise the actual fork/socket
            # boundary, not only controller_stopped() with individual values.
            for change in ('inputs', 'os'):
                changed = dict(snapshot, unexpected='changed')
                with self.subTest(drift=change), \
                     patch.object(recovery, 'retained', side_effect=[snapshot, changed]
                                  if change == 'inputs' else [snapshot, snapshot]), \
                     patch.object(recovery, 'observe', side_effect=[{'controller': 'original'},
                                                                   {'controller': 'changed'}]), \
                     self.assertRaisesRegex(ValueError, 'RECOVERY_INPUTS_CHANGED'
                                            if change == 'inputs' else 'RECOVERY_OS_CHANGED'):
                    run_recovery()
                self.assertEqual(before, self.snapshot())
                with patch.object(recovery.os, 'geteuid', return_value=uid), AuthorityLock(anchor, **registration):
                    pass
            original_close = os.close
            def failed_archive_close(fd):
                target = os.readlink('/proc/self/fd/' + str(fd))
                fails = (os.getpid() == original_pid and stat.S_ISDIR(os.fstat(fd).st_mode)
                         and target.startswith(str(root / 'lh-unstarted-recovery-')))
                original_close(fd)
                if fails:
                    raise OSError(errno.EIO, 'simulated archive close failure')
            with patch.object(recovery.os, 'close', side_effect=failed_archive_close), \
                 patch.object(recovery, 'observe', side_effect=ValueError('busy process tree')), \
                 self.assertRaisesRegex(ValueError, 'busy process tree') as caught:
                run_recovery()
            self.assertTrue(any('archive' in note for note in caught.exception.__notes__))
            self.assertEqual(before, self.snapshot())
            with patch.object(recovery.os, 'geteuid', return_value=uid), AuthorityLock(anchor, **registration):
                pass  # The actual worker exited and released its original flock.
            with patch.object(recovery, 'save', side_effect=selected_save), \
                 self.assertRaisesRegex(OSError, 'simulated lost final publication'):
                run_recovery()
            completed = self.snapshot()
            self.assertEqual('ALREADY_COMPLETED', run_recovery()['result'])
            self.assertEqual(completed, self.snapshot())


class ParentCleanupTests(unittest.TestCase):
    """Fault injection without root privileges, real PIDs or live state."""
    def test_nondefault_child_reaping_is_rejected_before_any_host_access(self):
        # SIG_IGN discards exit status; a caller handler can reap a child
        # between waitpid(WNOHANG) and kill. Neither belongs in this entry.
        for disposition in (recovery.signal.SIG_IGN, lambda *_: None):
            with self.subTest(disposition=disposition):
                with patch.object(recovery.os, 'getuid', return_value=0), \
                     patch.object(recovery.os, 'geteuid', return_value=0), \
                     patch.object(recovery.signal, 'getsignal', return_value=disposition), \
                     patch.object(recovery, 'retained', side_effect=AssertionError('host access')) as retained, \
                     patch.object(recovery.os, 'fork') as fork, \
                     patch.object(recovery.os, 'kill') as kill, \
                     self.assertRaisesRegex(ValueError, 'RECOVERY_CHILD_REAP_POLICY'):
                    recovery.run(Path('/synthetic/current'), 'original', 'a'*64, 3, Path('/synthetic'))
                retained.assert_not_called()
                fork.assert_not_called()
                kill.assert_not_called()

    def test_isolated_entry_checks_real_inherited_signal_disposition(self):
        # Exercise exec inheritance in a disposable ordinary-user interpreter.
        # Mock only administrator identity and the first host read; no task,
        # root transition, archive or recovery worker can be created here.
        script = '''
import importlib.util, signal, sys
from pathlib import Path
from unittest.mock import patch
sys.path[:] = PATHS
import admin.local_hand_system_manager
name = 'admin.local_hand_system_manager.unstarted_recovery'
spec = importlib.util.spec_from_file_location(name, PAYLOAD)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
if sys.argv[1] == 'handler':
    signal.signal(signal.SIGCHLD, lambda *_: None)
with patch.object(module.os, 'getuid', return_value=0), \\
     patch.object(module.os, 'geteuid', return_value=0), \\
     patch.object(module, 'retained', side_effect=RuntimeError('HOST_READ_SENTINEL')) as read:
    try:
        module.run(Path('/synthetic/current'), 'original', 'a'*64, 3, Path('/synthetic'))
    except RuntimeError as error:
        assert sys.argv[1] == 'default' and str(error) == 'HOST_READ_SENTINEL'
        read.assert_called_once()
    except ValueError as error:
        assert sys.argv[1] != 'default' and str(error) == 'RECOVERY_CHILD_REAP_POLICY'
        read.assert_not_called()
    else:
        raise AssertionError('Unexpected success')
'''.replace('PATHS', repr(sys.path)).replace('PAYLOAD', repr(recovery.__file__))
        bootstrap = ('import os,signal,sys; '
                     'signal.signal(signal.SIGCHLD, signal.SIG_IGN if sys.argv[2] == "ignored" '
                     'else signal.SIG_DFL); '
                     'os.execv(sys.executable, [sys.executable, "-I", "-B", "-c", sys.argv[1], sys.argv[2]])')
        for mode in ('default', 'ignored', 'handler'):
            with self.subTest(mode=mode):
                result = recovery.subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap, script, mode],
                                                  capture_output=True, timeout=10)
                self.assertEqual(0, result.returncode, result.stderr.decode(errors='replace'))

    def harness(self, *, close_failure=None, pair_failure=None):
        from contextlib import ExitStack
        stack = ExitStack()
        self.addCleanup(stack.close)
        parent, child = Mock(), Mock()
        if close_failure == 'parent':
            parent.close.side_effect = OSError(errno.EIO, 'parent close')
        if close_failure == 'child':
            child.close.side_effect = [None, OSError(errno.EIO, 'child close')]
        def close(fd):
            if close_failure == 'directory' and fd == 202:
                raise OSError(errno.EIO, 'directory close')
        policy = SimpleNamespace(source_commit='a'*40, installed_payload_digest='b'*64,
                                 execution_entrypoint='/synthetic/cli.py')
        values = dict(retained=dict(launch=dict(policy={})), Policy=policy,
                      open_protected=101, observe=None)
        for name, value in values.items():
            stack.enter_context(patch.object(recovery, name, return_value=value))
        for name in ('getuid', 'geteuid'):
            stack.enter_context(patch.object(recovery.os, name, return_value=0))
        stack.enter_context(patch.object(recovery, 'verify_release'))
        stack.enter_context(patch.object(recovery.tempfile, 'mkdtemp', return_value='/synthetic/archive'))
        stack.enter_context(patch.object(recovery.os, 'open', return_value=202))
        close_mock = stack.enter_context(patch.object(recovery.os, 'close', side_effect=close))
        stack.enter_context(patch.object(recovery.socket, 'socketpair', return_value=(parent, child),
                                        side_effect=pair_failure))
        stack.enter_context(patch.object(recovery.os, 'fork', return_value=3141))
        wait = stack.enter_context(patch.object(recovery.os, 'waitpid', side_effect=[(0, 0), (3141, 9)]))
        kill = stack.enter_context(patch.object(recovery.os, 'kill'))
        stack.enter_context(patch.object(recovery.cli, '_read_frame', return_value=b'{"locked":true}'))
        save = stack.enter_context(patch.object(recovery, 'save'))
        return parent, child, close_mock, wait, kill, save

    def test_cleanup_failure_never_skips_child_reaping_or_masks_primary(self):
        for target in ('parent', 'child', 'directory'):
            with self.subTest(target=target):
                case = ParentCleanupTests()
                try:
                    parent, child, close, wait, kill, save = case.harness(close_failure=target)
                    primary = ValueError('original quiescence failure')
                    with patch.object(recovery, 'observe', side_effect=primary):
                        try:
                            recovery.run(Path('/synthetic/current'), 'original', 'a'*64, 3,
                                         Path('/synthetic'), apply=True)
                        except BaseException as error:
                            self.assertIs(primary, error)
                        else:
                            self.fail('Missing primary failure')
                    kill.assert_called_once_with(3141, recovery.signal.SIGKILL)
                    self.assertEqual(2, wait.call_count)
                    self.assertGreaterEqual(child.close.call_count, 2)
                    parent.close.assert_called_once()
                    self.assertIn(((202,), {}), close.call_args_list)
                finally:
                    case.doCleanups()

    def test_socket_setup_failure_closes_already_open_archive(self):
        primary = OSError(errno.EMFILE, 'socket setup')
        _, _, close, wait, kill, _ = self.harness(pair_failure=primary)
        with self.assertRaises(OSError) as caught:
            recovery.run(Path('/synthetic/current'), 'original', 'a'*64, 3, Path('/synthetic'))
        self.assertIs(primary, caught.exception)
        self.assertIn(((202,), {}), close.call_args_list)
        wait.assert_not_called()
        kill.assert_not_called()

    def test_cleanup_failure_after_commit_never_prints_success_or_signals_reaped_pid(self):
        _, _, _, wait, kill, _ = self.harness(close_failure='parent')
        replies = [b'{"locked":true}', b'{"result":"RECOVERED_BEFORE_START"}']
        with patch.object(recovery.cli, '_read_frame', side_effect=replies), \
             patch.object(recovery, 'wait_worker', return_value=0), \
             patch('builtins.print') as output, self.assertRaises(OSError):
            recovery.run(Path('/synthetic/current'), 'original', 'a'*64, 3,
                         Path('/synthetic'), apply=True)
        self.assertFalse(any(str(call.args[0]).startswith('FINAL ') for call in output.call_args_list))
        wait.assert_not_called()
        kill.assert_not_called()

    def test_reap_never_signals_unowned_pid_and_reaps_exit_signal_race(self):
        with patch.object(recovery.os, 'waitpid', side_effect=ChildProcessError()), \
             patch.object(recovery.os, 'kill') as kill:
            recovery.reap_worker(3141)
        kill.assert_not_called()
        with patch.object(recovery.os, 'waitpid', side_effect=[(0, 0), (3141, 0)]) as wait, \
             patch.object(recovery.os, 'kill', side_effect=ProcessLookupError()):
            recovery.reap_worker(3141)
        self.assertEqual([((3141, os.WNOHANG), {}), ((3141, 0), {})], wait.call_args_list)

    def test_reap_error_still_closes_all_descriptors_and_preserves_original(self):
        parent, child, close, _, kill, _ = self.harness()
        primary = ValueError('original quiescence failure')
        with patch.object(recovery, 'observe', side_effect=primary), \
             patch.object(recovery.os, 'waitpid', side_effect=OSError(errno.EIO, 'wait failure')), \
             self.assertRaises(ValueError) as caught:
            recovery.run(Path('/synthetic/current'), 'original', 'a'*64, 3, Path('/synthetic'))
        self.assertIs(primary, caught.exception)
        self.assertTrue(any('worker' in note for note in caught.exception.__notes__))
        parent.close.assert_called_once()
        self.assertEqual(2, child.close.call_count)
        self.assertIn(((202,), {}), close.call_args_list)
        kill.assert_not_called()


if __name__ == '__main__':
    unittest.main()

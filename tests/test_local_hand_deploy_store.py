"""Real SQLite durability/budget boundaries; no services or business writes."""
from dataclasses import replace
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from admin.local_hand_deploy.model import DeployError, Limits, seal_plan
from admin.local_hand_deploy.store import Store
from test_local_hand_deploy_coordinator import plan


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'records', 'test-node')
        self.store.initialize()

    def test_readonly_status_does_not_change_database_or_create_lock(self):
        with self.store.locked(): op = self.store.create(plan())
        before = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.store.root.iterdir()}
        self.assertEqual(op, self.store.get(op['id']))
        self.assertEqual([op], self.store.list(unfinished=True))
        after = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.store.root.iterdir()}
        self.assertEqual(before, after)

    def test_missing_state_is_not_recreated_by_status(self):
        absent = Store(self.root / 'absent', 'test-node')
        with self.assertRaises(RuntimeError): absent.list()
        self.assertFalse(absent.root.exists())

    def test_configured_database_page_cap_survives_new_connection(self):
        cap = self.store.limits.max_database_bytes
        with self.store.locked():
            connection = self.store.connection
            page = connection.execute('PRAGMA page_size').fetchone()[0]
            self.assertEqual(cap // page, connection.execute('PRAGMA max_page_count').fetchone()[0])
        reopened = Store(self.store.root, 'test-node')
        with reopened.locked():
            self.assertEqual(cap // page, reopened.connection.execute('PRAGMA max_page_count').fetchone()[0])

    def test_operation_and_event_rollback_together(self):
        with self.store.locked():
            op = self.store.create(plan())
            original = self.store.get(op['id'])
            events = self.store.connection.execute('SELECT count(*) FROM events').fetchone()[0]
            op['phase'] = 'PREPARED'
            with mock.patch.object(self.store, '_event', side_effect=sqlite3.OperationalError('injected full')):
                with self.assertRaises(DeployError): self.store.save(op, 'PREPARED')
            self.assertEqual(original, self.store.get(op['id']))
            self.assertEqual(events, self.store.connection.execute('SELECT count(*) FROM events').fetchone()[0])

    def test_half_written_successor_link_is_not_committed(self):
        with self.store.locked():
            op = self.store.create(plan())
            event = self.store._event
            def fail_second(operation, kind, detail, **kwargs):
                if kind == 'CREATED': raise sqlite3.OperationalError('injected interruption')
                return event(operation, kind, detail, **kwargs)
            with mock.patch.object(self.store, '_event', side_effect=fail_second):
                with self.assertRaises(DeployError): self.store.link(op, plan('second'))
            self.assertIsNone(self.store.get(op['id'])['successor'])
            self.assertEqual(1, len(self.store.list()))
            successor = self.store.link(op, plan('second'))
            self.assertEqual(successor['id'], self.store.get(op['id'])['successor'])

    def test_changed_node_or_storage_identity_cannot_adopt_existing_records(self):
        with self.assertRaises(DeployError): Store(self.store.root, 'another-node').list()
        old = self.store.path.read_bytes()
        replacement = self.store.root / 'replacement'
        replacement.write_bytes(old); replacement.chmod(0o600)
        replacement.replace(self.store.path)
        with self.assertRaises(DeployError): self.store.list()

    def test_foreign_node_plan_cannot_create_or_link_records(self):
        foreign = seal_plan({**plan('foreign'), 'node_id': 'another-node'})
        with self.store.locked():
            original = self.store.create(plan())
            before = self.store.path.read_bytes()
            for name, action in (
                    ('create', lambda: self.store.create(foreign)),
                    ('handoff', lambda: self.store.link(original, foreign)),
                    ('rollback', lambda: self.store.link(original, foreign, rollback=True))):
                with self.subTest(action=name):
                    with self.assertRaises(DeployError) as failure:
                        action()
                    self.assertEqual('NODE_CONFLICT', failure.exception.code)
                    self.assertEqual(before, self.store.path.read_bytes())
                    self.assertEqual([original], self.store.list())

    def test_writable_ancestor_is_rejected_even_with_private_child(self):
        untrusted = self.root / 'untrusted'; untrusted.mkdir(mode=0o777); untrusted.chmod(0o777)
        with self.assertRaises(RuntimeError): Store(untrusted / 'private', 'test-node').initialize()

    def test_initial_operation_overhead_cannot_exceed_record_limit(self):
        limits = replace(Limits(), max_record_bytes=1000)
        store = Store(self.root / 'small', 'test-node', limits=limits); store.initialize()
        with store.locked():
            with self.assertRaises(DeployError): store.create(plan())
            self.assertEqual([], store.list())

    def test_attempt_budget_reserves_completion_and_database_headroom(self):
        with self.store.locked():
            op = self.store.create(plan())
            reserve = self.store.check_attempt_budget(op)
            self.assertGreater(reserve['events'], 64)
            self.assertGreater(reserve['operation_bytes'], 262144)
            for limits in (replace(self.store.limits, max_events=64, recovery_events=32),
                           replace(self.store.limits, max_record_bytes=32768),
                           replace(self.store.limits, max_database_bytes=32768)):
                # Inspect the bound, without changing the actual store metadata.
                with mock.patch.object(self.store, 'limits', limits), self.assertRaises(DeployError):
                    self.store.check_attempt_budget(op)

    def test_observation_budget_does_not_consume_reserved_recovery_events(self):
        with self.store.locked():
            op = self.store.create(plan())
            limits = replace(self.store.limits, max_events=5, recovery_events=3)
            with mock.patch.object(self.store, 'limits', limits):
                self.store.save(op, 'WAITING')
                before = self.store.path.read_bytes()
                with self.assertRaises(DeployError):
                    self.store.save(op, 'WAITING')
                self.assertEqual(before, self.store.path.read_bytes())
                self.store.save(op, 'DECISION', recovery=True)
                self.store.save(op, 'RELEASE_INTENT', recovery=True)
                self.store.save(op, 'RELEASED', recovery=True)


if __name__ == '__main__': unittest.main()

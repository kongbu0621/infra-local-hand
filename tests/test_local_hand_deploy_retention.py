"""Retained preparation decisions cross the real coordinator/gate boundary."""
import copy
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from admin.local_hand_deploy import preparations
from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.planner import build_plan
from admin.local_hand_deploy.runtime import ConcreteEnvironment
from local_hand_jobs import maintenance, startup
from local_hand_jobs.contract import JobError
import test_local_hand_deploy_runtime as runtime_fixtures
import test_local_hand_deploy_bootstrap as bootstrap_fixtures


class PreparationRetentionTests(unittest.TestCase):
    def setUp(self):
        self.f = runtime_fixtures.RuntimeTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        f = self.f
        root = f.root / "original-tasks"; root.mkdir(mode=0o700)
        self.operation = "12345678-1234-4234-8234-123456789abc"
        task = root / self.operation; task.mkdir(mode=0o700)
        output = task / "output"; output.mkdir(mode=0o700)
        self.record_path, self.launch_path = task / "current.json", task / "launch.json"
        self.launch = {"request": {"operation_id": self.operation, "request_digest": "d" * 64,
                                   "expires_at": time.time() + 600}, "resource": "original-resource"}
        f.profile["guarded_components"]["manager"]["entrypoints"] = ["prepare", "execute", "cli"]
        for config in (f.old_config, f.new_config):
            config.update(private_root=str(root), catalog=str(root), max_tasks=32)
        f.write(f.config, f.old_config); f.write(f.candidate, f.new_config)
        f.source = f.deployment(f.a, f.old_config); f.target = f.deployment(f.b, f.new_config)
        f.manifest.update(source=f.source, target=f.target)
        f.write(f.selection, f.source["selection"])
        self.loaded = maintenance.loaded_configuration(f.old_config, boot_id=startup.boot_id())
        self.prepared = maintenance.prepared_binding(self.loaded, operation_id=self.operation,
            attempt_id=str(task), request_digest="d" * 64, launch=self.launch)
        self.record = {"operation_id": self.operation, "state": "READY", "attempt": str(task),
                       "request": self.launch["request"], "launch_path": str(self.launch_path),
                       "output": str(output), "maintenance_prepared": self.prepared}
        f.write(self.launch_path, self.launch); f.write(self.record_path, self.record)
        self.store = f.store()
        # This fixture models only the manager's preparation inventory. Actual
        # retained SQLite/artifact readers are exercised by the companion suite.
        readback = patch.object(ConcreteEnvironment, "retained_results", return_value={})
        readback.start(); self.addCleanup(readback.stop)

    def coordinator(self, plan):
        return Coordinator(self.store, self.f.gate, ConcreteEnvironment(plan, self.store, self.f.gate))

    def test_actual_apply_saves_decision_before_grant_and_preserves_original_files(self):
        f = self.f
        original = self.record_path.read_bytes(), self.launch_path.read_bytes()
        plan = build_plan(f.manifest)
        self.assertEqual(1, len(plan["profile"]["retained_preparations"]["tasks"]))
        original_grant = f.gate.authorize_compatibility
        def grant(*args, **kwargs):
            durable = self.store.get(args[0])
            self.assertTrue(durable["checks"]["released_compatibility"][0]["compatible"])
            self.assertEqual("COMMITTED", durable["decision"])
            return original_grant(*args, **kwargs)
        with patch.object(f.gate, "authorize_compatibility", side_effect=grant):
            result = self.coordinator(plan).apply(plan)
        self.assertTrue(result["released"], result["waiting"])
        self.assertEqual(original, (self.record_path.read_bytes(), self.launch_path.read_bytes()))
        target = maintenance.loaded_configuration(f.new_config, boot_id=startup.boot_id())
        receipt = f.gate.accept("execute", self.operation, "submit-once", {"prepared": self.prepared},
                                target, prepared=self.prepared)
        self.assertEqual("ACCEPTED", receipt["state"])
        f.gate.finish(receipt, {"never_dispatched": True})
        with self.assertRaises(JobError):
            f.gate.accept("execute", self.operation, "new-boot", {}, dict(target, boot_id="different-boot"), prepared=self.prepared)

    def test_payload_change_records_incompatibility_and_opens_other_new_work(self):
        f = self.f
        f.new_config["installation"]["installed"]["payload_digest"] = "e" * 64
        f.write(f.candidate, f.new_config)
        f.target = f.deployment(f.b, f.new_config)
        f.target["selection"]["components"]["manager"]["payload_digest"] = "e" * 64
        f.manifest["target"] = f.target
        plan = build_plan(f.manifest); result = self.coordinator(plan).apply(plan)
        self.assertTrue(result["released"], result["waiting"])
        self.assertFalse(result["checks"]["released_compatibility"][0]["compatible"])
        self.assertEqual("OPEN", f.gate.snapshot()["state"])
        target = maintenance.loaded_configuration(f.new_config, boot_id=startup.boot_id())
        with self.assertRaises(JobError) as caught:
            f.gate.accept("execute", self.operation, "direct-submit", {}, target, prepared=self.prepared)
        self.assertEqual("STALE_DEPLOYMENT", caught.exception.code)

    def test_unresolved_original_dispatch_blocks_before_configuration_effect(self):
        f = self.f
        output = self.record_path.parent / "output"
        f.write(output / "launch-intent.json", {"original": "unknown"})
        plan = build_plan(f.manifest)
        before = f.config.read_bytes()
        result = self.coordinator(plan).apply(plan)
        self.assertFalse(result["released"])
        self.assertEqual("RETAINED_DISPATCH_UNRESOLVED", result["errors"]["primary"][-1]["code"])
        self.assertEqual(before, f.config.read_bytes())
        self.assertEqual("CLOSED", f.gate.snapshot()["state"])

    def test_changed_original_launch_is_not_relabelled_compatible(self):
        self.f.write(self.launch_path, dict(self.launch, resource="different"))
        with self.assertRaisesRegex(Exception, "resources changed"):
            build_plan(self.f.manifest)

    def test_changed_record_after_local_check_prevents_release_then_same_operation_recovers(self):
        f = self.f; plan = build_plan(f.manifest); coordinator = self.coordinator(plan)
        original = ConcreteEnvironment.check_local
        changed = [False]
        def check(environment, op, rollback=False):
            result = original(environment, op, rollback=rollback)
            if not op["decision"] and not changed[0]:
                changed[0] = True
                f.write(self.record_path, dict(self.record, serial="independent replacement"))
            return result
        with patch.object(ConcreteEnvironment, "check_local", check):
            result = coordinator.apply(plan)
        self.assertFalse(result["released"])
        self.assertEqual("CLOSED", f.gate.snapshot()["state"])
        f.write(self.record_path, self.record)
        recovered = coordinator.resume(result["id"])
        self.assertTrue(recovered["released"], recovered["waiting"])

    def test_inventory_budget_is_enforced_during_enumeration(self):
        with patch.object(preparations, "MAX_TASKS", 0), self.assertRaisesRegex(Exception, "task budget"):
            preparations.inventory(self.f.profile)

    def test_committed_rollback_reuses_original_preparation_without_new_business(self):
        plan = build_plan(self.f.manifest); coordinator = self.coordinator(plan)
        result = coordinator.apply(plan)
        self.assertTrue(result["released"], result["waiting"])
        restored = coordinator.rollback(result["id"])
        self.assertTrue(restored["released"], restored["waiting"])
        self.assertEqual(self.f.a, self.f.gate.snapshot()["deployment_digest"])
        self.assertEqual(self.prepared, restored["checks"]["retained"]["preparations"]["tasks"][0]["prepared"])

    def test_lost_readback_after_switch_resumes_without_republishing_configuration(self):
        f = self.f; plan = build_plan(f.manifest); coordinator = self.coordinator(plan)
        original = ConcreteEnvironment.check_local
        def unavailable(environment, op, rollback=False):
            raise JobError("IO_UNCERTAIN", "synthetic old result transport interruption")
        with patch.object(ConcreteEnvironment, "check_local", unavailable):
            result = coordinator.apply(plan)
        self.assertFalse(result["released"])
        identity = f.config.stat().st_ino, f.config.read_bytes()
        recovered = coordinator.resume(result["id"])
        self.assertTrue(recovered["released"], recovered["waiting"])
        self.assertEqual(identity, (f.config.stat().st_ino, f.config.read_bytes()))

    def test_reboot_closure_is_independent_of_missing_manager_socket_and_result_bytes(self):
        f = self.f
        old_boot = "11111111-1111-4111-8111-111111111111"
        loaded = dict(self.loaded, boot_id=old_boot)
        prepared = dict(self.prepared, boot_id=old_boot)
        self.record.update(maintenance_prepared=prepared, boot_id=old_boot)
        f.write(self.record_path, self.record)
        receipt = f.gate.accept("execute", self.operation, "old-boot-attempt", {"prepared": prepared}, loaded, prepared=prepared)
        f.gate.dispatch(receipt)
        f.write(self.record_path.parent / "output" / "launch-intent.json", {"original": "unknown"})
        plan = build_plan(f.manifest); coordinator = self.coordinator(plan)
        with patch.object(preparations, "observe_reboot_closure", return_value={"original_parents_empty": True}) as observe:
            result = coordinator.apply(plan)
        self.assertTrue(result["released"], result["waiting"])
        observe.assert_called_once()
        self.assertFalse((self.record_path.parent / "output" / "finished.json").exists())
        self.assertEqual("CLOSED", f.gate.snapshot()["responsibilities"][receipt["id"]]["state"])

    def test_reboot_observer_checks_original_parents_and_refuses_queued_stage(self):
        b = bootstrap_fixtures.BootstrapTests(); b.setUp(); self.addCleanup(b.doCleanups)
        directory, attempt, output = b.record(launch=True, closed=False)
        old_boot = "11111111-1111-4111-8111-111111111111"
        from admin.local_hand_deploy.model import decode
        current = decode((directory / "current.json").read_bytes())
        current["boot_id"] = old_boot
        b.write(directory / "current.json", current)
        profile = copy.deepcopy(b.profile)
        profile["guarded_components"]["manager"]["configuration"] = str(b.legacy_config)
        from admin.local_hand_deploy import bootstrap
        with patch.object(bootstrap, "OfflineObserver", return_value=b.observer):
            proof = preparations.observe_reboot_closure(profile, "manager", expected_boot=old_boot,
                                                       current_boot=startup.boot_id())
            self.assertEqual(old_boot, proof["original_boot_id"])
            self.assertFalse((output / "finished.json").exists())
            b.bus.pending = [(1, "original-stage.service")]
            b.bus.units["original-stage.service"] = {"Slice": "lhbootstrapfixture.slice"}
            with self.assertRaisesRegex(Exception, "queued system job"):
                preparations.observe_reboot_closure(profile, "manager", expected_boot=old_boot,
                                                   current_boot=startup.boot_id())

    def preparation_duty(self, *, dispatched=False, wrong_root=False):
        f = self.f
        root = Path(f.old_config['private_root'])
        operation = self.operation if dispatched else '22222222-2222-4222-8222-222222222222'
        attempt = root / operation / 'attempt-1'
        binding = {'private_root': str(root / 'foreign' if wrong_root else root),
                   'principal_id': 'owner', 'arguments': {'operation_id': operation,
                   'kind': 'host.inspect', 'profile_ref': 'fixture'}}
        loaded = dict(self.loaded, boot_id='11111111-1111-4111-8111-111111111111')
        receipt = f.gate.accept('prepare', operation, str(attempt), binding, loaded)
        if dispatched:
            attempt.mkdir(mode=0o700)
            unit = 'lhprepare' + operation.replace('-', '') + 'a1.service'
            f.write(attempt / 'preparation-delivery.json', {'command': ['systemd-run', '--unit=' + unit,
                    str(attempt / 'input.json'), str(attempt / 'result.json')]})
            self.record['principal_id'] = 'owner'
            f.write(self.record_path, self.record)
            f.gate.dispatch(receipt)
        plan = build_plan(f.manifest)
        environment = ConcreteEnvironment(plan, self.store, f.gate)
        f.gate.close('drain-orphan', expected=f.gate.snapshot())
        return receipt, environment

    def test_reboot_drain_closes_accepted_duty_without_a_current_pointer(self):
        receipt, environment = self.preparation_duty()
        with patch.object(environment, '_probe', side_effect=AssertionError('manager is stopped')), \
                patch.object(preparations, 'observe_reboot_closure', side_effect=AssertionError('never dispatched')):
            result = environment.drain({'id': 'drain-orphan'})
        self.assertTrue(result['quiescent'])
        duty = self.f.gate.snapshot()['responsibilities'][receipt['id']]
        self.assertEqual({'never_dispatched': True}, duty['proof'])
        self.assertFalse(Path(receipt['attempt_id']).exists())

    def test_reboot_drain_uses_original_attempt_after_current_pointer_advanced(self):
        receipt, environment = self.preparation_duty(dispatched=True)
        original = self.record_path.read_bytes()
        with patch.object(environment, '_probe', side_effect=AssertionError('manager is stopped')), \
                patch.object(preparations, 'observe_reboot_closure', return_value={'original_parents_empty': True}) as observe:
            self.assertTrue(environment.drain({'id': 'drain-orphan'})['quiescent'])
        observe.assert_called_once()
        self.assertEqual(original, self.record_path.read_bytes())
        self.assertEqual({'process_exited': True, 'writers_stopped': True},
                         self.f.gate.snapshot()['responsibilities'][receipt['id']]['proof'])

    def test_reboot_drain_rejects_a_foreign_preparation_root(self):
        receipt, environment = self.preparation_duty(wrong_root=True)
        with self.assertRaisesRegex(Exception, 'binding'):
            environment.drain({'id': 'drain-orphan'})
        self.assertEqual('ACCEPTED', self.f.gate.snapshot()['responsibilities'][receipt['id']]['state'])

    def test_reboot_drain_does_not_close_on_failed_old_process_observation(self):
        receipt, environment = self.preparation_duty(dispatched=True)
        with patch.object(preparations, 'observe_reboot_closure', side_effect=RuntimeError('queued original job')):
            with self.assertRaisesRegex(RuntimeError, 'queued original job'):
                environment.drain({'id': 'drain-orphan'})
        self.assertEqual('DISPATCHING', self.f.gate.snapshot()['responsibilities'][receipt['id']]['state'])
        with patch.object(preparations, 'observe_reboot_closure', return_value={'original_parents_empty': True}):
            self.assertTrue(environment.drain({'id': 'drain-orphan'})['quiescent'])

    def test_reboot_drain_requires_the_original_delivery_and_owner(self):
        receipt, environment = self.preparation_duty(dispatched=True)
        delivery = Path(receipt['attempt_id']) / 'preparation-delivery.json'
        original = delivery.read_bytes()
        for invalid in ({'command': ['systemd-run', '--unit=other.service']}, None):
            self.f.write(delivery, invalid)
            with self.assertRaisesRegex(Exception, 'binding'):
                environment.drain({'id': 'drain-orphan'})
            self.assertEqual('DISPATCHING', self.f.gate.snapshot()['responsibilities'][receipt['id']]['state'])
        delivery.write_bytes(original)
        self.f.write(self.record_path, {**self.record, 'principal_id': 'another-owner'})
        with self.assertRaisesRegex(Exception, 'binding'):
            environment.drain({'id': 'drain-orphan'})
        self.assertEqual('DISPATCHING', self.f.gate.snapshot()['responsibilities'][receipt['id']]['state'])

    def half_created_preparation(self, *, serial=1, principal='owner', wrong_root=False):
        root = Path(self.f.old_config['private_root'])
        operation = '33333333-3333-4333-8333-333333333333'
        directory = root / operation
        directory.mkdir(mode=0o700, exist_ok=True)
        attempt = directory / ('attempt-' + str(serial))
        attempt.mkdir(mode=0o700)
        binding = {'private_root': str(root / 'foreign' if wrong_root else root),
                   'principal_id': principal, 'arguments': {'operation_id': operation,
                   'kind': 'host.inspect', 'profile_ref': 'fixture'}}
        loaded = dict(self.loaded, boot_id='11111111-1111-4111-8111-111111111111')
        return self.f.gate.accept('prepare', operation, str(attempt), binding, loaded)

    def test_half_created_preparations_cross_actual_apply_without_fabricating_current(self):
        old = self.half_created_preparation()
        self.f.gate.finish(old, {'never_dispatched': True})
        accepted = self.half_created_preparation(serial=2)
        originals = self.record_path.read_bytes(), self.launch_path.read_bytes()
        before = preparations.inventory(self.f.profile)
        items = [item for item in before['tasks'] if item['operation_id'] == accepted['operation_id']]
        self.assertEqual({old['id'], accepted['id']}, {item['admission_id'] for item in items})
        self.assertTrue(all(item['record_source'] == 'admission' and item['state'] == 'PREPARING' for item in items))
        plan = build_plan(self.f.manifest)
        with patch.object(preparations, 'observe_reboot_closure', side_effect=AssertionError('never dispatched')):
            result = self.coordinator(plan).apply(plan)
        self.assertEqual('COMMITTED', result['decision'])
        self.assertTrue(result['released'], result['waiting'])
        self.assertEqual('OPEN', self.f.gate.snapshot()['state'])
        self.assertEqual({'never_dispatched': True}, self.f.gate.snapshot()['responsibilities'][accepted['id']]['proof'])
        self.assertEqual(before['tasks'], preparations.inventory(self.f.profile)['tasks'])
        self.assertFalse((Path(accepted['attempt_id']).parent / 'current.json').exists())
        self.assertEqual([], list(Path(accepted['attempt_id']).iterdir()))
        self.assertEqual(originals, (self.record_path.read_bytes(), self.launch_path.read_bytes()))
        self.assertEqual([self.operation], [item['operation_id'] for item in result['checks']['released_compatibility']])

    def test_missing_current_does_not_hide_an_unmatched_attempt(self):
        receipt = self.half_created_preparation()
        (Path(receipt['attempt_id']).parent / 'attempt-2').mkdir(mode=0o700)
        with self.assertRaisesRegex(Exception, 'Original preparation'):
            build_plan(self.f.manifest)
        self.assertEqual('ACCEPTED', self.f.gate.snapshot()['responsibilities'][receipt['id']]['state'])

    def test_missing_current_does_not_hide_dispatched_or_completed_attempt(self):
        receipt = self.half_created_preparation()
        self.f.gate.dispatch(receipt)
        with self.assertRaisesRegex(Exception, 'Original preparation'):
            build_plan(self.f.manifest)
        self.f.gate.finish(receipt, {'process_exited': True, 'writers_stopped': True})
        with self.assertRaisesRegex(Exception, 'Original preparation'):
            build_plan(self.f.manifest)

    def test_missing_current_still_requires_one_original_principal_and_root(self):
        self.half_created_preparation()
        self.half_created_preparation(serial=2, principal='other')
        with self.assertRaisesRegex(Exception, 'Original preparation'):
            build_plan(self.f.manifest)

    def test_missing_current_inventory_limits_admission_count(self):
        self.half_created_preparation()
        with patch.object(preparations, 'MAX_ORPHAN_ENTRIES', 0), \
                self.assertRaisesRegex(Exception, 'budget'):
            build_plan(self.f.manifest)

    def test_missing_current_rejects_a_foreign_root(self):
        receipt = self.half_created_preparation(wrong_root=True)
        with self.assertRaisesRegex(Exception, 'binding'):
            build_plan(self.f.manifest)
        # The original binding remains foreign even if its task directory is
        # present; do not repair it from today's configuration.
        self.assertEqual('ACCEPTED', self.f.gate.snapshot()['responsibilities'][receipt['id']]['state'])

    def test_missing_current_never_ignores_files_inside_an_unstarted_attempt(self):
        receipt = self.half_created_preparation()
        original = Path(receipt['attempt_id']) / 'result.json'
        self.f.write(original, {'unexpected': 'retained bytes'})
        saved = original.read_bytes()
        with self.assertRaisesRegex(Exception, 'unexplained attempt content'):
            build_plan(self.f.manifest)
        self.assertEqual(saved, original.read_bytes())

    def test_original_attempt_does_not_adopt_a_conflicting_current_boot(self):
        receipt, environment = self.preparation_duty(dispatched=True)
        self.f.write(self.record_path, {**self.record, 'attempt': receipt['attempt_id'],
                                       'boot_id': startup.boot_id()})
        with patch.object(preparations, 'observe_reboot_closure', side_effect=AssertionError('identity mismatch')):
            with self.assertRaisesRegex(Exception, 'binding'):
                environment.drain({'id': 'drain-orphan'})
        self.assertEqual('DISPATCHING', self.f.gate.snapshot()['responsibilities'][receipt['id']]['state'])

    def test_missing_current_rejects_any_retained_execution_history(self):
        receipt = self.half_created_preparation()
        prepared = dict(self.prepared, operation_id=receipt['operation_id'], attempt_id=receipt['attempt_id'],
                        boot_id=receipt['loaded']['boot_id'])
        execution = self.f.gate.accept('execute', receipt['operation_id'], 'old-execution', {'prepared': prepared},
                                       receipt['loaded'], prepared=prepared)
        for state in ('ACCEPTED', 'DISPATCHING', 'CLOSED'):
            with self.subTest(state=state):
                if state == 'DISPATCHING':
                    self.f.gate.dispatch(execution)
                elif state == 'CLOSED':
                    self.f.gate.finish(execution, {'process_exited': True, 'writers_stopped': True})
                with self.assertRaisesRegex(Exception, 'retained execution history'):
                    build_plan(self.f.manifest)

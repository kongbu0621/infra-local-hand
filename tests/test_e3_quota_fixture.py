"""Offline Q1 snapshot/geometry checks; no actual host admission or queries."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from admin.local_hand_quota_observer import admission as a, fixture_inputs as f, protected_inputs as p
from admin.local_hand_quota_observer import systemd_runtime as r
from test_e3_quota_monitor import binding, decode, encoded, fixture, NOW
from test_e3_quota_worker import runtime_value


def documents():
    manifest, runtime = fixture(), runtime_value()
    manifest['cgroup_parent'] = '/' + runtime['query_slice']
    return manifest, runtime


def make_inputs(manifest=None, runtime=None):
    default_manifest, default_runtime = documents()
    manifest = deepcopy(default_manifest if manifest is None else manifest)
    runtime = deepcopy(default_runtime if runtime is None else runtime)
    raw = encoded(runtime)
    config = p.decode_runtime(raw, hashlib.sha256(raw).hexdigest())
    manifest['installation_digest'] = p.installation_digest(config)
    manifest_bytes = encoded(manifest)
    runtime['manifest_digest'] = hashlib.sha256(manifest_bytes).hexdigest()
    runtime_bytes = encoded(runtime)
    return dict(manifest_bytes=manifest_bytes, runtime_bytes=runtime_bytes,
                manifest_digest=hashlib.sha256(manifest_bytes).hexdigest(),
                runtime_digest=hashlib.sha256(runtime_bytes).hexdigest(),
                expected_source_commit=manifest['source_commit'],
                runtime_path='/synthetic/admin/runtime.json', journal_path='/synthetic/control')


def second_slot(manifest, path='/synthetic/quota/other'):
    slot = deepcopy(manifest['slots'][0])
    slot.update(ref='other-root', path=path)
    slot['root']['inode'] += 1
    manifest['slots'].append(slot)
    return slot


def replace_snapshot(arguments, name, **changes):
    value = json.loads(arguments[name + '_bytes'])
    value.update(changes)
    raw = encoded(value)
    return dict(arguments, **{name + '_bytes': raw, name + '_digest': hashlib.sha256(raw).hexdigest()})


class OfflineFixtureTests(unittest.TestCase):
    def test_valid_snapshots_are_immutable_and_never_create_permissions_or_tickets(self):
        arguments = make_inputs()
        with patch('builtins.open', side_effect=AssertionError('offline validation opened a file')), \
             patch.object(p.os, 'open', side_effect=AssertionError('opened declared host path')), \
             patch.object(p, 'bind_query', side_effect=AssertionError('created request')):
            result = f.validate_fixture_inputs(**arguments)
        with self.assertRaises(FrozenInstanceError):
            result.manifest = None
        summary = result.as_dict()
        self.assertEqual((summary['status'], summary['evidence_class'], summary['host_readiness']),
                         ('CONFIG_CONSISTENT', 'OFFLINE_ONLY', 'NOT_VERIFIED'))
        for key in ('admission_proven', 'real_e3_accepted', 'production_supported'):
            self.assertIs(summary[key], False)
        self.assertEqual(summary['slot_count'], 1)
        self.assertEqual(summary['declared_hard_capacity_bytes'], 123 * 1024)
        self.assertEqual(summary['query_limits']['max_query_ns'], 2_000_000_000)
        self.assertEqual(summary['query_limits']['max_output_bytes'], 8192)
        raw = json.dumps(summary)
        for private in ('/synthetic/', result.manifest.boot_id, 'request_id', 'issued_ns', 'deadline_ns'):
            self.assertNotIn(private, raw)
        self.assertLess(len(raw.encode()), 4096)
        summary['unverified'].clear()
        self.assertTrue(result.as_dict()['unverified'])
        self.assertFalse(hasattr(result, 'run'))

    def test_external_digests_pin_exact_bytes_including_whitespace(self):
        for name in ('manifest', 'runtime'):
            arguments = make_inputs()
            arguments[name + '_bytes'] += b' '
            with self.subTest(name=name), self.assertRaisesRegex(a.Rejected, name.upper() + '_DIGEST'):
                f.validate_fixture_inputs(**arguments)

    def test_individually_valid_documents_cannot_disagree_about_manifest_or_installation(self):
        arguments = replace_snapshot(make_inputs(), 'runtime', manifest_digest='a' * 64)
        with self.assertRaisesRegex(a.Rejected, 'MANIFEST_BINDING'):
            f.validate_fixture_inputs(**arguments)
        arguments = replace_snapshot(make_inputs(), 'runtime', native_sha256='a' * 64)
        with self.assertRaisesRegex(a.Rejected, 'INSTALLATION_BINDING'):
            f.validate_fixture_inputs(**arguments)

    def test_exact_external_source_commit_is_required(self):
        for value, code in [('HEAD', 'TOKEN'), ('c' * 7, 'TOKEN'), ('a' * 40, 'SOURCE_COMMIT_CHANGED')]:
            with self.subTest(value=value), self.assertRaisesRegex(a.Rejected, code):
                f.validate_fixture_inputs(**dict(make_inputs(), expected_source_commit=value))

    def test_shared_billing_domains_are_counted_once_without_granting_reuse(self):
        manifest, runtime = documents()
        extra = second_slot(manifest)
        summary = f.validate_fixture_inputs(**make_inputs(manifest, runtime)).as_dict()
        self.assertEqual((summary['slot_count'], summary['billing_domain_count'],
                          summary['declared_hard_capacity_bytes']), (2, 1, 123 * 1024))
        extra['project_id'] += 1
        summary = f.validate_fixture_inputs(**make_inputs(manifest, runtime)).as_dict()
        self.assertEqual((summary['billing_domain_count'], summary['declared_hard_capacity_bytes']),
                         (2, 246 * 1024))
        self.assertIs(summary['admission_proven'], False)

    def test_unselected_slot_cannot_overlap_journal_or_any_fixed_input(self):
        cases = [('/synthetic/control/slot', 'ROOT_CONTROL_OVERLAP'),
                 ('/synthetic/admin', 'ROOT_INPUT_OVERLAP'),
                 ('/synthetic/bin/python3/root', 'ROOT_INPUT_OVERLAP')]
        for location, code in cases:
            manifest, runtime = documents()
            second_slot(manifest, location)
            arguments = make_inputs(manifest, runtime)
            with self.subTest(location=location), self.assertRaisesRegex(a.Rejected, code):
                f.validate_fixture_inputs(**arguments)
            # The actual runtime's selected first slot also rejects a conflicting
            # *unselected* slot, via exactly the same shared geometry function.
            mf = a.decode_manifest(arguments['manifest_bytes'], arguments['manifest_digest'])
            config = p.decode_runtime(arguments['runtime_bytes'], arguments['runtime_digest'])
            with self.assertRaisesRegex(a.Rejected, code):
                r.unit_command(config, binding(mf), arguments['runtime_path'], arguments['journal_path'],
                               now_ns=NOW)

    def test_fixed_regular_files_cannot_alias_or_be_parent_directories(self):
        for location in ('/synthetic/admin/manifest.json', '/synthetic/admin/worker.py',
                         '/synthetic/admin/protected_inputs.py', '/synthetic/admin/worker.py/nested'):
            with self.subTest(location=location), self.assertRaisesRegex(a.Rejected, 'FIXED_INPUT_OVERLAP'):
                f.validate_fixture_inputs(**dict(make_inputs(), runtime_path=location))
        manifest, runtime = documents()
        runtime['native_path'] = '/synthetic/admin/supervision.py'
        with self.assertRaisesRegex(a.Rejected, 'FIXED_INPUT_OVERLAP'):
            f.validate_fixture_inputs(**make_inputs(manifest, runtime))

    def test_all_package_sources_are_protected_from_root_and_journal_overlap(self):
        for filename in p.PACKAGE_FILES:
            with self.subTest(filename=filename), self.assertRaisesRegex(a.Rejected, 'CONTROL_INPUT_OVERLAP'):
                f.validate_fixture_inputs(**dict(make_inputs(), journal_path='/synthetic/admin/' + filename))

    def test_component_siblings_are_allowed_but_uncanonical_paths_are_not(self):
        arguments = dict(make_inputs(), journal_path='/synthetic/admin-control')
        self.assertEqual(f.validate_fixture_inputs(**arguments).as_dict()['status'], 'CONFIG_CONSISTENT')
        for key in ('runtime_path', 'journal_path'):
            for value in ('relative/path', '/', '/synthetic/../escape', '/synthetic/x%y', '//synthetic/a'):
                with self.subTest(key=key, value=value), self.assertRaises(a.Rejected):
                    f.validate_fixture_inputs(**dict(make_inputs(), **{key: value}))

    def test_query_slice_and_administrator_identity_must_match(self):
        for key, value, code in [('cgroup_parent', '/different.slice', 'DEDICATED_SLICE_REQUIRED'),
                                 ('query_uid', 1501, 'ADMIN_QUERY_UID_REQUIRED'),
                                 ('query_euid', 1501, 'ADMIN_QUERY_UID_REQUIRED')]:
            manifest, runtime = documents()
            manifest[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(a.Rejected, code):
                f.validate_fixture_inputs(**make_inputs(manifest, runtime))

    def test_runtime_rejects_a_foreign_selected_slot_even_with_valid_manifest(self):
        arguments = make_inputs()
        result = f.validate_fixture_inputs(**arguments)
        bound = binding(result.manifest)
        foreign = replace(bound.slot, path='/synthetic/elsewhere')
        with self.assertRaisesRegex(a.Rejected, 'FOREIGN_SLOT'):
            r.unit_command(result.runtime, replace(bound, slot=foreign), arguments['runtime_path'],
                           arguments['journal_path'], now_ns=NOW)


if __name__ == '__main__':
    unittest.main()

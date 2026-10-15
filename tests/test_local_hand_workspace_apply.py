"""Local landing uses real Git, CAS and fixed validators; old jobs are not run."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from config_fixtures import profile_v2
from local_hand import act, workspace_apply as landing
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError


class WorkspaceApplyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'demo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Local test')
        self.git('config', 'user.email', 'local@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.before = b'VALUE = 1\n'
        self.after = b'VALUE = 2\n'
        (self.repo / 'sample.py').write_bytes(self.before)
        (self.repo / 'other.txt').write_bytes(b'original\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'baseline')
        self.head = self.git('rev-parse', 'HEAD').decode().strip()
        self.result = dict(schema_version='lh-workspace-edit-v1', source_ref='demo',
            source_commit=self.head, relative_path='sample.py',
            before_sha256=hashlib.sha256(self.before).hexdigest(),
            after_sha256=hashlib.sha256(self.after).hexdigest(), validation_ref='core',
            scope='TASK_OWNED_COPY', original_modified=False, read_back_verified=True,
            validation_succeeded=True, edited_file_unchanged_by_validation=True,
            git_status=' M sample.py\n')
        self.result_path = self.root / 'workspace-result.json'
        self.before_path = self.root / 'before.txt'
        self.after_path = self.root / 'after.txt'
        self.before_path.write_bytes(self.before)
        self.after_path.write_bytes(self.after)
        self.profile_path = self.root / 'profile.json'
        self.set_validation("from pathlib import Path; assert Path('sample.py').read_bytes() == b'VALUE = 2\\n'")
        self.attempt = 0

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, stderr=subprocess.PIPE)

    def set_validation(self, code):
        data = profile_v2(dict(node_id='test', projects_root=str(self.root), repositories={
            'demo': dict(path='demo', single_writer=True, validations={
                'core': dict(argv=[sys.executable, '-I', '-B', '-c', code],
                             timeout_seconds=5, replay_safe=True)})}))
        self.profile_path.write_text(json.dumps(data))
        self.profile = load_profile(self.profile_path)

    def apply(self, **overrides):
        raw = json.dumps(self.result).encode()
        self.result_path.write_bytes(raw)
        self.attempt += 1
        args = dict(result_path=self.result_path, result_sha256=hashlib.sha256(raw).hexdigest(),
            before_path=self.before_path, after_path=self.after_path, expected_head=self.head,
            output=self.root / ('attempt-' + str(self.attempt)))
        args.update(overrides)
        return landing.apply_result(self.profile, 'demo', **args)

    def test_apply_preserves_unrelated_staged_unstaged_and_untracked_files(self):
        (self.repo / 'other.txt').write_bytes(b'staged\n')
        self.git('add', 'other.txt')
        (self.repo / 'other.txt').write_bytes(b'unstaged\n')
        (self.repo / 'notes.txt').write_bytes(b'private notes\n')
        index = self.git('ls-files', '--stage')
        outcome = self.apply()
        self.assertEqual('APPLIED', outcome['status'], outcome)
        self.assertEqual(0, outcome['validation']['exit_code'])
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())
        self.assertEqual(index, self.git('ls-files', '--stage'))
        self.assertEqual(b'unstaged\n', (self.repo / 'other.txt').read_bytes())
        self.assertEqual(b'private notes\n', (self.repo / 'notes.txt').read_bytes())
        self.assertIn(b'+VALUE = 2', (self.root / 'attempt-1/final.patch').read_bytes())
        self.assertEqual(self.before, (self.root / 'attempt-1/observed-before.txt').read_bytes())

    def test_later_unrelated_commit_is_allowed_with_exact_observed_head(self):
        (self.repo / 'other.txt').write_bytes(b'committed update\n')
        self.git('add', 'other.txt')
        self.git('commit', '-qm', 'unrelated')
        current = self.git('rev-parse', 'HEAD').decode().strip()
        self.assertEqual('APPLIED', self.apply(expected_head=current)['status'])

    def test_failed_validation_can_retry_without_a_second_write(self):
        self.set_validation("import sys; print('retained failure'); sys.exit(3)")
        first = self.apply()
        self.assertEqual('VALIDATION_FAILED', first['status'])
        self.assertEqual(3, first['validation']['exit_code'])
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())
        self.set_validation("from pathlib import Path; assert Path('sample.py').read_bytes() == b'VALUE = 2\\n'")
        with patch.object(act, 'fs_write_text_cas', side_effect=AssertionError('duplicate write')):
            second = self.apply()
        self.assertEqual('ALREADY_APPLIED', second['status'])
        self.assertEqual(0, second['validation']['exit_code'])
        self.assertFalse(second['write_attempted'])
        self.assertEqual('VALIDATION_FAILED', json.loads((self.root / 'attempt-1/report.json').read_bytes())['status'])

    def test_target_change_and_staged_target_conflict_are_retained(self):
        for staged in (False, True):
            with self.subTest(staged=staged):
                changed = b'VALUE = 99\n'
                (self.repo / 'sample.py').write_bytes(changed)
                if staged:
                    self.git('add', 'sample.py')
                    (self.repo / 'sample.py').write_bytes(self.before)
                expected = (self.repo / 'sample.py').read_bytes()
                index = self.git('ls-files', '--stage')
                outcome = self.apply()
                self.assertEqual('CONFLICT', outcome['status'])
                self.assertFalse(outcome['write_attempted'])
                self.assertIsNone(outcome['validation'])
                self.assertEqual(expected, (self.repo / 'sample.py').read_bytes())
                self.assertEqual(index, self.git('ls-files', '--stage'))

    def test_unverified_inputs_or_changed_head_never_write(self):
        for field, value in [('result_sha256', '0'*64), ('expected_head', '0'*40)]:
            with self.subTest(field=field):
                outcome = self.apply(**{field:value})
                self.assertEqual('CONFLICT', outcome['status'])
                self.assertFalse(outcome['write_attempted'])
        self.after_path.write_bytes(b'other bytes\n')
        self.assertEqual('CONFLICT', self.apply()['status'])
        self.assertEqual(self.before, (self.repo / 'sample.py').read_bytes())

    def test_failed_remote_validation_and_escape_are_rejected(self):
        for key, value in [('validation_succeeded', False), ('relative_path', '../escape'),
                           ('source_ref', 'different-project'), ('relative_path', '.git/config'),
                           ('relative_path', ['sample.py'])]:
            previous = self.result[key]
            self.result[key] = value
            with self.subTest(key=key, value=value):
                result = self.apply()
                self.assertEqual('FAILED', result['status'])
                self.assertFalse(result['write_attempted'])
            self.result[key] = previous
        self.assertEqual(self.before, (self.repo / 'sample.py').read_bytes())

    @unittest.skipIf(os.name == 'nt', 'symlink creation requires Windows privilege')
    def test_symlink_target_is_never_followed(self):
        target = self.repo / 'sample.py'
        target.unlink()
        target.symlink_to(self.before_path)
        self.assertEqual('FAILED', self.apply()['status'])
        self.assertEqual(self.before, self.before_path.read_bytes())

    def test_validator_mutation_is_retained_and_not_reported_as_success(self):
        self.set_validation("from pathlib import Path; Path('sample.py').write_bytes(b'VALUE = 3\\n')")
        outcome = self.apply()
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertEqual(b'VALUE = 3\n', (self.repo / 'sample.py').read_bytes())
        self.assertIn(b'+VALUE = 3', (self.root / 'attempt-1/final.patch').read_bytes())

    def test_uncertain_write_is_reconciled_from_bytes_before_retry(self):
        original = act.fs_write_text_cas
        def uncertain(*args, **kwargs):
            original(*args, **kwargs)
            raise LocalHandError('write_durability_unconfirmed', 'injected sync failure', 'indeterminate')
        with patch.object(act, 'fs_write_text_cas', side_effect=uncertain):
            outcome = self.apply()
        self.assertEqual('UNCONFIRMED', outcome['status'])
        self.assertTrue(json.loads((self.root / 'attempt-1/intent.json').read_bytes())['write_planned'])
        with patch.object(act, 'fs_write_text_cas', side_effect=AssertionError('duplicate write')):
            self.assertEqual('ALREADY_APPLIED', self.apply()['status'])

    def test_head_moved_after_write_is_detected_without_rollback(self):
        original = act.fs_write_text_cas
        def changed_head(*args, **kwargs):
            value = original(*args, **kwargs)
            self.git('commit', '--allow-empty', '-qm', 'concurrent head update')
            return value
        with patch.object(act, 'fs_write_text_cas', side_effect=changed_head):
            outcome = self.apply()
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())

    def test_final_observation_cannot_report_success_for_changed_target(self):
        original = landing.observe.git_status
        calls = 0
        def changed_at_final(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                (self.repo / 'sample.py').write_bytes(b'VALUE = 4\n')
            return original(*args, **kwargs)
        with patch.object(landing.observe, 'git_status', side_effect=changed_at_final):
            outcome = self.apply()
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertEqual(hashlib.sha256(b'VALUE = 4\n').hexdigest(), outcome['final_target_sha256'])

    def test_cli_writes_a_report_and_refuses_reusing_attempt_directory(self):
        raw = json.dumps(self.result).encode()
        self.result_path.write_bytes(raw)
        output = self.root / 'cli-attempt'
        tools = Path(landing.__file__).resolve().parents[1]
        bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from local_hand.workspace_apply import main;sys.exit(main())'
        command = [sys.executable, '-I', '-B', '-c', bootstrap, str(tools),
            '--profile', str(self.profile_path), '--repository', 'demo',
            '--result', str(self.result_path), '--result-sha256', hashlib.sha256(raw).hexdigest(),
            '--before', str(self.before_path), '--after', str(self.after_path),
            '--expected-head', self.head, '--output', str(output)]
        first = subprocess.run(command, capture_output=True, timeout=20)
        self.assertEqual(0, first.returncode, (first.stdout + first.stderr).decode())
        saved = (output / 'report.json').read_bytes()
        second = subprocess.run(command, capture_output=True, timeout=20)
        self.assertEqual(1, second.returncode)
        self.assertEqual(saved, (output / 'report.json').read_bytes())

    def test_staged_revert_of_newer_committed_target_is_not_overwritten(self):
        (self.repo / 'sample.py').write_bytes(b'VALUE = 99\n')
        self.git('add', 'sample.py')
        self.git('commit', '-qm', 'newer target')
        head = self.git('rev-parse', 'HEAD').decode().strip()
        (self.repo / 'sample.py').write_bytes(self.before)
        self.git('add', 'sample.py')
        outcome = self.apply(expected_head=head)
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertFalse(outcome['write_attempted'])
        self.assertEqual(self.before, (self.repo / 'sample.py').read_bytes())

    def test_final_head_change_does_not_report_success(self):
        original = landing.observe.git_status
        calls = 0
        def move_head(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.git('commit', '--allow-empty', '-qm', 'late head movement')
            return original(*args, **kwargs)
        with patch.object(landing.observe, 'git_status', side_effect=move_head):
            outcome = self.apply()
        self.assertEqual('CONFLICT', outcome['status'])

    def test_validator_changes_to_other_files_are_reported(self):
        self.set_validation("from pathlib import Path; Path('other.txt').write_bytes(b'validator changed this\\n')")
        outcome = self.apply()
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertEqual(b'validator changed this\n', (self.repo / 'other.txt').read_bytes())

    def test_report_write_failure_preserves_applied_state_in_return(self):
        original = landing._save
        def fail_report(root, name, raw):
            if name == 'report.json':
                raise OSError('injected report storage failure')
            return original(root, name, raw)
        with patch.object(landing, '_save', side_effect=fail_report):
            outcome = self.apply()
        self.assertEqual('UNCONFIRMED', outcome['status'])
        self.assertTrue(outcome['write_attempted'])
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())
        self.assertEqual(0, outcome['validation']['exit_code'])

    def test_cooperative_write_is_blocked_while_validation_is_running(self):
        original = landing.validate.run_profile
        def other_writer(*args, **kwargs):
            with self.assertRaises(LocalHandError) as caught:
                act.fs_write_text_cas(self.profile, 'demo', 'other.txt',
                    hashlib.sha256(b'original\n').hexdigest(), 'other writer\n')
            self.assertEqual('workspace_lease_busy', caught.exception.code)
            return original(*args, **kwargs)
        with patch.object(landing.validate, 'run_profile', side_effect=other_writer):
            outcome = self.apply()
        self.assertEqual('APPLIED', outcome['status'])

    def test_validation_interrupt_retains_an_unknown_completion(self):
        with patch.object(landing.validate, 'run_profile', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        report = json.loads((self.root / 'attempt-1/report.json').read_bytes())
        self.assertEqual('UNCONFIRMED', report['status'])
        self.assertTrue(report['write_attempted'])
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())

    def test_already_applied_sync_failure_stays_unconfirmed_without_rewriting(self):
        self.assertEqual('APPLIED', self.apply()['status'])
        original = landing._sync_directory
        def fail_target_sync(path):
            if path == self.repo:
                raise OSError('injected target directory fsync failure')
            return original(path)
        with patch.object(landing, '_sync_directory', side_effect=fail_target_sync), \
             patch.object(act, 'fs_write_text_cas', side_effect=AssertionError('duplicate write')):
            outcome = self.apply()
        self.assertEqual('UNCONFIRMED', outcome['status'])
        self.assertFalse(outcome['write_attempted'])
        self.assertIsNone(outcome['validation'])
        self.assertEqual('ALREADY_APPLIED', self.apply()['status'])

    def test_intent_storage_failure_proves_cas_was_not_called(self):
        original = landing._save
        def fail_intent(root, name, raw):
            if name == 'intent.json':
                raise OSError('injected intent failure')
            return original(root, name, raw)
        with patch.object(landing, '_save', side_effect=fail_intent), \
             patch.object(act, 'fs_write_text_cas', side_effect=AssertionError('unexpected write')):
            outcome = self.apply()
        self.assertFalse(outcome['write_attempted'])
        self.assertEqual(self.before, (self.repo / 'sample.py').read_bytes())

    def test_report_file_is_not_published_when_file_sync_fails(self):
        out = self.root / 'save-fault'
        out.mkdir()
        with patch.object(landing.os, 'fsync', side_effect=OSError('injected fsync failure')):
            with self.assertRaises(OSError):
                landing._save(out, 'report.json', b'{"status":"APPLIED"}')
        self.assertFalse((out / 'report.json').exists())
        self.assertEqual(b'{"status":"APPLIED"}', (out / '.report.json.pending').read_bytes())

    def test_released_lease_cannot_bypass_cas_lock(self):
        with act._repository_write_lease(self.repo, None) as lease:
            act.fs_write_text_cas(self.profile, 'demo', 'sample.py', self.result['before_sha256'],
                                 self.after.decode(), _lease=lease)
        with self.assertRaises(LocalHandError) as caught:
            act.fs_write_text_cas(self.profile, 'demo', 'sample.py', self.result['before_sha256'],
                                 self.after.decode(), _lease=lease)
        self.assertEqual('workspace_lease_invalid', caught.exception.code)

    def test_untracked_file_edit_by_validator_is_not_silent_success(self):
        (self.repo / 'notes.txt').write_bytes(b'original notes\n')
        self.set_validation("from pathlib import Path; Path('notes.txt').write_bytes(b'new notes\\n')")
        self.assertEqual('CONFLICT', self.apply()['status'])
        self.assertEqual(b'new notes\n', (self.repo / 'notes.txt').read_bytes())

    def test_binary_git_diff_reconstructs_valid_utf8_with_nul(self):
        self.after = b'VALUE = 2\r\n# \xe4\xb8\xad\x00\r\n'
        self.after_path.write_bytes(self.after)
        self.result['after_sha256'] = hashlib.sha256(self.after).hexdigest()
        self.set_validation("from pathlib import Path; assert Path('sample.py').read_bytes() == " + repr(self.after))
        outcome = self.apply()
        self.assertEqual('APPLIED', outcome['status'])
        patch_path = self.root / 'attempt-1/final.patch'
        self.assertIn(b'GIT binary patch', patch_path.read_bytes())
        (self.repo / 'sample.py').write_bytes(self.before)
        self.git('apply', str(patch_path))
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())

    def test_returned_patch_applies_despite_repository_diff_display_settings(self):
        self.before = b'HEADER = 0\nVALUE = 1\nFOOTER = 3\n'
        self.after = b'HEADER = 0\nVALUE = 2\nFOOTER = 3\n'
        (self.repo / 'sample.py').write_bytes(self.before)
        self.git('add', 'sample.py')
        self.git('commit', '-qm', 'multiline baseline')
        self.head = self.git('rev-parse', 'HEAD').decode().strip()
        self.result.update(source_commit=self.head,
            before_sha256=hashlib.sha256(self.before).hexdigest(),
            after_sha256=hashlib.sha256(self.after).hexdigest())
        self.before_path.write_bytes(self.before)
        self.after_path.write_bytes(self.after)
        self.set_validation("from pathlib import Path; assert Path('sample.py').read_bytes() == " + repr(self.after))
        for key, value in [('color.ui', 'always'), ('color.diff', 'always'),
                           ('diff.noprefix', 'true'), ('diff.context', '0')]:
            with self.subTest(config=key):
                (self.repo / 'sample.py').write_bytes(self.before)
                self.git('config', key, value)
                try:
                    config = (self.repo / '.git/config').read_bytes()
                    outcome = self.apply()
                    self.assertEqual('APPLIED', outcome['status'])
                    patch_path = self.root / f'attempt-{self.attempt}/final.patch'
                    # Exercise the consumer with ordinary Git defaults, not a
                    # workaround that strips color or accepts context-free diffs.
                    (self.repo / 'sample.py').write_bytes(self.before)
                    self.git('apply', str(patch_path))
                    self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())
                    self.assertEqual(config, (self.repo / '.git/config').read_bytes())
                finally:
                    self.git('config', '--unset', key)

    def test_two_real_cli_processes_share_the_full_validation_lease(self):
        ready, release = self.root / 'ready', self.root / 'release'
        code = ("from pathlib import Path; import time; "
            f"Path({str(ready)!r}).touch(); limit=time.monotonic()+15; "
            f"release=Path({str(release)!r})\n"
            "while not release.exists() and time.monotonic()<limit: time.sleep(0.02)\n"
            "assert release.exists()\n")
        self.set_validation(code)
        # The fixture's default 5s profile is too short for starting a second CLI.
        data = json.loads(self.profile_path.read_bytes())
        data['repositories']['demo']['validations']['core']['timeout_seconds'] = 20
        self.profile_path.write_text(json.dumps(data))
        raw = json.dumps(self.result).encode()
        self.result_path.write_bytes(raw)
        tools = Path(landing.__file__).resolve().parents[1]
        bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from local_hand.workspace_apply import main;sys.exit(main())'
        command = [sys.executable, '-I', '-B', '-c', bootstrap, str(tools),
            '--profile', str(self.profile_path), '--repository', 'demo',
            '--result', str(self.result_path), '--result-sha256', hashlib.sha256(raw).hexdigest(),
            '--before', str(self.before_path), '--after', str(self.after_path), '--expected-head', self.head]
        process = subprocess.Popen([*command, '--output', str(self.root / 'first-cli')],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists())
            second = subprocess.run([*command, '--output', str(self.root / 'second-cli')],
                capture_output=True, timeout=10)
            self.assertEqual(1, second.returncode, second.stderr.decode())
            report = json.loads((self.root / 'second-cli/report.json').read_bytes())
            self.assertEqual('workspace_lease_busy', report['error']['code'])
            self.assertFalse(report['write_attempted'])
            self.assertIsNone(report['validation'])
        finally:
            release.touch()
            stdout, stderr = process.communicate(timeout=25)
        self.assertEqual(0, process.returncode, stderr.decode())
        self.assertEqual('APPLIED', json.loads(stdout)['status'])

    def test_staged_revert_is_conflict_even_when_worktree_matches_after(self):
        target = self.repo / 'sample.py'
        target.write_bytes(self.after)
        self.git('add', 'sample.py')
        self.git('commit', '-qm', 'edit already committed')
        head = self.git('rev-parse', 'HEAD').decode().strip()
        target.write_bytes(self.before)
        self.git('add', 'sample.py')
        target.write_bytes(self.after)
        outcome = self.apply(expected_head=head)
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertFalse(outcome['write_attempted'])

    @unittest.skipIf(os.name == 'nt', 'POSIX file modes')
    def test_staged_mode_change_and_validation_mode_change_are_not_success(self):
        self.git('update-index', '--chmod=+x', 'sample.py')
        self.assertEqual('CONFLICT', self.apply()['status'])
        self.git('update-index', '--chmod=-x', 'sample.py')
        self.set_validation("import os; os.chmod('sample.py', 0o600)")
        self.assertEqual('CONFLICT', self.apply()['status'])
        self.assertEqual(0o600, (self.repo / 'sample.py').stat().st_mode & 0o777)

    def test_matching_after_image_already_staged_or_committed_is_idempotent(self):
        target = self.repo / 'sample.py'
        target.write_bytes(self.after)
        self.git('add', 'sample.py')
        self.assertEqual('ALREADY_APPLIED', self.apply()['status'])
        self.git('commit', '-qm', 'edit committed')
        head = self.git('rev-parse', 'HEAD').decode().strip()
        self.assertEqual('ALREADY_APPLIED', self.apply(expected_head=head)['status'])

    def test_final_observation_interrupt_still_releases_lease_and_retains_unknown(self):
        original = landing.observe.git_status
        calls = 0
        def interrupt_final(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt
            return original(*args, **kwargs)
        with patch.object(landing.observe, 'git_status', side_effect=interrupt_final):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        report = json.loads((self.root / 'attempt-1/report.json').read_bytes())
        self.assertEqual('UNCONFIRMED', report['status'])
        with act._repository_write_lease(self.repo, None):
            pass

    def test_unexpected_exception_retains_write_state_and_is_not_swallowed(self):
        with patch.object(landing.validate, 'run_profile', side_effect=RuntimeError('injected unexpected failure')):
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                self.apply()
        report = json.loads((self.root / 'attempt-1/report.json').read_bytes())
        self.assertEqual('UNCONFIRMED', report['status'])
        self.assertTrue(report['write_attempted'])
        with act._repository_write_lease(self.repo, None):
            pass

    def test_replace_refs_cannot_hide_a_newer_committed_target(self):
        (self.repo / 'sample.py').write_bytes(b'VALUE = 99\n')
        self.git('add', 'sample.py')
        self.git('commit', '-qm', 'newer target')
        newer = self.git('rev-parse', 'HEAD').decode().strip()
        replacement = self.git('commit-tree', self.head + '^{tree}', '-p', self.head,
                               '-m', 'alternate history').decode().strip()
        self.git('replace', newer, replacement)
        (self.repo / 'sample.py').write_bytes(self.before)
        self.git('add', 'sample.py')
        outcome = self.apply(expected_head=newer)
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertFalse(outcome['write_attempted'])
        self.assertEqual(self.before, (self.repo / 'sample.py').read_bytes())

    def test_grafts_cannot_fabricate_source_ancestry(self):
        unrelated = self.git('commit-tree', self.head + '^{tree}', '-m',
                             'independent root').decode().strip()
        self.git('update-ref', 'HEAD', unrelated)
        (self.repo / '.git/info/grafts').write_text(unrelated + ' ' + self.head + '\n')
        outcome = self.apply(expected_head=unrelated)
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertFalse(outcome['write_attempted'])
        self.assertEqual(self.before, (self.repo / 'sample.py').read_bytes())

    def test_valid_edit_and_status_use_stored_objects_without_removing_replace_refs(self):
        (self.repo / 'sample.py').write_bytes(b'VALUE = 99\n')
        self.git('add', 'sample.py')
        tree = self.git('write-tree').decode().strip()
        replacement = self.git('commit-tree', tree, '-m', 'local overlay').decode().strip()
        (self.repo / 'sample.py').write_bytes(self.before)
        self.git('add', 'sample.py')
        self.git('replace', self.head, replacement)
        outcome = self.apply()
        self.assertEqual('APPLIED', outcome['status'])
        status = json.loads((self.root / 'attempt-1/status-after.json').read_bytes())
        self.assertEqual([' M sample.py'], status['lines'][1:])
        self.assertEqual(replacement,
                         self.git('rev-parse', 'refs/replace/' + self.head).decode().strip())

    @unittest.skipIf(os.name == 'nt', 'POSIX permits moving the validation cwd')
    def test_replaced_checkout_identity_cannot_report_success(self):
        self.set_validation("from pathlib import Path; import shutil; "
            "p = Path.cwd(); old = p.with_name('retained-checkout'); "
            "p.rename(old); shutil.copytree(old, p)")
        outcome = self.apply()
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertEqual(self.after, (self.root / 'retained-checkout/sample.py').read_bytes())
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())

    def test_replaced_attempt_directory_cannot_receive_a_success_report(self):
        self.set_validation("from pathlib import Path; p = Path.cwd().parent / 'attempt-1'; "
            "p.rename(p.with_name('retained-attempt')); p.mkdir()")
        outcome = self.apply()
        self.assertEqual('UNCONFIRMED', outcome['status'])
        self.assertTrue(outcome['write_attempted'])
        self.assertEqual([], list((self.root / 'attempt-1').iterdir()))
        self.assertEqual(self.before, (self.root / 'retained-attempt/before.txt').read_bytes())
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())

    def test_validation_rewrite_requires_final_file_synchronization(self):
        self.set_validation("from pathlib import Path; p = Path('sample.py'); "
            "tmp = p.with_suffix('.new'); tmp.write_bytes(p.read_bytes()); "
            "tmp.chmod(p.stat().st_mode & 0o777); tmp.replace(p)")
        run_validation, fsync = landing.validate.run_profile, os.fsync
        validated_identity = None
        rejected_sync = False
        def validation(*args, **kwargs):
            nonlocal validated_identity
            result = run_validation(*args, **kwargs)
            info = (self.repo / 'sample.py').stat()
            validated_identity = (info.st_dev, info.st_ino)
            return result
        def fail_final_sync(fd):
            nonlocal rejected_sync
            info = os.fstat(fd)
            if validated_identity == (info.st_dev, info.st_ino):
                rejected_sync = True
                raise OSError('injected post-validation file synchronization failure')
            return fsync(fd)
        with patch.object(landing.validate, 'run_profile', side_effect=validation), \
             patch.object(landing.os, 'fsync', side_effect=fail_final_sync):
            outcome = self.apply()
        self.assertEqual('UNCONFIRMED', outcome['status'])
        self.assertTrue(rejected_sync)
        self.assertEqual(0, outcome['validation']['exit_code'])
        self.assertTrue(outcome['write_attempted'])
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())
        with patch.object(act, 'fs_write_text_cas', side_effect=AssertionError('duplicate write')):
            retry = self.apply()
        self.assertEqual('ALREADY_APPLIED', retry['status'])
        self.assertFalse(retry['write_attempted'])

    def test_sync_readback_cannot_switch_to_an_unsynchronized_same_bytes_file(self):
        target = self.repo / 'sample.py'
        target.write_bytes(self.after)
        read = landing.read_regular_file_bounded
        def replace_before_read(path, limit, code):
            if code == 'existing_target_unconfirmed':
                replacement = self.repo / 'sample.new'
                replacement.write_bytes(self.after)
                replacement.chmod(target.stat().st_mode & 0o777)
                replacement.replace(target)
            return read(path, limit, code)
        with patch.object(landing, 'read_regular_file_bounded', side_effect=replace_before_read):
            with self.assertRaises(LocalHandError) as caught:
                landing._confirm_existing(self.repo, 'sample.py', self.result['after_sha256'])
        # Windows prevents replacement of this open file. POSIX permits the
        # rename, so the final identity comparison must detect the replacement.
        self.assertEqual('write_durability_unconfirmed' if os.name == 'nt' else
                         'workspace_conflict', caught.exception.code)
        self.assertEqual(self.after, target.read_bytes())

    def test_birthtime_binding_allows_stat_fstat_ctime_semantics_but_detects_changes(self):
        target = self.repo / 'sample.py'
        target.write_bytes(self.after)
        fstat = os.fstat
        read = landing.read_regular_file_bounded
        for mutate in (False, True):
            with self.subTest(change_during_read=mutate):
                changed = False
                def descriptor(fd):
                    info = fstat(fd)
                    # Model Python 3.12 Windows: lstat ctime is birth time,
                    # while fstat ctime is change time for this same file.
                    return SimpleNamespace(**{key: getattr(info, key) for key in
                        ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns')},
                        st_birthtime_ns=getattr(info, 'st_birthtime_ns', info.st_ctime_ns),
                        st_ctime_ns=info.st_ctime_ns + 1000 + int(changed))
                def readback(*args):
                    nonlocal changed
                    result = read(*args)
                    changed = mutate
                    return result
                with patch.object(landing.os, 'fstat', side_effect=descriptor), \
                     patch.object(landing, 'read_regular_file_bounded', side_effect=readback):
                    if mutate:
                        with self.assertRaises(LocalHandError) as caught:
                            landing._confirm_existing(self.repo, 'sample.py', self.result['after_sha256'])
                        self.assertEqual('workspace_conflict', caught.exception.code)
                    else:
                        landing._confirm_existing(self.repo, 'sample.py', self.result['after_sha256'])
                self.assertEqual(self.after, target.read_bytes())

    def test_git_worktree_must_match_the_registered_repository(self):
        other = self.root / 'other-worktree'
        other.mkdir()
        for name in ('sample.py', 'other.txt'):
            shutil.copyfile(self.repo / name, other / name)
        self.git('config', 'core.worktree', str(other))
        outcome = self.apply()
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertFalse(outcome['write_attempted'])
        self.assertIsNone(outcome['validation'])
        self.assertEqual(self.before, (self.repo / 'sample.py').read_bytes())
        self.assertEqual(self.before, (other / 'sample.py').read_bytes())

    def test_validation_cannot_redirect_the_git_worktree_and_report_success(self):
        other = self.root / 'other-worktree'
        other.mkdir()
        for name in ('sample.py', 'other.txt'):
            shutil.copyfile(self.repo / name, other / name)
        self.set_validation("import subprocess; subprocess.run(['git', 'config', "
                            "'core.worktree', " + repr(str(other)) + "], check=True)")
        outcome = self.apply()
        self.assertEqual('CONFLICT', outcome['status'])
        self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())
        self.assertEqual(self.before, (other / 'sample.py').read_bytes())

    def test_linked_worktree_works_and_common_git_metadata_is_not_an_output_location(self):
        linked = self.root / 'linked'
        self.git('worktree', 'add', '--detach', str(linked), self.head)
        data = json.loads(self.profile_path.read_bytes())
        data['repositories']['demo']['path'] = 'linked'
        self.profile_path.write_text(json.dumps(data))
        self.profile = load_profile(self.profile_path)
        self.assertEqual('APPLIED', self.apply()['status'])
        self.assertEqual(self.after, (linked / 'sample.py').read_bytes())
        self.assertEqual(self.before, (self.repo / 'sample.py').read_bytes())
        output = self.repo / '.git/new-attempt'
        with self.assertRaises(LocalHandError) as caught:
            self.apply(output=output)
        self.assertEqual('invalid_output', caught.exception.code)
        self.assertFalse(output.exists())

    def test_hidden_target_index_flags_prevent_writing_and_are_retained(self):
        for flag in ('assume-unchanged', 'skip-worktree'):
            with self.subTest(flag=flag):
                self.git('update-index', '--' + flag, 'sample.py')
                index = self.git('ls-files', '-v', '--stage', '-z')
                outcome = self.apply()
                self.assertEqual('CONFLICT', outcome['status'])
                self.assertFalse(outcome['write_attempted'])
                self.assertIsNone(outcome['validation'])
                self.assertEqual(self.before, (self.repo / 'sample.py').read_bytes())
                self.assertEqual(index, self.git('ls-files', '-v', '--stage', '-z'))
                self.git('update-index', '--no-' + flag, 'sample.py')
        self.assertEqual('APPLIED', self.apply()['status'])

    def test_validation_cannot_hide_changes_by_setting_index_flags(self):
        for target, flag in (('sample.py', 'assume-unchanged'), ('other.txt', 'skip-worktree')):
            with self.subTest(target=target, flag=flag):
                self.set_validation("import subprocess; subprocess.run(['git', 'update-index', "
                                    + repr('--' + flag) + ', ' + repr(target) + "], check=True)")
                outcome = self.apply()
                self.assertEqual('CONFLICT', outcome['status'])
                self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())
                self.assertNotEqual(b'H', self.git('ls-files', '-v', '--', target)[:1])
                self.git('update-index', '--no-' + flag, target)

    def test_existing_unrelated_index_flags_are_preserved(self):
        self.git('update-index', '--skip-worktree', 'other.txt')
        index = self.git('ls-files', '-v', '--stage', '-z')
        outcome = self.apply()
        self.assertEqual('APPLIED', outcome['status'])
        self.assertEqual(index, self.git('ls-files', '-v', '--stage', '-z'))
        self.assertIn(b'+VALUE = 2', (self.root / 'attempt-1/final.patch').read_bytes())

    @unittest.skipIf(os.name == 'nt', 'POSIX real signal and process group')
    def test_real_cli_interrupt_stops_validator_and_retry_skips_patch_write(self):
        pidfile, release = self.root / 'validator.pid', self.root / 'release'
        self.set_validation("import os,time; from pathlib import Path; "
            "Path(" + repr(str(pidfile)) + ").write_text(str(os.getpid())); "
            "end = time.monotonic() + 10\n"
            "while not Path(" + repr(str(release)) + ").exists() and time.monotonic() < end: time.sleep(.02)\n"
            "assert Path('sample.py').read_bytes() == b'VALUE = 2\\n'")
        raw = json.dumps(self.result).encode()
        self.result_path.write_bytes(raw)
        source = str(Path(__file__).resolve().parents[1] / 'tools')
        command = [sys.executable, '-I', '-B', '-c',
            'import sys; sys.path.insert(0, ' + repr(source) + '); '
            'from local_hand.workspace_apply import main; raise SystemExit(main())',
            '--profile', str(self.profile_path), '--repository', 'demo',
            '--result', str(self.result_path), '--result-sha256', hashlib.sha256(raw).hexdigest(),
            '--before', str(self.before_path), '--after', str(self.after_path), '--expected-head', self.head]
        process = subprocess.Popen([*command, '--output', str(self.root / 'interrupted-cli')],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while (not pidfile.exists() or not pidfile.read_text().strip()) and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(pidfile.exists(), 'validator must start before interruption')
            child_pid = int(pidfile.read_text())
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=15)
            self.assertNotEqual(0, process.returncode, stdout.decode())
            report = json.loads((self.root / 'interrupted-cli/report.json').read_bytes())
            self.assertEqual('UNCONFIRMED', report['status'])
            self.assertEqual('interrupted', report['error']['code'])
            self.assertTrue(report['write_attempted'])
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
            self.assertEqual(self.after, (self.repo / 'sample.py').read_bytes())
            release.touch()
            retry = subprocess.run([*command, '--output', str(self.root / 'resumed-cli')],
                                   capture_output=True, timeout=20)
            self.assertEqual(0, retry.returncode, retry.stderr.decode())
            resumed = json.loads(retry.stdout)
            self.assertEqual('ALREADY_APPLIED', resumed['status'])
            self.assertFalse(resumed['write_attempted'])
            self.assertEqual(report, json.loads((self.root / 'interrupted-cli/report.json').read_bytes()))
        finally:
            release.touch()
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=15)

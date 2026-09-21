"""POSIX process-lifetime regressions with finite, locally owned fixtures."""
from __future__ import annotations

from contextlib import nullcontext
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from config_fixtures import profile_v2
from local_hand import bounded_io, validate
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError


@unittest.skipIf(os.name == 'nt', 'POSIX process-group fixtures; Windows deferred')
class ProcessLifetimeChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'projects/demo'
        self.repo.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)

    def _check_parent_exit(self, runner, inherit_pipes, deny_termination=False):
        # The child self-expires even if the implementation fails cleanup.
        child = self.repo / 'finite_child.py'
        child.write_text(
            'from pathlib import Path\nimport time\n'
            'end=time.monotonic()+12\n'
            'with Path("heartbeat").open("ab",buffering=0) as out:\n'
            ' while time.monotonic()<end:\n  out.write(b"x");time.sleep(.03)\n'
        )
        parent = self.repo / 'early_parent.py'
        redirected = '' if inherit_pipes else ',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL'
        parent.write_text(
            'import json,os,subprocess,sys,time\nfrom pathlib import Path\n'
            f'child=subprocess.Popen([sys.executable,"finite_child.py"]{redirected})\n'
            'Path("owned-pids.json").write_text(json.dumps({"child":child.pid,"group":os.getpgrp()}))\n'
            'end=time.monotonic()+2\n'
            'while not Path("heartbeat").exists() and time.monotonic()<end:time.sleep(.01)\n'
        )
        started = time.monotonic()
        injected = (mock.patch.object(bounded_io, '_kill_tree', return_value=False) if runner == 'generic'
                    else mock.patch.object(validate, '_terminate_tree', return_value=(0, False, 'fixture-unconfirmed')))
        try:
            with injected if deny_termination else nullcontext(), self.assertRaises(LocalHandError) as raised:
                if runner == 'generic':
                    bounded_io.run_process_bounded([sys.executable, str(parent)], cwd=self.repo,
                        env=dict(os.environ), timeout=.4, max_stdout=1024, max_stderr=1024,
                        code_prefix='lifetime', text=True)
                else:
                    data = profile_v2({'node_id':'lifetime-fixture','projects_root':str(self.repo.parent),
                        'repositories':{'demo':{'path':'demo','single_writer':True,'validations':{
                            'early-parent':{'argv':[sys.executable,str(parent)],'timeout_seconds':.4,'replay_safe':True}}}}})
                    path = self.root / 'profile.json';path.write_text(json.dumps(data))
                    validate.run_profile(load_profile(path), 'demo', 'early-parent')
            elapsed = time.monotonic() - started
            prefix = 'lifetime' if runner == 'generic' else 'validation'
            self.assertEqual(raised.exception.code, prefix + ('_termination_unconfirmed' if deny_termination else '_timeout'))
            if deny_termination:
                self.assertEqual(raised.exception.status, 'indeterminate')
            self.assertLess(elapsed, 8, 'must finish cleanup before the fixture self-expires at 12 seconds')
            if runner == 'validation' and not deny_termination:
                self.assertTrue(raised.exception.details['termination_confirmed'])
                self.assertTrue(raised.exception.details['pipes_closed'])
            heartbeat = self.repo / 'heartbeat'
            self.assertTrue(heartbeat.exists())
            if not deny_termination:
                before = heartbeat.read_bytes();time.sleep(.15)
                self.assertEqual(heartbeat.read_bytes(), before, 'descendant survived command completion')
        finally:
            path = self.repo / 'owned-pids.json'
            if path.exists():
                owned = json.loads(path.read_text())
                try:
                    if os.getpgid(owned['child']) == owned['group']:
                        os.kill(owned['child'], signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_generic_parent_exit_with_inherited_pipes_remains_bounded(self):
        self._check_parent_exit('generic', True)

    def test_validation_parent_exit_with_inherited_pipes_remains_bounded(self):
        self._check_parent_exit('validation', True)

    def test_generic_parent_exit_cannot_hide_redirected_descendant(self):
        self._check_parent_exit('generic', False)

    def test_validation_parent_exit_cannot_hide_redirected_descendant(self):
        self._check_parent_exit('validation', False)

    def test_generic_unconfirmed_termination_returns_without_blocking_close(self):
        self._check_parent_exit('generic', True, deny_termination=True)

    def test_validation_unconfirmed_termination_returns_without_blocking_close(self):
        self._check_parent_exit('validation', True, deny_termination=True)

    def test_short_lived_descendant_completes_and_captures_tail(self):
        parent = self.repo / 'short_parent.py'
        child_code = "import time;time.sleep(.1);print('child-tail')"
        parent.write_text(f'import subprocess,sys\nsubprocess.Popen([sys.executable,"-c",{child_code!r}])\n')
        for runner in ('generic', 'validation'):
            with self.subTest(runner=runner):
                if runner == 'generic':
                    result = bounded_io.run_process_bounded([sys.executable,str(parent)], cwd=self.repo,
                        env=dict(os.environ), timeout=3, max_stdout=1024,max_stderr=1024,code_prefix='short',text=True)
                    self.assertEqual(result.returncode,0)
                    self.assertEqual(result.stdout,'child-tail\n')
                else:
                    data = profile_v2({'node_id':'lifetime-fixture','projects_root':str(self.repo.parent),
                        'repositories':{'demo':{'path':'demo','single_writer':True,'validations':{
                            'short':{'argv':[sys.executable,str(parent)],'timeout_seconds':3,'replay_safe':True}}}}})
                    path=self.root/'short-profile.json';path.write_text(json.dumps(data))
                    result=validate.run_profile(load_profile(path),'demo','short')
                    self.assertEqual(result['exit_code'],0)
                    self.assertEqual(result['stdout'],'child-tail\n')
                    self.assertTrue(result['pipes_closed'])

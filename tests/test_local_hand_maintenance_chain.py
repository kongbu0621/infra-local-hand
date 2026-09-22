"""A controlled Git operation must not launch unrelated automatic maintenance."""
from __future__ import annotations
import errno
import json
import os
from pathlib import Path
import unittest
from unittest import mock
from local_hand import bounded_io,git_safety,worker
from local_hand.protocol import LocalHandError
from test_local_hand_state_lookup_chain import StateLookupChainTests

@unittest.skipIf(os.name=='nt','POSIX Git Trace2 fixture; Windows deferred')
class MaintenanceChainTests(unittest.TestCase):
    def test_fetch_does_not_launch_automatic_maintenance(self):
        c=StateLookupChainTests();c.setUp();self.addCleanup(c.doCleanups)
        for name,value in (('maintenance.auto','true'),('maintenance.autoDetach','false'),('gc.autoPackLimit','1')):
            c.f._git(c.f.mailbox,'config','--local',name,value)
        trace=c.f.root/'git-trace.jsonl';original=git_safety.sanitized_git_env
        def environment(**kwargs):
            return {**original(**kwargs),'GIT_TRACE2_EVENT':str(trace)}
        with mock.patch.object(git_safety,'sanitized_git_env',side_effect=environment):
            worker.sync_mailbox(c.f.mailbox,c.f.branch)
        events=[json.loads(line) for line in trace.read_text().splitlines()]
        children=[e['argv'] for e in events if e.get('event')=='child_start' and any(v in e.get('argv',[]) for v in ('maintenance','gc'))]
        self.assertFalse(children, f'implicit maintenance escaped the operation: {children}')
        self.assertEqual(c.f._git(c.f.mailbox,'config','--local','--get','maintenance.auto').stdout.strip(),'true')
        self.assertEqual(c.f._git(c.f.mailbox,'rev-parse','HEAD').stdout.strip(),c.f._git(c.f.seed,'rev-parse','HEAD').stdout.strip())

    def test_disappearing_file_does_not_bypass_disk_quota_scan(self):
        with mock.patch.object(bounded_io.os,'scandir',side_effect=FileNotFoundError(errno.ENOENT,'fixture directory changed')):
            with self.assertRaises(LocalHandError) as raised:
                bounded_io.directory_usage_bounded(Path('/synthetic/quota-fixture'),max_bytes=1024,max_entries=10,code='quota_unavailable')
        self.assertEqual(raised.exception.code,'quota_unavailable')
        self.assertEqual(raised.exception.status,'indeterminate')

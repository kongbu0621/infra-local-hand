"""A regular file replaced by a FIFO must not strand a bounded reader."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from config_fixtures import profile_v2
from local_hand import bounded_io

CHILD = r'''
import hashlib,json,os,signal,stat,sys
from pathlib import Path
from unittest import mock
sys.path.insert(0,sys.argv[1])
from local_hand import act,bounded_io,observe
from local_hand.paths import load_profile
from local_hand.protocol import LocalHandError
root=Path(sys.argv[2]);mode=sys.argv[3];target=root/'projects/demo/sample.txt'
profile=load_profile(root/'profile.json');original=os.open;swapped=False
before=b'before\n'
def operation():
 if mode=='reader':return bounded_io.read_regular_file_bounded(target,1024,'fixture_invalid')
 if mode=='observe':return observe.fs_read_text(profile,'demo','sample.txt')
 return act.fs_write_text_cas(profile,'demo','sample.txt',hashlib.sha256(before).hexdigest(),'after\n',lease_root=root/'leases')
def race(path,*args,**kwargs):
 global swapped
 if not isinstance(path,int) and Path(path)==target and not swapped:
  target.unlink();os.mkfifo(target);swapped=True
 return original(path,*args,**kwargs)
class ReaderDeadline(Exception):pass
def deadline(*_):raise ReaderDeadline('bounded reader blocked in FIFO open')
signal.signal(signal.SIGALRM,deadline);signal.alarm(2)
try:
 with mock.patch.object(os,'open',side_effect=race):operation()
except LocalHandError as exc:
 failure={'code':exc.code,'status':exc.status,'message':exc.message}
except ReaderDeadline as exc:
 print(json.dumps({'timeout':str(exc),'swapped':swapped}),flush=True);sys.exit(4)
else:raise AssertionError('FIFO replacement was accepted')
finally:signal.alarm(0)
assert swapped and stat.S_ISFIFO(target.lstat().st_mode),(failure,swapped)
assert failure['status']=='indeterminate' and 'not a regular file' in failure['message'],failure
# Restore only this synthetic target; the actual reader must work afterwards.
target.unlink();target.write_bytes(before);healthy=operation()
assert target.read_bytes()==(b'after\n' if mode=='cas' else before)
print(json.dumps({'failure':failure,'fifo_preserved':True,'healthy_recovery':True,'mode':mode}))
'''

@unittest.skipIf(os.name=='nt','POSIX FIFO race; Windows deferred')
class ReaderRaceChainTests(unittest.TestCase):
    def check_mode(self,mode):
        with tempfile.TemporaryDirectory(prefix='lh-reader-race-') as name:
            root=Path(name);repo=root/'projects/demo';repo.mkdir(parents=True)
            subprocess.run(['git','init','-q',str(repo)],check=True)
            (repo/'sample.txt').write_bytes(b'before\n')
            value=profile_v2({'node_id':'fixture-reader-node','projects_root':str(repo.parent),'repositories':{'demo':{'path':'demo','single_writer':True,'validations':{}}}})
            (root/'profile.json').write_text(json.dumps(value))
            proc=subprocess.run([sys.executable,'-I','-c',CHILD,str(Path(bounded_io.__file__).parent.parent),str(root),mode],capture_output=True,text=True,timeout=6)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            result=json.loads(proc.stdout);self.assertTrue(result['fifo_preserved']);self.assertTrue(result['healthy_recovery'])
    def test_bounded_reader_fifo_swap_does_not_block(self):self.check_mode('reader')
    def test_observation_fifo_swap_does_not_block(self):self.check_mode('observe')
    def test_cas_fifo_swap_does_not_block_or_replace(self):self.check_mode('cas')

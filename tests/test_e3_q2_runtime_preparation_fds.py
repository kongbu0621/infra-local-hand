"""Both retained archives stay held across actual custody and transport lifetimes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux custody and descriptor lifetime', allow_module_level=True)

from test_e3_q2_journal_retained_fds import CHILD
from runtime_preparation_continuation_fixture import records, archive, PIN

PAIR_CHILD = CHILD.replace(
    "archive_spec=json.loads(sys.argv[5]) if len(sys.argv)>5 else None",
    "pair_spec=json.loads(sys.argv[5]);archive_spec=None")
PAIR_CHILD = PAIR_CHILD.replace("fill=[]", '''inputs=h.prior.Inputs()
raws={}
for name,role in (('identity','vm_activation_archive'),('failure','runtime_preparation_archive')):
    spec=pair_spec[name]
    raws[name]=inputs.read(spec['path'],spec['bytes'],spec['sha256'],role)
proof,_,_=h.history.build_runtime_preparation_source(raws['failure'],raws['identity'])
frozen=dict(vm_activation=True,activation_archive=pair_spec['identity'],
    runtime_preparation_archive=pair_spec['failure'])
assert len(inputs.held)==2
h.recheck_vm_activation(inputs,frozen,lambda:None)
fill=[]''')
PAIR_CHILD = PAIR_CHILD.replace("inputs=h.prior.Inputs();frozen={'source_binding':{'sources':{}}}",
    "h.recheck_vm_activation(inputs,frozen,lambda:None)")
PAIR_CHILD = PAIR_CHILD.replace("if mode=='archive_drift':", '''if mode in ('identity_drift','failure_drift'):
    target=pair_spec[mode.removesuffix('_drift')]['path']
    fd=os.open(target,os.O_WRONLY);os.write(fd,b'changed');os.close(fd)
    try:h.recheck_vm_activation(inputs,frozen,lambda:None)
    except h.prior.r.ObservationError:pass
    else:raise AssertionError('admitted changed archive in fixed pair')
    inputs.close();held.close()
    assert count()==initial-57 and not c.ACTIVE
    print(json.dumps(dict(mode=mode,rejected=True)));sys.exit(0)
if mode=='archive_drift':''')
PAIR_CHILD = PAIR_CHILD.replace("    if phase=='pre':", "    h.recheck_vm_activation(inputs,frozen,lambda:None)\n    if phase=='pre':")
PAIR_CHILD = PAIR_CHILD.replace("count()==initial-55,(final", "count()==initial-57,(final")


@pytest.mark.parametrize('initial', [129, 250])
@pytest.mark.parametrize('mode', ['lifecycle', 'identity_drift', 'failure_drift'])
def test_fixed_pair_held_during_real_256_fd_handoff_and_output_lifetime(initial, mode):
    files, identity, _ = records()
    parent = os.environ.get('LOCAL_HAND_Q2_TEST_PARENT', str(Path.home()))
    with tempfile.TemporaryDirectory(prefix='.core-pair-fd-test-', dir=parent) as directory:
        specs = {}
        for name, raw in (('identity', identity), ('failure', archive(files))):
            path = Path(directory)/(name+'.tar')
            path.write_bytes(raw); path.chmod(0o600)
            specs[name] = dict(PIN(raw),path=str(path))
        result = subprocess.run([sys.executable,'-I','-B','-c',PAIR_CHILD,
            str(Path(__file__).parent),directory,mode,str(initial),json.dumps(specs)],
            stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
        assert result.returncode == 0, result.stderr.decode()
        value = json.loads(result.stdout)
        assert value['mode'] == mode
        if mode == 'lifecycle':
            assert value['before'] == initial and value['after_close'] == initial-57
        else:
            assert value['rejected'] is True

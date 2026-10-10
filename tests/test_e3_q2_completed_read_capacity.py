"""Completed read costs survive source projection and both core consumers."""
import copy
import sys
from types import SimpleNamespace

import pytest

from e3_host import q2_core_approved_inputs as a
from test_e3_q2_core_approved_inputs import artifact


@pytest.mark.parametrize('fault', ['missing', 'bytes', 'inodes', 'cpu', 'refunded'])
def test_rehashed_completed_read_refund_is_rejected_by_both_consumers(artifact, fault):
    value=copy.deepcopy(artifact[0])
    capacity=value['historical_capacity_obligations']
    read=capacity['maintenance']['protection_read']
    if fault=='missing':
        del capacity['maintenance']['protection_read']
    elif fault=='bytes':read['host_bytes']-=1048576
    elif fault=='inodes':read['host_inodes']-=32
    elif fault=='cpu':read['aggregate_cpu_seconds']=0
    else:read['refunded']=True
    with pytest.raises(a.c.ContractError,match='MAINTENANCE_COMMITMENTS'):
        a.validate(a.c.canonical(value,newline=True))
    if sys.platform.startswith('linux'):
        from e3_host import q2_core_delivery_dispatcher as d
        with pytest.raises(d.DispatchError,match='MAINTENANCE_COMMITMENTS'):
            d._approved_validate_capacity(capacity,value['source_relation']['obligations'])


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='Linux maintenance capacity')
@pytest.mark.parametrize('byte_short,inode_short', [(0,0),(2*1048576,0),(0,64)])
def test_maintenance_admission_includes_completed_read_without_a_new_observation(
        monkeypatch,byte_short,inode_short):
    from e3_host import q2_journal_growth as h
    calls=[]
    def observe(fd):
        calls.append(fd)
        return SimpleNamespace(f_frsize=1,f_bavail=22951*1048576-byte_short,
            f_favail=6802-inode_short)
    monkeypatch.setattr(h.os,'fstatvfs',observe)
    store=h.Store(7,lambda:None)
    if byte_short or inode_short:
        with pytest.raises(h.prior.r.ObservationError,match='GROWTH_HOST_CAPACITY') as caught:
            store.capacity()
        assert caught.value.diagnostic['required']==dict(bytes=22951*1048576,inodes=6802)
    else:store.capacity()
    assert calls==[7]

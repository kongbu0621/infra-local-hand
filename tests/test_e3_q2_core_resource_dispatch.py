"""Guest-side semantic validation independent of host acceptance decisions."""
import copy
import importlib.util
import sys
from pathlib import Path

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Field dispatcher requires Linux resource limits', allow_module_level=True)

from test_e3_q2_core_resource_result import fixture, incomplete_fixture, seal, digest, missing

SPEC = importlib.util.spec_from_file_location('_core_resource_dispatch_test',
    Path(__file__).parent / 'e3_host/q2_core_delivery_dispatcher.py')
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def arguments(incomplete=False):
    value, host = incomplete_fixture() if incomplete else fixture()
    clocks = host['guest_deadlines']
    context = dict(manifest={key: host[key] for key in ('implementation', 'locators')},
        hello={f'guest_{clock}_origin_ns': clocks[clock + '_origin_ns'] for clock in ('boottime', 'monotonic')},
        guest_deadlines={clock + '_deadline_ns': clocks[clock + '_deadline_ns'] for clock in ('boottime', 'monotonic')},
        bind={'guest_duration_ns': 900}, stdin_bytes_received=123)
    return value, context, dict(admission=host['admission'], plans=host['plans'])


def test_dispatcher_validates_all_thirty_two_pools_and_preserves_false_guarantee():
    value, context, kwargs = arguments()
    assert d._validate_resource_accounting(value, context, **kwargs) is value
    assert len(value['pools']) == 32 and value['full_guest_filesystem_peak_proven'] is False
    assert d.REMOTE_SCHEMA.endswith('/v2')


@pytest.mark.parametrize('mutation,error', [
    (lambda v: v.update(full_guest_filesystem_peak_proven=True), 'GUARANTEE'),
    (lambda v: v.update(extra=0), 'FIELDS'),
    (lambda v: v['pools'].reverse(), 'POOL_BINDING'),
    (lambda v: v['pools'].pop(), 'POOL_SET'),
    (lambda v: v['pools'][0].update(byte_limit=67108865), 'POOL_BINDING'),
    (lambda v: v['completion_adjustment']['implementation'].update(commit='3' * 40), 'AUTHORITY'),
    (lambda v: v['pools'][0]['last_observation'].update(boottime_ns=1000), 'WINDOW'),
    (lambda v: v['pools'][0]['last_observation'].update(monotonic_ns=199), 'WINDOW'),
    (lambda v: v['pools'][0]['bytes_maximum'].update(boottime_ns=501), 'TIME_ORDER'),
    (lambda v: v['pools'][0]['inodes_maximum'].update(monotonic_ns=601), 'TIME_ORDER'),
    (lambda v: v['pools'][0]['bytes_maximum'].update(allocated_bytes=0), 'MAXIMUM'),
    (lambda v: v['pools'][0]['last_observation'].update(boundary='CHILD_AFTER'), 'FINAL_BOUNDARY'),
    (lambda v: v['pools'][0]['last_observation']['identities'].pop(), 'ROOT_COVERAGE'),
    (lambda v: v['pools'][0]['last_observation']['identities'][0].update(dev=999), 'DEVICE_BINDING'),
    (lambda v: v['pools'][5]['last_observation']['identities'][0].update(ino=999), 'PREPARATION_BINDING'),
    (lambda v: v['pools'][5]['last_observation']['quota'].update(enforcement_flags=0x10), 'QUOTA'),
    (lambda v: v['pools'][5]['last_observation']['quota'].update(used_bytes=1), 'QUOTA'),
    (lambda v: v['pools'][0]['controlled_io'].update(written_bytes=None), 'IO_MISSING'),
    (lambda v: v['observed_maxima_sum'].update(bytes=0), 'TOTAL_BINDING'),
])
def test_guest_semantic_forgery_rejected_after_digest_recalculation(mutation, error):
    value, context, kwargs = arguments()
    mutation(value); seal(value)
    with pytest.raises(d.DispatchError, match=error):
        d._validate_resource_accounting(value, context, **kwargs)


def test_guest_source_and_complete_snapshot_digests_are_separately_verified():
    value, context, kwargs = arguments()
    value['pools'][0]['last_observation']['source_sha256'] = 'f' * 64
    value['snapshot_sha256'] = digest({key:value[key] for key in ('completion_adjustment','pools','observed_maxima_sum')})
    with pytest.raises(d.DispatchError, match='SOURCE_DIGEST'):
        d._validate_resource_accounting(value, context, **kwargs)
    seal(value)['snapshot_sha256'] = 'f' * 64
    with pytest.raises(d.DispatchError, match='SNAPSHOT_DIGEST'):
        d._validate_resource_accounting(value, context, **kwargs)


def test_guest_incomplete_null_totals_cannot_be_rewritten_as_zero():
    value, context, kwargs = arguments(True)
    assert d._validate_resource_accounting(value, context, **kwargs, complete=False) is value
    with pytest.raises(d.DispatchError, match='INCOMPLETE'):
        d._validate_resource_accounting(value, context, **kwargs)
    value['observed_maxima_sum'] = dict(bytes=0, inodes=0); seal(value)
    with pytest.raises(d.DispatchError, match='TOTAL_BINDING'):
        d._validate_resource_accounting(value, context, **kwargs, complete=False)


def test_guest_independent_maxima_preserve_observed_allocation_without_claiming_same_time_peak():
    value, context, kwargs = arguments(); pool = value['pools'][0]
    pool['bytes_maximum'].update(allocated_bytes=16384, allocated_inodes=2,
        boottime_ns=300, monotonic_ns=400, boundary='CHILD_AFTER')
    pool['inodes_maximum'].update(allocated_bytes=8192, allocated_inodes=5,
        boottime_ns=400, monotonic_ns=500, boundary='CHILD_AFTER')
    value['observed_maxima_sum']['bytes'] += 8192; value['observed_maxima_sum']['inodes'] += 3
    seal(value)
    assert d._validate_resource_accounting(value, context, **kwargs) is value


def test_guest_pins_shared_installation_identity_when_supplied():
    value, context, kwargs = arguments()
    identity = value['pools'][0]['last_observation']['identities'][1]
    pin = dict(destination=identity['path'], dev=identity['dev'], ino=identity['ino'])
    assert d._validate_resource_accounting(value, context, **kwargs, installation=pin) is value
    pin['ino'] += 1
    with pytest.raises(d.DispatchError, match='PREPARATION_BINDING'):
        d._validate_resource_accounting(value, context, **kwargs, installation=pin)


def test_guest_metadata_identity_replacement_cannot_hide_behind_same_quota_values():
    value, context, kwargs = arguments()
    identity = value['pools'][2]['last_observation']['identities'][0]
    prepared = {'facts': {'directories': {'state': dict(path=identity['path'], device=identity['dev'], inode=identity['ino'])}}}
    assert d._validate_resource_accounting(value, context, **kwargs, preparations=[prepared]) is value
    prepared['facts']['directories']['state']['inode'] += 1
    with pytest.raises(d.DispatchError, match='PREPARATION_BINDING'):
        d._validate_resource_accounting(value, context, **kwargs, preparations=[prepared])


def test_guest_can_retain_known_over_limit_observation_only_as_incomplete():
    value, context, kwargs = arguments()
    for field in ('last_observation', 'bytes_maximum', 'inodes_maximum'):
        value['pools'][0][field]['allocated_bytes'] = 67108865
    value['observed_maxima_sum']['bytes'] += 67108865 - 8192; seal(value)
    assert d._validate_resource_accounting(value, context, **kwargs, complete=False) is value
    with pytest.raises(d.DispatchError, match='LIMIT'):
        d._validate_resource_accounting(value, context, **kwargs)


def usage(value, context):
    fields = d._fields('guest_elapsed_ns carrier_cpu_ns carrier_memory_peak_bytes carrier_pids_peak stdin_bytes_received output_frame_bytes guest_allocated_bytes guest_allocated_inodes job_units_started controller_units_started quota_query_units_started dynamic_quota_units_started native_children_started')
    result = dict.fromkeys(fields, 1)
    result.update(stdin_bytes_received=context['stdin_bytes_received'], output_frame_bytes=0,
        guest_allocated_bytes=value['observed_maxima_sum']['bytes'],
        guest_allocated_inodes=value['observed_maxima_sum']['inodes'])
    return result


def test_guest_usage_null_requires_its_own_missing_role_and_cannot_complete():
    value, context, _ = arguments(True); counts = usage(value, context)
    rows = [missing('usage/' + key) for key,item in counts.items() if item is None]
    assert d._usage(counts, context, 100, accounting=value, missing=rows, complete=False) is counts
    with pytest.raises(d.DispatchError, match='MISSING'):
        d._usage(counts, context, 100, accounting=value, missing=rows[:-1], complete=False)
    with pytest.raises(d.DispatchError, match='MISSING'):
        d._usage(counts, context, 100, accounting=value, missing=rows, complete=True)


@pytest.mark.parametrize('key,amount', [('guest_elapsed_ns',901),('carrier_cpu_ns',800*d.NS+1),
    ('carrier_memory_peak_bytes',1073741825),('carrier_pids_peak',129),('job_units_started',16),
    ('controller_units_started',7),('quota_query_units_started',6),('dynamic_quota_units_started',16),
    ('native_children_started',17)])
def test_guest_usage_original_limits_are_rejection_lines_never_actual_counts(key, amount):
    value, context, _ = arguments(); counts = usage(value,context); counts[key] = amount
    with pytest.raises(d.DispatchError, match='LIMIT'):
        d._usage(counts,context,100,accounting=value)


def test_guest_usage_storage_must_equal_frozen_observed_sum():
    value, context, _ = arguments(); counts = usage(value,context)
    counts['guest_allocated_bytes'] += 1
    with pytest.raises(d.DispatchError, match='RESOURCE_BINDING'):
        d._usage(counts,context,100,accounting=value)


def test_guest_fixed_point_has_v2_inline_resource_bytes_and_original_frame_limits():
    value, context, _ = arguments()
    remote = dict(schema=d.REMOTE_SCHEMA,resource_accounting=value,usage=usage(value,context))
    manifest = dict(remote_result=remote)
    # Exercise the dispatcher's exact canonical framing construction on the
    # complete inline resource record without simulating any actual task.
    for _ in range(8):
        encoded = d.canonical(manifest,newline=True,limit=d.MANIFEST_LIMIT)
        frame = d.OUTPUT_MAGIC + d.struct.pack('>Q', len(encoded)) + encoded
        if remote['usage']['output_frame_bytes'] == len(frame): break
        remote['usage']['output_frame_bytes'] = len(frame)
    else: pytest.fail('fixed point did not converge')
    assert len(frame) > 65536 and len(frame) <= d.FRAME_LIMIT
    assert d._usage(remote['usage'],context,len(frame),accounting=value) is remote['usage']

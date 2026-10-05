"""Bounded core admission accounting; fixtures are not field acceptance."""
import copy
import ctypes
import errno
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import stat
import struct
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux filesystem descriptors and project quota UAPI', allow_module_level=True)

spec = importlib.util.spec_from_file_location('_core_capacity_test', Path(__file__).parent / 'e3_host/q2_core_delivery_dispatcher.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
LOCATORS = {role + '_parent': '/' + role for role in d._CAP_ROLES}


def fixture(monkeypatch, alias=False):
    fs = {role: dict(dev=(1 if alias else [1, 2, 1, 3, 4][index]),
        fs_uuid=('a' if alias else ['a', 'b', 'a', 'c', 'd'][index]) * 36,
        bytes_available=2**40, inodes_available=2**30) for index, role in enumerate(d._CAP_ROLES)}
    byrole = {role: (value['dev'], value['fs_uuid']) for role, value in fs.items()}
    byrole['system'] = byrole['state']
    rows = [dict(id=str(i), category='state', commitment=dict(bytes=100, inodes=2),
                 covered_paths=['/' + role for role in roles]) for i, roles in enumerate(d._CAP_SNAPSHOT_ROLES)]
    normalized = [dict(id=r['id'], category=r['category'], full_commitment=r['commitment'],
        no_refund=True, pool_roles=list(roles)) for r, roles in zip(rows, d._CAP_SNAPSHOT_ROLES, strict=True)]
    # Replace only immutable source pins, so the small fixture tests the real
    # placement arithmetic without disclosing retained raw machine evidence.
    raw = d.canonical(normalized)
    pins = dict(d.APPROVED_VECTOR_PINS, placement_normalized=(len(raw), hashlib.sha256(raw).hexdigest()))
    monkeypatch.setattr(d, 'APPROVED_VECTOR_PINS', pins)
    approved = dict(historical_capacity_obligations=dict(snapshot_rows=rows,
        delta_rows=[dict(commitment=dict(bytes=200, inodes=3), device_selector='quota_parent', covered_paths=['/quota'])],
        configured_quota_rows=[dict(project_id=100, hard_bytes=1024, inode_hard_limit=4)]))
    inventory = [dict(project=100, hard=1, ihard=4)]
    return approved, fs, lambda path: byrole[path[1:].split('/')[0]], inventory


def test_mountinfo_strict_selected_id():
    rows = d._cap_mounts(b'21 1 8:1 / / rw,relatime - ext4 /dev/vda1 rw,prjquota\n')
    assert rows[21]['device'] == os.makedev(8, 1)
    assert rows[21]['options'] == ['prjquota', 'relatime', 'rw']


@pytest.mark.parametrize('raw', [
    b'21 1 8:1 / / rw - ext4 /dev/vda1 rw\n21 1 8:1 / / rw - ext4 /dev/vda1 rw\n',
    b'21 1 8:1 / /a\\040b rw - ext4 /dev/vda1 rw\n', b''])
def test_mountinfo_rejects_ambiguous_and_empty(raw):
    with pytest.raises(d.DispatchError):
        d._cap_mounts(raw)


def test_uuid_uses_read_only_ext4_fd_ioctl(monkeypatch):
    import fcntl
    expected = bytes(range(1, 17))
    def ioctl(fd, command, value, mutate):
        assert (fd, command, mutate) == (43, 0x8008662c, True)
        assert struct.unpack('=II', value[:8]) == (16, 0)
        value[8:] = expected
    monkeypatch.setattr(fcntl, 'ioctl', ioctl)
    assert d._cap_uuid(43) == '01020304-0506-0708-090a-0b0c0d0e0f10'


def test_uuid_unsupported_has_no_tool_or_raw_disk_fallback(monkeypatch):
    import fcntl
    def unsupported(*_):
        raise OSError(errno.ENOTTY, 'unsupported')
    monkeypatch.setattr(fcntl, 'ioctl', unsupported)
    with pytest.raises(OSError) as failure:
        d._cap_uuid(43)
    assert failure.value.errno == errno.ENOTTY


def test_distinct_pool_full_commitment_and_no_refund(monkeypatch):
    approved, fs, mapper, inventory = fixture(monkeypatch)
    result = d._cap_charge(approved, fs, mapper, inventory, LOCATORS)
    assert sum(row['new_required_bytes'] for row in result) == 390070272
    assert sum(row['new_required_inodes'] for row in result) == 31872
    assert sum(row['historical_bytes'] for row in result) == 2400 + 7 * 200 + 5 * 100 + 200 + 1024 + 3 * 390070272
    assert result[0]['roles'] == ['install', 'state']


def test_alias_pools_charge_each_row_once(monkeypatch):
    approved, fs, mapper, inventory = fixture(monkeypatch, alias=True)
    result = d._cap_charge(approved, fs, mapper, inventory, LOCATORS)
    assert len(result) == 1
    assert result[0]['historical_bytes'] == 2400 + 200 + 1024 + 3 * 289406976
    assert result[0]['new_required_bytes'] == 289406976


def test_current_pool_cannot_replace_historical_placement(monkeypatch):
    approved, fs, mapper, inventory = fixture(monkeypatch)
    approved['historical_capacity_obligations']['snapshot_rows'][2]['covered_paths'] = ['/system']
    with pytest.raises(d.DispatchError, match='HISTORICAL_PLACEMENT'):
        d._cap_charge(approved, fs, mapper, inventory, LOCATORS)


def test_old_core_names_require_current_device_mapping_too(monkeypatch):
    approved, fs, mapper, inventory = fixture(monkeypatch)
    seen = []
    def changed(path):
        seen.append(path)
        if '20261003a' in path: return (999, 'foreign')
        return mapper(path)
    with pytest.raises(d.DispatchError, match='PRIOR_PLACEMENT'):
        d._cap_charge(approved, fs, changed, inventory, LOCATORS)
    assert any('20261003a' in path for path in seen)


def test_delta_covered_paths_cannot_split(monkeypatch):
    approved, fs, mapper, inventory = fixture(monkeypatch)
    approved['historical_capacity_obligations']['delta_rows'][0]['covered_paths'].append('/system')
    with pytest.raises(d.DispatchError, match='DELTA_PLACEMENT'):
        d._cap_charge(approved, fs, mapper, inventory, LOCATORS)


def test_quota_inventory_changes_stop_even_with_spare_capacity(monkeypatch):
    approved, fs, mapper, inventory = fixture(monkeypatch)
    inventory.append(dict(project=101, hard=2, ihard=8))
    with pytest.raises(d.DispatchError, match='CONFIGURED_QUOTA_CHANGED'):
        d._cap_charge(approved, fs, mapper, inventory, LOCATORS)


def test_capacity_includes_full_history_not_only_live_usage(monkeypatch):
    approved, fs, mapper, inventory = fixture(monkeypatch)
    fs['quota']['bytes_available'] = 21 * 1048576
    with pytest.raises(d.DispatchError, match='INSUFFICIENT'):
        d._cap_charge(approved, fs, mapper, inventory, LOCATORS)


@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('short', [('bytes',), ('inodes',), ('bytes', 'inodes')])
def test_capacity_rejection_reports_exact_first_pool_without_changing_threshold(monkeypatch, alias, short):
    approved, fs, mapper, inventory = fixture(monkeypatch, alias=alias)
    baseline = d._cap_charge(approved, fs, mapper, inventory, LOCATORS)
    for pool in baseline:
        for role in pool['roles']:
            for field in ('bytes', 'inodes'):
                fs[role][field + '_available'] = pool['historical_' + field] + pool['new_required_' + field]
    # Equality passes, including aliased roles charged once per physical pool.
    boundary = d._cap_charge(approved, fs, mapper, inventory, LOCATORS)
    for pool in boundary:
        limited = copy.deepcopy(fs)
        for field in short:
            for role in pool['roles']:
                limited[role][field + '_available'] -= 1
        before = copy.deepcopy((approved, limited, inventory))
        with pytest.raises(d.DispatchError) as captured:
            d._cap_charge(approved, limited, mapper, inventory, LOCATORS)
        code = str(captured.value)
        assert re.fullmatch(r'CORE_CAP_INSUFFICIENT_[A-Z0-9_]+', code)
        assert len(code.encode('ascii')) <= 1024
        assert '_ROLES_' + '_'.join(r.upper() for r in pool['roles']) + '_POOLSHA256_' in code
        identity = d._sha(d.canonical(dict(dev=pool['dev'], fs_uuid=pool['fs_uuid']))).upper()
        assert '_POOLSHA256_' + identity + '_' in code
        assert pool['fs_uuid'] not in code and '/state' not in code
        for field in ('bytes', 'inodes'):
            old, new = pool['historical_' + field], pool['new_required_' + field]
            deficit = int(field in short)
            for label, amount in (('AVAILABLE', old + new - deficit), ('HISTORICAL', old),
                                   ('NEW', new), ('REQUIRED', old + new), ('DEFICIT', deficit)):
                assert re.search('_' + field.upper() + '_' + label + '_' + str(amount) + r'(?:_|$)', code)
        assert (approved, limited, inventory) == before


def test_capacity_reports_first_failure_only_and_keeps_existing_bootstrap_channel(monkeypatch):
    from e3_host import q2_core_delivery_bootstrap as bootstrap
    approved, fs, mapper, inventory = fixture(monkeypatch)
    for row in fs.values():
        row['bytes_available'] = row['inodes_available'] = 0
    with pytest.raises(d.DispatchError) as captured:
        d._cap_charge(approved, fs, mapper, inventory, LOCATORS)
    code = str(captured.value)
    assert '_ROLES_INSTALL_STATE_' in code
    assert '_ROLES_QUOTA_' not in code
    def reject(**_kwargs):
        raise captured.value
    monkeypatch.setattr(bootstrap, 'serve', reject)
    stdout, stderr = io.BytesIO(), io.BytesIO()
    assert bootstrap.main(io.BytesIO(), stdout, stderr, bootstrap_sha256='a' * 64) == 3
    assert stdout.getvalue() == b''
    assert stderr.getvalue() == (code + '\n').encode('ascii')


def test_capacity_diagnostic_uses_pool_minimum_not_one_alias_sample(monkeypatch):
    approved, fs, mapper, inventory = fixture(monkeypatch, alias=True)
    fs['quota']['bytes_available'] = 0
    with pytest.raises(d.DispatchError) as captured:
        d._cap_charge(approved, fs, mapper, inventory, LOCATORS)
    assert '_BYTES_AVAILABLE_0_' in str(captured.value)
    assert '_ROLES_EVIDENCE_INSTALL_JOURNAL_QUOTA_STATE_' in str(captured.value)


def diagnostic_row():
    return dict(roles=list(d._CAP_ROLES), dev=2**63-1, fs_uuid='PRIVATE_UUID_NOT_TO_ECHO',
        historical_bytes=2**64-1, historical_inodes=2**64-1,
        new_required_bytes=2**64-1, new_required_inodes=2**64-1,
        bytes_available=-(2**63), inodes_available=0)


def test_capacity_diagnostic_is_bounded_and_handles_negative_availability():
    code = d._cap_insufficient_code(diagnostic_row())
    assert re.fullmatch(r'CORE_CAP_INSUFFICIENT_[A-Z0-9_]+', code)
    assert len(code) <= 1024 and 'PRIVATE_UUID' not in code
    assert '_BYTES_AVAILABLE_NEG9223372036854775808_' in code
    assert '_BYTES_DEFICIT_46116860184273879038_' in code


@pytest.mark.parametrize('key,value', [
    ('roles', ['state', 'PRIVATE_PATH']), ('roles', ['state', 'state']), ('roles', []),
    ('roles', ['state\n']), ('roles', ['state', []]), ('roles', 'state'),
    ('dev', True), ('dev', -1), ('dev', 2**63), ('fs_uuid', 'é'), ('fs_uuid', ''),
    ('fs_uuid', 'x'*65), ('bytes_available', True), ('bytes_available', 2**64),
    ('bytes_available', -(2**63)-1), ('inodes_available', 'PRIVATE_VALUE'),
    ('historical_bytes', -1), ('new_required_inodes', 2**64), ('new_required_bytes', None),
])
def test_capacity_invalid_diagnostic_retains_fail_closed_base_code(key, value):
    row = diagnostic_row(); row[key] = value
    assert d._cap_insufficient_code(row) == 'CORE_CAP_INSUFFICIENT'


def test_32_pool_mapping_and_cross_device_wrapper_reservations(monkeypatch):
    _, fs, _, _ = fixture(monkeypatch)
    specs = d._resource_pools(LOCATORS)
    assert len(specs) == 32 and len({p['pool_id'] for p in specs}) == 32
    assert sum(p['byte_limit'] for p in specs) == 188743680
    assert sum(p['inode_limit'] for p in specs) == 13440
    assert sum(p['measurement_kind'] == 'PROJECT_QUOTA' for p in specs) == 21
    values = d._cap_new_reservations(fs, LOCATORS)
    # Quota device owes not only 21 quota roots, but its session/case wrappers.
    quota = values[(fs['quota']['dev'], fs['quota']['fs_uuid'])]
    assert quota == dict(bytes=(21 + 8 + 3 * 8) * 1048576,
                         inodes=21 * 128 + 512 + 3 * 1536)


def test_new_root_device_drift_stops_admission(monkeypatch):
    approved, fs, mapper, inventory = fixture(monkeypatch)
    def replaced(path):
        return (999, 'changed') if d.SESSION in path else mapper(path)
    with pytest.raises(d.DispatchError, match='NEW_PLACEMENT'):
        d._cap_charge(approved, fs, replaced, inventory, LOCATORS)


def test_kernel_reader_rejects_regular_filesystem_imitation(tmp_path):
    value = effects(); (tmp_path / 'pids.peak').write_bytes(b'1\n')
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(d.DispatchError, match='KERNEL_FILESYSTEM'):
            value._capacity_kernel('pids.peak', 64, dir_fd=fd)
    finally:
        os.close(fd)


def test_kernel_reader_observes_only_local_tool_process_not_guest():
    value = effects()
    raw = value._capacity_kernel('/proc/self/cgroup', 4096)
    assert raw and len(raw) <= 4096
    # This read does not test guest identity, PID 1, quota or pids.peak support.
    with pytest.raises(d.DispatchError, match='KERNEL_PATH'):
        value._capacity_kernel('/etc/passwd', 4096)


def effects():
    value = object.__new__(d.FieldEffects)
    value.context = {}
    value._effect_guard = lambda: None
    value._capacity_protection = lambda _info: None
    return value


def test_absence_stops_at_nearest_existing_parent_without_creating(tmp_path):
    value = effects()
    fd, info, missing = value._capacity_path(str(tmp_path / 'new' / 'leaf'), absent=True)
    try:
        assert missing and (info.st_dev, info.st_ino) == (tmp_path.stat().st_dev, tmp_path.stat().st_ino)
    finally:
        os.close(fd)
    assert list(tmp_path.iterdir()) == []


def test_absence_rejects_symlink_and_existing_empty_directory(tmp_path):
    value = effects(); (tmp_path / 'directory').mkdir(); (tmp_path / 'link').symlink_to('directory')
    for name in ('directory', 'link'):
        with pytest.raises(d.DispatchError):
            value._capacity_path(str(tmp_path / name), absent=True)


def test_retained_snapshot_keeps_identity_and_content_without_atime(tmp_path, monkeypatch):
    value = effects(); file = tmp_path / 'retained'; file.write_bytes(b'old evidence')
    os.utime(file, ns=(1000000000, 2000000000))
    root = tmp_path.stat()
    monkeypatch.setattr(d, '_approved_inputs_envelope', lambda _context:
        dict(retained_preparation=dict(paths=[dict(path=str(tmp_path), device=root.st_dev, inode=root.st_ino)])))
    before = value._capacity_retained_snapshot()
    assert before == value._capacity_retained_snapshot()
    assert file.stat().st_atime_ns == 1000000000
    file.write_bytes(b'new evidence')
    assert value._capacity_retained_snapshot() != before


def test_retained_snapshot_rejects_symlink(tmp_path, monkeypatch):
    value = effects(); (tmp_path / 'link').symlink_to('/etc/passwd'); root = tmp_path.stat()
    monkeypatch.setattr(d, '_approved_inputs_envelope', lambda _context:
        dict(retained_preparation=dict(paths=[dict(path=str(tmp_path), device=root.st_dev, inode=root.st_ino)])))
    with pytest.raises(d.DispatchError, match='RETAINED_TYPE'):
        value._capacity_retained_snapshot()


def test_quota_reader_has_no_mutation_command():
    quota = object.__new__(d._CapQuota)
    with pytest.raises(d.DispatchError, match='QUOTA_READ_ONLY'):
        quota.call(0x800008, 123, None)


@pytest.mark.parametrize('text,expected', [('1s', 1000000), ('13min 20s', 800000000), ('5ms', 5000)])
def test_systemd_duration_parser(text, expected):
    assert d._cap_usec(text) == expected


@pytest.mark.parametrize('text', ['infinity', '-1s', '1s trailing', '1.1s'])
def test_systemd_duration_rejects_unqualified_or_unknown(text):
    with pytest.raises(d.DispatchError, match='TIME_VALUE'):
        d._cap_usec(text)


def manager_fixture(tmp_path, monkeypatch):
    value = effects(); value._admission_detail = {}
    locators = {role + '_parent_unit': role + '.slice' for role in
                ('controller', 'management', 'supervisor', 'query', 'ordinary')}
    locators.update(retained_ordinary_parent_path='/retained.slice', user_manager_unit='user@1100.service',
                    carrier_unit='carrier.service')
    units = sorted([*locators.values()])
    units = [item.removeprefix('/') for item in units]
    records = {}
    for unit in units:
        properties = dict(Id=unit, LoadState='loaded', ActiveState='active', SubState='running',
            ControlGroup='/' + unit, InvocationID='a' * 32, MemoryMax='536870912',
            MemorySwapMax='0', TasksMax='64', CPUQuotaPerSecUSec='1s')
        if unit in ('ordinary.slice', 'retained.slice'):
            properties['MemoryMax'] = '268435456'
        if unit == 'ordinary.slice':
            properties['TasksMax'] = '32'
        if unit == 'user@1100.service':
            properties.update(Delegate='yes', User='1100')
        if unit == 'carrier.service':
            properties.update(RuntimeMaxUSec='13min 20s', TimeoutStopUSec='5s', Restart='no',
                              KillMode='control-group', ExitType='cgroup')
        records[unit] = properties
        (tmp_path / unit).mkdir()
    hello = dict(name='carrier.service', control_group='/carrier.service', invocation_id='a' * 32,
        active_state='active', sub_state='running', runtime_max_usec=800000000, timeout_stop_usec=5000000,
        memory_max=536870912, memory_swap_max=0, tasks_max=64, cpu_quota_per_sec_usec=1000000,
        restart='no', kill_mode='control-group', exit_type='cgroup')
    value.context = dict(manifest=dict(locators=locators), hello=dict(carrier_unit=hello))
    def command(arguments, _program):
        if arguments[0] == 'show':
            return ('\n\n'.join('\n'.join(key + '=' + item for key, item in properties.items())
                                for properties in records.values()) + '\n').encode()
        return b''
    value._capacity_systemctl = command
    value._capacity_directory = lambda path: os.open(tmp_path / Path(path).name, os.O_RDONLY | os.O_DIRECTORY)
    def kernel(path, _maximum=1048576, *, dir_fd=None):
        if path == '/proc/self/cgroup':
            return b'0::/carrier.service\n'
        if path == 'cgroup.controllers':
            return b'cpu io memory pids\n'
        unit = Path(os.readlink('/proc/self/fd/' + str(dir_fd))).name
        if path == 'cpu.max':
            return b'100000 100000\n'
        field = {'memory.max': 'MemoryMax', 'memory.swap.max': 'MemorySwapMax', 'pids.max': 'TasksMax'}[path]
        return (records[unit][field] + '\n').encode()
    value._capacity_kernel = kernel
    value._capacity_path = lambda path, **kwargs: (os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY), None, True)
    return value, records


def test_manager_collects_actual_geometry_and_static_absence(tmp_path, monkeypatch):
    value, _records = manager_fixture(tmp_path, monkeypatch)
    result = value._capacity_managers({'systemctl': {}}, 1100)
    assert len(result['parents']) == 6
    assert len(result['absence']) == 21
    assert result['manager']['user_manager_cgroup'] == '/user@1100.service'
    assert value._admission_detail['system_geometry']['ordinary_parent']['memory_bytes'] == 268435456
    assert value._admission_detail['carrier']['inode'] == (tmp_path / 'carrier.service').stat().st_ino


def test_manager_rejects_carrier_invocation_change(tmp_path, monkeypatch):
    value, records = manager_fixture(tmp_path, monkeypatch)
    records['carrier.service']['InvocationID'] = 'b' * 32
    with pytest.raises(d.DispatchError, match='CARRIER_DRIFT'):
        value._capacity_managers({'systemctl': {}}, 1100)


def test_manager_rejects_wrong_account_and_nonempty_units(tmp_path, monkeypatch):
    value, records = manager_fixture(tmp_path, monkeypatch)
    records['user@1100.service']['User'] = '1101'
    with pytest.raises(d.DispatchError, match='MANAGER_DELEGATION'):
        value._capacity_managers({'systemctl': {}}, 1100)
    records['user@1100.service']['User'] = '1100'
    old = value._capacity_systemctl
    value._capacity_systemctl = lambda args, program: (d.CASES[0]['controller_prefix'] + '-target.service loaded active running\n').encode() if args[0] == 'list-units' else old(args, program)
    with pytest.raises(d.DispatchError, match='UNIT_EXISTS'):
        value._capacity_managers({'systemctl': {}}, 1100)

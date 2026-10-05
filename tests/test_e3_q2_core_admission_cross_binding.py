"""Consumer checks bind collected unit facts to the original fixed objects."""
from pathlib import PurePosixPath

import pytest

import test_e3_q2_core_delivery_dispatcher as fixture

d = fixture.d


@pytest.fixture(autouse=True)
def synthetic_prior_pins(monkeypatch):
    from core_prior_fixture import fixture as prior_fixture
    prior_fixture(monkeypatch, d)


def admission():
    context = fixture.context()
    value = fixture.FakeEffects(context).admit({})
    locators = context['manifest']['locators']
    for role in ('controller', 'management', 'supervisor', 'query', 'ordinary'):
        row = value['parents'][role + '_cgroup']
        row['unit'] = locators[role + '_parent_unit']
        row['path'] = '/sys/fs/cgroup/' + row['unit']
    retained = value['parents']['retained_ordinary_cgroup']
    retained['path'] = locators['retained_ordinary_parent_path']
    retained['unit'] = PurePosixPath(retained['path']).name
    units = set()
    for case in d.CASES:
        units.update(row[key] for row in d._phase_units(case['operation_id'], case['phases'])
            for key in ('bootstrap_unit', 'helper_unit', 'result_reader_unit'))
        units.update(case['controller_prefix'] + '-' + role + '.service'
            for role in ('target', 'supervisor'))
    value['absence'] = [row for row in value['absence'] if row['kind'] != 'unit']
    value['absence'].extend(dict(kind='unit', name=unit, parent_dev=None,
        parent_ino=None, project_id=None, unit=unit, absent=True, collision=False)
        for unit in sorted(units))
    value['absence'].sort(key=lambda row: (row['kind'], row['name']))
    return context, value


def test_complete_fixed_object_admission_still_validates():
    context, value = admission()
    assert d._validate_admission(value, context) == value


@pytest.mark.parametrize('change', ['controller_unit', 'retained_path', 'unit_absence'])
def test_missing_or_changed_fixed_unit_identity_is_rejected(change):
    context, value = admission()
    if change == 'controller_unit':
        value['parents']['controller_cgroup']['unit'] = 'different.service'
    elif change == 'retained_path':
        value['parents']['retained_ordinary_cgroup']['path'] = '/sys/fs/cgroup/different.slice'
    else:
        value['absence'] = [row for row in value['absence'] if row['kind'] != 'unit']
    with pytest.raises(d.DispatchError):
        d._validate_admission(value, context)

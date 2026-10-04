"""Current admission must retain the fixed cgroup and planned-unit identities."""
import pytest

import test_e3_q2_core_delivery_dispatcher as fixture

d = fixture.d


def admission():
    context = fixture.context()
    return context, fixture.FakeEffects(context).admit({})


@pytest.mark.parametrize('role', ['controller', 'management', 'supervisor', 'query', 'ordinary'])
def test_cgroup_unit_cannot_be_replaced_even_with_a_matching_basename(role):
    context, value = admission()
    row = value['parents'][role + '_cgroup']
    row.update(unit='different.service', path='/sys/fs/cgroup/different.service')
    with pytest.raises(d.DispatchError, match='CGROUP_BINDING'):
        d._validate_admission(value, context)


@pytest.mark.parametrize('change', ['outside_mount', 'wrong_basename', 'retained_parent'])
def test_cgroup_path_must_bind_the_declared_unit_without_guessing_slice_layout(change):
    context, value = admission()
    if change == 'retained_parent':
        row = value['parents']['retained_ordinary_cgroup']
        row['path'] = '/sys/fs/cgroup/another.slice/' + row['unit']
    else:
        row = value['parents']['controller_cgroup']
        row['path'] = ('/tmp/' + row['unit'] if change == 'outside_mount'
                       else '/sys/fs/cgroup/another.service')
    with pytest.raises(d.DispatchError, match='CGROUP_BINDING'):
        d._validate_admission(value, context)


def test_observed_intermediate_cgroup_slices_are_not_guessed():
    context, value = admission()
    row = value['parents']['controller_cgroup']
    row['path'] = '/sys/fs/cgroup/observed.slice/nested.slice/' + row['unit']
    assert d._validate_admission(value, context) == value


@pytest.mark.parametrize('change', ['missing', 'wrong_unit', 'foreign', 'project_data'])
def test_planned_unit_absence_requires_complete_unambiguous_unit_rows(change):
    context, value = admission()
    row = next(row for row in value['absence'] if row['kind'] == 'unit')
    if change == 'missing':
        value['absence'].remove(row)
    elif change == 'wrong_unit':
        row['unit'] = 'different.service'
    elif change == 'foreign':
        value['absence'].append(dict(row, name='different.service', unit='different.service'))
        value['absence'].sort(key=lambda item: (item['kind'], item['name']))
    else:
        row['project_id'] = 12345
    with pytest.raises(d.DispatchError, match='ABSENCE_UNIT_SET'):
        d._validate_admission(value, context)

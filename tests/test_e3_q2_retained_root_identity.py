"""Real protected walks and independent consumers for historical quota roots."""
import copy
import errno
import os
from types import SimpleNamespace

import pytest

from test_e3_q2_journal_runtime_failure import local_inventory
from test_e3_q2_core_minimal_continuation import originals
from test_e3_q2_journal_growth_guest_completion import description, runtime_pin
from e3_host import q2_journal_growth_guest as g, q2_journal_growth as h
from e3_host import q2_core_obligation_inputs as o
from e3_host import q2_core_prior_attempt as p, q2_core_delivery_dispatcher as d


@pytest.fixture
def retained(local_inventory, monkeypatch):
    inv, root, calls, reads = local_inventory
    paths = [f'/evidence/retained-{i}' for i in range(4)]
    leaves = [root / path[1:] for path in paths]
    for leaf in leaves:
        leaf.mkdir(mode=0o700)
    bindings = [dict(path=path, device=leaf.stat().st_dev, inode=leaf.stat().st_ino)
                for path, leaf in zip(paths, leaves)]
    inv.description = dict(essential_paths=paths, protected_roots=paths,
                           retained_quota_roots=bindings, phase='pre')
    monkeypatch.setattr(g, 'RETAINED_QUOTA_SHA', g.digest(g.canonical(bindings)))
    real_stat = os.fstat
    changed = {}
    sampled = []
    inodes = {leaf.stat().st_ino for leaf in leaves}

    def historical_stat(fd):
        info = real_stat(fd)
        sampled.append(fd)
        if info.st_ino in inodes:
            values = {key: getattr(info, key) for key in dir(info) if key.startswith('st_')}
            # A different historical owner; real descriptors/paths remain unchanged.
            values.update(st_uid=os.getuid()+5, st_gid=os.getgid()+9)
            values.update(changed)
            return SimpleNamespace(**values)
        return info

    g.os.fstat = historical_stat
    return inv, root, calls, reads, leaves, changed, sampled, real_stat


def assert_closed(sampled, real_stat):
    for fd in set(sampled):
        with pytest.raises(OSError) as caught:
            real_stat(fd)
        assert caught.value.errno == errno.EBADF


def test_old_owner_check_rejects_but_exact_roots_pass_without_extra_reads(retained):
    inv, _, calls, reads, _, _, sampled, real_stat = retained
    bound = inv.description.pop('retained_quota_roots')
    with pytest.raises(g.r.ObservationError, match='GROWTH_PATH_PROTECTION'):
        inv.persistent()
    inv.description['retained_quota_roots'] = bound
    calls.clear(); reads.clear(); sampled.clear()
    first = inv.persistent()
    assert first['retained_roots']['count'] == first['count'] == 4
    assert len(calls) == 12 and len(sampled) == 16
    assert len(reads) == 5  # mountinfo + original fdinfo per object, no new reads
    assert inv.persistent() == first
    assert_closed(sampled, real_stat)


@pytest.mark.parametrize('field', ['st_dev', 'st_ino', 'st_mode'])
def test_wrong_object_or_writable_leaf_rejects(retained, field):
    inv, _, _, _, _, changed, sampled, real_stat = retained
    changed[field] = {'st_dev': 90001, 'st_ino': 9999999, 'st_mode': 0o40722}[field]
    with pytest.raises(g.r.ObservationError):
        inv.persistent()
    assert_closed(sampled, real_stat)


@pytest.mark.parametrize('field,value', [('st_uid', 4321), ('st_gid', 4322), ('st_mode', 0o40750)])
def test_owner_group_or_protected_mode_drift_rejects_each_phase(retained, field, value):
    inv, _, _, _, _, changed, _, _ = retained
    first = inv.persistent()
    changed[field] = value
    with pytest.raises(g.r.ObservationError, match='GROWTH_RETAINED_ROOT_DRIFT'):
        inv.persistent()
    inv.description.update(phase='post', pre_report={'quiescence': {'persistent': first}})
    del inv.retained_snapshot
    with pytest.raises(g.r.ObservationError, match='GROWTH_RETAINED_ROOT_DRIFT'):
        inv.persistent()


def test_drift_between_existing_stats_rejects_before_filesystem_read(retained):
    inv, _, _, reads, _, _, sampled, real_stat = retained
    sample = g.os.fstat
    def drift(fd):
        info = sample(fd)
        if len(sampled) == 4:
            info.st_uid += 1
        return info
    g.os.fstat = drift
    with pytest.raises(g.r.ObservationError, match='GROWTH_RETAINED_ROOT_DRIFT'):
        inv.persistent()
    assert reads == ['/proc/self/mountinfo']
    assert_closed(sampled, real_stat)


@pytest.mark.parametrize('fault', ['ancestor', 'symlink', 'missing', 'unbound'])
def test_binding_never_extends_to_other_objects_or_weak_ancestors(retained, fault):
    inv, root, _, _, leaves, _, sampled, real_stat = retained
    if fault == 'ancestor':
        (root/'evidence').chmod(0o777)
    elif fault == 'missing':
        leaves[0].rmdir()
    elif fault == 'symlink':
        leaves[0].rmdir(); leaves[0].symlink_to(leaves[1], target_is_directory=True)
    else:
        del inv.description['retained_quota_roots']
    with pytest.raises((OSError, g.r.ObservationError)):
        inv.persistent()
    assert_closed(sampled, real_stat)


@pytest.mark.parametrize('fault', ['drop', 'append', 'path', 'device', 'inode', 'coverage'])
def test_description_requires_the_exact_complete_source_binding(retained, fault):
    inv, *_ = retained
    roots = inv.description['retained_quota_roots']
    if fault == 'drop': roots.pop()
    elif fault == 'append': roots.append(copy.deepcopy(roots[0]))
    elif fault == 'coverage': inv.description['protected_roots'].pop()
    elif fault == 'path': roots[0]['path'] += '/other'
    else: roots[0][fault] += 1
    with pytest.raises(g.r.ObservationError, match='GROWTH_RETAINED_ROOT_'):
        inv.persistent()


def test_plan_projection_is_exact_and_does_not_mutate_source(monkeypatch):
    from retained_root_fixture import roots
    plan = dict(retained=[{}, {}, {}, *roots()], other='original source')
    before = copy.deepcopy(plan)
    monkeypatch.setattr(o, 'RETAINED_PLAN_SHA', g.digest(g.canonical(plan)))
    monkeypatch.setattr(o, 'RETAINED_QUOTA_SHA', g.digest(g.canonical(roots())))
    bound = o.retained_quota_roots(plan)
    bound[0]['inode'] += 1
    assert plan == before
    plan['other'] = 'changed'
    with pytest.raises(o.c.ContractError, match='RETAINED_PLAN_PIN'):
        o.retained_quota_roots(plan)


def test_descriptor_cannot_downgrade_away_the_identity_policy(runtime_pin):
    value = description()
    assert g.descriptor(g.canonical(value)) == value
    del value['retained_quota_roots']
    value['schema'] = 'lhq-journal-growth-input/v4'
    with pytest.raises(g.r.ObservationError, match='GROWTH_DESCRIPTION'):
        g.descriptor(g.canonical(value))


@pytest.mark.parametrize('fault', ['missing_binding', 'root_identity', 'source', 'sample', 'count', 'report', 'schema'])
def test_both_completion_consumers_require_bound_stable_root_evidence(originals, fault):
    files, args = originals
    value = p.build_journal_transition(files, **args)
    record = value['retained_identity']
    if fault == 'missing_binding': value.pop('retained_identity')
    elif fault == 'root_identity': record['roots_sha256'] = '0'*64
    elif fault == 'source': record['source_plan_sha256'] = '0'*64
    elif fault == 'sample': record['post']['sha256'] = '0'*64
    elif fault == 'count': record['pre']['count'] = record['post']['count'] = 3
    elif fault == 'report': record['reports']['post']['sha256'] = '0'*64
    else: value['schema'] = 'local-hand-q2-core-journal-transition/v17'
    for consumer, error in ((p.validate_journal_transition, p.c.ContractError),
                            (d._validate_journal_transition, d.DispatchError)):
        with pytest.raises(error):
            consumer(value, priors=args['priors'], implementation=args['implementation'])


def test_current_freeze_cannot_drop_new_binding(originals):
    _, args = originals
    frozen = args['frozen']
    del frozen['inventory']['retained_quota_roots']
    with pytest.raises(g.r.ObservationError, match='GROWTH_RETAINED_ROOT_REQUIRED'):
        h.validate_q1_frozen(frozen)

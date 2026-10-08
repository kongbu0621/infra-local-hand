"""One 07b continuation binds both consumed histories without replay authority."""
import copy
import json
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux protected maintenance inputs', allow_module_level=True)

from core_prior_fixture import previous_journal_files
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from e3_host import q2_journal_growth as h
from test_e3_q2_journal_diagnostic_resume import source_git
from test_e3_q2_core_minimal_continuation import originals


@pytest.mark.parametrize('location', ['manifest', 'marker', 'receipt', 'inputs'])
@pytest.mark.parametrize('fault', ['missing', 'wrong_D', 'wrong_order', 'bool', 'new_schema'])
def test_second_failure_must_bind_original_serial_resume(monkeypatch, location, fault):
    files = previous_journal_files(monkeypatch, d)
    prefix = '.' + p.SECOND_JOURNAL_SESSION + '.'
    marker = json.loads(files[prefix + 'consumed.json'])
    receipt = json.loads(files[prefix + 'receipt.json'])
    target = {'manifest': marker['manifest'], 'marker': marker,
              'receipt': receipt, 'inputs': marker['manifest']['inputs']}[location]
    if fault == 'missing':
        del target['resume']
    elif fault == 'new_schema':
        target['resume'] = p.maintenance_resume()
    elif fault == 'wrong_D':
        target['resume']['previous_D'] = p.SECOND_JOURNAL_D
    elif fault == 'wrong_order':
        target['resume']['originals'].reverse()
    else:
        target['resume']['old_window_consumed'] = 1
    # Recompute byte pins and dependent hashes to isolate semantic rejection.
    dump = h.canonical
    marker['pre_description']['source_binding_sha256'] = h.digest(dump(marker['manifest']['inputs']))
    marker['manifest_sha256'] = receipt['manifest_sha256'] = h.digest(dump(marker['manifest']))
    events = [json.loads(line) for line in files[prefix + 'events.jsonl'].splitlines()]
    events[1]['result']['manifest_sha256'] = marker['manifest_sha256']
    events[3]['description_sha256'] = h.digest(dump(marker['pre_description']))
    for name, raw in {'consumed.json': dump(marker), 'receipt.json': dump(receipt),
                     'events.jsonl': b''.join(dump(row) for row in events)}.items():
        files[prefix + name] = raw
        monkeypatch.setitem(p.SECOND_JOURNAL_PINS, name, (len(raw), h.digest(raw)))
    with pytest.raises(p.c.ContractError, match='PREVIOUS_SERIAL_RESUME'):
        p.build_previous_maintenance(files)


@pytest.mark.parametrize('fault', ['missing_generation', 'duplicate', 'order', 'authority', 'old_resume'])
def test_both_consumers_reject_wrong_history_list(originals, fault):
    files, args = originals
    value = p.build_journal_transition(files, **args)
    resume = value['previous_maintenance']
    rows = resume['previous_maintenance']
    if fault == 'missing_generation': rows.pop()
    elif fault == 'duplicate': rows[1] = copy.deepcopy(rows[0])
    elif fault == 'order': rows.reverse()
    elif fault == 'authority': rows[1]['authority']['A'] = p.c.SYSTEMCTL_BASELINE['commit']
    else: value['previous_maintenance'] = p.serial_maintenance_resume()
    with pytest.raises(p.c.ContractError):
        p.validate_journal_transition(value, priors=args['priors'], implementation=args['implementation'])
    with pytest.raises(d.DispatchError):
        d._validate_journal_transition(value, priors=args['priors'], implementation=args['implementation'])


@pytest.mark.parametrize('record', list(p.c.SYSTEMCTL_BASELINE['documents_sha256'])
                         + [p.c.SYSTEMCTL_OWNER_DECISION['record_path']])
def test_systemctl_authority_bytes_required_before_source_admission(source_git, record):
    source_git.changed_doc = record
    with pytest.raises(h.prior.r.ObservationError, match='GROWTH_SYSTEMCTL_'):
        h.growth_sources(source_git.head)
    assert not any(call[0] == 'show' and ':tests/' in call[1] for call in source_git.calls)


@pytest.mark.parametrize('edge', [(h.SYSTEMCTL_A, h.SYSTEMCTL_C), (h.SYSTEMCTL_C, 'd' * 40)])
def test_new_implementation_must_descend_from_independent_closure(source_git, edge):
    source_git.rejected_edge = edge
    with pytest.raises(h.prior.r.ObservationError, match='GROWTH_SOURCE'):
        h.growth_sources(source_git.head)


def test_complete_new_preflight_fits_original_limit_and_rejects_old_schema():
    value = h.make_preflight('d' * 40, 'e' * 64,
        dict(boot_id='11111111-2222-3333-4444-555555555555', origins=[10**18, 10**18]),
        'f' * 64, dict(cpu_nanoseconds=120000000000, rss_peak_bytes=536870912),resume=p.maintenance_resume())
    assert len(h.canonical(value)) <= 4096
    assert value['resume_sha256'] == h.digest(h.canonical(d._maintenance_resume()))
    assert len(p.maintenance_resume()['previous_maintenance']) == 4
    value['schema'] = 'lhq-journal-growth-preflight/v2'
    with pytest.raises(h.prior.r.ObservationError, match='GROWTH_PREFLIGHT_SCHEMA'):
        h.parse_preflight(h.canonical(value))


@pytest.mark.parametrize('field', ['R', 'A', 'C'])
def test_preflight_rejects_rehashed_wrong_top_level_authority(field):
    value = h.make_preflight('d' * 40, 'e' * 64,
        dict(boot_id='11111111-2222-3333-4444-555555555555', origins=[1, 2]),
        'f' * 64, dict(cpu_nanoseconds=1, rss_peak_bytes=1),resume=p.maintenance_resume())
    value[field] = '0' * 40
    with pytest.raises(h.prior.r.ObservationError, match='GROWTH_PREFLIGHT_AUTHORITY'):
        h.parse_preflight(h.canonical(value))

"""Fifth retained failure and exact Exec continuation authority."""
import copy
import json
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux protected continuation', allow_module_level=True)

from core_prior_fixture import previous_journal_files
from e3_host import q2_core_prior_attempt as p
from e3_host import q2_core_delivery_dispatcher as d
from e3_host import q2_journal_growth as h
from test_e3_q2_core_minimal_continuation import originals
from test_e3_q2_core_template_continuation import preflight


@pytest.mark.parametrize('location', ['manifest', 'marker', 'receipt', 'inputs'])
@pytest.mark.parametrize('fault', ['missing','new_resume','order','authority','bool','extra','missing_fourth'])
def test_fifth_failure_keeps_original_four_generation_resume(monkeypatch,location,fault):
    files=previous_journal_files(monkeypatch,d)
    prefix='.'+p.FIFTH_JOURNAL_SESSION+'.'
    marker=json.loads(files[prefix+'consumed.json']);receipt=json.loads(files[prefix+'receipt.json'])
    target={'manifest':marker['manifest'],'marker':marker,'receipt':receipt,
            'inputs':marker['manifest']['inputs']}[location]
    if fault=='missing':del target['resume']
    elif fault=='new_resume':target['resume']=p.maintenance_resume()
    elif fault=='order':target['resume']['previous_maintenance'].reverse()
    elif fault=='authority':target['resume']['previous_maintenance'][3]['authority']['A']=h.EXEC_A
    elif fault=='bool':target['resume']['previous_maintenance'][3]['window_consumed']=1
    elif fault=='extra':target['resume']['retry']=True
    else:target['resume']['previous_maintenance'].pop()
    # Rebind only synthetic original pins so rejection must come from semantics.
    marker['pre_description']['source_binding_sha256']=h.digest(h.canonical(marker['manifest']['inputs']))
    marker['manifest_sha256']=receipt['manifest_sha256']=h.digest(h.canonical(marker['manifest']))
    events=[json.loads(raw) for raw in files[prefix+'events.jsonl'].splitlines()]
    events[1]['result']['manifest_sha256']=marker['manifest_sha256']
    events[3]['description_sha256']=h.digest(h.canonical(marker['pre_description']))
    for name,raw in {'consumed.json':h.canonical(marker),'receipt.json':h.canonical(receipt),
                     'events.jsonl':b''.join(h.canonical(row) for row in events)}.items():
        files[prefix+name]=raw
        monkeypatch.setitem(p.FIFTH_JOURNAL_PINS,name,(len(raw),h.digest(raw)))
    with pytest.raises(p.c.ContractError,match='PREVIOUS_NAMES_RESUME'):
        p.build_previous_maintenance(files)


def test_old_v5_short_handoff_cannot_open_exec_window():
    value=preflight();value['schema']='lhq-journal-growth-preflight/v5'
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_PREFLIGHT_SCHEMA'):
        h.parse_preflight(h.canonical(value))


def test_original_names_resume_digest_cannot_substitute_for_fifth_history():
    value=preflight();value['resume_sha256']=h.digest(h.canonical(p.names_maintenance_resume()))
    with pytest.raises(h.prior.r.ObservationError,match='GROWTH_PREFLIGHT_HISTORY'):
        h.parse_preflight(h.canonical(value))

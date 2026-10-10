"""Synthetic historical directory bindings; never read private or guest files."""
import hashlib
import json
import sys


def roots():
    return [dict(path=f'/fixture/retained-{i}', device=12, inode=100+i) for i in range(4)]


def sample():
    return dict(count=4, sha256='7'*64)


def patch(monkeypatch,*dispatchers):
    from e3_host import q2_core_prior_attempt as p
    modules=[p,*dispatchers]
    for name in ('q2_core_delivery_dispatcher','q2_journal_growth_guest'):
        module=sys.modules.get('e3_host.'+name)
        if module is not None:modules.append(module)
    raw=(json.dumps(roots(),sort_keys=True,separators=(',',':'))+'\n').encode()
    for module in modules:
        monkeypatch.setattr(module, 'RETAINED_QUOTA_SHA', hashlib.sha256(raw).hexdigest())


def projection(reports):
    from e3_host import q2_core_prior_attempt as p
    return dict(schema='lhq-retained-quota-identity/v1', source_plan_sha256=p.RETAINED_PLAN_SHA,
                roots_sha256=p.RETAINED_QUOTA_SHA, pre=sample(), post=sample(), reports=reports)

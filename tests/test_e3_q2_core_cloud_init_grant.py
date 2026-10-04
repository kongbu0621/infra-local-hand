"""Synthetic grammar tests; exact private source verification is separate."""
import hashlib

import pytest

from e3_host import q2_core_policy_basis as p
from e3_host import q2_core_approved_inputs as a


RAW = (b'#cloud-config\nhostname: isolated-fixture\nusers:\n  - name: q1admin\n'
       b'    groups: [sudo]\n    shell: /bin/bash\n'
       b'    sudo: ["ALL=(ALL) NOPASSWD:ALL"]\n'
       b'    ssh_authorized_keys:\n      - ssh-ed25519 AAAA synthetic-fixture\n'
       b'ssh_pwauth: false\n')
PARAMETERS = dict(account='q1admin', cloud_config_literal=p.GRANT, cloud_config_literal_count=1)


def verify(monkeypatch, raw, parameters=PARAMETERS):
    monkeypatch.setitem(p.SOURCE_PINS, 'fixture_cloud_config', hashlib.sha256(raw).hexdigest())
    return a._verify_cloud_grant(raw, parameters)


def test_same_mapping_projection_and_independent_consumer(monkeypatch):
    assert p.GRANT.encode() not in RAW
    assert p.cloud_init_grant(RAW) == (p.GRANT, 1)
    monkeypatch.setattr(p, 'cloud_init_grant', lambda _raw: pytest.fail('consumer called builder'))
    monkeypatch.setattr(p, 'build_policy_basis', lambda **_kw: pytest.fail('consumer called builder'))
    verify(monkeypatch, RAW)


@pytest.mark.parametrize('raw', [
    RAW.replace(b'q1admin', b'otheruser'),
    RAW.replace(b'users:', b'users: &users'),
    RAW + b'users:\n',
    RAW.replace(b'    groups:', b'    name: q1admin\n    groups:'),
    RAW.replace(b'    groups:', b'  - name: q1admin\n    groups:'),
    RAW.replace(b'    groups:', b'    sudo: ["ALL=(ALL) NOPASSWD:ALL"]\n    groups:'),
    RAW.replace(b'    sudo:', b'sudo:'),
    RAW.replace(b'    sudo:', b'other:\n    sudo:'),
    RAW.replace(b'    sudo:', b'  - sudo:'),
    RAW.replace(b'    sudo:', b'      sudo:'),
    RAW.replace(b'["ALL=(ALL) NOPASSWD:ALL"]', b'["ALL=(ALL) NOPASSWD:ALL", "OTHER"]'),
    RAW.replace(b'(ALL)', b'(ALL:ALL)'),
    RAW.replace(b'    sudo:', b'    <<: *grant\n    sudo:'),
    RAW.replace(b'    sudo:', b'    extra: !tag\n    sudo:'),
    RAW.replace(b'    sudo:', b'    extra: &anchor value\n    sudo:'),
    RAW.replace(b'    sudo:', b'    extra: *anchor\n    sudo:'),
    RAW.replace(b'    sudo:', b'    extra: |\n    sudo:'),
    RAW.replace(b'    sudo:', b'    extra: >\n    sudo:'),
    RAW.replace(b'    sudo:', b'    "sudo":'),
    RAW.replace(b'users:', b'"users":'),
    RAW.replace(b'    groups:', b'    extra:\n      name: q1admin\n    groups:'),
    RAW + b'---\n',
    RAW.replace(b'    shell:', b'\tshell:'),
    RAW.replace(b'\n', b'\r\n'),
    RAW + b'\x00',
    RAW + b'\xc3\xa9\n',
    b'#cloud-config\n' + p.GRANT.encode() + b'\n',
])
def test_rejects_ambiguous_sources_even_when_test_recomputes_pin(monkeypatch, raw):
    with pytest.raises(p.c.ContractError):
        p.cloud_init_grant(raw)
    with pytest.raises(p.c.ContractError):
        verify(monkeypatch, raw)


def test_raw_pin_required_by_consumer():
    with pytest.raises(p.c.ContractError, match='SOURCE_POLICY_PIN'):
        a._verify_cloud_grant(RAW, PARAMETERS)


@pytest.mark.parametrize('field,value', [('account', 'otheruser'), ('cloud_config_literal', 'ALL'),
                                      ('cloud_config_literal_count', 2), ('cloud_config_literal_count', True)])
def test_consumer_rejects_wrong_derived_fields(monkeypatch, field, value):
    with pytest.raises(p.c.ContractError, match='SOURCE_POLICY_GRANT'):
        verify(monkeypatch, RAW, {**PARAMETERS, field: value})

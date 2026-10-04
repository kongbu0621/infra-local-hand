"""Held ELF/venv integration in temporary files; never a field acceptance run."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Held ELF binding requires Linux protected descriptors', allow_module_level=True)

from test_e3_q2_core_delivery_dispatcher import d, _command_effects


def pin(path):
    raw, identity = d.FieldEffects.stable_read(str(path), maximum=d.MEMBER_LIMIT, noatime=False)
    return dict(path=str(path), **identity)


@pytest.fixture
def bound(tmp_path):
    if os.geteuid() != 0:
        pytest.skip('Production O_NOATIME reads of root-owned system ELF require root identity')
    interpreter = Path('/usr/bin/python3.12')
    if not interpreter.is_file():
        pytest.skip('The frozen candidate requires Python 3.12')
    e = _command_effects(tmp_path)
    del e._installation_binding
    python = pin(interpreter)
    e.context['manifest'] = {'locators': {'install_parent': str(tmp_path)}}
    e._admission = {'programs': {name: dict(python) for name in
        ('python', 'git', 'cc', 'systemctl', 'systemd_run')},
        'guest': {'ordinary_uid': 65534, 'ordinary_gid': 65534}}
    e._admission['programs']['setpriv'] = pin('/usr/bin/setpriv')
    e._admission['programs']['git'] = pin('/usr/bin/git')
    return e


def close_binding(result):
    for fd in result[3]:
        os.close(fd)


def test_real_held_python_preserves_original_argv_and_runtime_identity(bound):
    program = bound._admission['programs']['python']['path']
    code = 'import json,sys; print(json.dumps([sys.executable,sys.prefix,sys.base_prefix]))'
    expected = subprocess.check_output([program, '-I', '-B', '-c', code])
    assert bound._installation_command([program, '-I', '-B', '-c', code]) == expected
    assert bound._install_commands[-1]['eof'] == ['stderr', 'stdout']
    assert bound._install_commands[-1]['wait4']['wait_status'] == 0


@pytest.mark.parametrize('field,value', [('sha256', '0' * 64), ('ino', 1), ('mode', 0o777)])
def test_admitted_identity_drift_rejected_before_child(bound, field, value, monkeypatch):
    program = bound._admission['programs']['python']['path']
    # No second admission entry may disguise the changed identity.
    for item in bound._admission['programs'].values():
        if item['path'] == program:
            item[field] = value
    monkeypatch.setattr(d.subprocess, 'Popen', lambda *a, **k: pytest.fail('unexpected child'))
    with pytest.raises(d.DispatchError, match='PROGRAM_CHANGED'):
        bound._installation_command([program, '-I', '-B', '-c', 'pass'])
    assert bound._install_commands == []


def test_unadmitted_program_refused(bound, monkeypatch):
    monkeypatch.setattr(d.subprocess, 'Popen', lambda *a, **k: pytest.fail('unexpected child'))
    with pytest.raises(d.DispatchError, match='PROGRAM_CHANGED'):
        bound._installation_command(['/usr/bin/true'])


def test_missing_admission_refused_before_read(monkeypatch):
    bound = d.FieldEffects({})
    monkeypatch.setattr(bound, 'stable_read', lambda *a, **k: pytest.fail('unexpected read'))
    with pytest.raises(d.DispatchError, match='ADMISSION_REQUIRED'):
        bound._installation_binding(['/usr/bin/python3.12'])


def test_file_capability_refused_before_exec(bound, monkeypatch):
    monkeypatch.setattr(d.os, 'getxattr', lambda *a, **k: b'capability')
    with pytest.raises(d.DispatchError, match='PROGRAM_CAPABILITY'):
        bound._installation_binding([bound._admission['programs']['python']['path']])


@pytest.mark.parametrize('suffix', ['runtime/bin/python3', 'native/abi'])
def test_generated_program_requires_active_installation(bound, tmp_path, suffix):
    target = tmp_path / d.INSTALL_BASENAME / suffix
    target.parent.mkdir(parents=True)
    target.write_bytes(Path('/usr/bin/python3.12').read_bytes())
    target.chmod(0o755)
    with pytest.raises(d.DispatchError, match='PROGRAM_STAGE'):
        bound._installation_binding([str(target)])


@pytest.mark.skipif(os.geteuid() != 0, reason='Protected fresh program requires root-owned ELF fixture')
def test_completed_install_binds_executed_abi_and_runtime_receipt(bound, tmp_path):
    generated = {}
    bound._install_build_active = True
    for suffix, source in [('runtime/bin/python3', '/usr/bin/python3.12'), ('native/abi', '/usr/bin/true')]:
        target = tmp_path / d.INSTALL_BASENAME / suffix
        target.parent.mkdir(parents=True)
        target.write_bytes(Path(source).read_bytes())
        target.chmod(0o755)
        close_binding(bound._installation_binding([str(target)]))
        generated[suffix] = pin(target)
    python, abi = generated['runtime/bin/python3'], generated['native/abi']
    receipt = {'installed': {'programs': {'python': {key: python[key] for key in ('path', 'sha256')}}},
        'native_build': {'abi_program': {key: abi[key] for key in ('path', 'sha256')}},
        'python_identity': {'device': python['dev'], 'inode': python['ino']}}
    bound._install_build_receipt = receipt
    bound._verify_install_programs()
    bound._install_build_active = False
    bound._installation_receipt = receipt
    close_binding(bound._installation_binding([python['path']]))
    receipt['python_identity']['inode'] += 1
    with pytest.raises(d.DispatchError, match='PROGRAM_CHANGED'):
        bound._installation_binding([python['path']])
    receipt['native_build']['abi_program']['sha256'] = '0' * 64
    with pytest.raises(d.DispatchError, match='PROGRAM_CHANGED'):
        bound._verify_install_programs()


def test_binding_error_closes_open_descriptor(bound, monkeypatch):
    opened = []
    def fail(fd, amount, offset):
        opened.append(fd)
        raise OSError('test read failure')
    monkeypatch.setattr(d.os, 'pread', fail)
    with pytest.raises(OSError, match='test read failure'):
        bound._installation_binding([bound._admission['programs']['python']['path']])
    assert len(opened) == 1
    with pytest.raises(OSError):
        os.fstat(opened[0])


def test_setpriv_rejects_changed_flags_before_read(tmp_path, monkeypatch):
    bound = d.FieldEffects({'manifest': {'locators': {'install_parent': str(tmp_path)}}})
    bound._admission = {'programs': {'setpriv': {'path': '/usr/bin/setpriv'}},
                        'guest': {'ordinary_uid': 1000, 'ordinary_gid': 1000}}
    monkeypatch.setattr(bound, 'stable_read', lambda *a, **k: pytest.fail('unexpected read'))
    with pytest.raises(d.DispatchError, match='PROGRAM_CHAIN'):
        bound._installation_binding(['/usr/bin/setpriv', '--reuid=0', '/usr/bin/python3.12'])


def test_held_executable_descriptor_closed_after_popen_failure(bound, monkeypatch):
    captured = []
    def fail(*args, **kwargs):
        captured.extend(kwargs['pass_fds'])
        raise OSError('test spawn failure')
    monkeypatch.setattr(d.subprocess, 'Popen', fail)
    with pytest.raises(OSError, match='test spawn failure'):
        bound._installation_command([bound._admission['programs']['python']['path'], '-V'])
    assert len(captured) == 1
    with pytest.raises(OSError):
        os.fstat(captured[0])


@pytest.mark.skipif(os.geteuid() != 0, reason='Protected fresh venv requires root-owned ELF fixture')
def test_real_protected_venv_and_second_hop_preserve_prefix(bound, tmp_path):
    destination = tmp_path / d.INSTALL_BASENAME
    runtime = destination / 'runtime'
    program = bound._admission['programs']['python']['path']
    bound._installation_command([program, '-I', '-B', '-m', 'venv', '--copies', '--without-pip', str(runtime)])
    copied = str(runtime / 'bin/python3')
    bound._install_build_active = True
    code = 'import json,os,sys; print(json.dumps([sys.executable,sys.prefix,sys.base_prefix,os.getuid()]))'
    expected = json.loads(subprocess.check_output([copied, '-I', '-B', '-c', code]))
    assert json.loads(bound._installation_command([copied, '-I', '-B', '-c', code])) == expected
    # The setpriv argv stays fixed; the real second-hop Python is tested below.
    # This does not change a field account, installation or management service.
    bound._admission['guest'] = {'ordinary_uid': 0, 'ordinary_gid': 0}
    args = ['/usr/bin/setpriv', '--reuid=0', '--regid=0', '--clear-groups',
            '--no-new-privs', '--bounding-set=-all', '--inh-caps=-all', '--ambient-caps=-all',
            copied, '-I', '-B', '-c', code]
    result = bound._installation_binding(args)
    try:
        actual, options, environment, descriptors = result
        assert len(descriptors) == 2 and actual[8] == '/proc/self/fd/' + str(descriptors[1])
        assert json.loads(subprocess.check_output(actual[8:], pass_fds=tuple(descriptors),
            env=environment)) == expected
        status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines()
                      if ':' in line)
        # Real credential transitions are independently exercised where the
        # executor owns these capabilities. A namespace-restricted Work
        # runner reports uid 0 but has CapEff=0; that is not a field PASS.
        needed = (1 << 6) | (1 << 7) | (1 << 8)
        if int(status['CapEff'], 16) & needed == needed:
            assert json.loads(subprocess.check_output(actual, **options, env=environment)) == expected
    finally:
        close_binding(result)
    # Equal bytes never authorize a replacement interpreter inode.
    replacement = runtime / 'bin/replacement'
    replacement.write_bytes(Path(copied).read_bytes())
    replacement.chmod(0o755)
    replacement.replace(copied)
    with pytest.raises(d.DispatchError, match='PROGRAM_CHANGED'):
        bound._installation_binding([copied])

"""Only synthetic roots and local test pipes; no approved field object is read."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

if not sys.platform.startswith('linux'):
    pytest.skip('Linux O_PATH, proc and resource boundaries', allow_module_level=True)

from e3_host import q2_host_reboot_read as h
from e3_host import q2_host_reboot_consumer as consumer


@pytest.fixture(autouse=True)
def private_umask():
    prior = os.umask(0o077)
    yield
    os.umask(prior)


@pytest.fixture
def fixture(tmp_path):
    root = tmp_path / 'root'
    for directory in ('usr/bin', 'objects', 'out', 'sources'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    for path in ('usr/bin/ss', 'usr/bin/qemu-system-x86_64', 'objects/serial',
                 'sources/source', *('objects/' + r for r in h.ROLES)):
        p = root / path
        p.write_bytes(b'fixed synthetic file')
        p.chmod(0o700 if path.startswith('usr') else 0o600)
    images = {r: dict(path='/objects/' + r, device=(root / 'objects' / r).stat().st_dev,
                     inode=(root / 'objects' / r).stat().st_ino) for r in h.ROLES}
    request = dict(R=h.R, A=h.A, B=h.B, C=h.C, D='d' * 40, scope=h.SCOPE, event=h.EVENT,
                   session=h.SESSION, nonce=str(uuid.uuid4()), limits=h.LIMITS, costs=h.COSTS,
                   owner_uid=os.geteuid(), old_host_boot='00000000-0000-0000-0000-000000000001',
                   rp2_host_boot='00000000-0000-0000-0000-000000000002',
                   inputs={'source': dict(path='/sources/source', **h.pin(b'fixed synthetic file'))},
                   tool_metadata={k: h.metadata((root / 'usr/bin' / n).stat()) for k, n in
                                  [('qemu', 'qemu-system-x86_64'), ('listener', 'ss')]},
                   target=dict(images=images, listener_argv=h.ARGV, pidfile='/objects/vm.pid',
                   serial_metadata_only='/objects/serial', host_boot_path='/proc/sys/kernel/random/boot_id',
                   self_namespaces=['/proc/self/ns/' + n for n in ('pid', 'mnt', 'net')],
                   qemu_metadata_path='/usr/bin/qemu-system-x86_64', maximum_pid_slots=2,
                   ssh_calls=0, network_requests=0, foreign_process_cmdline_read=False,
                   old_vm=dict(pid=12345, starttime=5, argv_sha256='f' * 64)))
    return root, request


def host(request):
    return dict(boot_id='00000000-0000-0000-0000-000000000002',
                namespaces=dict(pid='pid:[1]', mnt='mnt:[2]', net='net:[3]'))


def absent(pid, qemu, check):
    check()
    return dict(pid=pid, state='ABSENT')


def pipe_command(script='pass'):
    def command(argv, executable, pass_fds, check, save):
        def popen(*args, **kwargs):
            kwargs.pop('executable')
            kwargs.pop('pass_fds')
            return subprocess.Popen([sys.executable, '-I', '-B', '-c', script], **kwargs)
        return h.capture(argv, executable, pass_fds, check, save, popen=popen)
    return command


def run(fixture, **kwargs):
    root, request = fixture
    held = h.Held(lambda: None, root=str(root), tool_owner=os.geteuid())
    output = h.Outputs(held, '/out')
    # File/pipe unit cases are hosted by the entire pytest process. Its prior
    # suite CPU/RSS is not this synthetic reader's usage. Native resource tests
    # below and the private carrier tests run the unchanged Budget in fresh
    # processes; this seam supplies an explicitly synthetic positive sample.
    class FixtureBudget:
        last = dict(cpu_seconds=0.1, peak_rss_bytes=16777216, elapsed_seconds=0.1)

        def check(self):
            return self.last

    budget = FixtureBudget()
    try:
        rc = h.run_once(request, held=held, output=output, budget=budget,
                        host=kwargs.pop('host', host), process=kwargs.pop('process', absent),
                        command=kwargs.pop('command', pipe_command()), **kwargs)
        return rc, json.loads((root / 'out/read-result.json').read_bytes())
    finally:
        held.close()


def test_complete_real_pipes_and_old_boot_relation(fixture):
    rc, result = run(fixture)
    assert rc == 0 and result['state'] == 'FIXED_HOST_READ_COMPLETE'
    assert result['host_before'] == result['host_after']
    assert result['listener']['completion']['eof'] == {'stdout': True, 'stderr': True}
    assert result['processes'] == [{'pid': 12345, 'state': 'ABSENT'}]
    assert result['pidfile'] == {'state': 'ABSENT'}
    assert result['ssh_calls'] == result['vm_actions'] == 0


@pytest.mark.parametrize('value', [b'12345\n', b'67890\n'])
def test_pid_slots_deduplicate_and_never_expand(fixture, value):
    root, _ = fixture
    (root / 'objects/vm.pid').write_bytes(value)
    seen = []
    def process(pid, *args):
        seen.append(pid)
        return absent(pid, *args)
    assert run(fixture, process=process)[0] == 0
    assert seen == ([12345, 12345] if int(value) == 12345 else [12345, 67890, 12345, 67890])


@pytest.mark.parametrize('bad', [b'', b'1', b'-1', b' 7', b'123\n456', b'2147483648', b'x' * 65])
def test_bad_pidfile_stops_before_process_or_command(fixture, bad):
    root, _ = fixture
    (root / 'objects/vm.pid').write_bytes(bad)
    def forbidden(*args):
        pytest.fail('expanded after failure')
    rc, result = run(fixture, process=forbidden, command=forbidden)
    assert rc == 3 and result['stage'] == 'FIXED_FILES'


def test_symlink_pidfile_is_not_followed(fixture):
    root, _ = fixture
    (root / 'objects/vm.pid').symlink_to(root / 'sources/source')
    assert run(fixture)[0] == 3


@pytest.mark.parametrize('role', sorted(h.ROLES))
def test_each_image_identity_mismatch_is_fact(fixture, role):
    fixture[1]['target']['images'][role]['inode'] += 1
    rc, result = run(fixture)
    assert rc == 0 and result['images'][role]['matches_retained'] is False


@pytest.mark.parametrize('role', sorted(h.ROLES))
def test_each_image_writable_protection_stops_before_command(fixture, role):
    (fixture[0] / 'objects' / role).chmod(0o620)
    rc, result = run(fixture)
    assert rc == 3 and result['error']['reason'] == 'PROTECTION'
    assert result['listener_queries'] == 0


@pytest.mark.parametrize('kind', ['boot', 'namespace'])
def test_host_changes_stop_and_keep_originals(fixture, kind):
    seen = []
    def changed(target):
        value = host(target)
        if seen:
            if kind == 'boot':
                value['boot_id'] = str(uuid.uuid4())
            else:
                value['namespaces']['mnt'] = 'mnt:[4]'
        seen.append(1)
        return value
    rc, result = run(fixture, host=changed)
    assert rc == 3 and result['error']['reason'] == 'HOST_DRIFT'
    assert (fixture[0] / 'out/listener-completion.json').exists()


def test_present_listener_is_fact(fixture):
    script = "print('LISTEN 0 128 127.0.0.1:22221 0.0.0.0:*')"
    rc, result = run(fixture, command=pipe_command(script))
    assert rc == 0 and result['listener']['state'] == 'PRESENT'


@pytest.mark.parametrize('script', ["raise SystemExit(7)", "print('not a listener')",
                                    "import sys;sys.stderr.write('diagnostic')",
                                    "print('x'*65537)"])
def test_command_failures_retain_and_never_retry(fixture, script):
    assert run(fixture, command=pipe_command(script))[0] == 3
    output = fixture[0] / 'out'
    assert (output / 'listener.stdout').exists() and (output / 'listener.stderr').exists()
    original = (output / 'read-started.json').read_bytes()
    with pytest.raises(FileExistsError):
        run(fixture)
    assert (output / 'read-started.json').read_bytes() == original


def test_missing_eof_is_failure_even_with_zero_exit(tmp_path):
    saved = {}
    calls = []
    class Child:
        def __init__(self):
            self.readers, self.writers = [], []
            for _ in range(2):
                r, w = os.pipe()
                self.readers.append(os.fdopen(r, 'rb')); self.writers.append(w)
            self.stdout, self.stderr = self.readers
            self.returncode = 0
        def poll(self): return 0
        def wait(self, **kw): return 0
    child = Child()
    def check():
        calls.append(1)
        if len(calls) > 3:
            raise h.ReadError('DEADLINE')
    try:
        with pytest.raises(h.ReadError, match='CONTROL_INCOMPLETE'):
            h.capture(h.ARGV, '', (), check, lambda n, v: saved.update({n: v}),
                      popen=lambda *a, **kw: child)
        assert saved['listener-completion.json']['returncode'] == 0
        assert saved['listener-completion.json']['eof'] == {'stdout': False, 'stderr': False}
    finally:
        for fd in child.writers: os.close(fd)


def test_source_change_stops_before_tools(fixture):
    (fixture[0] / 'sources/source').write_bytes(b'changed')
    rc, result = run(fixture)
    assert rc == 3 and result['stage'] == 'INPUTS'
    assert result['listener_queries'] == 0


def test_image_drift_during_local_command(fixture):
    root, _ = fixture
    def command(*args):
        result = pipe_command()(*args)
        (root / 'objects/journal').write_bytes(b'drift')
        return result
    rc, result = run(fixture, command=command)
    assert rc == 3 and result['error']['reason'] == 'HELD_DRIFT'


def test_process_reuse_between_snapshots(fixture):
    calls = []
    def process(pid, qemu, check):
        calls.append(pid)
        return dict(pid=pid, state='OTHER_EXECUTABLE', starttime=len(calls))
    rc, result = run(fixture, process=process)
    assert rc == 3 and result['error']['reason'] == 'PROCESS_FINAL_DRIFT'


def test_real_proc_reader_foreign_process_never_reads_cmdline(tmp_path, monkeypatch):
    proc = tmp_path / 'proc'; pid = 123
    directory = proc / str(pid); directory.mkdir(parents=True)
    fields = ['S'] + ['0'] * 18 + ['42']
    (directory / 'stat').write_bytes(b'123 (fixture) ' + ' '.join(fields).encode())
    (directory / 'exe').symlink_to(sys.executable)
    # Any accidental cmdline access would fail; additionally record all bounded reads.
    reads = []
    original = h.kernel
    def kernel(path, *a, **kw):
        reads.append(path)
        return original(path, *a, **kw)
    monkeypatch.setattr(h, 'kernel', kernel)
    result = h.process_identity(pid, {}, lambda: None, proc=str(proc))
    assert result['state'] == 'OTHER_EXECUTABLE' and reads == ['stat', 'stat']
    assert h.process_identity(456, {}, lambda: None, proc=str(proc)) == dict(pid=456, state='ABSENT')


def evidence(fixture):
    root, request = fixture
    assert run(fixture)[0] == 0
    originals = {p.name: p.read_bytes() for p in (root / 'out').iterdir()}
    # Synthetic executable owners for the independent consumer fixture. No machine proof.
    result = h.parse(originals['read-result.json'])
    for role in ('qemu', 'listener'):
        request['tool_metadata'][role]['uid'] = 0
        result['tools'][role]['uid'] = 0
    request_raw = h.canonical(request)
    binding = dict(event=h.EVENT, session=h.SESSION, nonce=request['nonce'], request=h.pin(request_raw))
    result.update(binding)
    originals['read-started.json'] = h.canonical(binding)
    originals['read-result.json'] = h.canonical(result)
    index = h.parse(originals['read-index.json']); index['binding'] = binding
    index['files'] = {n: h.pin(v) for n, v in originals.items() if n != 'read-index.json'}
    originals['read-index.json'] = h.canonical(index)
    originals.update({'caller.stdout': b'', 'caller.stderr': b''})
    parent = dict(binding=binding, invocations=1, eof=dict(stdout=True, stderr=True), returncode=0,
                  stdout=h.pin(b''), stderr=h.pin(b''),
                  usage=dict(cpu_seconds=1,peak_rss_bytes=123456,elapsed_seconds=2))
    return [request_raw, originals, {'source': b'fixed synthetic file'}, parent, h.pin(request_raw)]


def test_independent_consumer_has_no_activation_or_release(fixture):
    result = consumer.consume(*evidence(fixture))
    assert result['state'] == 'CONSUMED_FIXED_HOST_READ_COMPLETE' and result['release'] is False
    assert result['core'] == 'NOT_RUN' and result['boot_matches_activation'] is False
    assert result['boot_matches_rp2'] is True and result['listener'] == 'ABSENT'


@pytest.mark.parametrize('change', ['nonce', 'source', 'eof', 'exit', 'extra', 'missing',
                                    'limits', 'costs', 'listener', 'process', 'image', 'stream'])
def test_independent_consumer_rejects_unbound_or_inconsistent_returns(fixture, change):
    args = evidence(fixture)
    originals, parent = args[1], args[3]
    if change == 'source': args[2]['source'] = b'changed'
    elif change == 'eof': parent['eof']['stderr'] = False
    elif change == 'exit': parent['returncode'] = 3
    elif change == 'extra': originals['extra.json'] = b'{}'
    elif change == 'missing': originals.pop('listener.stdout')
    elif change == 'stream': originals['caller.stdout'] = b'changed'
    else:
        result = h.parse(originals['read-result.json'])
        if change == 'nonce': result['nonce'] = str(uuid.uuid4())
        elif change == 'limits': result['limits']['process_fds'] = 512
        elif change == 'costs': result['costs']['total_mib'] -= 2
        elif change == 'listener': result['listener']['state'] = 'PRESENT'
        elif change == 'process': result['processes'].append({'pid': 987, 'state': 'ABSENT'})
        elif change == 'image': result['images']['seed']['matches_retained'] = False
        originals['read-result.json'] = h.canonical(result)
        index = h.parse(originals['read-index.json'])
        index['files']['read-result.json'] = h.pin(originals['read-result.json'])
        originals['read-index.json'] = h.canonical(index)
    with pytest.raises((consumer.EvidenceError, KeyError)):
        consumer.consume(*args)


@pytest.mark.parametrize('key', ['A', 'B', 'C', 'R', 'limits', 'costs'])
def test_request_authority_and_limits_cannot_be_substituted(fixture, key):
    fixture[1][key] = 'bad'
    rc, result = run(fixture)
    assert rc == 3 and result['stage'] == 'ADMISSION_OR_BUDGET'
    assert not (fixture[0] / 'out/listener-completion.json').exists()


def test_same_boot_is_observation_not_release(fixture):
    fixture[1]['old_host_boot'] = host(None)['boot_id']
    result = consumer.consume(*evidence(fixture))
    assert result['boot_matches_activation'] is True and result['release'] is False


def test_success_cannot_hide_missing_source_final_or_tool_pin(fixture):
    root, request = fixture
    request['tool_metadata']['qemu']['ino'] += 1
    rc, result = run(fixture)
    assert rc == 3 and result['error']['reason'] == 'TOOL_IDENTITY'
    assert result['listener_queries'] == 0


def test_absent_pidfile_cannot_appear_during_query(fixture):
    root, _ = fixture
    def command(*args):
        result = pipe_command()(*args)
        (root / 'objects/vm.pid').write_bytes(b'12345')
        return result
    rc, result = run(fixture, command=command)
    assert rc == 3 and result['error']['reason'] == 'ABSENCE_DRIFT'


def test_live_qemu_reader_stable_identity_and_namespaces(tmp_path, monkeypatch):
    proc = tmp_path / 'proc'; pid = 123
    directory = proc / str(pid); (directory / 'ns').mkdir(parents=True)
    fields = ['S'] + ['0'] * 18 + ['42']
    (directory / 'stat').write_bytes(b'123 (fixture) ' + ' '.join(fields).encode())
    (directory / 'exe').symlink_to(sys.executable)
    (directory / 'cmdline').write_bytes(b'qemu\0fixed\0')
    for name in ('pid', 'mnt', 'net'):
        (directory / 'ns' / name).symlink_to(name + ':[1]')
    original = os.readlink
    monkeypatch.setattr(os, 'readlink', lambda p, **kw: '/usr/bin/qemu-system-x86_64'
                        if p == 'exe' else original(p, **kw))
    meta = h.metadata(os.stat(directory / 'exe'))
    result = h.process_identity(pid, meta, lambda: None, proc=str(proc))
    assert result['state'] == 'QEMU' and result['starttime'] == 42
    assert result['argv_sha256'] == h.sha(b'qemu\0fixed\0')
    assert set(result['namespaces']) == {'pid', 'mnt', 'net'}


def test_output_record_limit_and_existing_marker_are_never_overwritten(fixture):
    root, _ = fixture
    held = h.Held(lambda: None, root=str(root))
    try:
        output = h.Outputs(held, '/out')
        with pytest.raises(h.ReadError, match='OUTPUT_LIMIT'):
            output.save('large.json', b'x' * 131073)
        output.save('marker.json', b'first')
        with pytest.raises(h.ReadError, match='OUTPUT_NAME'):
            output.save('marker.json', b'replaced')
        assert (root / 'out/marker.json').read_bytes() == b'first'
    finally:
        held.close()


@pytest.mark.parametrize('kind', ['cpu', 'rss', 'wall'])
def test_aggregate_budget_keeps_measured_failure(kind, monkeypatch):
    from types import SimpleNamespace
    budget = h.Budget()
    sample = SimpleNamespace(ru_utime=0.1, ru_stime=0.1, ru_maxrss=10)
    if kind == 'cpu': sample.ru_utime = 130
    if kind == 'rss': sample.ru_maxrss = 600 * 1024
    if kind == 'wall': budget.began -= 250
    monkeypatch.setattr(budget.resource, 'getrusage', lambda _: sample)
    with pytest.raises(h.ReadError, match='RESOURCE_LIMIT'):
        budget.check()
    assert budget.last is not None and budget.last['peak_rss_bytes'] > 0


def test_actual_256_fd_limits_with_full_read_lifecycle(fixture):
    root, request = fixture
    (root / 'request.json').write_bytes(h.canonical(request))
    code = r'''
import importlib.util,json,os,resource,sys
spec=importlib.util.spec_from_file_location('hb',sys.argv[1]);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
b=h.Budget();b.configure()
assert resource.getrlimit(resource.RLIMIT_NOFILE)==(256,256)
assert resource.getrlimit(resource.RLIMIT_AS)==(536870912,536870912)
root=sys.argv[2];request=json.load(open(root+'/request.json'))
held=h.Held(b.check,root=root,tool_owner=os.geteuid());out=h.Outputs(held,'/out')
def host(_):return dict(boot_id='00000000-0000-0000-0000-000000000002',namespaces=dict(pid='pid:[1]',mnt='mnt:[2]',net='net:[3]'))
def process(pid,*args):return dict(pid=pid,state='ABSENT')
def command(argv,exe,fds,check,save):
 import subprocess
 def popen(*args,**kwargs):
  kwargs.pop('executable');kwargs.pop('pass_fds')
  return subprocess.Popen([sys.executable,'-I','-B','-c','pass'],**kwargs)
 return h.capture(argv,exe,fds,check,save,popen=popen)
# 190 inherited descriptors leave a measured margin for held parents and the real pipe child.
fill=[os.open('/dev/null',os.O_RDONLY|os.O_CLOEXEC) for _ in range(190)]
try:
 assert h.run_once(request,held=held,output=out,budget=b,host=host,process=process,command=command)==0
 print(json.dumps(dict(fd_limit=256,as_limit=536870912,held_files=len(held.files),held_directories=len(held.dirs),usage=b.last)))
finally:
 held.close()
 for fd in fill:os.close(fd)
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, h.__file__, str(root)],
                            capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode()
    report = json.loads(result.stdout)
    assert report['fd_limit'] == 256 and report['held_files'] == 10

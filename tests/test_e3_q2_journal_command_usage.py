"""Owned control-child accounting across normal exit; no VM or field inputs."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux proc accounting", allow_module_level=True)

from command_usage_fixture import stat_record
from e3_host import q2_journal_growth as h


@pytest.fixture
def ordinary_budget(monkeypatch):
    # These identity cases model a short coordinator, not the pytest runner's
    # cumulative CPU after the complete suite. Real lifecycle runs separately.
    monkeypatch.setattr(h.resource, "getrusage", lambda _kind:
        SimpleNamespace(ru_utime=1, ru_stime=1, ru_maxrss=2048))


def test_cpu_and_rss_come_from_one_complete_stat_with_parentheses_in_name(monkeypatch):
    monkeypatch.setattr(os, "sysconf", lambda key: 100 if key == "SC_CLK_TCK" else 4096)
    raw = stat_record(101, start=201, cpu_ticks=300, rss_bytes=12288,
                      name=b"command ) with ( spaces")
    assert h.command_usage(101, raw) == (201, 3, 12288)


@pytest.mark.parametrize("state", [b"R", b"S", b"Z", b"X"])
def test_explicit_kernel_zero_rss_is_measured_not_substituted_for_missing_data(state):
    raw = stat_record(101, cpu_ticks=100, rss_bytes=0, state=state)
    assert h.command_usage(101, raw) == (201, 100 / os.sysconf("SC_CLK_TCK"), 0)


@pytest.mark.parametrize("change", ["pid", "truncated", "delimiter", "state",
                                  "cpu_negative", "rss_missing", "rss_negative",
                                  "rss_nonnumeric", "start_zero", "oversize_number"])
def test_incomplete_or_wrong_stat_is_rejected(change):
    raw = stat_record(101)
    head, sep, rest = raw.rpartition(b") ")
    fields = rest.split()
    if change == "pid":
        head = b"102 (fixture"
    elif change == "truncated":
        fields = fields[:21]
    elif change == "delimiter":
        sep = b" "
    elif change == "state":
        fields[0] = b"unknown"
    else:
        index, value = {"cpu_negative": (11, b"-1"), "rss_missing": (21, b""),
            "rss_negative": (21, b"-1"), "rss_nonnumeric": (21, b"unknown"),
            "start_zero": (19, b"0"), "oversize_number": (11, b"9" * 21)}[change]
        fields[index] = value
    if change == "rss_missing":
        raw = head + sep + b" ".join(fields[:21])
    else:
        raw = head + sep + b" ".join(fields)
    with pytest.raises(h.prior.r.ObservationError, match="^GROWTH_USAGE_STAT$"):
        h.command_usage(101, raw)


@pytest.mark.parametrize("binding", [None, {}, {"pid": 102, "starttime": 201},
                                   {"pid": 101, "starttime": 202},
                                   {"pid": 101, "starttime": True}])
def test_wrong_owned_child_identity_stops_with_diagnostic(monkeypatch, binding, ordinary_budget):
    child = SimpleNamespace(is_vm=False, identity=binding,
        process=SimpleNamespace(pid=101, poll=lambda: None))
    monkeypatch.setattr(h, "COMMANDS", [child])
    monkeypatch.setattr(h.custody, "ACTIVE", [])
    monkeypatch.setattr(h.custody, "proc", lambda *_: stat_record(101))
    with pytest.raises(h.prior.r.ObservationError, match="^GROWTH_USAGE_UNKNOWN$") as raised:
        h.management_usage()
    failure = raised.value.diagnostic["failed_children"][0]
    assert failure["stage"] == "process_identity" and failure["reason"] == "GROWTH_USAGE_IDENTITY"


def test_first_complete_observation_binds_missing_start_without_another_read(monkeypatch, ordinary_budget):
    child = SimpleNamespace(is_vm=False, identity=dict(pid=101, starttime=None),
        process=SimpleNamespace(pid=101, poll=lambda: None))
    calls = []
    def read(pid, name, limit):
        calls.append((pid, name, limit))
        return stat_record(pid)
    monkeypatch.setattr(h, "COMMANDS", [child])
    monkeypatch.setattr(h.custody, "ACTIVE", [])
    monkeypatch.setattr(h.custody, "proc", read)
    assert h.management_usage()["complete"] is True
    assert child.identity == dict(pid=101, starttime=201)
    assert calls == [(101, "stat", 4096)]


EXIT_LIFECYCLE = r'''
import json,resource,sys,time
sys.path.insert(0,sys.argv[1])
from e3_host import q2_journal_growth as h
resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
resource.setrlimit(resource.RLIMIT_AS,(256*1048576,256*1048576))
sampler=h.Usage();started=time.monotonic();samples=0;completed=0;observed_rss=0
source='import mmap,os,time; pages=[mmap.mmap(-1,65536) for _ in range(512)]; [p.write(b"x"*65536) for p in pages]; time.sleep(0.01); os._exit(0)'
real=h.command_usage
def parse(pid,raw):
    global observed_rss
    start,cpu,rss=real(pid,raw);observed_rss=max(observed_rss,rss)
    return start,cpu,rss
h.command_usage=parse
# Separate known fixtures exercise complete lifetimes, never rerun a failed one.
for case in range(8):
    command=h.Command([sys.executable,'-I','-c',source],lambda:None)
    try:
        while command.process.poll() is None:
            assert samples<100000 and time.monotonic()-started<10,(case,samples)
            sampler.sample();samples+=1
        assert command.collect()['returncode']==0
        completed+=1
    finally:
        command.process.wait(timeout=3)
        command.selector.close()
        command.process.stdout.close();command.process.stderr.close()
final=sampler.sample()
assert completed==8 and samples>0 and observed_rss>=16*1048576
assert all(command.process.returncode==0 for command in h.COMMANDS)
assert final['cpu_nanoseconds']>0 and final['rss_peak_bytes']>=observed_rss
print(json.dumps(dict(completed=completed,samples=samples,live_rss_observed=True,
 exited_cost_included=True,nofile=128,address_space=256*1048576)))
'''


def test_real_known_children_complete_exit_accounting_inside_original_limits():
    result = subprocess.run([sys.executable, "-I", "-c", EXIT_LIFECYCLE,
        str(Path(__file__).parent)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=20, check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    value = json.loads(result.stdout)
    assert value["completed"] == 8 and value["live_rss_observed"] and value["exited_cost_included"]


TRANSPORT_LIFECYCLE = r'''
import json,os,resource,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
from e3_host import q2_journal_growth as h
phase,mode=sys.argv[2:]
resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
resource.setrlimit(resource.RLIMIT_AS,(256*1048576,256*1048576))
sampler=h.Usage();reads=[];real=h.custody.proc
def observed(pid,name,limit):
    reads.append((pid,name,limit));return real(pid,name,limit)
h.custody.proc=observed
nonce,source='1'*64,'2'*64
old_boot='10000000-0000-4000-8000-000000000001'
new_boot='20000000-0000-4000-8000-000000000001'
value=dict(schema=h.REPORT_SCHEMA,session=h.SESSION,phase=phase,nonce=nonce,
 source_binding_sha256=source,boot_id=old_boot if phase=='pre' else new_boot,
 status='GUEST_QUIET' if phase=='pre' else 'FILESYSTEM_GROWN')
if phase=='post':value['original_boot_id']=old_boot
sha=h.digest(h.canonical(value))
with tempfile.TemporaryDirectory() as path:
    root=Path(path);release=root/'release-fixture'
    parent=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    exe=os.open(sys.executable,os.O_PATH|os.O_CLOEXEC)
    store=h.Store(parent,sampler.sample);transport=None
    peer='import sys,time\nfrom pathlib import Path\nsys.stdout.buffer.write('+repr(h.canonical(value))+');sys.stdout.flush()\n'
    if phase=='pre':
        ack=dict(schema=h.REPORT_SCHEMA,session=h.SESSION,status='POWER_OFF_REQUESTED',
            nonce=nonce,pre_report_sha256=sha,guest_startup_assurance=h.guest_startup_assurance())
        peer+='token=sys.stdin.buffer.readline()\nif token=='+repr(h.continue_token(nonce,sha))+':\n sys.stdout.buffer.write('+repr(h.canonical(ack))+');sys.stdout.flush()\n'
    else:
        peer+='end=time.monotonic()+5\nwhile not Path('+repr(str(release))+').exists() and time.monotonic()<end: time.sleep(.01)\n'
    argv=[sys.executable,'-I','-B','-c',peer]
    try:
        transport=h.MaintenanceTransport(SimpleNamespace(ssh=exe),store,argv,phase,
            nonce,source,old_boot,sampler.sample)
        assert transport.process.poll() is None
        # Constructor uses only its owned Popen identity; the original sampler
        # supplies start/CPU/RSS in exactly one read, including the SSH path.
        before=len(reads);first=sampler.sample()
        assert reads[before:]==[(transport.process.pid,'stat',4096)]
        assert transport.identity['pid']==transport.process.pid
        assert transport.identity['argv_sha256']==h.digest(h.canonical(argv))
        assert type(transport.identity['starttime']) is int and transport.identity['starttime']>0
        if mode=='drift':
            transport.identity['starttime']+=1
            try:sampler.sample()
            except h.prior.r.ObservationError as error:
                assert str(error)=='GROWTH_USAGE_UNKNOWN'
                failure=error.diagnostic['failed_children'][0]
                assert failure['stage']=='process_identity' and failure['reason']=='GROWTH_USAGE_IDENTITY'
            else:raise AssertionError('accepted changed transport identity')
            assert not transport.sent and transport.report is None
        else:
            assert transport.receive_report()==value
            if phase=='pre':transport.continue_poweroff(sha)
            else:release.write_bytes(b'fixture complete')
            result=transport.finish()
            assert result['returncode']==0 and all(result['eof'].values())
            assert sampler.sample()['cpu_nanoseconds']>=first['cpu_nanoseconds']>0
    finally:
        release.write_bytes(b'fixture complete')
        if transport is not None:
            transport.close();transport.process.wait(timeout=5)
        store.close();os.close(exe);os.close(parent)
print(json.dumps(dict(phase=phase,mode=mode,complete=True,nofile=128,address_space=256*1048576)))
'''


@pytest.mark.parametrize("phase", ["pre", "post"])
@pytest.mark.parametrize("mode", ["complete", "drift"])
def test_actual_transport_uses_owned_identity_and_real_accounting(phase, mode):
    result = subprocess.run([sys.executable, "-I", "-c", TRANSPORT_LIFECYCLE,
        str(Path(__file__).parent), phase, mode], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert json.loads(result.stdout) == dict(phase=phase, mode=mode, complete=True,
        nofile=128, address_space=256 * 1048576)

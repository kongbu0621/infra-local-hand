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

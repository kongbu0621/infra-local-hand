"""Real descriptor pressure in isolated synthetic children; never SSH or a VM."""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux resource limits and descriptors", allow_module_level=True)

from e3_host import q2_journal_growth as h


CHILD = r'''
import errno,json,os,resource,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
from e3_host import q2_journal_growth as h
mode,count=sys.argv[3],int(sys.argv[4])
anchor=os.open(sys.argv[2],os.O_RDONLY|os.O_DIRECTORY)
exe=os.open(sys.executable,os.O_PATH|os.O_CLOEXEC)
resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
def descriptors():
    result=set()
    for fd in range(128):
        try: os.fstat(fd)
        except OSError as e:
            assert e.errno==errno.EBADF
        else: result.add(fd)
    return result
fill=[]
while len(descriptors())<count:
    fill.append(os.open(os.devnull,os.O_RDONLY|os.O_CLOEXEC))
before=descriptors()
assert len(before)==count
identity=os.fstat(anchor)
if mode=='admission':
    try:
        h.host_fd_admission(anchor,lambda:None,'synthetic')
        result={'accepted':True}
    except h.prior.r.ObservationError as e:
        result={'accepted':False,'reason':str(e),'diagnostic':e.diagnostic}
    assert descriptors()==before
    assert os.fstat(anchor)==identity
else:
    store=h.Store(anchor,lambda:None)
    store.put('consumed.json',b'{}\n')
    store.event({'synthetic':True})
    try:
        h.MaintenanceTransport(SimpleNamespace(ssh=exe),store,
            [sys.executable,'-I','-B','-c','pass'],'pre','1'*64,'2'*64,
            '10000000-0000-4000-8000-000000000001',lambda:None)
    except OSError as e:
        assert e.errno==errno.EMFILE
        t=e.growth_transport
        assert t.process is None and not h.COMMANDS
        assert t.selector.get_map() is None
        assert descriptors()==before|set(store.opened.values())
        result={'reason':e.errno,'diagnostic':e.diagnostic,
            'outputs':sorted(store.opened)}
    else:
        raise AssertionError('expected real EMFILE before spawning synthetic peer')
    store.close()
    assert descriptors()==before
print(json.dumps(result))
'''


def isolated(tmp_path, mode, count):
    result = subprocess.run([sys.executable, "-I", "-B", "-c", CHILD,
        str(Path(__file__).parent), str(tmp_path), mode, str(count)],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr.decode()
    return json.loads(result.stdout)


@pytest.mark.parametrize("count,accepted", [(80, True), (108, True), (109, False),
                                          (116, False), (121, False)])
def test_actual_128_limit_reserves_full_lifecycle_without_releasing_identity(tmp_path, count, accepted):
    value = isolated(tmp_path, "admission", count)
    assert value["accepted"] is accepted
    if not accepted:
        assert value["reason"] == "GROWTH_HOST_FD_BUDGET"
        assert value["diagnostic"] == dict(operation="host_fd_admission", stage="synthetic",
            descriptor_limit=128, required_free=20, available_below_limit=128-count)


def test_prior_peak_reproduces_emfile_and_retains_outputs_without_selector_leak(tmp_path):
    value = isolated(tmp_path, "transport", 116)
    assert value["diagnostic"] == dict(operation="maintenance_transport_construct",
        stage="spawn", phase="pre", process_created=False)
    assert value["outputs"] == ["consumed.json", "events.jsonl", "pre.stderr", "pre.stdout"]


@pytest.mark.parametrize("stage", ["capture_stdout", "capture_stderr", "selector", "spawn", "pipe_registration"])
def test_partial_transport_construction_retains_files_closes_owned_io(tmp_path, monkeypatch, stage):
    anchor = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    store = h.Store(anchor, lambda: None)
    real_create, real_selector = store.create, h.selectors.DefaultSelector
    selectors, streams, spawned = [], [], []
    error = OSError(errno.EMFILE, "synthetic allocation failure")
    def create(name):
        if stage == "capture_" + name.split(".")[1]:
            raise error
        return real_create(name)
    def select():
        if stage == "selector":
            raise error
        value = real_selector()
        selectors.append(value)
        if stage == "pipe_registration":
            monkeypatch.setattr(value, "register", lambda *_: (_ for _ in ()).throw(error))
        return value
    def spawn(*args, **kwargs):
        if stage == "spawn":
            raise error
        for _ in range(3):
            streams.append(open(os.devnull, "rb"))
        value = SimpleNamespace(stdin=streams[0], stdout=streams[1], stderr=streams[2])
        spawned.append(value)
        return value
    monkeypatch.setattr(store, "create", create)
    monkeypatch.setattr(h.selectors, "DefaultSelector", select)
    monkeypatch.setattr(h, "COMMANDS", [])
    try:
        with pytest.raises(OSError) as failure:
            h.MaintenanceTransport(SimpleNamespace(ssh=anchor), store, ["synthetic"],
                "pre", "1"*64, "2"*64, "unused", lambda: None, popen=spawn)
        assert failure.value is error
        assert error.diagnostic["stage"] == stage
        assert error.diagnostic["process_created"] is bool(spawned)
        assert len(h.COMMANDS) == len(spawned)
        assert all(value.get_map() is None for value in selectors)
        assert all(value.closed for value in streams)
        assert len(store.opened) == (0 if stage == "capture_stdout" else 1 if stage == "capture_stderr" else 2)
        for fd in store.opened.values():
            assert os.fstat(fd).st_size == 0  # Evidence stays held by Store.
        error.growth_transport.close()
    finally:
        store.close()
        os.close(anchor)

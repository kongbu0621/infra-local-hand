"""T2 terminal-auth tests. No sudo, original VM, marker or maintenance action."""
from __future__ import annotations

import json
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux-only terminal contract", allow_module_level=True)

import fcntl
import termios

from e3_host import q2_journal_growth as h
from e3_host import q2_journal_growth_guest as g


def terminal_stat():
    return SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_dev=11, st_ino=12,
                           st_rdev=13, st_uid=1000, st_gid=1000)


def test_terminal_binding_is_foreground_pathless_and_exact(monkeypatch):
    monkeypatch.setattr(g.os, "fstat", lambda fd: terminal_stat())
    monkeypatch.setattr(g.os, "isatty", lambda fd: fd == 0)
    monkeypatch.setattr(g.os, "getsid", lambda pid: 20)
    monkeypatch.setattr(g.os, "getpgrp", lambda: 21)
    monkeypatch.setattr(g.os, "tcgetpgrp", lambda fd: 21)
    value = h.terminal_binding()
    assert value == dict(mode="terminal", sid=20, dev=11, ino=12, rdev=13,
                         uid=1000, gid=1000, perm=0o600)
    assert not any("path" in key or "name" in key for key in value)
    assert h.terminal_binding(value) == value
    monkeypatch.setattr(g.os, "getpgrp", lambda: 23)
    monkeypatch.setattr(g.os, "tcgetpgrp", lambda fd: 23)
    assert h.terminal_binding(value) == value  # A new foreground CLI may have a new PGID.
    with pytest.raises(g.r.ObservationError, match="DRIFT"):
        h.terminal_binding(value | {"ino": 99})
    monkeypatch.setattr(g.os, "tcgetpgrp", lambda fd: 22)
    with pytest.raises(g.r.ObservationError, match="FOREGROUND"):
        h.terminal_binding()
    monkeypatch.setattr(g.os, "isatty", lambda fd: False)
    with pytest.raises(g.r.ObservationError, match="FOREGROUND"):
        h.terminal_binding()


def test_only_terminal_command_keeps_control_tty_and_private_pipes(tmp_path):
    master, slave = os.openpty()
    worker = r'''
import json,os,sys
from e3_host import q2_journal_growth as h
b=h.terminal_binding()
p="""import json,os,sys
fd=os.open('/dev/tty',os.O_RDWR);os.write(fd,b'TTY_PROBE\\n');os.close(fd)
print(json.dumps({'sid':os.getsid(0),'stdin_eof':os.read(0,1)==b'',
'env':{k:os.environ.get(k) for k in ('PATH','LANG','LC_ALL','SUDO_ASKPASS','DISPLAY','WAYLAND_DISPLAY','WAYLAND_SOCKET')}}))
sys.stderr.write('FIXED_STDERR')"""
c=h.Command([sys.executable,'-I','-B','-c',p],lambda:None,terminal=True)
r=c.collect();h.terminal_binding(b)
print(json.dumps({'binding':b,'stdout':r['stdout'].decode(),'stderr':r['stderr'].decode(),
'eof':r['eof'],'returncode':r['returncode']}))
'''
    def controlling_terminal():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        os.tcsetpgrp(0, os.getpgrp())
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": str(Path(__file__).parent)}
    process = subprocess.Popen([sys.executable, "-c", worker], stdin=slave,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, preexec_fn=controlling_terminal)
    os.close(slave)
    try:
        stdout, stderr = process.communicate(timeout=8)
        tty = bytearray()
        limit = time.monotonic() + 1
        while time.monotonic() < limit:
            ready, _, _ = select.select([master], [], [], 0.05)
            if not ready:
                if process.poll() is not None:
                    break
                continue
            try:
                part = os.read(master, 4096)
            except OSError:
                break
            if not part:
                break
            tty.extend(part)
    finally:
        os.close(master)
    assert process.returncode == 0, stderr.decode(errors="replace")
    result = json.loads(stdout)
    child = json.loads(result["stdout"])
    assert child["sid"] == result["binding"]["sid"]
    assert child["stdin_eof"] is True
    assert child["env"] == {"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                            "SUDO_ASKPASS": None, "DISPLAY": None, "WAYLAND_DISPLAY": None,
                            "WAYLAND_SOCKET": None}
    assert result["stderr"] == "FIXED_STDERR"
    assert result["eof"] == {"stdout": True, "stderr": True} and result["returncode"] == 0
    assert b"TTY_PROBE" in tty


def test_nonterminal_commands_still_start_a_new_session(monkeypatch):
    calls = []
    class Stop(Exception):
        pass
    def popen(*args, **kwargs):
        calls.append(kwargs)
        raise Stop
    monkeypatch.setattr(h.subprocess, "Popen", popen)
    with pytest.raises(Stop):
        h.Command(["fixed"], lambda: None)
    with pytest.raises(Stop):
        h.Command(["fixed"], lambda: None, terminal=True)
    assert calls[0]["start_new_session"] is True
    assert calls[1]["start_new_session"] is False
    assert calls[1]["stdin"] is subprocess.DEVNULL
    assert calls[1]["env"] == {"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}

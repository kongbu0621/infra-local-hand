"""Outer byte capture of an existing, independently supervised Q2 controller.

No launch, signal, deadline renewal, unit-stop inference or acceptance decision.
The fixture owns the original Popen object and external service supervision.
"""
from __future__ import annotations

import hashlib
import io
import os
import select
import subprocess

from local_hand_jobs import quota_contract as q, budget
from .experiment_capture import _reader_identity


def capture_existing(process, *, boot_id, started_ns, deadline_ns, limit):
    q.require(type(process) is subprocess.Popen and not getattr(process,'_q2_capture_consumed',False), 'OUTER_ORIGINAL_CLIENT')
    q.integer(limit,1,32768);q.integer(started_ns,1)
    q.integer(deadline_ns,started_ns+1,started_ns+120_000_000_000)
    q.require(all(type(x) is io.FileIO and not x.closed for x in (process.stdout,process.stderr)), 'OUTER_UNBUFFERED_PIPES')
    process._q2_capture_consumed=True
    streams=dict(stdout=process.stdout,stderr=process.stderr)
    output={name:bytearray() for name in streams};eof=set();error=None;closes=[];identities={};previous=started_ns
    try:
        identities={name:_reader_identity(stream) for name,stream in streams.items()}
        q.require(identities['stdout'] != identities['stderr'],'OUTER_PIPE_ALIAS')
        for stream in streams.values():os.set_blocking(stream.fileno(),False)
        while True:
            clock=budget.current_clock();now=clock['boottime_ns']
            q.require(clock['boot_id'] == boot_id and previous <= now < deadline_ns,'OUTER_DEADLINE_OR_BOOT')
            previous=now
            if len(eof)==2 and process.poll() is not None:break
            readers=[stream for name,stream in streams.items() if name not in eof]
            ready=select.select(readers,[],[],min(0.025,(deadline_ns-now)/1e9))[0]
            for name,stream in streams.items():
                if stream not in ready:continue
                try:raw=os.read(stream.fileno(),4096)
                except BlockingIOError:continue
                if not raw:eof.add(name);continue
                room=limit-sum(map(len,output.values()))
                output[name].extend(raw[:room]);q.require(len(raw)<=room,'OUTER_BYTE_LIMIT')
    except (OSError,ValueError,RuntimeError) as exc:
        error=getattr(exc,'code',type(exc).__name__)
    finally:
        for name,stream in streams.items():
            try:stream.close()
            except OSError:closes.append(name)
    return dict(schema='local-hand-q2-outer-capture/v1',client_pid=process.pid,
        returncode=process.poll(),stdout=bytes(output['stdout']),stderr=bytes(output['stderr']),
        stdout_sha256=hashlib.sha256(output['stdout']).hexdigest(),stderr_sha256=hashlib.sha256(output['stderr']).hexdigest(),
        pipe_identities=identities,eof=sorted(eof),error=error,close_errors=closes,
        complete=error is None and not closes and len(eof)==2 and process.poll() is not None,
        started_ns=started_ns,deadline_ns=deadline_ns,independent_stop_required=True,
        production_supported=False,q3_accepted=False)

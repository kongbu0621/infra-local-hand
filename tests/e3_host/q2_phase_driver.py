"""Explicit test-only driver for one ALREADY prepared resident broker phase.

The trusted fixture supervisor supplies the inherited socket, live peer pin,
original grant and existing empty management record. No process/host/ledger
provisioning or production qualification override occurs here. This entry does
not construct a broker, issue a grant, or claim H01-H13 completion.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import socket
import sys


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture');parser.add_argument('--sha256')
    args=parser.parse_args(argv)
    result=dict(schema='local-hand-q2-phase-driver/v1',status='BLOCKED',q3_accepted=False,production_supported=False)
    record=channel=None;coordinator=None
    try:
        if not args.fixture or not args.sha256:raise ValueError('EXPLICIT_PRIVATE_FIXTURE_REQUIRED')
        # This adjacent trusted-source module is pinned again by the complete
        # fixture check before any runtime transport or manager construction.
        path=Path(__file__).with_name('q2_batch_check.py')
        spec=importlib.util.spec_from_file_location('_q2_fixture_check',path)
        check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
        raw=check.protected(args.fixture,check.LIMIT)
        if hashlib.sha256(raw).hexdigest()!=args.sha256:raise ValueError('FIXTURE_DIGEST')
        fixture=json.loads(raw,object_pairs_hook=check.unique)
        if (type(fixture) is not dict or set(fixture)!={'schema','preflight','bridge'}
                or fixture['schema']!='local-hand-q2-prepared-phase/v1'):raise ValueError('FIXTURE_SCHEMA')
        preflight=json.dumps(fixture['preflight'],sort_keys=True,separators=(',',':')).encode()
        declaration=check.decode(preflight,hashlib.sha256(preflight).hexdigest())
        if 'tests/e3_host/q2_phase_driver.py' not in declaration['files']:raise ValueError('DRIVER_PIN_MISSING')
        checked=check.check(declaration,Path(__file__).resolve().parents[2])
        if checked['status']!='CHECKED':
            result['preflight']=checked
            print(json.dumps(result,sort_keys=True,separators=(',',':')))
            return 3
        from local_hand_jobs import quota_contract as q, quota_bridge as bridge
        from admin.local_hand_quota_observer import q2_config as c, q2_management as m, q2_coordinator as driver
        pin=fixture['bridge']
        q._keys(pin,{'fd','pid','uid','gid','start_ticks','session','boot_id','deadline_ns'})
        q.integer(pin['fd'],3);q.integer(pin['pid'],1);q.integer(pin['start_ticks'],1)
        q.require((pin['uid'],pin['gid'])==(declaration['ordinary']['uid'],declaration['ordinary']['gid']),'BRIDGE_ACCOUNT')
        def start_ticks():
            with open('/proc/'+str(pin['pid'])+'/stat','rb') as stream:raw=stream.read(4097)
            q.require(len(raw)<=4096,'BRIDGE_PROC_LIMIT')
            return int(raw[raw.rfind(b')')+2:].split()[19])
        q.require(start_ticks()==pin['start_ticks'],'BRIDGE_PROCESS_REPLACED')
        sock=socket.socket(fileno=pin['fd'])
        try:
            channel=bridge.Channel(sock,peer=(pin['pid'],pin['uid'],pin['gid']),session=pin['session'],
                boot_id=pin['boot_id'],deadline_ns=pin['deadline_ns'])
        except BaseException:sock.close();raise
        q.require(start_ticks()==pin['start_ticks'],'BRIDGE_PROCESS_REPLACED')
        config=c.load(declaration['observer']['path'],declaration['observer']['sha256'])
        q.require(pin['boot_id']==config.active().request.as_dict()['boot_id'] and
                  pin['deadline_ns']<=declaration['controller_envelope']['deadline_ns'],'BRIDGE_ENVELOPE')
        # Verify the controller before acquiring any mutable record.
        m.controller(config,declaration['controller_envelope'])
        record=m.RunRecord(declaration['management_record'])
        coordinator=driver.Coordinator(config,declaration['controller_envelope'],record,bridge.Client(channel))
        result=coordinator.run()
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        result.update(status='INCOMPLETE' if coordinator and coordinator.used else 'BLOCKED',
                      reason=getattr(exc,'code',str(exc) if re.fullmatch(r'[A-Z_]{1,100}',str(exc)) else type(exc).__name__),events=[] if coordinator is None else coordinator.events)
    finally:
        if channel is not None:channel.close()
        if record is not None:record.close()
    print(json.dumps(result,sort_keys=True,separators=(',',':')))
    return 0 if result['status']=='PHASE_CLOSED' else 3


if __name__=='__main__':raise SystemExit(main())

"""One-phase administrator orchestration over an authenticated resident bridge.

Run under the actual independent controller checked by Management. All paths,
programs, peers and grants originate in the protected installation, not the
ordinary bridge response. No provisioning, retries, refund or restart adoption.
"""
from __future__ import annotations

import os
from pathlib import PurePosixPath
import stat
import time

from local_hand_jobs import quota_contract as q, quota_closure as close, quota_lifecycle, budget
from . import q2_config as c, q2_management as m
from .q2_journal import Journal
from .q2_service import Service
from .systemd_runtime import boottime_ns

SNAPSHOT_POLLS = 48  # Plus initial snapshot/bind/start/close stays below 64.
MANAGEMENT_POLLS = 10
MANAGEMENT_STOP_POLLS = 3


def ready(path, uid, gid, mode):
    """Observe, never connect to/consume the one-request socket for readiness."""
    parent = c.open_protected(str(PurePosixPath(path).parent), directory=True)
    try:
        try:info = os.stat(PurePosixPath(path).name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:return False
        if stat.S_ISSOCK(info.st_mode) and info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0:
            return False  # Listener has reserved the path but not published listen readiness.
        q.require(stat.S_ISSOCK(info.st_mode) and (info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode))
                  == (uid,gid,mode), 'COORDINATOR_ENDPOINT')
        return True
    finally:os.close(parent)


class Coordinator:
    def __init__(self, installation, envelope, record, client):
        self.config = installation
        self.client = client
        self.management = m.Management(installation,envelope,record)
        self.end = min(envelope['deadline_ns'],budget.phase_deadline_ns(installation.active().as_dict()['budget']))
        self.management_closed = False
        self.used = False
        self.failed = False
        self.events = []

    def _event(self, kind, value):
        # The caller's outer capture retains this bounded transcript alongside
        # management RunRecord and both original ledgers; it is not a third
        # authoritative ledger and cannot repair either original.
        q.require(len(self.events) < 12, 'COORDINATOR_EVENT_LIMIT')
        self.events.append(dict(kind=kind,digest=close.digest(value),observed_ns=boottime_ns()))

    def _pump(self):
        q.require(boottime_ns() < self.end, 'COORDINATOR_DEADLINE')
        if self.management_closed:return
        q.require(boottime_ns() < self.management.end, 'MANAGEMENT_DEADLINE')
        for part in self.management.runs.values():
            cap=part['capture'];cap.pump()
            q.require(cap.error is None and (not cap.exited or cap.process.returncode == 0), 'MANAGEMENT_CLIENT_FAILED')

    def _wait_socket(self, path, gid, mode):
        while True:
            self._pump()
            if ready(path,0,gid,mode):return
            time.sleep(0.01)

    def _snapshot(self):
        self._pump()
        result=self.client.call('snapshot')
        q._keys(result,{'preparation','observation','pending','closed'})
        data=self.config.active().as_dict()
        prep=result['preparation']
        q.require(prep['allocation'] == data['allocation'] and prep['budget'] == data['budget']
                  and prep['phase'] == data['request']['phase'], 'COORDINATOR_PREPARATION')
        return result

    def run(self):
        q.require(not self.used, 'COORDINATOR_CONSUMED')
        self.used=True
        journal=None
        try:
            config=self.config;data=config.data();grant=config.active();v=grant.as_dict()
            # Before any manager delivery, prove the original resident
            # preparation matches this fixed admin grant byte for byte.
            snapshot=self._snapshot()
            q.require(all(snapshot[k] is None for k in ('observation','pending','closed')), 'COORDINATOR_ALREADY_STARTED')
            self._event('PREPARATION',snapshot)
            journal=Journal(data['journal']['path'],data['journal']['pin'],data['capacity'],list(config.grants().values()))
            with journal.locked():
                state=journal.scan()[grant.request.as_dict()['request_id']]
                q.require(state['status'] == 'READY', 'COORDINATOR_REQUEST_CONSUMED')
            service=Service(journal,closure_version=2)
            self.management.begin()
            self._wait_socket(data['service']['control_path'],0,0o600)
            self.management.launch('admission')
            self._wait_socket(v['endpoint']['path'],v['endpoint']['gid'],0o660)
            # Both original manager invocations are bound before ordinary start.
            self.management.poll()
            q.require(all(p['invocation'] is not None for p in self.management.runs.values()), 'MANAGEMENT_IDENTITY_PENDING')
            self._event('ENDPOINT_READY',dict(config_digest=config.digest))
            self.client.call('bind',v)
            self.client.call('start')
            self._event('ORDINARY_START',dict(grant_digest=grant.digest))
            management=None;snapshot=None;next_snapshot=0;next_management=0
            management_polls=stop_polls=snapshot_polls=0
            while snapshot is None or snapshot['pending'] is None or management is None:
                self._pump()
                # --pipe clients may remain alive while RemainAfterExit is
                # active. Observe/stop the original service BEFORE requiring
                # client EOF; waiting for EOF first can deadlock. Ten regular
                # and three reserved post-stop polls cost at most 32 controls:
                # begin=2, initial=2, polls=26, the two original stops=2.
                if management is None:
                    stopped=all(p.get('stop_ok') and p.get('after') for p in self.management.runs.values())
                    done=None
                    if stopped:
                        # Services already have original post-stop facts. Only
                        # pump the original clients while waiting for real EOF;
                        # repeated systemctl calls would waste the finite budget.
                        if all(p['capture'].done for p in self.management.runs.values()):
                            done=self.management.finish()
                    elif boottime_ns() >= next_management:
                        stopping=any(p.get('stop_attempted') and p.get('after') is None
                                     for p in self.management.runs.values())
                        if stopping:
                            q.require(stop_polls < MANAGEMENT_STOP_POLLS, 'MANAGEMENT_STOP_POLL_LIMIT')
                            stop_polls += 1
                        else:
                            q.require(management_polls < MANAGEMENT_POLLS, 'MANAGEMENT_POLL_LIMIT')
                            management_polls += 1
                        if self.management.poll() is not None:
                            done=self.management.finish()
                        else:
                            now=boottime_ns()
                            stopping=any(p.get('stop_attempted') and p.get('after') is None
                                         for p in self.management.runs.values())
                            interval=10_000_000 if stopping else max(10_000_000,
                                (self.management.end-now)//(MANAGEMENT_POLLS+1-management_polls))
                            next_management=now+interval
                    if done is not None:
                        management=done
                        self.management_closed=True
                        self._event('MANAGEMENT_CLOSED',management)
                if boottime_ns() >= next_snapshot and (snapshot is None or snapshot['pending'] is None):
                    q.require(snapshot_polls < SNAPSHOT_POLLS, 'COORDINATOR_SNAPSHOT_LIMIT')
                    snapshot=self._snapshot();snapshot_polls += 1
                    now=boottime_ns()
                    next_snapshot=now+max(10_000_000,(self.end-now)//(SNAPSHOT_POLLS+1-snapshot_polls))
                time.sleep(0.01)
            ordinary=snapshot['pending']['proof']
            q.require(snapshot['closed'] is None and snapshot['observation'] is not None, 'COORDINATOR_ORIGINAL_OBSERVATION')
            with journal.locked():
                state=journal.scan()[grant.request.as_dict()['request_id']]
                q.require(state['status'] == 'RESULT', 'COORDINATOR_ORIGINAL_RESULT')
                stored=state['result']
                receipt=q.decode_receipt(q._canonical(stored['receipt'],q.RESPONSE_LIMIT),grant.request,
                    v['roots'],now_ns=stored['received_ns'])
                peer=state['intent']['peer']
            q.require(snapshot['observation']['observation']['receipt'] == receipt.as_dict(), 'COORDINATOR_RECEIPT_MISMATCH')
            parents={}
            for name,pin in (('ordinary',peer['parent']),('query',v['query_parent']),('management',v['management_parent'])):
                actual,empty=quota_lifecycle.parent('/sys/fs/cgroup'+pin['path'],pin)
                q.require(empty,'COORDINATOR_PARENT_OCCUPIED')
                facts=dict(identity=actual,populated=0,observed_ns=boottime_ns())
                parents[name]=dict(facts,proof_digest=close.digest(facts))
            fence=m.assemble(grant,receipt,peer,ordinary,management,parents,now_ns=boottime_ns())
            # Ordering is intentional. Lost ack after either durable closure
            # remains incomplete; never manufacture atomicity or rerun query.
            service.close_phase(grant.request,fence)
            self._event('ADMIN_CLOSED',fence)
            final=self.client.call('close',fence)
            q.require(final['closed']['fence'] == fence, 'BROKER_CLOSE_ACK')
            self._event('BROKER_CLOSED',fence)
            return dict(schema='local-hand-q2-coordinator/v1',status='PHASE_CLOSED',
                grant_digest=grant.digest,fence=fence,events=self.events,
                production_supported=False,q3_accepted=False)
        except BaseException:
            self.failed=True
            raise
        finally:
            if journal is not None:journal.close()

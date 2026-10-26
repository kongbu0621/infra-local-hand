"""Wait for one admitted task, then launch the existing bounded TaskService.

This administrator listener accepts only start/status for a fixed identity.
It accepts no executable, filesystem target, policy or task parameters from a
client. A retained launch intent survives an uncertain reply or daemon exit.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import stat
import struct
import subprocess
import threading
import time
import uuid

from local_hand_jobs import budget, cli, forwarded_bounds, maintenance, quota_contract as q
from local_hand_jobs.contract import JobError, strict_loads
from local_hand_jobs.evidence import _publish_create_only, _same
from admin.local_hand_quota_observer import controller_guard, q2_config
from admin.local_hand_quota_observer.protected_inputs import read_protected
from . import task_service


def acquire_service_lock(path):
    """Pin and protect the single recovery/dispatch owner before any recovery."""
    path=Path(path)
    info=path.stat()
    directory=q2_config.pinned_directory(dict(path=str(path),device=info.st_dev,inode=info.st_ino))
    lock=None
    try:
        info=os.fstat(directory)
        q.require(info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o700,'PREPARED_OUTPUT_PROTECTION')
        lock=os.open('service.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,
                     0o600,dir_fd=directory)
        info=os.fstat(lock)
        q.require(stat.S_ISREG(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o600
                  and info.st_nlink==1,'SERVICE_LOCK_PROTECTION')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        named=os.stat('service.lock',dir_fd=directory,follow_symlinks=False)
        q.require((named.st_dev,named.st_ino)==(info.st_dev,info.st_ino),'SERVICE_LOCK_CHANGED')
        return lock
    except BaseException:
        if lock is not None:os.close(lock)
        raise
    finally:os.close(directory)


def unit_closed(systemctl, unit):
    """Inactive alone does not rule out a queued systemd start job."""
    result=subprocess.run([systemctl,'show',unit,'-p','ActiveState','-p','Job'],
                          capture_output=True,text=True,timeout=3)
    values={}
    for line in result.stdout.splitlines():
        key,separator,value=line.partition('=')
        if not separator or key in values:return False
        values[key]=value
    return (result.returncode==0 and set(values)=={'ActiveState','Job'}
            and values['ActiveState'] in {'inactive','failed'} and values['Job'] in {'','0','0 /'})


def controller_command(launch, installation, static, dynamic):
    spec = launch['controller_envelope']['controller']
    controller_guard.decode_controller(dict(spec, invocation_id='0'*32, cgroup_device=0, cgroup_inode=1))
    programs = installation['installed']['programs']
    properties = dict(User='root', Group='root', Slice=Path(spec['cgroup']).parent.name,
        Type='exec', ExitType='cgroup', RemainAfterExit='no', Restart='no', RestartForceExitStatus='',
        KillMode='control-group', SendSIGKILL='yes', FinalKillSignal='SIGKILL', NotifyAccess='none',
        ExecStartPre='', ExecStartPost='', ExecStop='', ExecStopPost='', ExecReload='', OnFailure='', OnSuccess='',
        RuntimeMaxSec=str(spec['runtime_max_usec'])+'us', RuntimeRandomizedExtraSec='0',
        TimeoutStopSec=str(spec['timeout_stop_usec'])+'us', TimeoutStopFailureMode='kill',
        MemoryMax=str(spec['memory_bytes']), MemorySwapMax='0', TasksMax=str(spec['tasks_max']),
        CPUQuota=controller_guard.cpu_quota_percent(spec['cpu_quota_per_sec_usec']), CPUQuotaPeriodSec='100ms',
        LimitCPU=str(spec['limit_cpu_seconds']), UMask='0077', WorkingDirectory='/', NoNewPrivileges='yes',
        CapabilityBoundingSet='CAP_DAC_READ_SEARCH CAP_SETGID CAP_SETUID CAP_SETPCAP CAP_SYS_ADMIN',
        AmbientCapabilities='', StandardInput='null')
    return [programs['systemd_run']['path'], '--system', '--quiet', '--wait', '--pipe', '--no-ask-password',
        '--unit='+spec['unit'], *('--property='+k+'='+v for k,v in properties.items()), '--',
        programs['python']['path'], '-I', '-B', '-c',
        'import sys; sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)]; '
        'from admin.local_hand_system_manager.prepared_service import controller; controller(*sys.argv[1:])',
        installation['installed']['package_root'], installation['source']['root']+'/tools', static, dynamic]


def controller(static, dynamic):
    """Issue the existing 80-second execution window only after a real submit."""
    value = q._load(read_protected(static, 2*1024**2), 2*1024**2, 32)
    clock = budget.current_clock()
    spec = value['controller_envelope']['controller']
    q.require(Path('/proc/self/cgroup').read_text() == '0::'+spec['cgroup']+'\n', 'PREPARED_CONTROLLER_CGROUP')
    info = os.stat('/sys/fs/cgroup'+spec['cgroup'])
    spec.update(invocation_id=os.environ['INVOCATION_ID'], cgroup_device=info.st_dev, cgroup_inode=info.st_ino)
    value['controller_envelope'].update(issued_ns=clock['boottime_ns'],
        deadline_ns=clock['boottime_ns']+80*budget.NANOSECONDS)
    parent = os.open(str(Path(dynamic).parent), os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        task_service.save(parent, Path(dynamic).name, value)
    finally:
        os.close(parent)
    raise SystemExit(task_service.main(['--launch', dynamic]))


class FixedLauncher:
    def __init__(self, launch, installation, static, output, *, maintenance_gate=None, loaded=None, prepared=None):
        self.launch, self.installation, self.static = launch, installation, static
        self.output = Path(output)
        self.directory = q2_config.pinned_directory(dict(path=str(self.output),
            device=self.output.stat().st_dev, inode=self.output.stat().st_ino))
        directory=self.directory
        try:self._initialize_state(maintenance_gate,loaded,prepared)
        except BaseException:
            os.close(directory)
            raise

    def _initialize_state(self,maintenance_gate,loaded,prepared):
        info = os.fstat(self.directory)
        q.require(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700, 'PREPARED_OUTPUT_PROTECTION')
        self.process = None
        self.complete = threading.Event()
        self.record_lock = threading.Lock()
        self.result = None
        self.failure = None
        self.publication_failure = None
        self.local_failure = None
        self.intent_fd = None
        self.intent_identity = None
        self.sequence = 0
        self.maintenance_gate=maintenance_gate
        self.loaded_deployment=loaded
        self.maintenance_prepared=prepared
        self.maintenance_admission=None
        self.admission_attempt=None
        self.unstarted_admission=None
        self.popen_unresolved=False
        self.maintenance_recovery_pending=maintenance_gate is not None
        self.started = (self.output/'started.json').exists() or (self.output/'launch-intent.json').exists()
        self.finished = (self.output/'finished.json').exists()
        if self.finished:
            value = q._load(read_protected(str(self.output/'finished.json'), 256*1024), 256*1024, 12)
            q.require(value.get('streams_eof') is True and type(value.get('returncode')) is int,
                      'PREPARED_EXIT_PROOF')
            self.result=value
        if maintenance_gate is not None:
            try:duties=maintenance_gate.active()
            except JobError:pass # Preserve old reads, but absence was not proved.
            else:self._restore_maintenance_admission(duties)

    def _restore_maintenance_admission(self, duties):
        matches=[duty for duty in duties if duty['kind']=='execute'
                 and duty['operation_id']==self.launch['request']['operation_id']
                 and duty['binding'].get('prepared')==self.maintenance_prepared]
        if len(matches)>1:
            raise JobError('IO_UNCERTAIN','Several execution admissions need original-state inspection')
        self.maintenance_admission=matches[0] if matches else None
        self.maintenance_recovery_pending=False
        if matches and matches[0]['state']=='ACCEPTED' and not self.started:
            # The enclosing service lock excludes the old caller. Retain the
            # original receipt if confirming this closure loses its reply.
            self.unstarted_admission=matches[0]
            self._finish_unstarted_admission()

    def _retry_maintenance_recovery(self):
        if not getattr(self,'maintenance_recovery_pending',False):return
        try:self._restore_maintenance_admission(self.maintenance_gate.active())
        except (JobError,OSError,ValueError) as error:
            raise JobError('IO_UNCERTAIN','Original execution admissions need state inspection') from error

    def _maintenance_finish(self):
        gate=getattr(self,'maintenance_gate',None)
        receipt=getattr(self,'maintenance_admission',None)
        if gate is None or receipt is None or not self.finished:return
        try:
            proof=self.result
            if proof is None or proof.get('streams_eof') is not True:return
            if proof['returncode']!=0:
                if not unit_closed(self.installation['installed']['programs']['systemctl']['path'],
                                   self.launch['controller_envelope']['controller']['unit']):return
            gate.finish(receipt,dict(process_exited=True,writers_stopped=True))
        except (JobError,OSError,ValueError,KeyError,subprocess.SubprocessError):
            pass # Reads remain available; uncertain duty remains visible.

    def state(self):
        self._finish_local_failure()
        if getattr(self,'popen_unresolved',False):
            raise JobError('IO_UNCERTAIN','Original controller process creation is unresolved')
        self._finish_unstarted_admission()
        if self.failure is not None:
            raise JobError('IO_UNCERTAIN', 'Prepared controller capture needs inspection')
        if self.finished:
            try:self._retry_maintenance_recovery()
            except JobError:pass # The retained exit remains readable during a gate outage.
            self._maintenance_finish()
            return 'EXITED'
        if self.process is not None:
            if self.complete.is_set():
                with self.record_lock:
                    if not self.finished:
                        try:
                            self._publish_completion()
                        except (OSError, ValueError) as error:
                            self.publication_failure = type(error).__name__
                            raise JobError('IO_UNCERTAIN', 'Controller exited; completion record needs publication') from error
                        self.finished = True
                self._maintenance_finish()
                return 'EXITED'
            return 'RUNNING'
        if self.started:
            raise JobError('IO_UNCERTAIN', 'A prior launch is unresolved; inspect the original task')
        self._retry_maintenance_recovery()
        receipt=getattr(self,'maintenance_admission',None)
        if receipt is not None and receipt['state']=='DISPATCHING':
            raise JobError('IO_UNCERTAIN','Original execution admission has no local no-child proof')
        return 'IDLE'

    def retire_unstarted_admission(self):
        """Explicitly relinquish a failed acceptance before replacement/drain.

        Ordinary state reads retain the attempt for an authorized start retry.
        This lookup never accepts work, and cannot adopt another caller's duty.
        """
        self._finish_local_failure()
        if getattr(self,'popen_unresolved',False):
            raise JobError('IO_UNCERTAIN','Original controller process creation is unresolved')
        self._retry_maintenance_recovery()
        self._finish_unstarted_admission()
        attempt=getattr(self,'admission_attempt',None)
        if getattr(self,'maintenance_admission',None) is not None:
            raise JobError('IO_UNCERTAIN','Original execution admission still needs reconciliation')
        if attempt is None:return
        if self.process is not None or self.started or self.finished:
            raise JobError('IO_UNCERTAIN','Original acceptance has no local no-child proof')
        matches=[duty for duty in self.maintenance_gate.snapshot()['responsibilities'].values()
                 if duty['kind']=='execute' and duty['operation_id']==self.launch['request']['operation_id']
                 and duty['attempt_id']==attempt]
        if not matches:return # No admission exists; a later normal start can retry this same UUID.
        if (len(matches)!=1 or matches[0]['binding']!={'prepared':self.maintenance_prepared}
                or matches[0]['loaded']!=self.loaded_deployment
                or self.maintenance_prepared['resource_digest']!=maintenance.digest(self.launch)
                or matches[0]['state'] not in {'ACCEPTED','CLOSED'}
                or matches[0]['state']=='CLOSED' and matches[0]['proof']!={'never_dispatched':True}):
            raise JobError('IO_UNCERTAIN','Original acceptance binding or no-child state differs')
        # Retiring is now an explicit decision. Keep its exact receipt in the
        # existing no-child recovery slot before finish can lose its reply;
        # normal state/start must complete it rather than reopen a CLOSED UUID.
        self.maintenance_admission=matches[0]
        self.unstarted_admission=matches[0]
        self._finish_unstarted_admission()

    def _finish_unstarted_admission(self):
        receipt=getattr(self,'unstarted_admission',None)
        if receipt is None:return
        attempt=getattr(self,'admission_attempt',None)
        if (self.maintenance_admission!=receipt or self.process is not None or self.started
                or attempt is not None and attempt!=receipt['attempt_id']):
            raise JobError('IO_UNCERTAIN','Original no-child admission identity changed')
        try:self.maintenance_gate.finish(receipt,dict(never_dispatched=True))
        except (JobError,OSError,ValueError) as error:
            raise JobError('IO_UNCERTAIN','Original no-child admission still needs closure') from error
        self.maintenance_admission=None
        self.unstarted_admission=None
        if attempt is not None:self.admission_attempt=None

    def _retain_unstarted_intent(self, prefix):
        # Only paths reached before successful Popen may release this intent.
        # Keep this attempt's identity in memory across a storage outage. A new
        # daemon still treats a surviving intent as unknown and cannot replay it.
        # Latch the no-delivery proof before metadata or randomness can fail.
        # Identity comes from our O_EXCL descriptor, never a later name lookup.
        self.local_failure = dict(prefix=prefix, identity=getattr(self,'intent_identity',None),
                                  destination=None)
        self._finish_local_failure()

    def _pin_intent(self):
        fd = self.intent_fd
        info = os.fstat(fd)
        q.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                  and info.st_uid == os.fstat(self.directory).st_uid
                  and stat.S_IMODE(info.st_mode) == 0o600, 'PREPARED_INTENT_IDENTITY')
        self.intent_identity = _same(info)[:-1]
        self.intent_fd = None
        os.close(fd)

    def _finish_local_failure(self):
        pending = getattr(self, 'local_failure', None)
        if pending is None:return
        try:
            if pending['identity'] is None:
                if getattr(self,'intent_identity',None) is None:self._pin_intent()
                pending['identity'] = self.intent_identity
            if pending['destination'] is None:
                pending['destination'] = pending['prefix']+'-'+os.urandom(16).hex()+'.json'
            for _ in range(8):
                try:source = os.stat('launch-intent.json', dir_fd=self.directory, follow_symlinks=False)
                except FileNotFoundError:break  # A previous rename may precede a failed sync.
                q.require(_same(source)[:-1] == pending['identity'], 'PREPARED_INTENT_CHANGED')
                try:
                    _publish_create_only(Path('launch-intent.json'), Path(pending['destination']),
                                         source_dir_fd=self.directory, destination_dir_fd=self.directory)
                    break
                except FileExistsError:
                    pending['destination'] = pending['prefix']+'-'+os.urandom(16).hex()+'.json'
            else:raise OSError('Failure record names collided')
            retained = os.stat(pending['destination'], dir_fd=self.directory, follow_symlinks=False)
            # rename changes ctime; all other pinned fields must still match.
            q.require(_same(retained)[:-1] == pending['identity'], 'PREPARED_INTENT_CHANGED')
            os.fsync(self.directory)
            q.require(_same(os.stat(pending['destination'], dir_fd=self.directory, follow_symlinks=False))
                      == _same(retained), 'PREPARED_INTENT_CHANGED')
            try:os.stat('launch-intent.json', dir_fd=self.directory, follow_symlinks=False)
            except FileNotFoundError:pass
            else:raise ValueError('PREPARED_INTENT_CHANGED')
            self.local_failure = None
            self.intent_identity = None
        except (OSError, ValueError) as error:
            raise JobError('IO_UNCERTAIN', 'Unstarted attempt retained; failure publication needs retry') from error

    def _publish_completion(self):
        """Publish the captured result without exposing partial or replacing old bytes."""
        expected = q._canonical(self.result, 2*1024**2)+b'\n'
        flags = os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC
        try:
            fd = os.open('finished.json', flags, dir_fd=self.directory)
        except FileNotFoundError:
            # Failed writes retain their own attempt file. Only a complete,
            # synced record becomes visible to a restarted reader.
            temporary = '.finished-'+os.urandom(16).hex()+'.json'
            task_service.save(self.directory, temporary, self.result)
            _publish_create_only(Path(temporary), Path('finished.json'),
                                 source_dir_fd=self.directory, destination_dir_fd=self.directory)
            fd = os.open('finished.json', flags, dir_fd=self.directory)
        try:
            before = os.fstat(fd)
            q.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                      and before.st_uid == os.fstat(self.directory).st_uid
                      and stat.S_IMODE(before.st_mode) == 0o600
                      and before.st_size == len(expected), 'PREPARED_COMPLETION_IDENTITY')
            raw = bytearray()
            while len(raw) <= len(expected):
                chunk = os.read(fd, min(8192, len(expected)+1-len(raw)))
                if not chunk:break
                raw.extend(chunk)
            q.require(raw == expected, 'PREPARED_COMPLETION_CHANGED')
            # A previous directory sync may have failed after publication.
            # Reuse and synchronize that exact result, never rerun the child.
            os.fsync(fd)
            os.fsync(self.directory)
            q.require(_same(os.fstat(fd)) == _same(before)
                      == _same(os.stat('finished.json', dir_fd=self.directory, follow_symlinks=False)),
                      'PREPARED_COMPLETION_CHANGED')
        finally:
            os.close(fd)

    def _capture(self):
        # This worker was started before process delivery. Multiplex both
        # pipes here: allocating more threads after Popen could strand the
        # original child and leave the service reporting RUNNING forever.
        try:
            poller = select.poll()
            pending, streams = {}, {}
            for name in ('stdout','stderr'):
                stream = getattr(self.process, name)
                fd = stream.fileno()
                os.set_blocking(fd, False)
                poller.register(fd, select.POLLIN|select.POLLHUP|select.POLLERR)
                pending[fd] = (name, stream, bytearray(), 0)
            while pending:
                for fd, _ in poller.poll(100):
                    name, stream, content, total = pending[fd]
                    try:
                        raw = os.read(fd, 4096)
                    except BlockingIOError:
                        continue
                    if raw:
                        total += len(raw)
                        content.extend(raw[:max(0,32768-len(content))])
                        pending[fd] = (name, stream, content, total)
                    else:
                        poller.unregister(fd)
                        stream.close()
                        del pending[fd]
                        streams[name] = dict(hex=content.hex(), total_bytes=total, truncated=total>len(content))
            code = self.process.wait()
            self.result = dict(returncode=code, streams_eof=True, streams=streams)
            self.complete.set()
        except BaseException as error:
            self.failure = [type(error).__name__]
            for name in ('stdout','stderr'):
                try:getattr(self.process, name).close()
                except OSError:pass
            return
        try:
            self.state() # Persist exit/EOF even if no client polls again.
        except JobError:
            # Collection succeeded. A later poll can publish those same bytes;
            # only actual pipe/exit observation failure poisons the collector.
            pass

    def _commit_intent(self, command):
        raw = q._canonical(dict(command=command,
            operation_id=self.launch['request']['operation_id']), 2*1024**2)+b'\n'
        try:
            fd = os.open('launch-intent.json', os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                         0o600, dir_fd=self.directory)
        except FileExistsError as error:
            # This intent was not created by this call. Its effects are unknown.
            self.started = True
            raise JobError('IO_UNCERTAIN', 'A prior launch intent requires inspection') from error
        except OSError as error:
            raise JobError('IO_UNCERTAIN', 'Launch intent could not be opened; no process was created') from error
        self.intent_fd = fd
        self.intent_identity = None
        try:
            os.fchmod(fd, 0o600)
            pending = memoryview(raw)
            while pending:
                count = os.write(fd, pending)
                q.require(count > 0, 'PREPARED_INTENT_WRITE')
                pending = pending[count:]
            os.fsync(fd)
            os.fsync(self.directory)
            self._pin_intent()
        except (OSError, ValueError) as error:
            # O_EXCL proved this call created the intent, and Popen has not
            # run. Retain these bytes while allowing a later local retry.
            self._retain_unstarted_intent('local-intent-failed')
            raise JobError('IO_UNCERTAIN', 'Launch intent could not be committed; no process was created') from error

    def start(self, *, authorization=None):
        if authorization is not None:authorization.require_current()
        if self.state()!='IDLE':return self.state()
        gate=getattr(self,'maintenance_gate',None)
        receipt=None
        if gate is not None:
            if self.maintenance_admission is not None:
                # A reconstructed DISPATCHING receipt has no same-process
                # no-child fact. Missing intent files cannot authorize replay.
                raise JobError('IO_UNCERTAIN','Original execution admission still needs reconciliation')
            prepared=self.maintenance_prepared
            if (prepared is None or prepared.get('request_digest')!=self.launch['request']['request_digest']
                    or prepared.get('resource_digest')!=maintenance.digest(self.launch)):
                raise JobError('STALE_DEPLOYMENT','Original prepared resources differ from their deployment binding')
            if getattr(self,'admission_attempt',None) is None:self.admission_attempt=uuid.uuid4().hex
            # A failed acknowledgement may follow the durable acceptance.
            # Reconfirm that same attempt rather than hiding it with a new one.
            receipt=gate.accept('execute',self.launch['request']['operation_id'],self.admission_attempt,
                dict(prepared=prepared),self.loaded_deployment,authorization=authorization,prepared=prepared)
            self.maintenance_admission=receipt
            self.admission_attempt=None
        try:
            return self._start(authorization=authorization)
        except BaseException as error:
            # This process still owns the attempt and no Popen returned a
            # child. A durable dispatch intent alone does not fabricate a
            # remote effect; positive local no-delivery proof permits retry.
            if (receipt is not None and self.process is None and not self.started
                    and not getattr(self,'popen_unresolved',False)):
                self.unstarted_admission=receipt
                try:self._finish_unstarted_admission()
                except JobError as closure:
                    error.add_note('Original no-child closure remains pending: '+str(closure.__cause__)[:512])
            raise

    def _start(self, *, authorization=None):
        if authorization is not None:
            authorization.require_current()
        state = self.state()
        if state != 'IDLE':
            return state
        expected_boot = self.launch['policy']['process_manager']['manager_binding']['boot_id']
        q.require(budget.current_clock()['boot_id'] == expected_boot, 'PREPARED_BOOT_CHANGED')
        # A local process creation failure has no system-manager effect. Retain
        # it, then permit another attempt; uncertain started children do not replay.
        dynamic = str(self.output/('controller-'+str(time.time_ns())+'.json'))
        command = controller_command(self.launch, self.installation, self.static, dynamic)
        for name in ('python','systemd_run'):
            os.close(q2_config.executable(self.installation['installed']['programs'][name]))
        gate = threading.Event()
        delivered = False
        def capture_after_delivery():
            gate.wait()
            # The decision belongs to this attempt. A worker whose start
            # raised after native creation must never adopt a later child.
            if delivered:self._capture()
        worker = threading.Thread(target=capture_after_delivery, daemon=True)
        # Command construction and executable verification may outlive the
        # manager's admission check. Keep the original network deadline until
        # actual delivery, without imposing it on an already running task.
        if authorization is not None:
            authorization.require_current()
        self._commit_intent(command)
        try:
            try:
                worker.start()
            except BaseException as error:
                self._retain_unstarted_intent('local-start-failed')
                if isinstance(error, (KeyboardInterrupt, SystemExit)):raise
                raise JobError('IO_UNCERTAIN', 'Controller capture could not be started; no process was created') from error
            if authorization is not None:
                try:
                    authorization.require_current()
                except JobError:
                    # This attempt owns the intent, and no process has been
                    # delivered. Retain it without blocking a refreshed retry.
                    self._retain_unstarted_intent('local-authorization-expired')
                    raise
            try:
                if getattr(self,'maintenance_gate',None) is not None:
                    try:
                        self.maintenance_gate.dispatch(self.maintenance_admission,authorization=authorization)
                    except BaseException:
                        self._retain_unstarted_intent('local-maintenance-failed')
                        raise
                self.popen_unresolved=True
                self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, cwd='/', env={'PATH':'/usr/bin:/bin'})
            except OSError as error:
                self.popen_unresolved=False
                self._retain_unstarted_intent('local-start-failed')
                raise JobError('IO_UNCERTAIN', 'Controller process could not be created') from error
            self.popen_unresolved=False
            self.started = True
            delivered = True
        finally:
            gate.set()
        task_service.save(self.directory, 'started.json', dict(pid=self.process.pid,
            operation_id=self.launch['request']['operation_id']))
        # Readiness is only a socket observation. No helper submits a job here.
        endpoint = Path(self.launch['policy']['broker_root'])/'maintenance.sock'
        end = time.monotonic()+1.5
        while time.monotonic()<end and not self.complete.is_set():
            if endpoint.exists():
                info=endpoint.lstat()
                q.require(stat.S_ISSOCK(info.st_mode) and info.st_uid==self.launch['policy']['process_manager']['uid'],
                          'PREPARED_BACKEND_SOCKET')
                break
            time.sleep(.025)
        return self.state()


def bounded_request(request, launch):
    """Only narrow the fixed owner after serve authenticates its OS peer."""
    from local_hand_jobs.contract import Principal
    principal = None
    if 'authorization_bounds' in request:
        owner=launch['principal_id']
        peer=Principal(owner,frozenset(launch['policy']['principals'][owner]['scopes']))
        request,principal=forwarded_bounds.restrict(request,peer)
        scopes={'lh:submit'} if request.get('action')=='start' else {'lh:read','lh:submit','lh:cancel','lh:evidence'}
        if not scopes.intersection(principal.scopes):
            raise JobError('UNAUTHORIZED','Forwarded scope does not permit this action')
    if (set(request)!={'action','operation_id','request_digest'}
            or request['action'] not in ('start','status')
            or any(request[k]!=launch['request'][k] for k in ('operation_id','request_digest'))):
        raise JobError('UNAUTHORIZED','Only the original prepared identity is admitted')
    return request, principal


def serve(config):
    q.require(os.getuid()==os.geteuid()==0, 'PREPARED_ADMINISTRATOR')
    q.require(type(config) is dict and
        {'schema','launch_path','launch_sha256','installation','output','socket','descriptor'}<=config.keys()<=
        {'schema','launch_path','launch_sha256','installation','output','socket','descriptor','maintenance','maintenance_prepared'},
        'PREPARED_SERVICE_FIELDS')
    q.require(config['schema']=='local-hand-prepared-service/v1', 'PREPARED_SERVICE_SCHEMA')
    raw=read_protected(config['launch_path'], 2*1024**2)
    q.require(hashlib.sha256(raw).hexdigest()==config['launch_sha256'], 'PREPARED_LAUNCH_CHANGED')
    launch=q._load(raw,2*1024**2,32)
    q.require(launch['transport']=='broker' and launch['mcp'] is None, 'PREPARED_LOCAL_BACKEND')
    # Existing admission checks run before making the fixed launcher reachable.
    admission=task_service.TaskService(launch)
    admission.close()
    gate=maintenance.from_config(config)
    loaded=(maintenance.loaded_configuration(config,boot_id=budget.current_clock()['boot_id'])
            if gate is not None else None)
    # One listener owns recovery and dispatch for this immutable task. Never
    # retire an ACCEPTED receipt while an earlier caller can still deliver it.
    service_lock=acquire_service_lock(config['output'])
    launcher=FixedLauncher(launch,config['installation'],config['launch_path'],config['output'],
        maintenance_gate=gate,loaded=loaded,prepared=config.get('maintenance_prepared'))
    manager=launch['policy']['process_manager'];uid,gid=manager['uid'],manager['gid']
    endpoint=Path(config['socket']);parent=endpoint.parent
    for path in (parent,*parent.parents):
        info=path.lstat()
        q.require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,
                  'PREPARED_SOCKET_PARENT')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
        if gate is not None:
            from local_hand_jobs import startup
        with startup.authorize(config,loaded,gate) if gate is not None else nullcontext():
            listener.bind(str(endpoint));os.chown(endpoint,0,gid);endpoint.chmod(0o660);listener.listen(8)
        info=endpoint.lstat()
        descriptor=dict(schema='local-hand-prepared-task/v1',policy_path=config['launch_path'],
            request=launch['request'],principal_id=launch['principal_id'],
            launcher=dict(path=str(endpoint),device=info.st_dev,inode=info.st_ino))
        # The adapter uses the policy only; TaskService retains the root launch.
        descriptor['policy_path']=launch['policy_path']
        directory=os.open(str(Path(config['descriptor']).parent),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:task_service.save(directory,Path(config['descriptor']).name,descriptor,0o644)
        finally:os.close(directory)
        print(json.dumps({'status':'PREPARED_TASK_READY','operation_id':launch['request']['operation_id']}),flush=True)
        while True:
            connection,_=listener.accept()
            with connection:
                end=time.monotonic()+2
                try:
                    peer_pid,peer_uid,peer_gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    request=strict_loads(cli._read_frame(connection,4096,deadline=end))
                    if (request=={'action':'startup_authorize','component':'mcp'}
                            and (peer_uid==0 or (peer_uid,peer_gid)==(uid,gid))):
                        if gate is None:
                            raise JobError('UNSUPPORTED','Legacy service has no startup selection authority')
                        startup.serve_authorization(connection,config,gate,peer_pid=peer_pid)
                        continue
                    if peer_uid==0 and request in ({'action':'startup_authorize','component':'gateway','mode':'candidate'},
                                                    {'action':'startup_authorize','component':'gateway','mode':'public'}):
                        if gate is None:
                            raise JobError('UNSUPPORTED','Legacy service has no gateway startup authority')
                        startup.serve_gateway_authorization(connection,config,gate,
                            peer_pid=peer_pid,peer_uid=peer_uid,mode=request['mode'])
                        continue
                    if peer_uid==0 and request in ({'action':'deployment_status'},{'action':'deployment_observe'}):
                        if request['action']=='deployment_status':
                            if launcher.state()=='IDLE' and gate is not None and gate.snapshot()['state']=='CLOSED':
                                launcher.retire_unstarted_admission()
                        response={'result':dict(maintenance_supported=gate is not None,
                            loaded=maintenance.process_proof(loaded,protocol_ready=True) if gate is not None else None)}
                        cli._send_frame(connection,response,deadline=end,limit=4096)
                        continue
                    if (peer_uid,peer_gid)!=(uid,gid):raise JobError('UNAUTHORIZED','Prepared peer is not admitted')
                    request,authorization=bounded_request(request,launch)
                    bounds={} if authorization is None else {'authorization':authorization}
                    state=launcher.start(**bounds) if request['action']=='start' else launcher.state()
                    response={'result':{'state':state}}
                except JobError as error:response={'error':error.as_dict()}
                except (OSError,ValueError,TypeError):
                    response={'error':{'code':'IO_UNCERTAIN','message':'Prepared launch needs state inspection'}}
                try:cli._send_frame(connection,response,deadline=end,limit=4096)
                except (JobError,OSError):pass


def main(argv=None):
    parser=argparse.ArgumentParser(description='Serve one fixed prepared Local Hand task')
    parser.add_argument('--config',required=True)
    args=parser.parse_args(argv)
    serve(q._load(read_protected(args.config,2*1024**2),2*1024**2,32))


if __name__=='__main__':main()

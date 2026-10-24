"""Wait for one admitted task, then launch the existing bounded TaskService.

This administrator listener accepts only start/status for a fixed identity.
It accepts no executable, filesystem target, policy or task parameters from a
client. A retained launch intent survives an uncertain reply or daemon exit.
"""
from __future__ import annotations

import argparse
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

from local_hand_jobs import budget, cli, forwarded_bounds, quota_contract as q
from local_hand_jobs.contract import JobError, strict_loads
from local_hand_jobs.evidence import _publish_create_only, _same
from admin.local_hand_quota_observer import controller_guard, q2_config
from admin.local_hand_quota_observer.protected_inputs import read_protected
from . import task_service


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
    def __init__(self, launch, installation, static, output):
        self.launch, self.installation, self.static = launch, installation, static
        self.output = Path(output)
        self.directory = q2_config.pinned_directory(dict(path=str(self.output),
            device=self.output.stat().st_dev, inode=self.output.stat().st_ino))
        info = os.fstat(self.directory)
        q.require(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700, 'PREPARED_OUTPUT_PROTECTION')
        self.process = None
        self.complete = threading.Event()
        self.record_lock = threading.Lock()
        self.result = None
        self.failure = None
        self.publication_failure = None
        self.sequence = 0
        self.started = (self.output/'started.json').exists() or (self.output/'launch-intent.json').exists()
        self.finished = (self.output/'finished.json').exists()
        if self.finished:
            value = q._load(read_protected(str(self.output/'finished.json'), 256*1024), 256*1024, 12)
            q.require(value.get('streams_eof') is True and type(value.get('returncode')) is int,
                      'PREPARED_EXIT_PROOF')

    def state(self):
        if self.failure is not None:
            raise JobError('IO_UNCERTAIN', 'Prepared controller capture needs inspection')
        if self.finished:
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
                return 'EXITED'
            return 'RUNNING'
        if self.started:
            raise JobError('IO_UNCERTAIN', 'A prior launch is unresolved; inspect the original task')
        return 'IDLE'

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
        try:
            try:
                os.fchmod(fd, 0o600)
                pending = memoryview(raw)
                while pending:
                    count = os.write(fd, pending)
                    q.require(count > 0, 'PREPARED_INTENT_WRITE')
                    pending = pending[count:]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(self.directory)
        except (OSError, ValueError) as error:
            # O_EXCL proved this call created the intent, and Popen has not
            # run. Retain these bytes while allowing a later local retry.
            os.rename('launch-intent.json', 'local-intent-failed-'+str(time.time_ns())+'.json',
                      src_dir_fd=self.directory, dst_dir_fd=self.directory)
            os.fsync(self.directory)
            raise JobError('IO_UNCERTAIN', 'Launch intent could not be committed; no process was created') from error

    def start(self, *, authorization=None):
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
                os.rename('launch-intent.json', 'local-start-failed-'+str(time.time_ns())+'.json',
                          src_dir_fd=self.directory, dst_dir_fd=self.directory)
                os.fsync(self.directory)
                if isinstance(error, (KeyboardInterrupt, SystemExit)):raise
                raise JobError('IO_UNCERTAIN', 'Controller capture could not be started; no process was created') from error
            if authorization is not None:
                try:
                    authorization.require_current()
                except JobError:
                    # This attempt owns the intent, and no process has been
                    # delivered. Retain it without blocking a refreshed retry.
                    os.rename('launch-intent.json', 'local-authorization-expired-'+str(time.time_ns())+'.json',
                              src_dir_fd=self.directory, dst_dir_fd=self.directory)
                    os.fsync(self.directory)
                    raise
            try:
                self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, cwd='/', env={'PATH':'/usr/bin:/bin'})
            except OSError as error:
                os.rename('launch-intent.json', 'local-start-failed-'+str(time.time_ns())+'.json',
                          src_dir_fd=self.directory, dst_dir_fd=self.directory)
                os.fsync(self.directory)
                raise JobError('IO_UNCERTAIN', 'Controller process could not be created') from error
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
    q._keys(config, {'schema','launch_path','launch_sha256','installation','output','socket','descriptor'})
    q.require(config['schema']=='local-hand-prepared-service/v1', 'PREPARED_SERVICE_SCHEMA')
    raw=read_protected(config['launch_path'], 2*1024**2)
    q.require(hashlib.sha256(raw).hexdigest()==config['launch_sha256'], 'PREPARED_LAUNCH_CHANGED')
    launch=q._load(raw,2*1024**2,32)
    q.require(launch['transport']=='broker' and launch['mcp'] is None, 'PREPARED_LOCAL_BACKEND')
    # Existing admission checks run before making the fixed launcher reachable.
    admission=task_service.TaskService(launch)
    admission.close()
    launcher=FixedLauncher(launch,config['installation'],config['launch_path'],config['output'])
    manager=launch['policy']['process_manager'];uid,gid=manager['uid'],manager['gid']
    endpoint=Path(config['socket']);parent=endpoint.parent
    for path in (parent,*parent.parents):
        info=path.lstat()
        q.require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,
                  'PREPARED_SOCKET_PARENT')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
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
                    _,peer_uid,peer_gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if (peer_uid,peer_gid)!=(uid,gid):raise JobError('UNAUTHORIZED','Prepared peer is not admitted')
                    request=strict_loads(cli._read_frame(connection,4096,deadline=end))
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

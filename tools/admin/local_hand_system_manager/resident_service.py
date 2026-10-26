"""Persistent, bounded preparation service for the existing task executor.

The ordinary adapter supplies only a task UUID and an admitted principal. It
cannot select paths, programs, quota projects, installation or resource limits.
Preparation and execution have separate durable records; reads start neither.
"""
from __future__ import annotations

import argparse
from contextlib import closing, nullcontext
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import stat
import struct
import subprocess
import threading
import time
import uuid
import weakref

from local_hand_jobs import budget, cli, forwarded_bounds, maintenance, quota_contract as q
from local_hand_jobs.contract import DISABLED_JOB_KINDS, JobError, Principal, MAX_WORKSPACE_TEXT_BYTES, canonical_bytes, strict_loads, validate_tool_args
from local_hand_jobs.task_session import read_descriptor
from admin.local_hand_quota_observer.protected_inputs import read_protected, read_fd, file_identity
from . import provision_task, task_service
from .prepared_service import FixedLauncher, unit_closed


def load(path):
    return q._load(read_protected(str(path), 2*1024**2), 2*1024**2, 32)


def publish(path, value, mode=0o600, *, publication=None):
    """Replace only this service's current pointer; attempt records stay intact."""
    path=Path(path)
    directory=os.open(path.parent, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    name='.'+path.name+'-'+uuid.uuid4().hex
    try:
        task_service.save(directory, name, value, mode)
        if publication is not None:
            # Keep this exact candidate and parent alive across an uncertain
            # rename/sync reply. Same bytes at another inode are not its proof.
            publication['directory']=os.dup(directory)
            publication['file']=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,
                                        dir_fd=directory)
            publication['temporary']=name
            try:
                publication['previous']=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,
                                                dir_fd=directory)
            except FileNotFoundError:publication['previous']=None
            if publication['previous'] is not None:
                publication['previous_identity']=file_identity(os.fstat(publication['previous']))
            publication['rename_attempted']=True
        os.rename(name, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:os.close(directory)


class ReadyPublicationUncertain(JobError):
    def __init__(self):
        super().__init__('IO_UNCERTAIN','Original preparation publication needs confirmation')


def save_ready_failure(directory, failure):
    """Retain each distinct pending-publication error without growing on polls."""
    expected=q._canonical(failure,2*1024**2)+b'\n'
    original='preparation-failure.json'
    for name in (original,'preparation-failure-'+hashlib.sha256(expected).hexdigest()+'.json'):
        try:task_service.save(directory,name,failure)
        except FileExistsError:
            fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=directory)
            try:
                info=os.fstat(fd);before=file_identity(info)
                q.require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=2*1024**2,
                          'RESIDENT_FAILURE_RECORD_FILE')
                raw=read_fd(fd,2*1024**2)
                q.require(file_identity(os.fstat(fd))==before
                          and file_identity(os.stat(name,dir_fd=directory,follow_symlinks=False))==before,
                          'RESIDENT_FAILURE_RECORD_CHANGED')
                if raw==expected:
                    os.fsync(fd);os.fsync(directory)
                    q.require(file_identity(os.fstat(fd))==before
                              and file_identity(os.stat(name,dir_fd=directory,follow_symlinks=False))==before,
                              'RESIDENT_FAILURE_RECORD_CHANGED')
                    return
                q.require(name==original,'RESIDENT_FAILURE_RECORD_CONFLICT')
            finally:os.close(fd)
        else:return


def close_publication(publication):
    for key in ('file','previous','directory'):
        fd=publication.pop(key,None)
        if fd is not None:os.close(fd)


def close_pending_publications(pending):
    for _,publication in pending.values():close_publication(publication)
    pending.clear()


def confirm_publication(path, value, publication, *, expected_bytes=None):
    """Confirm only the original pinned candidate, including its durability."""
    directory,fd=publication['directory'],publication['file']
    expected=q._canonical(value,2*1024**2)+b'\n' if expected_bytes is None else expected_bytes
    def identity(info):return info.st_dev,info.st_ino
    parent=os.fstat(directory);original=os.fstat(fd)
    q.require(identity(Path(path).parent.stat(follow_symlinks=False))==identity(parent),'RESIDENT_PUBLICATION_PARENT')
    q.require(identity(os.stat(Path(path).name,dir_fd=directory,follow_symlinks=False))==identity(original),
              'RESIDENT_PUBLICATION_IDENTITY')
    q.require(stat.S_ISREG(original.st_mode) and original.st_nlink==1 and original.st_size==len(expected),
              'RESIDENT_PUBLICATION_FILE')
    os.lseek(fd,0,os.SEEK_SET);raw=bytearray()
    while len(raw)<=len(expected):
        part=os.read(fd,min(65536,len(expected)+1-len(raw)))
        if not part:break
        raw.extend(part)
    q.require(bytes(raw)==expected,'RESIDENT_PUBLICATION_BYTES')
    os.fsync(fd);os.fsync(directory)
    q.require(identity(Path(path).parent.stat(follow_symlinks=False))==identity(parent)
              and identity(os.stat(Path(path).name,dir_fd=directory,follow_symlinks=False))==identity(original),
              'RESIDENT_PUBLICATION_CHANGED')


def resume_publication(path, value, publication):
    """Retry the original rename only if both of its operands are still pinned."""
    path=Path(path);directory=publication['directory'];candidate=os.fstat(publication['file'])
    def identity(info):return info.st_dev,info.st_ino
    def current():
        try:return os.stat(path.name,dir_fd=directory,follow_symlinks=False)
        except FileNotFoundError:return None
    observed=current()
    if observed is None or identity(observed)!=identity(candidate):
        def check_previous():
            previous=publication['previous'];observed=current()
            if previous is None:
                q.require(observed is None,'RESIDENT_PUBLICATION_PREVIOUS')
            else:
                q.require(observed is not None and identity(observed)==identity(os.fstat(previous))
                          and file_identity(observed)==publication['previous_identity'],
                          'RESIDENT_PUBLICATION_PREVIOUS')
        check_previous()
        # A failed rename may have had no effect. Reuse its exact staged file;
        # a missing/replaced name or changed parent remains unresolved.
        confirm_publication(path.with_name(publication['temporary']),value,publication)
        check_previous()
        os.rename(publication['temporary'],path.name,src_dir_fd=directory,dst_dir_fd=directory)
    confirm_publication(path,value,publication)


def load_current(path):
    """Confirm a retained READY pointer before publishing it after restart."""
    path=Path(path)
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=directory)
        try:
            before=file_identity(os.fstat(fd))
            record=load(path) # Keep the existing protected ancestor/file checks.
            if record.get('state')=='READY':
                try:
                    # The held object must stay unchanged through protected
                    # loading. Preserve its original valid JSON bytes, including
                    # legacy formatting; this is not an old publisher FD claim.
                    raw=read_fd(fd,2*1024**2)
                    q.require(file_identity(os.fstat(fd))==before and q._load(raw,2*1024**2,32)==record,
                              'RESIDENT_CURRENT_CHANGED')
                    confirm_publication(path,record,dict(directory=directory,file=fd),expected_bytes=raw)
                    q.require(file_identity(os.fstat(fd))==before,'RESIDENT_CURRENT_CHANGED')
                except (OSError,ValueError) as error:
                    uncertain=ReadyPublicationUncertain()
                    uncertain.add_note('Retained READY confirmation failed: '+type(error).__name__+': '+str(error)[:2048])
                    raise uncertain from error
            return record
        finally:os.close(fd)
    finally:os.close(directory)


def check_local_a2_management_paths(config):
    """Keep resident bookkeeping outside every registered read-only runtime.

    This runs before startup publication/locking and before a new preparation's
    private attempt files. Provisioning separately checks its generated roots.
    """
    local=config.get('local_a2')
    if local is None:
        return
    q.require(type(local) is dict and type(local.get('runtimes')) is dict,
              'RESIDENT_RUNTIME_CONFIGURATION')
    paths=[config[key] for key in ('private_root','catalog','socket','socket_descriptor') if key in config]
    for reference,runtime in local['runtimes'].items():
        value=dict(local_a2=dict(inputs={'runtime_ref':reference},runtimes={reference:runtime}),bases=paths)
        provision_task.check_local_a2_paths_before_allocation(value,dict(directories={},roots=[]))


class ResidentService:
    def __init__(self, config):
        check_local_a2_management_paths(config)
        self.config=copy.deepcopy(config) if config.get('maintenance') is not None else config
        config=self.config
        self.root=Path(config['private_root']);self.catalog=Path(config['catalog'])
        self.fence=threading.RLock();self.worker=None;self.launchers={}
        self.boot=budget.current_clock()['boot_id']
        self.maintenance_gate=maintenance.from_config(config)
        self.loaded_deployment=(maintenance.loaded_configuration(config,boot_id=self.boot)
                                if self.maintenance_gate is not None else None)
        self.protocol_ready=False
        self.records={}
        # At most one pending publication per retained task; each owns at most
        # three FDs. Confirmation/close releases them, with GC as a fallback for
        # callers that abandon a service after an exception.
        self._pending_ready={}
        self._pending_cleanup=weakref.finalize(self,close_pending_publications,self._pending_ready)
        for path in sorted(self.root.glob('*/current.json')):
            record=load_current(path)
            operation=record['operation_id']
            validate_tool_args('lh_job_status',dict(operation_id=operation))
            q.require(path.parent.name==operation, 'RESIDENT_TASK_IDENTITY')
            self.records[operation]=record
        # The private record is authoritative. Publication may have been
        # interrupted after its commit but before replacing this derived view.
        for record in self.records.values():
            self._catalog(record)

    def close(self):
        with self.fence:self._pending_cleanup()

    def recover_undispatched(self):
        """Called only after acquiring the exclusive original service lock.

        Covers death between accepting duty and publishing the task's pointer.
        ACCEPTED proves the gate's durable dispatch barrier was never crossed;
        DISPATCHING requires original exit/unit proof and is never guessed away.
        """
        self._reconcile_preparations()

    def _preparation_duties(self, operation=None, *, include_closed=False):
        if self.maintenance_gate is None:return []
        return [duty for duty in self.maintenance_gate.snapshot()['responsibilities'].values()
                if duty['kind']=='prepare' and duty['binding'].get('private_root')==str(self.root)
                and (operation is None or duty['operation_id']==operation)
                and (include_closed or duty['state']!='CLOSED')]

    def _preparation_identity(self, duty):
        binding=duty['binding'];arguments=binding.get('arguments')
        q.require(set(binding)=={'arguments','principal_id','private_root'}
                  and binding['private_root']==str(self.root)
                  and type(arguments) is dict and type(binding['principal_id']) is str
                  and 0<len(binding['principal_id'])<=256,'RESIDENT_PREPARATION_BINDING')
        validate_tool_args('lh_job_prepare',arguments)
        operation_id=duty['operation_id']
        q.require(arguments['operation_id']==operation_id
                  and duty['loaded']['component']==self.loaded_deployment['component'],
                  'RESIDENT_PREPARATION_BINDING')
        record=self.records.get(operation_id)
        if record is not None:
            q.require(record['principal_id']==binding['principal_id'],'RESIDENT_PREPARATION_OWNER')
        attempt=Path(duty['attempt_id'])
        q.match(attempt.name,r'attempt-[1-9][0-9]{0,19}')
        q.require(str(attempt)==duty['attempt_id'] and attempt.parent==self.root/operation_id,
                  'RESIDENT_PREPARATION_PATH')
        return record,attempt

    @staticmethod
    def _not_started_proof(duty):
        return dict(schema='local-hand-preparation-not-started/v1',admission_id=duty['id'],
                    binding_digest=duty['binding_digest'])

    def _finish_unstarted_preparation(self, duty, record):
        # Absence is required, not a false/null decoded value. A saved exit,
        # dangling link or unreadable name conflicts with no-child recovery.
        try:(Path(duty['attempt_id'])/'preparation-exit.json').lstat()
        except FileNotFoundError:pass
        else:raise ValueError('RESIDENT_PREPARATION_START_CONFLICT')
        repair=(record is not None and record['attempt']==duty['attempt_id'] and record['state']=='PREPARING')
        if repair:
            q.require(record.get('maintenance_admission',{}).get('id')==duty['id'],
                      'RESIDENT_PREPARATION_BINDING')
        self.maintenance_gate.finish(duty,dict(never_dispatched=True))
        if repair:self._save(dict(record,state='FAILED'))

    def _reconcile_preparations(self, operation=None):
        """Recover original duties, including attempts no longer in current.json.

        The service fence/exclusive service lock excludes another dispatcher.
        Gate bindings retain the original attempt; only its protected delivery
        and exit records plus its exact inactive/job-free unit can close it.
        Missing or inconsistent proof stays unresolved and is retryable later.
        """
        if self.worker is not None and self.worker.is_alive():return
        for duty in self._preparation_duties(operation,include_closed=True):
            try:
                record,attempt=self._preparation_identity(duty)
                if duty['state']=='CLOSED':
                    # Closure and the current pointer are different durable
                    # writes. Repair only this exact unfinished local record;
                    # later attempts and successful preparations are untouched.
                    if (duty['proof']=={'never_dispatched':True} and record is not None
                            and record['attempt']==duty['attempt_id'] and record['state']=='PREPARING'):
                        self._finish_unstarted_preparation(duty,record)
                    continue
                if duty['state']=='ACCEPTED':
                    # No caller crossed the durable dispatch barrier. Identity
                    # still belongs to this service and original task; only the
                    # delivery/exit evidence can be omitted for an unstarted duty.
                    self._finish_unstarted_preparation(duty,record)
                    continue
                try:unstarted=load(attempt/'preparation-not-started.json')
                except FileNotFoundError:pass
                else:
                    q.require(unstarted==self._not_started_proof(duty),'RESIDENT_PREPARATION_START_PROOF')
                    self._finish_unstarted_preparation(duty,record)
                    continue
                serial=attempt.name.removeprefix('attempt-')
                unit='lhprepare'+uuid.UUID(duty['operation_id']).hex+'a'+serial+'.service'
                delivery=load(attempt/'preparation-delivery.json')
                q.require(type(delivery) is dict,'RESIDENT_PREPARATION_DELIVERY')
                command=delivery.get('command')
                q.require(type(command) is list and all(type(arg) is str for arg in command)
                          and [arg for arg in command if arg.startswith('--unit=')]==['--unit='+unit]
                          and command[-2:]==[str(attempt/'input.json'),str(attempt/'result.json')],
                          'RESIDENT_PREPARATION_DELIVERY')
                proof=load(attempt/'preparation-exit.json')
                q.require(type(proof) is dict and type(proof.get('returncode')) is int,
                          'RESIDENT_PREPARATION_EXIT')
                if unit_closed(self.config['installation']['installed']['programs']['systemctl']['path'],unit):
                    self.maintenance_gate.finish(duty,dict(process_exited=True,writers_stopped=True))
            except (JobError,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
                pass # Retain the original duty; never substitute another attempt's proof.

    def _catalog(self, record):
        public={k:record[k] for k in ('operation_id','principal_id','state')}
        if record['state']=='READY':
            public.update(request=record['request'],policy_path=record['policy_path'])
        publish(self.catalog/(record['operation_id']+'.json'),public,0o644)

    def _save(self, record):
        q.require(self._pending_cleanup.alive,'RESIDENT_CLOSED')
        if record['operation_id'] in self._pending_ready:raise ReadyPublicationUncertain()
        path=self.root/record['operation_id']/'current.json'
        publication={} if record['state']=='READY' else None
        retained=False
        try:
            try:publish(path,record,publication=publication)
            except OSError as error:
                if publication is not None and publication.get('rename_attempted'):
                    try:confirm_publication(path,record,publication)
                    except (OSError,ValueError) as confirmation:
                        self._pending_ready[record['operation_id']]=(copy.deepcopy(record),publication)
                        retained=True
                        uncertain=ReadyPublicationUncertain()
                        uncertain.add_note('Original publication failure: '+type(error).__name__+': '+str(error)[:2048])
                        uncertain.add_note('READY confirmation failed: '+type(confirmation).__name__+': '+str(confirmation)[:2048])
                        raise uncertain from error
                    # The original READY pointer did commit. Retain the initial
                    # failure through the caller, which must not demote it.
                    self.records[record['operation_id']]=record
                raise
        finally:
            if publication is not None and not retained:close_publication(publication)
        self.records[record['operation_id']]=record
        self._catalog(record)

    def _resume_ready(self, record):
        ready,publication=self._pending_ready[record['operation_id']]
        try:
            q.require(all(record[key]==ready[key] for key in ('operation_id','principal_id','attempt')),
                      'RESIDENT_PUBLICATION_TASK')
            resume_publication(self.root/record['operation_id']/'current.json',ready,publication)
        except (OSError,ValueError) as error:
            uncertain=ReadyPublicationUncertain()
            uncertain.add_note('Original READY publication confirmation failed: '+type(error).__name__+': '+str(error)[:2048])
            raise uncertain from error
        self.records[record['operation_id']]=ready
        del self._pending_ready[record['operation_id']]
        close_publication(publication)
        self._catalog(ready)
        return ready

    def _owned(self, operation, principal):
        record=self.records.get(operation)
        if record is None:raise JobError('NOT_FOUND','Task is not prepared')
        if record['principal_id']!=principal:raise JobError('UNAUTHORIZED','Task owner differs')
        return record

    def _unit_active(self, record):
        unit=record.get('controller_unit')
        if not unit:return False
        return self._observe_unit_active(unit)

    def _observe_unit_active(self, unit):
        result=subprocess.run([self.config['installation']['installed']['programs']['systemctl']['path'],
            'show',unit,'-p','ActiveState','-p','Job'],capture_output=True,text=True,timeout=3)
        values={}
        for line in result.stdout.splitlines():
            key,separator,value=line.partition('=')
            if not separator or key in values:
                raise JobError('IO_UNCERTAIN','Cannot observe the original system unit')
            values[key]=value
        active={'active','activating','deactivating','reloading'}
        if (result.returncode!=0 or set(values)!={'ActiveState','Job'}
                or values['ActiveState'] not in active|{'inactive','failed'}):
            raise JobError('IO_UNCERTAIN','Cannot observe the original system unit')
        # A stopped unit with a queued start still owns its original work.
        # Observe both properties in one reply before allowing replacement.
        return values['ActiveState'] in active or values['Job'] not in {'','0','0 /'}

    def _launcher(self, record):
        key=record['attempt']
        if key not in self.launchers:
            launch=load(record['launch_path'])
            bounds={}
            if self.maintenance_gate is not None:
                prepared=record.get('maintenance_prepared')
                if prepared is not None and (prepared.get('operation_id')!=record['operation_id']
                        or prepared.get('attempt_id')!=record['attempt']
                        or prepared.get('request_digest')!=launch['request']['request_digest']
                        or prepared.get('resource_digest')!=maintenance.digest(launch)):
                    raise JobError('STALE_DEPLOYMENT','Original preparation has no matching deployment binding')
                bounds=dict(maintenance_gate=self.maintenance_gate,loaded=self.loaded_deployment,prepared=prepared)
            self.launchers[key]=FixedLauncher(launch,self.config['installation'],
                record['launch_path'],record['output'],**bounds)
        return self.launchers[key]

    def execution_state(self, record):
        output=Path(record['output'])
        if (output/'finished.json').exists():
            launcher=self.launchers.get(record.get('attempt'))
            if launcher is not None and launcher.complete.is_set():
                # The name can exist before its directory sync succeeds.
                # Let the original collector verify/persist its own result.
                launcher.state()
            return self._captured_execution_state(record)
        intent=(output/'launch-intent.json').exists() or (output/'started.json').exists()
        if record['boot_id']!=self.boot:
            return 'UNRESOLVED' if intent else 'IDLE'
        launcher=self._launcher(record)
        try:state=launcher.state()
        except JobError as error:
            if error.code!='IO_UNCERTAIN':raise
            # A daemon restart loses the pipe collector, not the original task.
            # Reattach only its API for queries/submission deduplication. Never
            # issue another controller start for a retained launch intent.
            return 'RUNNING' if self._unit_active(record) else 'UNRESOLVED'
        return self._captured_execution_state(record) if state=='EXITED' else state

    def _captured_execution_state(self, record):
        proof=load(Path(record['output'])/'finished.json')
        q.require(type(proof.get('returncode')) is int and proof.get('streams_eof') is True,'RESIDENT_EXIT_PROOF')
        # Nonzero waiter exit plus EOF does not prove that its systemd unit
        # stopped. Keep routing to a live controller and fence new work until
        # it has stopped; an observation failure remains retryable uncertainty.
        if proof['returncode']!=0 and record['boot_id']==self.boot and self._unit_active(record):
            return 'RUNNING'
        return 'EXITED'

    def _has_committed_task(self, record):
        policy=load(record['launch_path'])['policy']
        path=Path(policy['broker_root'])/'jobs.sqlite'
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            return db.execute("select 1 from operations where namespace='job' and id=?",
                              (record['operation_id'],)).fetchone() is not None

    def _replaceable(self, record, *, failed_only=False):
        output=Path(record['output'])
        if not (output/'launch-intent.json').exists() and not (output/'started.json').exists():
            # A retry poll after successful preparation must keep the exact
            # READY request. Unsubmitted tasks are replaced only when stale.
            if not failed_only and not (output/'finished.json').exists():
                self._retire_unstarted_execution(record)
            return not failed_only
        # A proved pre-admission failure may be prepared again. A committed job,
        # missing exit capture or unknown write is never replaced.
        finished=output/'finished.json'
        if not finished.exists():return False
        proof=load(finished)
        return (type(proof.get('returncode')) is int and proof.get('streams_eof') is True
                and (record['boot_id']!=self.boot or not self._unit_active(record))
                and not self._has_committed_task(record))

    def _retire_unstarted_execution(self, record):
        if self.maintenance_gate is None:return
        def original(duty):
            return (duty['kind']=='execute' and duty['operation_id']==record['operation_id']
                    and duty['loaded']['component']==self.loaded_deployment['component']
                    and duty['binding'].get('prepared')==record.get('maintenance_prepared'))
        launcher=self.launchers.get(record['attempt'])
        if launcher is None and any(original(duty) for duty in self.maintenance_gate.active()):
            launcher=self._launcher(record)
        if launcher is not None:launcher.retire_unstarted_admission()
        if any(original(duty) for duty in self.maintenance_gate.active()):
            raise JobError('IO_UNCERTAIN','Original execution responsibility needs closure before replacement')

    def _busy(self, except_operation=None):
        if self.worker is not None and self.worker.is_alive():return True
        for record in self.records.values():
            attempt=Path(record['attempt'])
            if record['state']!='READY' and (attempt/'preparation-delivery.json').exists():
                # A failed/killed systemd-run waiter may leave its service
                # running. Only a successful --wait exit proves completion;
                # otherwise observe the original unit before admitting work.
                exit_path=attempt/'preparation-exit.json'
                code=load(exit_path).get('returncode') if exit_path.exists() else None
                if not (type(code) is int and code==0) and self._preparation_active(record):
                    return True
        return any(record['state']=='READY' and operation!=except_operation
                   and self.execution_state(record)=='RUNNING' for operation,record in self.records.items())

    def _preparation_active(self, record):
        return self._observe_unit_active(record['prepare_unit'])

    def prepare(self, args, principal, *, allow_new=True, authorization=None):
        check_local_a2_management_paths(self.config)
        operation=args['operation_id']
        if args['profile_ref']!=self.config['profile_ref']:
            raise JobError('UNAUTHORIZED','Preparation profile differs')
        if args['kind']=='workspace.edit':
            workspace=self.config.get('workspace',{})
            source=workspace.get('sources',{}).get(args['inputs']['source_ref'])
            if (source is None or args['inputs']['validation_ref'] not in source.get('validations',{})
                    or args['inputs']['relative_path'] not in source['blobs']):
                raise JobError('UNAUTHORIZED','Workspace source, file or validation is not admitted')
        # Old runtime registration cannot reactivate a retired temporary job.
        # Existing immutable preparations remain queryable with original inputs.
        allow_new = allow_new and args['kind'] not in DISABLED_JOB_KINDS
        with self.fence:
            record=self.records.get(operation)
            if record is None:
                # Admission may be the only durable identity when creating the
                # task directory/current pointer failed. Preserve that original
                # owner and request even after its local duty has been closed.
                for duty in self._preparation_duties(operation,include_closed=True):
                    self._preparation_identity(duty)
                    binding=duty['binding'];original=binding['arguments']
                    if binding['principal_id']!=principal:
                        raise JobError('UNAUTHORIZED','Task owner differs')
                    if (original['kind']!=args['kind'] or original['profile_ref']!=args['profile_ref']
                            or original.get('inputs',{})!=args.get('inputs',{})):
                        raise JobError('CONFLICT','Prepared task input changed; keep its original identity')
            if record is not None:
                self._owned(operation,principal)
                selected=record.get('request',record)
                if (selected.get('kind','host.inspect')!=args['kind']
                        or selected.get('inputs',{})!=args.get('inputs',{})):
                    raise JobError('CONFLICT','Prepared task input changed; keep its original identity')
                if record['state']=='PREPARING':
                    if self.worker is not None and self.worker.is_alive():
                        return dict(operation_id=operation,state='PREPARING')
                    # After restart, recover a completed preparation or retain
                    # its failure. Neither path submits any business operation.
                    if operation not in self._pending_ready and self._preparation_active(record):
                        return dict(operation_id=operation,state='PREPARING')
                    if operation in self._pending_ready or (Path(record['attempt'])/'result.json').exists():
                        try:record=self._ready(record)
                        except Exception as error:record=self._preparation_failed(record,error)
                    else:
                        record=dict(record,state='FAILED');self._save(record)
                if record['state']=='READY':
                    if not allow_new:
                        self._catalog(record)
                        return dict(operation_id=operation,state='READY',request=record['request'])
                    stale=record['boot_id']!=self.boot or record['request']['expires_at']<=time.time()
                    if self.maintenance_gate is not None:
                        bound=record.get('maintenance_prepared',{})
                        stale=stale or any(bound.get(key)!=self.loaded_deployment[key] for key in
                                          ('deployment_digest','configuration_digest','payload_digest'))
                    if (args.get('retry_failed') and self.config.get('installation',{}).get('source')
                            and record.get('launch_path')):
                        original=load(record['launch_path'])['policy']
                        # A local admission failure before execution may use
                        # the repaired installation under the same UUID. Keep
                        # completed or possibly delivered work on its version.
                        stale = stale or (original['source_commit']!=self.config['installation']['source']['commit']
                                          and not self._has_committed_task(record))
                    if not (stale or args.get('retry_failed')) or not self._replaceable(record,failed_only=not stale):
                        self._catalog(record)
                        return dict(operation_id=operation,state='READY',request=record['request'])
                if record['state']=='FAILED' and (not args.get('retry_failed') or not allow_new):
                    return dict(operation_id=operation,state='FAILED',retryable=allow_new)
            if not allow_new:
                raise JobError('UNSUPPORTED','This job is not available for new preparation')
            if self._busy():raise JobError('RESOURCE_BUSY','Another task is preparing or running')
            self._reconcile_preparations(operation)
            if self._preparation_duties(operation):
                raise JobError('IO_UNCERTAIN','Original preparation responsibility needs closure before retry')
            if record is None and len(self.records)>=self.config['max_tasks']:
                raise JobError('LIMIT_EXCEEDED','Retained task capacity is full')
            operation_root=self.root/operation
            used=[int(p.name.split('-')[-1]) for p in self.root.glob('*/attempt-*') if p.is_dir()]
            # Admission can commit before mkdir/current publication fails. Its
            # retained identity reserves the serial even without a directory.
            # The quota sequence is global across this service's tasks.
            for duty in self._preparation_duties(include_closed=True):
                _,reserved=self._preparation_identity(duty)
                used.append(int(reserved.name.removeprefix('attempt-')))
            serial=max(used,default=0)+1
            if self.config['first_project_id']+serial*7-1>self.config['last_project_id']:
                raise JobError('LIMIT_EXCEEDED','Configured quota project range is full')
            if authorization is not None:
                authorization.require_current()
            attempt=operation_root/('attempt-'+str(serial))
            record=dict(operation_id=operation,principal_id=principal,state='PREPARING',attempt=str(attempt),
                serial=serial,boot_id=self.boot,prepare_unit='lhprepare'+uuid.UUID(operation).hex+'a'+str(serial)+'.service')
            if args['kind'] in {'workspace.edit','ledger.test.local_a2'}:
                record.update(kind=args['kind'],inputs=args['inputs'])
            receipt=None
            if self.maintenance_gate is not None:
                receipt=self.maintenance_gate.accept('prepare',operation,str(attempt),
                    dict(arguments=args,principal_id=principal,private_root=str(self.root)),
                    self.loaded_deployment,authorization=authorization)
                record['maintenance_admission']=receipt
            ready=threading.Event()
            started=False
            def work_after_start():
                ready.wait()
                if started:self._prepare_worker(*worker_args)
            try:
                operation_root.mkdir(mode=0o700,exist_ok=True)
                attempt.mkdir(mode=0o700)
                self._save(record)
                worker_args=(record,) if authorization is None else (record,authorization)
                self.worker=threading.Thread(target=work_after_start,daemon=True)
                self.worker.start()
                started=True
            except BaseException:
                # Even if native thread creation happened, it cannot dispatch
                # until successful start() acknowledgement sets started.
                if receipt is not None and not started:
                    self.maintenance_gate.finish(receipt,dict(never_dispatched=True))
                raise
            finally:
                ready.set()
            return dict(operation_id=operation,state='PREPARING')

    def _ready(self, record):
        if record['operation_id'] in self._pending_ready:return self._resume_ready(record)
        prepared=load(Path(record['attempt'])/'result.json')
        launch=prepared['launch'];request=launch['request']
        q.require(request['operation_id']==record['operation_id'] and launch['principal_id']==record['principal_id'],
                  'RESIDENT_PREPARED_IDENTITY')
        q.require(request['kind']==record.get('kind','host.inspect')
                  and request['inputs']==record.get('inputs',{}),'RESIDENT_PREPARED_INPUTS')
        admission=task_service.TaskService(launch)
        admission.close()
        output=Path(record['attempt'])/'execution'
        output.mkdir(mode=0o700,exist_ok=True)
        record=dict(record,state='READY',request=request,policy_path=launch['policy_path'],
            launch_path=str(Path(prepared['reservation'])/'launch-static.json'),output=str(output),
            controller_unit=launch['controller_envelope']['controller']['unit'])
        if self.maintenance_gate is not None:
            original=record.get('maintenance_admission')
            if original is None:
                raise JobError('STALE_DEPLOYMENT','Preparation did not enter the shared maintenance barrier')
            record['maintenance_prepared']=maintenance.prepared_binding(original['loaded'],
                operation_id=record['operation_id'],attempt_id=record['attempt'],
                request_digest=request['request_digest'],launch=launch)
        self._save(record)
        return record

    def _prepare_worker(self, record, authorization=None):
        attempt=Path(record['attempt'])
        receipt=record.get('maintenance_admission')
        delivered=False
        waiter_exited=False
        closed=False
        try:
            extra={'workspace_inputs':record['inputs']} if record.get('kind')=='workspace.edit' else {}
            if record.get('kind')=='ledger.test.local_a2':
                extra={'local_a2_inputs':record['inputs']}
            value=provision_task.task_input(self.config,record['operation_id'],record['principal_id'],record['serial'],**extra)
            publish(attempt/'input.json',value)
            installation=self.config['installation'];programs=installation['installed']['programs']
            command=[programs['systemd_run']['path'],'--quiet','--wait','--pipe','--unit='+record['prepare_unit'],
                '--property=Type=exec','--property=RuntimeMaxSec=70s','--property=TimeoutStopSec=2s',
                '--property=KillMode=control-group','--property=MemoryMax=256M','--property=TasksMax=32',
                '--property=CPUQuota=100%','--property=NoNewPrivileges=yes','--property=UMask=0077','--',
                programs['python']['path'],'-I','-B','-c',
                'import sys;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];'
                'from admin.local_hand_system_manager.resident_service import prepare_main;prepare_main(*sys.argv[1:])',
                installation['installed']['package_root'],installation['source']['root']+'/tools',
                str(attempt/'input.json'),str(attempt/'result.json')]
            publish(attempt/'preparation-delivery.json',dict(command=command))
            if authorization is not None:authorization.require_current()
            if receipt is not None:
                self.maintenance_gate.dispatch(receipt,authorization=authorization)
            delivered=True
            try:
                process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,env={'PATH':'/usr/bin:/bin'},cwd='/')
            except OSError:
                # Only Popen failure proves no child was returned. A capture
                # error or timeout after this point must keep delivery unknown.
                delivered=False
                raise
            try:
                with process:
                    try:stdout,stderr=process.communicate(timeout=78)
                    except BaseException:
                        process.kill()
                        raise
                    result=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
                waiter_exited=True
            except BaseException as error:
                # The context manager has reaped the actual waiter. Capture
                # failure is not non-delivery and does not prove its systemd
                # unit stopped; retain only the known exit and partial streams.
                if type(process.returncode) is int:
                    waiter_exited=True
                    proof=dict(returncode=process.returncode,capture_complete=False)
                    for name in ('stdout','stderr'):
                        partial=getattr(error,name,None)
                        if type(partial) is bytes:
                            proof[name]=partial[:32768].hex();proof[name+'_bytes']=len(partial)
                    try:publish(attempt/'preparation-exit.json',proof)
                    except (OSError,ValueError) as recording_error:
                        error.add_note('Waiter exit proof publication failed: '+type(recording_error).__name__)
                raise
            publish(attempt/'preparation-exit.json',dict(returncode=result.returncode,
                stdout=result.stdout[:32768].hex(),stderr=result.stderr[:32768].hex(),
                stdout_bytes=len(result.stdout),stderr_bytes=len(result.stderr)))
            if result.returncode!=0:raise ValueError('PROVISION_PROCESS_FAILED')
            closed=True
            with self.fence:self._ready(record)
        except BaseException as error:
            if receipt is not None and not delivered:
                # This includes a failed dispatch-record acknowledgement:
                # Popen was never reached, regardless of what gate write stuck.
                try:publish(attempt/'preparation-not-started.json',self._not_started_proof(receipt))
                except (OSError,ValueError) as recording_error:
                    error.add_note('No-delivery proof publication failed: '+type(recording_error).__name__)
            with self.fence:self._preparation_failed(record,error)
        finally:
            if receipt is not None:
                try:
                    if not delivered:
                        self.maintenance_gate.finish(receipt,dict(never_dispatched=True))
                    elif closed or (waiter_exited and unit_closed(
                            self.config['installation']['installed']['programs']['systemctl']['path'],record['prepare_unit'])):
                        self.maintenance_gate.finish(receipt,dict(process_exited=True,writers_stopped=True))
                except (JobError,OSError,ValueError,subprocess.SubprocessError):
                    pass # Unobserved closure remains visible to deployment.

    def deployment_observe(self):
        """Strictly read-only proof for planning; no responsibility reconciliation."""
        if self.maintenance_gate is None:
            return dict(maintenance_supported=False)
        marker=self.maintenance_gate.snapshot()
        return dict(maintenance_supported=True,loaded=maintenance.process_proof(
                        self.loaded_deployment,protocol_ready=self.protocol_ready),
                    marker={key:marker[key] for key in ('state','sequence','owner','decision_id','deployment_digest')})

    def deployment_status(self):
        """Explicit drain observation may close only positively proved duties."""
        if self.maintenance_gate is None:
            return dict(maintenance_supported=False)
        # A current pointer may have advanced after an old closure write failed.
        # Reconcile those original attempts before inspecting current launches.
        self._reconcile_preparations()
        draining=self.maintenance_gate.snapshot()['state']=='CLOSED'
        for record in self.records.values():
            if record.get('maintenance_admission') is not None:
                try:
                    if record['state']=='READY':
                        launcher=self._launcher(record)
                        if launcher.state()=='IDLE' and draining:
                            launcher.retire_unstarted_admission()
                except (JobError,OSError,ValueError,subprocess.SubprocessError):
                    pass
        return self.deployment_observe()

    def _preparation_failed(self, record, error):
        directory=os.open(record['attempt'],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        failure=dict(type=type(error).__name__,message=str(error)[:2048])
        if getattr(error,'__notes__',None):failure['notes']=[str(note)[:2048] for note in error.__notes__[:8]]
        try:
            if isinstance(error,ReadyPublicationUncertain):save_ready_failure(directory,failure)
            else:
                try:task_service.save(directory,'preparation-failure.json',failure)
                except FileExistsError:
                    task_service.save(directory,'preparation-failure-'+uuid.uuid4().hex+'.json',failure)
        finally:os.close(directory)
        if isinstance(error,ReadyPublicationUncertain):
            # Keep PREPARING plus its original result for a later confirmation;
            # writing FAILED here could overwrite an already published READY.
            raise error
        current=self.records[record['operation_id']]
        # A publication error after the private READY commit must not demote a
        # successful preparation. A later poll/restart repairs its public view.
        if current['state']=='READY' and current['attempt']==record['attempt']:
            return current
        failed=dict(record,state='FAILED')
        self._save(failed)
        return failed

    def call(self, request):
        with self.fence:
            q.require(self._pending_cleanup.alive,'RESIDENT_CLOSED')
            action=request.get('action');principal=request.get('principal_id')
            if principal not in self.config['principals']:
                raise JobError('UNAUTHORIZED','Principal is not admitted')
            authorization=None
            if 'authorization_bounds' in request:
                # serve() has already authenticated the fixed adapter UID.
                # Its registered principal and installed task grant remain
                # the upper bound; JSON cannot introduce a new principal.
                scopes=self.config.get('template',{}).get('scopes')
                if type(scopes) is not list:
                    raise JobError('UNAUTHORIZED','Installed scope grant is unavailable')
                request,authorization=forwarded_bounds.restrict(request,Principal(principal,frozenset(scopes)))
                required={'prepare':{'lh:submit'},'start':{'lh:submit'},'workspace_read':{'lh:read'},
                          'status':{'lh:read','lh:submit','lh:cancel','lh:evidence'},
                          'deployment_status':{'lh:inspect'},'deployment_observe':{'lh:inspect'}}.get(action,set())
                if not required.intersection(authorization.scopes):
                    raise JobError('UNAUTHORIZED','Forwarded scope does not permit this action')
            if action in {'deployment_status','deployment_observe'}:
                q.require(set(request)=={'action','principal_id'},'RESIDENT_REQUEST')
                if authorization is not None:authorization.require_current()
                return self.deployment_status() if action=='deployment_status' else self.deployment_observe()
            if action=='workspace_read':
                q.require(set(request)=={'action','principal_id','profile_ref','source_ref','relative_path'},'RESIDENT_REQUEST')
                args=validate_tool_args('lh_workspace_read',{k:v for k,v in request.items() if k not in {'action','principal_id'}})
                source=self.config.get('workspace',{}).get('sources',{}).get(args['source_ref'])
                if (args['profile_ref']!=self.config['profile_ref'] or source is None
                        or args['relative_path'] not in source['blobs']):
                    raise JobError('UNAUTHORIZED','Workspace source or file is not admitted')
                if authorization is not None:authorization.require_current()
                try:raw=read_protected(str(Path(source['root'])/args['relative_path']),MAX_WORKSPACE_TEXT_BYTES)
                except ValueError as error:
                    if str(error)=='INPUT_BYTE_LIMIT':
                        raise JobError('LIMIT_EXCEEDED','Workspace file exceeds 120 KiB of UTF-8 text') from None
                    raise
                if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=source['blobs'][args['relative_path']]:
                    raise JobError('CONFLICT','Workspace source file changed')
                try:content=raw.decode('utf-8',errors='strict')
                except UnicodeError:raise JobError('UNSUPPORTED','Workspace file is not UTF-8 text') from None
                result=dict(source_ref=args['source_ref'],source_commit=source['commit'],relative_path=args['relative_path'],
                            sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),content=content)
                if len(canonical_bytes(dict(result=result)))>cli.MAX_RESPONSE_BYTES:
                    raise JobError('LIMIT_EXCEEDED','Workspace text exceeds the 512 KiB response budget after JSON escaping')
                return result
            if action=='prepare':
                q.require({'action','principal_id','operation_id','kind','profile_ref'}<=set(request)
                          <={'action','principal_id','operation_id','kind','profile_ref','retry_failed','inputs','allow_new'},'RESIDENT_REQUEST')
                allow_new=request.get('allow_new',True)
                q.require(type(allow_new) is bool,'RESIDENT_REQUEST')
                args=validate_tool_args('lh_job_prepare',{k:v for k,v in request.items() if k not in {'action','principal_id','allow_new'}})
                bounds={} if authorization is None else {'authorization':authorization}
                return self.prepare(args,principal,allow_new=allow_new,**bounds)
            if action not in {'status','start'}:raise JobError('UNSUPPORTED','Unknown task service action')
            q.require(set(request)=={'action','principal_id','operation_id'}|({'request_digest'} if action=='start' else set()),
                      'RESIDENT_REQUEST')
            operation=validate_tool_args('lh_job_status',dict(operation_id=request['operation_id']))['operation_id']
            record=self._owned(operation,principal)
            if record['state']!='READY':raise JobError('RESOURCE_BUSY','Preparation is not ready')
            state=self.execution_state(record)
            if action=='start':
                if request['request_digest']!=record['request']['request_digest']:
                    raise JobError('CONFLICT','Task request changed')
                if state=='IDLE':
                    if record['request']['kind'] in DISABLED_JOB_KINDS:
                        raise JobError('UNSUPPORTED','This job kind is not available for new execution')
                    if record['boot_id']!=self.boot or record['request']['expires_at']<=time.time():
                        raise JobError('STALE_DEPLOYMENT','Prepare the unsubmitted task for this boot')
                    if self._busy(except_operation=operation):
                        raise JobError('RESOURCE_BUSY','Another task is active')
                    if authorization is not None:authorization.require_current()
                    bounds={} if authorization is None else {'authorization':authorization}
                    state=self._launcher(record).start(**bounds)
                    if state=='EXITED':state=self._captured_execution_state(record)
            return dict(state=state)


def prepare_main(input_path,result_path):
    value=provision_task.prepare(load(input_path))
    directory=os.open(str(Path(result_path).parent),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:task_service.save(directory,Path(result_path).name,value)
    finally:os.close(directory)


def initialize_host(config):
    """Start the original execution slices; new tasks bind their current pins."""
    q.require(os.getuid()==os.geteuid()==0,'RESIDENT_ADMINISTRATOR')
    q.require(config.get('maintenance') is None,'RESIDENT_GUARDED_INITIALIZATION_FORBIDDEN')
    template=config['template'];uid,gid=config['uid'],config['gid']
    systemctl=config['installation']['installed']['programs']['systemctl']['path']
    units=sorted({Path(value['path']).name for value in template['observed']['parents'].values()})
    def run(argv,env=None):
        result=subprocess.run(argv,capture_output=True,timeout=15,env=env)
        q.require(result.returncode==0,'RESIDENT_RUNTIME_PREPARATION')
    run([systemctl,'start',*units,'user@'+str(uid)+'.service'])
    old=template['observed']['system_geometry']['retained_ordinary_parent']
    q.require((old['memory_bytes'],old['tasks_max'],old['memory_swap_max'],old['cpu_quota_per_sec_usec'])
              ==(268435456,64,0,1000000),'RESIDENT_RETAINED_PARENT_BUDGET')
    prefix=[template['plan']['tools']['setpriv']['path'],'--reuid='+str(uid),'--regid='+str(gid),
            '--clear-groups','--no-new-privs','--',systemctl,'--user']
    env={'PATH':'/usr/bin:/bin','XDG_RUNTIME_DIR':'/run/user/'+str(uid),
         'DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/'+str(uid)+'/bus'}
    name=Path(old['parent']['path']).name
    run(prefix+['start',name],env)
    run(prefix+['set-property','--runtime',name,'MemoryMax=268435456','MemorySwapMax=0',
                'TasksMax=64','CPUQuota=100%','CPUQuotaPeriodSec=100ms'],env)


def serve(config):
    q.require(os.getuid()==os.geteuid()==0,'RESIDENT_ADMINISTRATOR')
    check_local_a2_management_paths(config)
    for key in ('private_root','catalog'):
        path=Path(config[key])
        for item in (path,*path.parents):
            info=item.lstat()
            q.require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'RESIDENT_DIRECTORY')
    lock=os.open(Path(config['private_root'])/'service.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with closing(ResidentService(config)) as service:
        _serve_requests(config,service)


def _serve_requests(config,service):
    service.recover_undispatched()
    if service.maintenance_gate is not None:
        from local_hand_jobs.deployment import verify_release
        from local_hand_jobs import startup
        installation=config['installation']
        verify_release(expected_source_commit=installation['source']['commit'],
            expected_payload_digest=installation['installed']['payload_digest'],
            expected_entrypoint=installation['installed']['package_root']+'/local_hand_jobs/cli.py',
            actual_entrypoint=cli.__file__)
    endpoint=Path(config['socket']);parent=endpoint.parent
    for item in (parent,*parent.parents):
        info=item.lstat()
        q.require(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'RESIDENT_SOCKET_PARENT')
    if endpoint.exists():
        info=endpoint.lstat()
        q.require(stat.S_ISSOCK(info.st_mode) and info.st_uid==0,'RESIDENT_SOCKET_CHANGED')
        endpoint.unlink() # The service lock excludes another admitted listener.
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
        guard=(startup.authorize(config,service.loaded_deployment,service.maintenance_gate)
               if service.maintenance_gate is not None else nullcontext())
        with guard:
            listener.bind(str(endpoint));os.chown(endpoint,0,config['gid']);endpoint.chmod(0o660);listener.listen(16)
            service.protocol_ready=True
        info=endpoint.lstat()
        publish(config['socket_descriptor'],dict(socket=dict(path=str(endpoint),device=info.st_dev,inode=info.st_ino)),0o644)
        while True:
            connection,_=listener.accept()
            with connection:
                end=time.monotonic()+3
                try:
                    peer_pid,uid,gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    request=strict_loads(cli._read_frame(connection,cli.MAX_REQUEST_BYTES,deadline=end))
                    if (request=={'action':'startup_authorize','component':'mcp'}
                            and (uid==0 or (uid,gid)==(config['uid'],config['gid']))):
                        if service.maintenance_gate is None:
                            raise JobError('UNSUPPORTED','Legacy service has no startup selection authority')
                        startup.serve_authorization(connection,config,service.maintenance_gate,peer_pid=peer_pid)
                        continue
                    if uid==0 and request in ({'action':'startup_authorize','component':'gateway','mode':'candidate'},
                                               {'action':'startup_authorize','component':'gateway','mode':'public'}):
                        if service.maintenance_gate is None:
                            raise JobError('UNSUPPORTED','Legacy service has no gateway startup authority')
                        startup.serve_gateway_authorization(connection,config,service.maintenance_gate,
                            peer_pid=peer_pid,peer_uid=uid,mode=request['mode'])
                        continue
                    if uid==0 and request in ({'action':'deployment_status'},{'action':'deployment_observe'}):
                        with service.fence:
                            result=(service.deployment_status() if request['action']=='deployment_status'
                                    else service.deployment_observe())
                    else:
                        if (uid,gid)!=(config['uid'],config['gid']):raise JobError('UNAUTHORIZED','Peer is not admitted')
                        result=service.call(request)
                    response=dict(result=result)
                except JobError as error:response=dict(error=error.as_dict())
                except Exception:response=dict(error=dict(code='IO_UNCERTAIN',message='Task service needs state inspection'))
                try:cli._send_frame(connection,response,deadline=end,limit=cli.MAX_RESPONSE_BYTES)
                except (OSError,JobError):pass


def main(argv=None):
    parser=argparse.ArgumentParser(description='Run the persistent Local Hand preparation service')
    parser.add_argument('--config',required=True)
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--initialize-host',action='store_true')
    actions.add_argument('--check-host',action='store_true',help='Check prepared host resources without starting units or changing limits')
    args=parser.parse_args(argv)
    config=load(args.config)
    if args.check_host:
        from .host_readiness import check_host
        print(json.dumps(check_host(config),sort_keys=True),flush=True)
    elif args.initialize_host:initialize_host(config)
    else:serve(config)


if __name__=='__main__':main()

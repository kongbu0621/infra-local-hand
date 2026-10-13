"""Authenticated preparation and routing for independent retained tasks."""
from __future__ import annotations

from collections import OrderedDict
import os
from pathlib import Path
import socket
import struct
import threading
import time

from local_hand_jobs import cli
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError, TOOL_SCHEMAS, TOOL_SCOPES, TOOL_SCHEMA_DIGEST, validate_tool_args
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs.task_session import read_descriptor
from .prepared import Launcher


class ServiceClient:
    def __init__(self, descriptor):
        self.descriptor = descriptor

    def call(self, action, **arguments):
        try:
            # Re-read the administrator's socket identity after a daemon restart.
            value = read_descriptor(self.descriptor)
            pin = value['socket']
            guard = Launcher(pin, {})
            guard._check()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                end = time.monotonic() + 3
                cli._deadline(connection, end)
                connection.connect(pin['path'])
                _, uid, gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if (uid, gid) != (0, 0):
                    raise JobError('UNAUTHORIZED', 'Task service identity changed')
                guard._check()
                cli._send_frame(connection, dict(action=action, **arguments), deadline=end, limit=8192)
                response = cli._response(cli._read_frame(connection, 16384, deadline=end))
                if 'error' in response:
                    raise JobError(response['error']['code'], response['error']['message'])
                return response['result']
        except OSError as error:
            raise JobError('IO_UNCERTAIN', 'Task service unavailable; retain the original identity') from error


class ResidentBroker:
    read_only = False
    _authorize = Broker._authorize
    supported_tools = frozenset({'lh_capabilities', 'lh_job_prepare', 'lh_job_submit', 'lh_job_status',
                                 'lh_evidence_manifest', 'lh_evidence_read_chunk'})

    def __init__(self, retained, config, service, reader_factory):
        self.retained, self.config, self.service = retained, config, service
        self.policy = retained.policy
        self.state, self.authority_lock = retained.state, retained.authority_lock
        self.reader_factory, self.readers = reader_factory, {}
        self.artifact_routes = OrderedDict()
        self.fence, self._rates = threading.RLock(), {}
        self.closed = False

    @classmethod
    def open(cls, retained, descriptor):
        config = read_descriptor(descriptor)
        if (set(config) != {'schema', 'service', 'catalog', 'profile_ref', 'authority_id', 'budgets', 'retained'}
                or config['schema'] != 'local-hand-resident-adapter/v1'):
            raise JobError('UNAUTHORIZED', 'Invalid resident adapter configuration')
        return cls(retained, config, ServiceClient(config['service']),
            lambda path: cli.create_broker(path, actual_entrypoint=cli.__file__, read_only=True))

    def start(self):
        self.retained.start()

    def _record(self, operation):
        try:
            value = read_descriptor(str(Path(self.config['catalog']) / (operation + '.json')))
        except FileNotFoundError:
            return None
        if value.get('operation_id') != operation:
            raise JobError('IO_UNCERTAIN', 'Task catalog identity changed')
        return value

    def _reader(self, path):
        if path not in self.readers:
            self.readers[path] = self.reader_factory(path)
        return self.readers[path]

    def _history(self, name, args, principal):
        # A small administrator-owned retained-policy list preserves older
        # deployments; newly prepared tasks are selected by their own catalog.
        from local_hand_jobs.evidence import EvidenceError
        for path in (None, *self.config['retained']):
            reader = self.retained if path is None else self._reader(path)
            try:
                return reader.call(name, args, principal)
            except (JobError, EvidenceError) as error:
                if error.code != 'NOT_FOUND':
                    raise
        raise JobError('NOT_FOUND', 'No owned task or artifact matches')

    def _remember_manifest(self, record, result, principal):
        # Remember only artifacts returned by an authorized task manifest.
        # This bounded hint avoids probing unrelated ledgers for each chunk;
        # the selected reader still verifies ownership and the requested hash.
        for artifact in result['artifacts']:
            key = (principal.principal_id, artifact['artifact_id'])
            self.artifact_routes[key] = (record['operation_id'], record['policy_path'])
            self.artifact_routes.move_to_end(key)
            if len(self.artifact_routes) > 256:
                self.artifact_routes.popitem(last=False)

    def _task_artifact(self, record, args, principal):
        if record['principal_id'] != principal.principal_id:
            raise JobError('UNAUTHORIZED', 'Task belongs to another principal')
        if record['state'] != 'READY':
            raise JobError('RESOURCE_BUSY', 'Task preparation is not ready; keep the same identity')
        policy = Policy.from_file(record['policy_path'])
        policy.authorize(principal, 'lh:evidence')
        state = self.service.call('status', operation_id=record['operation_id'],
                                  principal_id=principal.principal_id)['state']
        if state == 'IDLE':
            raise JobError('NOT_FOUND', 'Task has not been submitted')
        if state == 'RUNNING':
            return cli.request(Path(policy.broker_root) / 'maintenance.sock',
                               'lh_evidence_read_chunk', args, timeout=3)
        if state not in {'EXITED', 'UNRESOLVED'}:
            raise JobError('IO_UNCERTAIN', 'Task execution state needs inspection')
        return self._reader(record['policy_path']).call('lh_evidence_read_chunk', args, principal)

    def _artifact(self, args, principal):
        from local_hand_jobs.evidence import EvidenceError
        key = (principal.principal_id, args['artifact_id'])
        if key in self.artifact_routes:
            operation, policy_path = self.artifact_routes[key]
            record = self._record(operation)
            if record is None or record.get('policy_path') != policy_path:
                raise JobError('CONFLICT', 'Artifact task binding changed; query its manifest again')
            self.artifact_routes.move_to_end(key)
            return self._task_artifact(record, args, principal)
        try:
            return self._history('lh_evidence_read_chunk', args, principal)
        except (JobError, EvidenceError) as error:
            if error.code != 'NOT_FOUND':
                raise
        # Only bounded, root-owned catalog entries are considered. Artifact
        # ownership is still enforced by each ordinary result reader.
        for path in sorted(Path(self.config['catalog']).glob('*.json')):
            record = read_descriptor(str(path))
            if record.get('state') != 'READY' or record.get('principal_id') != principal.principal_id:
                continue
            try:
                return self._task_artifact(record, args, principal)
            except (JobError, EvidenceError) as error:
                if error.code != 'NOT_FOUND':
                    raise
        raise JobError('NOT_FOUND', 'No owned artifact matches')

    def call(self, name, arguments, principal):
        args = validate_tool_args(name, arguments)
        with self.fence:
            if self.closed:
                raise JobError('IO_UNCERTAIN', 'Resident adapter closed')
            if name not in self.supported_tools:
                raise JobError('UNSUPPORTED', 'This entry does not offer that operation')
            # Keep the entry authority's durable revocations effective even
            # when this request routes to a newly prepared independent ledger.
            self._authorize(principal, TOOL_SCOPES[name])
            Broker._rate(self, principal)
            if name == 'lh_capabilities':
                result = thaw(self.policy.capabilities(principal, **args))
                result.update(authority_id=self.config['authority_id'], tool_schema_digest=TOOL_SCHEMA_DIGEST,
                    profiles=[dict(profile_ref=self.config['profile_ref'], allowed_kinds=['host.inspect'],
                                   budgets=self.config['budgets'])], next_cursor=None,
                    preparation=dict(tool='lh_job_prepare', profile_ref=self.config['profile_ref'],
                                     kind='host.inspect', max_active=1))
                return result
            if name == 'lh_job_prepare':
                if args['profile_ref'] != self.config['profile_ref']:
                    raise JobError('UNAUTHORIZED', 'Profile is not admitted')
                if self._record(args['operation_id']) is None:
                    # The catalog routes by UUID across deployments. Creating a
                    # new entry for retained history would hide that original
                    # task and defeat same-identity recovery.
                    for path in (None, *self.config['retained']):
                        reader = self.retained if path is None else self._reader(path)
                        if reader.state.get('job', args['operation_id']) is not None:
                            raise JobError('CONFLICT', 'Task identity already belongs to retained history')
                return self.service.call('prepare', principal_id=principal.principal_id, **args)
            if name == 'lh_evidence_read_chunk':
                return self._artifact(args, principal)
            operation = args['operation_id']
            record = self._record(operation)
            if record is None:
                if name == 'lh_job_submit':
                    raise JobError('NOT_FOUND', 'Prepare this task before submitting it')
                return self._history(name, args, principal)
            if record['principal_id'] != principal.principal_id:
                raise JobError('UNAUTHORIZED', 'Task belongs to another principal')
            if record['state'] != 'READY':
                raise JobError('RESOURCE_BUSY', 'Task preparation is not ready; keep the same identity')
            policy = Policy.from_file(record['policy_path'])
            policy.authorize(principal, TOOL_SCOPES[name])
            if name == 'lh_job_submit':
                if args != record['request']:
                    raise JobError('CONFLICT', 'Prepared task request changed')
                policy.authorize(principal, 'lh:submit', request=args)
            route = self.service.call('status', operation_id=operation, principal_id=principal.principal_id)
            state = route['state']
            if state == 'IDLE':
                if name != 'lh_job_submit':
                    raise JobError('NOT_FOUND', 'Task has not been submitted')
                if args['expires_at'] <= time.time():
                    raise JobError('STALE_DEPLOYMENT', 'Prepared request has expired')
                state = self.service.call('start', operation_id=operation,
                    principal_id=principal.principal_id, request_digest=args['request_digest'])['state']
            if state == 'RUNNING':
                result = cli.request(Path(policy.broker_root) / 'maintenance.sock', name, args, timeout=3)
            elif state not in {'EXITED', 'UNRESOLVED'}:
                raise JobError('IO_UNCERTAIN', 'Task execution state needs inspection')
            else:
                reader = self._reader(record['policy_path'])
                if name == 'lh_job_submit':
                    row = reader.state.get('job', operation)
                    if row is None:
                        raise JobError('IO_UNCERTAIN', 'Controller ended without a committed task')
                    if row['digest'] != args['request_digest'] or row['principal'] != principal.principal_id:
                        raise JobError('CONFLICT', 'Committed task identity changed')
                    reader._authorize(principal, 'lh:submit', owner=row['principal'])
                    return reader._view(row)
                result = reader.call(name, args, principal)
            if name == 'lh_evidence_manifest':
                self._remember_manifest(record, result, principal)
            return result

    def close(self):
        with self.fence:
            self.closed = True
            failure = None
            for reader in self.readers.values():
                try:
                    cli.close_service(reader, None)
                except BaseException as error:
                    if failure is None:
                        failure = error
            try:
                self.retained.close()
            except BaseException as error:
                if failure is None:
                    failure = error
            if failure is not None:
                raise failure

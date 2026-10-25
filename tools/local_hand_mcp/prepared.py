"""Admit one prepared task on demand while retaining the original result reader.

The privileged launcher accepts only its fixed task identity. Execution and all
task writes remain in the existing Broker/TaskService, including deduplication.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import stat
import struct
import threading
import time

from local_hand_jobs import cli
from local_hand_jobs.broker import Broker
from local_hand_jobs.contract import JobError, Principal, TOOL_SCOPES, validate_submit, validate_tool_args
from local_hand_jobs.deployment import verify_release
from local_hand_jobs.policy import Policy, thaw
from local_hand_jobs import forwarded_bounds
from local_hand_jobs.task_session import read_descriptor


class Launcher:
    """A bounded, authenticated exchange with an administrator's fixed launcher."""
    def __init__(self, pin, request):
        if (set(pin) != {"path", "device", "inode"} or not Path(pin["path"]).is_absolute()
                or any(type(pin[k]) is not int or pin[k] < 1 for k in ("device", "inode"))):
            raise JobError("UNAUTHORIZED", "Invalid prepared launcher binding")
        self.pin, self.request = pin, request

    def _check(self):
        path = Path(self.pin["path"])
        for parent in (path.parent, *path.parent.parents):
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise JobError("UNAUTHORIZED", "Prepared launcher parent changed")
        info = path.lstat()
        if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o007
                or (info.st_dev, info.st_ino) != (self.pin["device"], self.pin["inode"])):
            raise JobError("UNAUTHORIZED", "Prepared launcher identity changed")

    def call(self, action, *, principal=None):
        if action not in ("status", "start"):
            raise JobError("UNSUPPORTED", "Unknown prepared launcher action")
        try:
            self._check()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                deadline = time.monotonic() + 2
                cli._deadline(connection, deadline)
                connection.connect(self.pin["path"])
                _, uid, gid = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if (uid, gid) != (0, 0):
                    raise JobError("UNAUTHORIZED", "Prepared launcher is not the administrator")
                self._check()
                body = dict(action=action, operation_id=self.request["operation_id"],
                            request_digest=self.request["request_digest"])
                if principal is not None:
                    body = forwarded_bounds.attach(body, principal)
                cli._send_frame(connection, body, deadline=deadline, limit=4096)
                result = cli._response(cli._read_frame(connection, 4096, deadline=deadline))
                if "error" in result:
                    raise JobError(result["error"]["code"], result["error"]["message"])
                value = result["result"]
                if set(value) != {"state"} or value["state"] not in {"IDLE", "RUNNING", "EXITED"}:
                    raise JobError("IO_UNCERTAIN", "Prepared launcher state is unresolved")
                return value["state"]
        except OSError as error:
            raise JobError("IO_UNCERTAIN", "Prepared launcher exchange is unresolved; keep the same task") from error


class PreparedBroker:
    """Route a single new task to the existing executor; never replay on reads."""
    read_only = False
    _authorize = Broker._authorize

    def __init__(self, retained, policy, request, principal_id, launcher, reader_factory):
        self.retained, self.policy = retained, policy
        self.request = validate_submit(thaw(request))
        self.principal_id, self.launcher = principal_id, launcher
        principal = Principal(principal_id, frozenset(policy.principals[principal_id]["scopes"]))
        policy.authorize(principal, "lh:submit", request=self.request)
        if (self.request["kind"] != "host.inspect"
                or self.request["expected"] != policy.expected(self.request["profile_ref"])):
            raise JobError("UNAUTHORIZED", "Prepared task does not match the admitted deployment")
        if retained.state.get("job", self.request["operation_id"]) is not None:
            raise JobError("CONFLICT", "Prepared task identity already belongs to retained history")
        self.state, self.authority_lock = retained.state, retained.authority_lock
        self.reader_factory, self.reader = reader_factory, None
        self.fence, self._rates = threading.RLock(), {}
        self.closed = False

    @classmethod
    def open(cls, retained, path, *, actual_entrypoint):
        value = read_descriptor(path)
        if (set(value) != {"schema", "policy_path", "request", "principal_id", "launcher"}
                or value["schema"] != "local-hand-prepared-task/v1"):
            raise JobError("UNAUTHORIZED", "Invalid prepared task declaration")
        policy = Policy.from_file(value["policy_path"])
        # The prepared executor is the installed CLI broker. The retained
        # reader separately verifies the public MCP adapter's entrypoint.
        backend_entrypoint = cli.__file__
        identity = dict(retained.reader_identity, execution_entrypoint=str(Path(backend_entrypoint).absolute()))
        verify_release(expected_source_commit=identity['source_commit'],
            expected_payload_digest=identity['installed_payload_digest'],
            expected_entrypoint=identity['execution_entrypoint'], actual_entrypoint=backend_entrypoint)
        if (policy.broker_root == retained.policy.broker_root
                or policy.authority_root == retained.policy.authority_root
                or policy.config["process_manager"]["uid"] != os.geteuid()):
            raise JobError("UNAUTHORIZED", "Prepared task must use its separate admitted ledger")
        return cls(retained, policy, value["request"], value["principal_id"],
            Launcher(value["launcher"], value["request"]),
            lambda: cli.create_retained_broker(value["policy_path"], actual_entrypoint=backend_entrypoint,
                                              reader_identity=identity))

    def start(self):
        self.retained.start()

    def _original_artifact(self, artifact_id):
        from local_hand_jobs.evidence import EvidenceError
        try:
            self.retained.evidence.owner_of(artifact_id)
            return True
        except (JobError, EvidenceError) as error:
            if error.code != "NOT_FOUND":
                raise
            return False

    def call(self, name, arguments, principal):
        args = validate_tool_args(name, arguments)
        scope = TOOL_SCOPES[name]
        with self.fence:
            if self.closed:
                raise JobError("IO_UNCERTAIN", "Prepared adapter is closed")
            # Authenticate before asking the privileged launcher to do anything.
            self._authorize(principal, scope)
            Broker._rate(self, principal)
            if name == "lh_capabilities":
                result = thaw(self.policy.capabilities(principal, **args))
                if principal.principal_id == self.principal_id:
                    result["prepared_request"] = thaw(self.request)
                return result
            if (("operation_id" in args and args["operation_id"] != self.request["operation_id"])
                    or name == "lh_evidence_read_chunk" and self._original_artifact(args["artifact_id"])):
                if name == "lh_job_submit":
                    raise JobError("UNAUTHORIZED", "Only the prepared task can be submitted")
                return self.retained.call(name, args, principal)
            if principal.principal_id != self.principal_id:
                raise JobError("UNAUTHORIZED", "Prepared task belongs to another principal")
            if name == "lh_job_submit":
                if args != self.request:
                    raise JobError("CONFLICT", "Prepared task request changed")
                self.policy.authorize(principal, scope, request=args)
            bounds = {'principal': principal} if principal.expires_at is not None else {}
            principal.require_current()
            try:
                state = self.launcher.call("status", **bounds)
            except JobError as error:
                if error.code != "IO_UNCERTAIN" or name not in {
                        "lh_job_status", "lh_evidence_manifest", "lh_evidence_read_chunk"}:
                    raise
                # A lost controller/collector must not hide an original ledger.
                # The retained reader's authority lock still refuses a live
                # writer, and this path cannot initialize or dispatch a job.
                state = "UNRESOLVED"
            if state == "IDLE":
                if name != "lh_job_submit":
                    raise JobError("NOT_FOUND", "Prepared task has not been submitted")
                if args["expires_at"] <= time.time():
                    raise JobError("STALE_DEPLOYMENT", "Prepared request has expired")
                principal.require_current()
                state = self.launcher.call("start", **bounds)
            if state in {"EXITED", "UNRESOLVED"}:
                if name == "lh_job_submit":
                    self._authorize(principal, "lh:read")
                if self.reader is None:
                    self.reader = self.reader_factory()
                if name == "lh_job_submit":
                    # A repeated submission after controller exit is only a read
                    # of the original committed result, never another execution.
                    row = self.reader.state.get("job", self.request["operation_id"])
                    if row is None:
                        raise JobError("IO_UNCERTAIN", "Execution session ended without a committed task")
                    if row["digest"] != args["request_digest"] or row["principal"] != principal.principal_id:
                        raise JobError("CONFLICT", "Committed prepared task identity changed")
                    self.reader._authorize(principal, scope, owner=row["principal"])
                    self.reader._authorize(principal, "lh:read", owner=row["principal"])
                    return self.reader._view(row)
                return self.reader.call(name, args, principal)
            if state != "RUNNING":
                raise JobError("IO_UNCERTAIN", "Prepared execution did not start")
            # The ordinary account has an explicit local-peer mapping in the
            # private policy. The backend performs its own durable admission.
            principal.require_current()
            return cli.request(Path(self.policy.broker_root) / "maintenance.sock", name, args, timeout=3, **bounds)

    def close(self):
        with self.fence:
            self.closed = True
            try:
                if self.reader is not None:
                    cli.close_service(self.reader, None)
            finally:
                self.retained.close()

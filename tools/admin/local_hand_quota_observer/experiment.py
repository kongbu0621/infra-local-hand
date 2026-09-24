"""Single Q1 administrator experiment on a pre-provisioned private fixture.

This is not the Q2 peer protocol, an installation tool, or the three-unit harness.
It never creates a ticket/ID/deadline, provisions a host, or retries a query.
Before touching the journal, the actual controller supervision is checked.
All storage operations and stdout delivery still require the independently
supervised controller and the fixture's finite private evidence collector.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from .admission import Rejected, decode_manifest, fields, integer, path, require, strict_json, token
from .controller_guard import ControllerSpec, admit_controller, decode_controller
from .experiment_evidence import encode_failure, encode_outcome
from .protected_inputs import (decode_ticket, installation_digest, load_runtime,
                               read_protected, validate_geometry)
from .supervision import Decision
from .systemd_runtime import Outcome, Q1Controller


MAX_EXPERIMENT_BYTES = 16384


@dataclass(frozen=True)
class JournalIdentity:
    path: str
    owner_uid: int
    device: int
    inode: int


@dataclass(frozen=True)
class Experiment:
    digest: str
    operation: str
    source_commit: str
    runtime_path: str
    runtime_digest: str
    journal: JournalIdentity
    ticket: str
    controller: ControllerSpec


def decode_experiment(raw, expected_digest, expected_source_commit):
    """Pure strict decode; an experiment pins an original ticket, not a duration."""
    token(expected_digest, r"[0-9a-f]{64}")
    token(expected_source_commit, r"[0-9a-f]{40}")
    require(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == expected_digest,
            "EXPERIMENT_DIGEST")
    value = fields(strict_json(raw, MAX_EXPERIMENT_BYTES, depth=4), (
        "schema", "operation", "source_commit", "runtime_path", "runtime_digest",
        "journal", "ticket", "controller"))
    require(value["schema"] == "local-hand-quota-q1-experiment-input/v1", "EXPERIMENT_VERSION")
    require(value["operation"] in ("run", "recover_original"), "EXPERIMENT_OPERATION")
    source = token(value["source_commit"], r"[0-9a-f]{40}")
    require(source == expected_source_commit, "SOURCE_COMMIT_CHANGED")
    journal = fields(value["journal"], ("path", "owner_uid", "device", "inode"))
    owner = integer(journal["owner_uid"], 0, 0)
    return Experiment(expected_digest, value["operation"], source, path(value["runtime_path"]),
                      token(value["runtime_digest"], r"[0-9a-f]{64}"),
                      JournalIdentity(path(journal["path"]), owner, integer(journal["device"]),
                                      integer(journal["inode"], 1)),
                      token(value["ticket"], r"[A-Za-z0-9+/]{1,10922}={0,2}"),
                      decode_controller(value["controller"]))


def _open_journal(identity):
    # Linux-only module: portable decoder/test collection must not import fcntl.
    from .journal import StartJournal
    return StartJournal(identity.path, owner_uid=identity.owner_uid,
                        directory_device=identity.device, directory_inode=identity.inode)


def _error_code(error):
    if isinstance(error, Rejected):
        code = str(error)
        return code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code) else "EXPERIMENT_REJECTED"
    if isinstance(error, KeyboardInterrupt):
        return "EXPERIMENT_INTERRUPTED"
    return "EXPERIMENT_IO_UNCERTAIN" if isinstance(error, OSError) else "EXPERIMENT_INTERNAL_ERROR"


def _partial_outcome(controller, binding, reason):
    """Preserve already captured prefixes without inventing an exit/invocation.

    All known children remain conservatively listed; this function does not
    poll, signal, read the journal again or start a replacement controller.
    """
    launcher = controller.launcher
    captures = controller.controls + ([launcher] if launcher else [])
    pending = tuple(item.process.pid for item in captures if item.process is not None)
    return Outcome(Decision("UNKNOWN", reason), binding,
                   bytes(launcher.stdout) if launcher else b"",
                   bytes(launcher.stderr) if launcher else b"", None,
                   binding.manifest.cgroup_parent, len(controller.controls),
                   pending_clients=pending)


def execute_experiment(input_path, expected_digest, expected_source_commit):
    """Return one private diagnostic record; never treat it as an admission receipt.

    controller_entered becomes true BEFORE constructing StartJournal: even an
    initialization error cannot establish that an old intent/resource is free.
    run/recover use the exact supplied ticket and pinned original installation.
    """
    spec = observation = journal = controller = binding = outcome = None
    entered = False
    error_code = entry_error = None
    try:
        input_path = path(input_path)
        spec = decode_experiment(read_protected(input_path, MAX_EXPERIMENT_BYTES),
                                 expected_digest, expected_source_commit)
        config = load_runtime(spec.runtime_path, spec.runtime_digest)
        manifest = decode_manifest(read_protected(config.manifest_path, 32768), config.manifest_digest)
        require(manifest.source_commit == spec.source_commit, "SOURCE_COMMIT_CHANGED")
        require(installation_digest(config) == manifest.installation_digest, "INSTALLATION_BINDING")
        validate_geometry(config, manifest, spec.runtime_path, spec.journal.path, extra_input=input_path)
        binding = decode_ticket(spec.ticket, manifest)
        observation = admit_controller(config, manifest, spec.controller)
        entered = True
        journal = _open_journal(spec.journal)
        controller = Q1Controller(spec.runtime_path, spec.runtime_digest, journal)
        require(controller.config == config and controller.manifest == manifest, "EXPERIMENT_INPUT_CHANGED")
        if spec.operation == "run":
            outcome = controller.run(spec.ticket)
        else:
            outcome = controller.recover_original(spec.ticket)
    except (Exception, KeyboardInterrupt) as error:
        error_code = _error_code(error)
        if controller is not None and binding is not None:
            outcome = _partial_outcome(controller, binding, error_code)
    finally:
        if journal is not None:
            try:
                journal.close()
            except (Exception, KeyboardInterrupt):
                entry_error = "JOURNAL_CLOSE_UNCERTAIN"

    context = {} if spec is None else {
        "operation": spec.operation, "source_commit": spec.source_commit,
        "runtime_digest": spec.runtime_digest, "experiment_digest": spec.digest,
    }
    if binding is not None:
        context["original_ticket"] = spec.ticket
    if observation is not None:
        context["controller_observation"] = observation.as_dict()
    if outcome is not None:
        try:
            return encode_outcome(outcome, entry_error=entry_error, **context)
        except (Exception, KeyboardInterrupt) as error:
            # Do not call run/recover or read the original output a second time.
            error_code = _error_code(error)
    try:
        return encode_failure(error_code or entry_error or "EXPERIMENT_NOT_COMPLETED",
                              controller_entered=entered, entry_error=entry_error, **context)
    except (Exception, KeyboardInterrupt):
        return encode_failure("EVIDENCE_ENCODING_FAILED", controller_entered=entered)

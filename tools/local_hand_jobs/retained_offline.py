"""One-shot, no-listener readback for intentionally stopped deployments.

Launched as the original data owner by the fixed administrative adapter. It
imports only the selected runtime and cannot initialize or execute any job.
"""
import json
import os
from pathlib import Path
import sys
import time

from . import cli, retained_probe
from .contract import JobError, TOOL_SCOPES, strict_loads
from .task_session import read_descriptor


class OfflineReaders:
    def __init__(self, entry, readers, *, entry_authority=True):
        self.retained = entry
        self.verification_readers = readers
        self.entry_authority = entry_authority

    def call(self, tool, args, principal):
        if self.entry_authority:
            self.retained._authorize(principal, TOOL_SCOPES[tool])
        for reader in [self.retained, *self.verification_readers]:
            try:
                if tool == "lh_evidence_read_chunk":
                    if reader.evidence is None:
                        continue
                    reader.evidence.owner_of(args["artifact_id"])
                elif reader.state.get("job", args["operation_id"]) is None:
                    continue
                return reader.call(tool, args, principal)
            except JobError as error:
                if error.code != "NOT_FOUND":
                    raise
        raise JobError("NOT_FOUND", "No original retained read route matches")


def readback(spec):
    paths = []
    mode, inputs = spec["mode"], spec["inputs"]
    if mode == "policies":
        paths.extend(inputs["policies"])
    elif mode == "resident":
        descriptor = read_descriptor(inputs[mode])
        paths.extend(descriptor["retained"])
        with os.scandir(descriptor["catalog"]) as entries:
            for count, entry in enumerate(entries):
                if count >= retained_probe.MAX_TASKS * 4:
                    raise JobError("LIMIT_EXCEEDED", "Offline catalog scan exceeds its fixed bound")
                if entry.name.endswith(".json"):
                    record = read_descriptor(str(Path(descriptor["catalog"]) / entry.name))
                    if record.get("operation_id", "") + ".json" != entry.name:
                        raise JobError("CONFLICT", "Offline catalog identity differs")
                    if record.get("state") == "READY":
                        paths.append(record["policy_path"])
    elif mode == "prepared_task":
        paths.append(read_descriptor(inputs[mode])["policy_path"])
    elif mode != "read_only":
        raise JobError("UNSUPPORTED", "Offline verifier has no execution mode")
    if len(paths) > retained_probe.MAX_TASKS * 2:
        raise JobError("LIMIT_EXCEEDED", "Offline retained policies exceed their fixed bound")
    with retained_probe.owned_readers() as temporary:
        readers = []
        for path in dict.fromkeys(paths if mode == "policies" else [inputs["config"], *paths]):
            readers.append(temporary(lambda: cli.create_retained_broker(path, actual_entrypoint=cli.__file__,
                                                                        reader_identity=spec["reader_identity"])))
        if not readers:
            raise JobError("CONFLICT", "Offline verification requires an original policy route")
        router = OfflineReaders(readers[0], readers[1:], entry_authority=mode != "policies")
        return retained_probe.collect(lambda request: retained_probe.handle(router, request),
                                      deadline=time.monotonic() + spec["seconds"])


def main():
    try:
        spec = strict_loads(sys.stdin.buffer.read(65537), maximum_bytes=65536)
        if (set(spec) != {"mode", "inputs", "reader_identity", "seconds"}
                or type(spec["seconds"]) is not int or not 0 < spec["seconds"] <= 120):
            raise JobError("UNSUPPORTED", "Invalid fixed offline verification request")
        result = {"result": readback(spec)}
    except JobError as error:
        result = {"error": error.as_dict()}
    raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    if len(raw) > 1024 * 1024:
        raise JobError("LIMIT_EXCEEDED", "Offline verification report exceeds its fixed bound")
    sys.stdout.buffer.write(raw)


if __name__ == "__main__":
    main()

"""Original-window transport and explicit remote-deadline proof boundaries.

No transport outcome proves remote stop. An SSH client is only a local client;
the existing remote management domain must independently enforce its deadline.
The framed input keeps one bounded admission response on the original stdin.
"""
from __future__ import annotations

import hashlib
import importlib.util
import base64
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shlex
import signal
import stat
import subprocess
import time
import zlib


def helper(name):
    spec = importlib.util.spec_from_file_location("_host_window_delivery_" + name,
        Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = helper("q2_reconciliation_delivery")
require, NS = base.require, base.NS
INPUT_LIMIT, OUTPUT_LIMIT = base.INPUT_LIMIT, base.OUTPUT_LIMIT
ACK_LIMIT = 16384
HEADER_BYTES = 9
SCHEMA = "local-hand-q2-host-window-framed-capture/v1"
CONFIG_LIMIT = 32 * 1024**2
CONFIG_SCHEMA = "local-hand-q2-host-window-compressed-config/v1"
ENV_BASH_LITERAL_SSH_PROFILE = "env-bash-literal-ssh-v1"
_LITERAL_SSH_SOURCE = re.compile(
    r'#!/usr/bin/env bash\n'
    r'set -euo pipefail\n'
    r'q1_vm=(?P<directory>/[A-Za-z0-9_./-]{1,4094})\n'
    r'exec ssh -F /dev/null \\\n'
    r'  -i "\$q1_vm/id_ed25519" -p (?P<port>[1-9][0-9]{0,4}) \\\n'
    r'  -o IdentitiesOnly=yes -o BatchMode=yes \\\n'
    r'  -o StrictHostKeyChecking=accept-new \\\n'
    r'  -o UserKnownHostsFile="\$q1_vm/known_hosts" \\\n'
    r'  -o ConnectTimeout=10 \\\n'
    r'  [A-Za-z_][A-Za-z0-9_.-]{0,63}@'
    r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])? "\$@"\n'
)
ANCHOR_PINS = {
    "278d2c8fa1a08697730ce6bc44b3cff19f44c10fdfc39682aa0c6e8d4eea83c6": 360,
    "91078ec71900208e48096026b456664c2128556a56c99acd50d593109125a965": 366,
}


def controlled_environment(environ=None):
    """Keep existing credential discovery; remove shell startup injection."""
    original = os.environ if environ is None else environ
    require(type(original) is dict or environ is None, "HOST_WINDOW_ENVIRONMENT")
    retained = {key: original[key] for key in ("HOME", "USER", "LOGNAME", "SSH_AUTH_SOCK", "SSH_AGENT_PID")
        if key in original}
    require(all(type(value) is str and "\0" not in value for value in retained.values()),
        "HOST_WINDOW_ENVIRONMENT")
    return dict(retained, PATH="/usr/bin:/bin", LANG="C", LC_ALL="C", SYSTEMD_COLORS="0")


def _unique(pairs):
    value = {}
    for name, child in pairs:
        require(name not in value, "HOST_WINDOW_DUPLICATE_KEY")
        value[name] = child
    return value


def _number_forbidden(_):
    raise ValueError("HOST_WINDOW_JSON_NUMBER")


def _json(raw):
    value = json.loads(raw, object_pairs_hook=_unique, parse_float=_number_forbidden,
        parse_constant=_number_forbidden)
    require(type(value) is dict, "HOST_WINDOW_JSON_OBJECT")
    return value


def pack_config(config):
    """Compress the complete configuration; no field-specific limit expands."""
    require(type(config) is dict, "HOST_WINDOW_CONFIG_OBJECT")
    raw = (json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    require(len(raw) <= CONFIG_LIMIT, "HOST_WINDOW_CONFIG_DECODED_LIMIT")
    _json(raw)
    compressed = gzip.compress(raw, compresslevel=6, mtime=0)
    data = base64.b64encode(compressed).decode("ascii")
    require(len(data) <= INPUT_LIMIT - ACK_LIMIT - HEADER_BYTES, "HOST_WINDOW_CONFIG_WIRE_LIMIT")
    return dict(schema=CONFIG_SCHEMA, codec="gzip+base64", decoded_bytes=len(raw),
        decoded_sha256=hashlib.sha256(raw).hexdigest(), data=data)


def unpack_config(value):
    require(type(value) is dict and set(value) == {"schema", "codec", "decoded_bytes", "decoded_sha256", "data"}
        and value["schema"] == CONFIG_SCHEMA and value["codec"] == "gzip+base64", "HOST_WINDOW_CONFIG_ENVELOPE")
    require(type(value["decoded_bytes"]) is int and 0 < value["decoded_bytes"] <= CONFIG_LIMIT
        and type(value["decoded_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["decoded_sha256"])
        and type(value["data"]) is str and len(value["data"]) <= INPUT_LIMIT - ACK_LIMIT - HEADER_BYTES,
        "HOST_WINDOW_CONFIG_LIMIT")
    compressed = base64.b64decode(value["data"], validate=True)
    decompressor = zlib.decompressobj(wbits=31)
    raw = decompressor.decompress(compressed, value["decoded_bytes"] + 1)
    require(len(raw) == value["decoded_bytes"] and decompressor.eof and not decompressor.unused_data
        and not decompressor.unconsumed_tail and hashlib.sha256(raw).hexdigest() == value["decoded_sha256"],
        "HOST_WINDOW_CONFIG_CONTENT")
    return _json(raw)


def config_loader_source(config):
    """Return a bounded stdlib prelude that defines ``_bootstrap_config``.

    The caller appends the existing pinned source-loader/entry, then uses
    validate_script_bytes on the complete result before dispatch. This avoids
    bootstrapping imports from guest files that have not yet been admitted.
    """
    packed = pack_config(config)
    # Reuse the exact audited decoder source through a fixed inline prelude;
    # no guest helper file or interpreter import path is created.
    source = ("import base64,hashlib,json,zlib\n"
        f"_packed={packed!r}\n"
        "_compressed=base64.b64decode(_packed['data'],validate=True)\n"
        "_decompressor=zlib.decompressobj(wbits=31)\n"
        "_decoded=_decompressor.decompress(_compressed,_packed['decoded_bytes']+1)\n"
        "if len(_decoded)!=_packed['decoded_bytes'] or not _decompressor.eof or _decompressor.unused_data or _decompressor.unconsumed_tail or hashlib.sha256(_decoded).hexdigest()!=_packed['decoded_sha256']: raise ValueError('HOST_WINDOW_CONFIG_CONTENT')\n"
        "def _unique_config(pairs):\n"
        " value={}\n"
        " for name,child in pairs:\n"
        "  if name in value: raise ValueError('HOST_WINDOW_DUPLICATE_KEY')\n"
        "  value[name]=child\n"
        " return value\n"
        "def _bad_config_number(value): raise ValueError('HOST_WINDOW_JSON_NUMBER')\n"
        "_bootstrap_config=json.loads(_decoded,object_pairs_hook=_unique_config,parse_float=_bad_config_number,parse_constant=_bad_config_number)\n"
        "if type(_bootstrap_config) is not dict: raise ValueError('HOST_WINDOW_CONFIG_OBJECT')\n"
        "del _packed,_compressed,_decompressor,_decoded\n")
    validate_script_bytes(source.encode())
    return source


def validate_script_bytes(raw):
    require(type(raw) is bytes and 0 < len(raw) <= INPUT_LIMIT - ACK_LIMIT - HEADER_BYTES,
        "HOST_WINDOW_FRAME_LIMIT")
    return raw


def remote_deadline_proof(retained_anchors, *, host_boot_id, guest_boot_id):
    """Machine-check the actual retained clocks without promoting missing facts.

    These two approved historical formats bind only the guest boot and host
    MONOTONIC numbers. Neither binds the current host boot or host BOOTTIME.
    The existing systemd RuntimeMaxSec boundary is activation-relative. It is
    not an absolute pre-probe deadline and cannot repair that missing mapping.
    """
    _boot(host_boot_id); _boot(guest_boot_id)
    require(type(retained_anchors) in (list, tuple) and len(retained_anchors) <= 2,
        "HOST_WINDOW_RETAINED_CLOCKS")
    observed, seen = [], set()
    for raw in retained_anchors:
        require(type(raw) is bytes, "HOST_WINDOW_RETAINED_CLOCK_BYTES")
        digest = hashlib.sha256(raw).hexdigest()
        require(digest in ANCHOR_PINS and len(raw) == ANCHOR_PINS[digest] and digest not in seen,
            "HOST_WINDOW_RETAINED_CLOCK_PIN")
        seen.add(digest)
        anchor = _json(raw)
        validators = {"local-hand-q2-recovery-clock-anchor/v1": "q2_recovery_delivery",
            "local-hand-q2-cpuquota-retry-clock-anchor/v1": "q2_retry_delivery"}
        require(anchor.get("schema") in validators, "HOST_WINDOW_RETAINED_CLOCK_SCHEMA")
        helper(validators[anchor["schema"]]).validate_clock_anchor(anchor)
        require(anchor["guest_boot_id"] == guest_boot_id, "HOST_WINDOW_RETAINED_GUEST_BOOT")
        observed.append(dict(sha256=digest, bytes=len(raw), fields=sorted(anchor),
            guest_boot_bound=True, current_host_boot_bound=False, host_boottime_bound=False))
    return dict(schema="local-hand-q2-host-window-remote-deadline-proof/v1", status="BLOCKED",
        reason="HOST_WINDOW_EXISTING_REMOTE_HARD_DEADLINE_UNPROVEN", dispatch_allowed=False,
        phase="BEFORE_FIRST_REMOTE_PROBE", clock_evidence=observed,
        missing_pinned_anchors=sorted(set(ANCHOR_PINS) - seen),
        current_host_boot_bound=False, host_boottime_mapping_proven=False,
        absolute_manager_deadline_proven=False,
        existing_mechanism="SYSTEMD_RUNTIME_MAX_RELATIVE_TO_ACTIVATION",
        queue_and_transport_delay_do_not_renew_proven=False,
        remote_stop_proven=False, q2_accepted=False, q3_accepted=False, production_supported=False)


def require_remote_deadline(retained_anchors, *, host_boot_id, guest_boot_id):
    """No caller-supplied ADMITTED flag can bypass the pinned-clock review."""
    proof = remote_deadline_proof(retained_anchors, host_boot_id=host_boot_id, guest_boot_id=guest_boot_id)
    require(proof["dispatch_allowed"], proof["reason"])
    return proof


def dispatch_original(argv, script_bytes, *, retained_anchors, host_boot_id, guest_boot_id,
                      window, until_ns, on_stdout_line, prior_bytes=0):
    """Fail before spawning when the existing remote boundary is unproven."""
    window.guard()
    require_remote_deadline(retained_anchors, host_boot_id=host_boot_id, guest_boot_id=guest_boot_id)
    return capture_framed_memory(argv, script_bytes, window=window, until_ns=until_ns,
        on_stdout_line=on_stdout_line, prior_bytes=prior_bytes)


def _boot(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value),
        "HOST_WINDOW_GUEST_BOOT")
    return value


def framed_loader(*, boot_id, deadline_ns):
    """A fixed in-memory loader; its existing management domain is external.

    The absolute guard precedes input reads and compilation. This guard cannot
    establish a manager hard deadline or supervise a blocked kernel operation.
    Dispatch must establish that independent boundary before using the loader.
    """
    _boot(boot_id)
    require(type(deadline_ns) is int and deadline_ns > 0, "HOST_WINDOW_GUEST_DEADLINE")
    return ("import os,select,time\n"
        f"_boot={boot_id!r};_end={deadline_ns};_max={INPUT_LIMIT - ACK_LIMIT - HEADER_BYTES}\n"
        "def _guard():\n"
        " if open('/proc/sys/kernel/random/boot_id').read().strip()!=_boot or time.clock_gettime_ns(time.CLOCK_BOOTTIME)>=_end: raise ValueError('HOST_WINDOW_LOADER_EXPIRED')\n"
        "def _read(n):\n"
        " value=bytearray()\n"
        " while len(value)<n:\n"
        "  _guard()\n"
        "  if not select.select([0],[],[],min(.05,max(0,(_end-time.clock_gettime_ns(time.CLOCK_BOOTTIME))/1e9)))[0]: continue\n"
        "  raw=os.read(0,min(65536,n-len(value)))\n"
        "  if not raw: raise ValueError('HOST_WINDOW_FRAME_EOF')\n"
        "  value.extend(raw)\n"
        " _guard();return bytes(value)\n"
        "_head=_read(9)\n"
        "if _head[-1:]!=b'\\n' or not _head[:8].isdigit(): raise ValueError('HOST_WINDOW_FRAME_HEADER')\n"
        "_length=int(_head[:8])\n"
        "if not 0<_length<=_max: raise ValueError('HOST_WINDOW_FRAME_LIMIT')\n"
        "_source=_read(_length);_guard()\n"
        "_code=compile(_source,'<exact-host-window-input>','exec');_guard()\n"
        "exec(_code,{'__name__':'__main__'})\n")


def read_ack(*, boot_id, deadline_ns, fd=0):
    """Read exactly one bounded line inside the original preparation deadline."""
    _boot(boot_id)
    require(type(deadline_ns) is int and deadline_ns > 0 and type(fd) is int and fd >= 0,
        "HOST_WINDOW_ACK_ARGUMENTS")
    require(stat.S_ISFIFO(os.fstat(fd).st_mode) or stat.S_ISSOCK(os.fstat(fd).st_mode),
        "HOST_WINDOW_ACK_PIPE_REQUIRED")
    from select import select
    raw = bytearray()
    while True:
        require(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == boot_id,
            "HOST_WINDOW_ACK_BOOT_CHANGED")
        remaining = deadline_ns - time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        require(remaining > 0, "HOST_WINDOW_ACK_EXPIRED")
        if not select([fd], [], [], min(.05, remaining / NS))[0]:
            continue
        # One byte prevents consuming any later protocol input accidentally.
        part = os.read(fd, 1)
        require(bool(part), "HOST_WINDOW_ACK_EOF")
        raw.extend(part)
        require(len(raw) <= ACK_LIMIT, "HOST_WINDOW_ACK_LIMIT")
        if part == b"\n":
            require(time.clock_gettime_ns(time.CLOCK_BOOTTIME) < deadline_ns,
                "HOST_WINDOW_ACK_EXPIRED")
            return bytes(raw)


def analyze_wrapper_profile(raw, *, expected_sha256, wrapper_path, profile_id):
    """Analyze one complete finite grammar in RAM; never admit its execution.

    Literal slots are data within an otherwise exact source shape. This is not
    a shell parser, nor authority to adopt a caller-supplied source digest.
    Paths are checked lexically; no file, executable or credential is opened.
    """
    require(type(profile_id) is str and profile_id == ENV_BASH_LITERAL_SSH_PROFILE,
        "HOST_WINDOW_WRAPPER_PROFILE_UNSUPPORTED")
    require(type(raw) is bytes and 0 < len(raw) <= 1024**2
        and hashlib.sha256(raw).hexdigest() == expected_sha256, "HOST_WINDOW_WRAPPER_DIGEST")
    require(type(wrapper_path) is str and wrapper_path.startswith("/")
        and not wrapper_path.startswith("//") and wrapper_path != "/"
        and str(PurePosixPath(wrapper_path)) == wrapper_path
        and ".." not in PurePosixPath(wrapper_path).parts and "\0" not in wrapper_path,
        "HOST_WINDOW_WRAPPER_PATH")
    try:
        source = raw.decode("utf-8", "strict")
    except UnicodeError:
        raise ValueError("HOST_WINDOW_WRAPPER_ENCODING") from None
    match = _LITERAL_SSH_SOURCE.fullmatch(source)
    require(match is not None, "HOST_WINDOW_WRAPPER_PROFILE_SOURCE_UNSUPPORTED")
    directory = match["directory"]
    require(not directory.startswith("//") and directory != "/"
        and str(PurePosixPath(directory)) == directory
        and ".." not in PurePosixPath(directory).parts
        and int(match["port"]) <= 65535, "HOST_WINDOW_WRAPPER_PROFILE_LITERAL_UNSUPPORTED")
    return dict(schema="local-hand-q2-wrapper-profile-analysis/v1", profile_id=profile_id,
        source_sha256=expected_sha256, source_bytes=len(raw), supported_syntax=True,
        local_variables=["q1_vm"], dependency_roles=["env", "bash", "ssh", "identity_file", "known_hosts"],
        source_execution_admitted=False)


def memory_wrapper_argv(raw, *, expected_sha256, wrapper_path, remote_argv, profile_id=None):
    """Use exact pinned shell text without reopening its preserved source path.

    Unknown interpreters and script-file introspection are unsupported. This is
    an execution adapter for the existing wrapper, not a replacement SSH recipe.
    An explicit finite profile constructs argv for controlled_environment();
    this function does not apply that environment or prove field tool identity,
    credential/cwd equivalence, source adoption or permission to execute.
    """
    require(type(raw) is bytes and 0 < len(raw) <= 1024**2
        and hashlib.sha256(raw).hexdigest() == expected_sha256, "HOST_WINDOW_WRAPPER_DIGEST")
    require(type(wrapper_path) is str and wrapper_path.startswith("/")
        and not wrapper_path.startswith("//") and wrapper_path != "/"
        and str(Path(wrapper_path)) == wrapper_path and ".." not in Path(wrapper_path).parts,
        "HOST_WINDOW_WRAPPER_PATH")
    require(type(remote_argv) in (list, tuple) and 0 < len(remote_argv) <= 64
        and all(type(arg) is str and 0 < len(arg) <= 65536 and "\0" not in arg for arg in remote_argv),
        "HOST_WINDOW_REMOTE_ARGV")
    try:
        source = raw.decode("utf-8", "strict")
    except UnicodeError:
        raise ValueError("HOST_WINDOW_WRAPPER_ENCODING") from None
    if profile_id is not None:
        analyze_wrapper_profile(raw, expected_sha256=expected_sha256,
            wrapper_path=wrapper_path, profile_id=profile_id)
        try:
            command = shlex.join(remote_argv)
            command.encode("utf-8", "strict")
        except UnicodeError:
            raise ValueError("HOST_WINDOW_WRAPPER_REMOTE_ENCODING") from None
        # Preserve the original env/PATH interpreter lookup and every source
        # byte. The profile excludes file introspection and any stdin reader
        # before exec; $0 and the one existing remote-command argument remain.
        # This construction does not prove tool identity or field readiness.
        return ["/usr/bin/env", "bash", "-c", source, wrapper_path, command]
    interpreter = source.splitlines()[0]
    interpreters = {"#!/bin/sh": ["/bin/sh"], "#!/bin/bash": ["/bin/bash", "--noprofile", "--norc"],
        "#!/usr/bin/bash": ["/usr/bin/bash", "--noprofile", "--norc"]}
    require(interpreter in interpreters, "HOST_WINDOW_WRAPPER_INTERPRETER_UNSUPPORTED")
    require("\0" not in source and not any(token in source for token in
        ("BASH_SOURCE", "BASH_ENV", "BASH_EXECUTION_STRING", "/proc/self/", "/proc/$$/",
         "${0}", "$0", "LINENO", "FUNCNAME", "BASH_ARGV0", "caller", "set -o posix")),
        "HOST_WINDOW_WRAPPER_FILE_SEMANTICS_UNSUPPORTED")
    # A shell text using an unbound external variable cannot be shown equivalent
    # under the controlled environment. Local shell assignments are not inferred
    # by a partial parser; more complex wrappers are explicitly unsupported.
    names = re.findall(r"\$(?:\{)?([A-Za-z_][A-Za-z0-9_]*)", source)
    require(set(names) <= {"HOME", "USER", "LOGNAME", "SSH_AUTH_SOCK", "SSH_AGENT_PID", "PATH", "LANG", "LC_ALL"}
        and "${!" not in source and "eval" not in source and "source " not in source,
        "HOST_WINDOW_WRAPPER_ENVIRONMENT_UNSUPPORTED")
    return [*interpreters[interpreter], "-c", source, wrapper_path, shlex.join(remote_argv)]


def capture_framed_memory(argv, script_bytes, *, window, until_ns, prior_bytes=0,
                          output_limit=None, on_stdout_line=None):
    """One original local client, script frame, and at most one returned ACK.

    The callback returns None for ordinary lines or one newline-terminated ACK.
    No ACK is sent before the complete script frame. No EOF is sent in its place.
    The input pipe closes only after that ACK is written, or during containment.
    """
    window.guard()
    base.legacy.number(until_ns, window.issued_ns + 1, window.deadline_ns)
    base.legacy.number(prior_bytes, 0, OUTPUT_LIMIT)
    available = OUTPUT_LIMIT - prior_bytes
    limit = available if output_limit is None else output_limit
    base.legacy.number(limit, 1, available)
    require(type(script_bytes) is bytes and 0 < len(script_bytes) <= INPUT_LIMIT - ACK_LIMIT - HEADER_BYTES,
        "HOST_WINDOW_FRAME_LIMIT")
    require(type(argv) in (list, tuple) and 0 < len(argv) <= 64 and
        all(type(arg) is str and 0 < len(arg) <= 1024**2 and "\0" not in arg for arg in argv),
        "HOST_WINDOW_TRANSPORT_COMMAND")
    require(callable(on_stdout_line), "HOST_WINDOW_ACK_OBSERVER_REQUIRED")
    frame = f"{len(script_bytes):08d}\n".encode() + script_bytes
    pending = bytearray(frame)
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    line = bytearray()
    proc, error, started = None, None, None
    selector = selectors.DefaultSelector()
    eof, identities = set(), {}
    sent, ack, exit_observed, input_registered = 0, None, False, False
    stop_reserve = min(NS, max(1, window.remaining_ns(until_ns) // 5))
    def observe(raw_line):
        nonlocal ack, input_registered
        window.guard()
        reply = on_stdout_line(raw_line)
        if reply is None:
            return
        require(ack is None, "HOST_WINDOW_ACK_REPEATED")
        require(sent >= len(frame), "HOST_WINDOW_ACK_BEFORE_FRAME")
        require(type(reply) is bytes and 0 < len(reply) <= ACK_LIMIT
            and reply.endswith(b"\n") and reply.count(b"\n") == 1,
            "HOST_WINDOW_ACK_FRAME")
        window.guard()
        require(window.remaining_ns(until_ns) > stop_reserve, "HOST_WINDOW_ACK_EXPIRED")
        ack = reply
        pending.extend(reply)
        if not input_registered:
            selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
            input_registered = True
    try:
        require(window.remaining_ns(until_ns) > stop_reserve, "HOST_WINDOW_CAPTURE_TIME")
        proc = subprocess.Popen(list(argv), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, start_new_session=True, bufsize=0,
            env=controlled_environment())
        started = window.monotonic()
        for name in ("stdout", "stderr"):
            stream = getattr(proc, name)
            os.set_blocking(stream.fileno(), False)
            info = os.fstat(stream.fileno())
            identities[name] = [info.st_dev, info.st_ino]
            selector.register(stream, selectors.EVENT_READ, name)
        os.set_blocking(proc.stdin.fileno(), False)
        selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
        input_registered = True
        while eof != {"stdout", "stderr"} or proc.poll() is None:
            window.guard()
            remaining = window.remaining_ns(until_ns)
            require(remaining > stop_reserve, "HOST_WINDOW_CAPTURE_TIMEOUT")
            for key, _ in selector.select(min(.05, remaining / NS)):
                if key.data == "stdin":
                    count = os.write(key.fd, pending[sent:sent + 65536])
                    require(count > 0, "HOST_WINDOW_STDIN_SHORT_WRITE")
                    sent += count
                    if sent == len(pending):
                        selector.unregister(key.fileobj)
                        input_registered = False
                        if ack is not None:
                            key.fileobj.close()
                    continue
                block = os.read(key.fd, 65536)
                if not block:
                    eof.add(key.data)
                    selector.unregister(key.fileobj)
                    continue
                room = max(0, limit - sum(map(len, captured.values())))
                captured[key.data].extend(block[:room])
                require(len(block) <= room, "HOST_WINDOW_CAPTURE_LIMIT")
                if key.data == "stdout":
                    line.extend(block)
                    while b"\n" in line:
                        end = line.index(b"\n") + 1
                        raw_line = bytes(line[:end]); del line[:end]
                        observe(raw_line)
            if proc.poll() is not None:
                exit_observed = True
        require(ack is not None and sent == len(pending), "HOST_WINDOW_ACK_UNDELIVERED")
        if line:
            # A partial line cannot carry another admission response.
            require(on_stdout_line(bytes(line)) is None, "HOST_WINDOW_ACK_UNTERMINATED_SIGNAL")
    except BaseException as failure:
        error = base.reason(failure)
    finally:
        if proc is not None:
            if error or proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError:
                    error = error or "HOST_WINDOW_CLIENT_KILL_UNPROVEN"
            try:
                proc.wait(timeout=max(.1, min(1., max(0, window.remaining_ns(until_ns)) / NS)))
                exit_observed = True
            except subprocess.TimeoutExpired:
                error = error or "HOST_WINDOW_CLIENT_EXIT_UNPROVEN"
            for name in ("stdin", "stdout", "stderr"):
                stream = getattr(proc, name)
                if stream is not None and not stream.closed:
                    try:
                        stream.close()
                    except OSError:
                        error = error or "HOST_WINDOW_PIPE_CLOSE"
        selector.close()
    finished, finished_boot = window.monotonic(), window.boottime()
    within = (finished <= until_ns and
        finished_boot <= window.boottime_issued_ns + until_ns - window.issued_ns)
    raw = {name: bytes(value) for name, value in captured.items()}
    total = sum(map(len, raw.values()))
    complete = (proc is not None and exit_observed and proc.returncode == 0 and
        eof == {"stdout", "stderr"} and error is None and within and ack is not None)
    record = dict(schema=SCHEMA, status="CAPTURED" if complete else "INCOMPLETE", complete=complete,
        **window.fields(), started_ns=started, finished_ns=finished, finished_boottime_ns=finished_boot,
        capture_deadline_ns=until_ns, error=error, returncode=proc.returncode if proc else None,
        eof=sorted(eof), original_client_exit_observed=exit_observed, pipe_identities=identities,
        captured_bytes=total, total_captured_bytes=prior_bytes + total,
        input_bytes=len(pending), input_bytes_sent=sent, input_sha256=hashlib.sha256(pending).hexdigest(),
        script_sha256=hashlib.sha256(script_bytes).hexdigest(),
        ack_sha256=hashlib.sha256(ack).hexdigest() if ack is not None else None,
        ack_delivered=ack is not None and sent == len(pending),
        stdout_sha256=hashlib.sha256(raw["stdout"]).hexdigest(),
        stderr_sha256=hashlib.sha256(raw["stderr"]).hexdigest(), within_original_deadline=within,
        remote_stop_proven=False, q2_accepted=False, q3_accepted=False, production_supported=False)
    return dict(record=record, **raw)

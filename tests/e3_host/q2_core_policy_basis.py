"""Fixed, source-bound policy inputs for core amendment A 0bdb49c.

This constructs expectations only. It never reads current guest configuration,
runs sudo/sshd, or turns a source predicate into an admission verdict.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import shlex
import struct

from . import q2_core_delivery_contract as c


SCHEMA = "local-hand-q2-core-policy-basis/v1"
ITEM_SCHEMA = "local-hand-q2-core-policy-basis-item/v1"
SOURCE_PINS = {
    "fixture_cloud_config": "5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523",
    "identity_public": "e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c",
    "known_hosts": "d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd",
}
GRANT = "q1admin ALL=(ALL) NOPASSWD:ALL"
ENVIRONMENT = {"HOME": "/root", "LANG": "C", "LC_ALL": "C", "LOGNAME": "root",
               "PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "SYSTEMD_COLORS": "0", "USER": "root"}
ABSENT = ["/home/q1admin/.ssh/rc", "/home/q1admin/.ssh/environment", "/etc/ssh/sshrc"]
STARTUP = ["/home/q1admin/" + name for name in (".profile", ".bash_profile", ".bash_login", ".bashrc")]


def _require(condition, code):
    c.require(condition, "CORE_POLICY_BASIS_" + code)


def _hash(value):
    return hashlib.sha256(c.canonical(value)).hexdigest()


def _key(raw):
    try:
        lines = [line.strip() for line in raw.decode("ascii").splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        _require(len(lines) == 1, "KEY_COUNT")
        fields = lines[0].split()
        _require(len(fields) >= 2 and fields[0] == "ssh-ed25519", "KEY_TYPE")
        decoded = base64.b64decode(fields[1], validate=True)
        _require(base64.b64encode(decoded).decode("ascii") == fields[1]
                 and decoded == struct.pack(">I", 11) + b"ssh-ed25519"
                 + struct.pack(">I", 32) + decoded[-32:] and len(decoded) == 51,
                 "KEY_ENCODING")
    except (UnicodeError, ValueError, IndexError) as error:
        raise c.ContractError("CORE_POLICY_BASIS_KEY") from error
    return dict(type="ssh-ed25519", key_base64=fields[1], source_sha256=SOURCE_PINS["identity_public"])


def remote_expectation(tokens):
    """Bind already source-verified fixed tokens, never an observed command."""
    _require(type(tokens) is list and tokens and all(type(x) is str and x and "\0" not in x
                                                   for x in tokens), "TOKENS")
    return dict(account="q1admin", home_path="/home/q1admin", login_shell="/bin/bash",
        hello_schema="local-hand-q2-core-carrier-hello/v2", parser_profile="bash-noninteractive-c-v1",
        aliases=dict(shell="/bin/bash", sudo="/usr/bin/sudo", env="/usr/bin/env",
                     systemd_run="/usr/bin/systemd-run", python="/usr/bin/python3"),
        remote_tokens_sha256=_hash(tokens),
        remote_command_sha256=hashlib.sha256(shlex.join(tokens).encode("utf-8")).hexdigest(),
        remote_entity_preimages_stage="HELLO_JIT")


def _paths(profile, fixed, home, includes, limits):
    return dict(profile=profile,
        fixed_paths=[dict(path=path, required=required) for path, required in fixed],
        home_relative_paths=[dict(path=path, required=required) for path, required in home],
        include_roots=[dict(path=path, required=required, selection=selection)
                       for path, required, selection in includes],
        limits=dict(zip(("max_files", "max_directories", "max_depth", "max_file_bytes",
                         "max_total_bytes", "max_directory_entries"), limits, strict=True)))


def _execution(executable=None, identity=None):
    helper = executable is not None
    action = "SIGKILL_THEN_WAIT_NO_RETRY" if helper else "NOT_APPLICABLE"
    return dict(executable=executable, executable_identity_source=identity,
        executable_max_bytes=16777216 if helper else 0, cwd="/" if helper else None,
        stdin="/dev/null" if helper else "NOT_APPLICABLE", shell=False,
        max_invocations=1 if helper else 0, required_exit_status=0 if helper else None,
        require_stdout_eof=helper, require_stderr_eof=helper,
        drain_profile="concurrent-nonblocking-v1" if helper else "NOT_APPLICABLE",
        overflow_action=action, timeout_action=action,
        side_effect_class="CURRENT_GUEST_SEMANTIC_HELPER_WITH_AUDIT_NSS_PLUGIN_EFFECTS"
        if helper else "NO_HELPER_PROCESS")


def _item(*, mode, sources, paths, argv, execution, profile, parameters, output=0):
    predicate = dict(profile=profile, parameters=parameters)
    return dict(schema=ITEM_SCHEMA, mode=mode, sources=sources, paths=paths, argv=argv,
        environment=copy.deepcopy(ENVIRONMENT) if output else {}, execution=execution,
        predicate=predicate,
        limits=dict(command_seconds=5 if output else 0, command_cpu_seconds=2 if output else 0,
                    stdout_bytes=output, stderr_bytes=output, combined_output_bytes=output),
        predicate_sha256=_hash(predicate))


def build_policy_basis(*, source_raw, tokens):
    """Construct A's four exact static predicates from the three fixed sources.

    The caller must bind ``tokens`` to the verified D loader/bootstrap and
    cross-check each source against the held local-management binding. No
    current observation or caller-selected predicate is accepted here.
    """
    _require(type(source_raw) is dict and set(source_raw) == set(SOURCE_PINS), "SOURCE_SET")
    for name, pin in SOURCE_PINS.items():
        _require(type(source_raw[name]) is bytes and hashlib.sha256(source_raw[name]).hexdigest() == pin,
                 "SOURCE_PIN")
    _require(source_raw["fixture_cloud_config"].count(GRANT.encode("ascii")) == 1, "SOURCE_GRANT")
    approved_key = _key(source_raw["identity_public"])
    policies = {
        "sudo": _item(mode="same-carrier-current-self-observation",
            sources=["/fixture_cloud_config", "/remote_expectation"],
            paths=_paths("sudoers-fixed-closure-v1", [("/etc/sudo.conf", True), ("/etc/sudoers", True)],
                [], [("/etc/sudoers.d", True, "sudoers-includedir-v1")],
                (66, 3, 8, 262144, 1048576, 256)),
            argv=["/usr/bin/sudo", "-n", "-ll", "-U", "q1admin"],
            execution=_execution("/usr/bin/sudo", "HELLO_REMOTE_MANAGEMENT_SUDO"),
            profile="sudo-ll-c-v1", output=65536,
            parameters=dict(account="q1admin", cloud_config_literal=GRANT, cloud_config_literal_count=1,
                required_grant=dict(commands=["ALL"], host="ALL", runas_groups=[], runas_users=["ALL"],
                                    tags=["NOPASSWD"]), on_unknown="STOP_AND_RETAIN")),
        "sshd": _item(mode="source-plus-effective", sources=["/known_hosts", "/remote_expectation"],
            paths=_paths("sshd-fixed-closure-v1", [("/etc/ssh/sshd_config", True)], [],
                [("/etc/ssh/sshd_config.d", True, "ascii-star-dot-conf-v1")],
                (65, 2, 8, 262144, 1048576, 256)),
            argv=["/usr/sbin/sshd", "-T"],
            execution=_execution("/usr/sbin/sshd", "POLICY_SNAPSHOT_OBJECT"),
            profile="sshd-T-c-v1", output=1048576,
            parameters=dict(required_effective=dict(authorizedkeyscommand="none",
                authorizedkeysfile=[".ssh/authorized_keys", ".ssh/authorized_keys2"], forcecommand="none",
                permituserenvironment="no", pubkeyauthentication="yes"), on_unknown="STOP_AND_RETAIN")),
        "authorized_keys": _item(mode="exact-single-key", sources=["/identity_public", "/remote_expectation"],
            paths=_paths("authorized-keys-fixed-home-v1", [],
                [(".ssh/authorized_keys", True), (".ssh/authorized_keys2", False)], [],
                (2, 3, 4, 65536, 131072, 64)), argv=[], execution=_execution(),
            profile="authorized-key-single-v1",
            parameters=dict(account="q1admin", home_path="/home/q1admin",
                authorized_keys_files=[".ssh/authorized_keys", ".ssh/authorized_keys2"],
                approved_key=approved_key, key_comparison="TYPE_AND_DECODED_KEY_BYTES_EQUAL",
                allowed_options=[], required_effective_entries=1, comments="IGNORED_AFTER_KEY",
                blank_lines="IGNORED", on_unknown="STOP_AND_RETAIN")),
        "rc": _item(mode="ssh-rc-absence-shell-provenance", sources=["/remote_expectation"],
            paths=_paths("ssh-rc-bash-noninteractive-v1", [("/etc/ssh/sshrc", False)],
                [(name, False) for name in (".ssh/rc", ".ssh/environment", ".profile",
                                            ".bash_profile", ".bash_login", ".bashrc")], [],
                (7, 4, 4, 1048576, 4194304, 64)), argv=[], execution=_execution(),
            profile="ssh-rc-bash-noninteractive-v1",
            parameters=dict(account="q1admin", home_path="/home/q1admin", required_absent=list(ABSENT),
                shell_startup_paths=list(STARTUP), bashrc_guard_profile="first-executable-interactive-return-v1",
                forbidden_environment=["BASH_ENV", "ENV"], shell_parser_profile="bash-noninteractive-c-v1",
                on_unknown="STOP_AND_RETAIN")),
    }
    result = dict(schema=SCHEMA,
        **{name: dict(binding_pointer="/" + name, sha256=pin) for name, pin in SOURCE_PINS.items()},
        remote_expectation=remote_expectation(tokens), policies=policies,
        policy_predicates_sha256=_hash(policies))
    c.canonical(result, limit=1048576)
    return result


def verify_policy_basis(value, *, source_raw, tokens):
    """Reject any drift, including extra keys, modified grammar or helper budgets."""
    expected = build_policy_basis(source_raw=source_raw, tokens=tokens)
    _require(c.canonical(value) == c.canonical(expected), "RELATION")
    return _hash(value)

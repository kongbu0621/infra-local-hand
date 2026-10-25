"""Fixed bounded offline reader; never re-enable an intentionally stopped service."""
import hashlib
import os
from pathlib import Path
import subprocess
import time

from local_hand_jobs import startup

from .model import DeployError, canonical, decode


def offline_readback(environment, component, selected, *, deadline, candidates=None, original_policies=None):
    profile, owner = environment.profile, environment.owner
    candidates = candidates or {}
    def read(path, uid=owner):
        return decode(startup.protected_read(candidates.get(path, path), owner_uid=uid))
    path = profile["guarded_components"][component]["configuration"]
    config = read(path)
    if profile["probes"][component]["kind"] == "mcp":
        if config.get("schema") != "local-hand-mcp-startup/v1":
            raise DeployError("RETENTION_CONFIGURATION", "Offline readback requires the selected complete MCP configuration")
        managers = [name for name, probe in profile["probes"].items()
                    if probe["kind"] in {"resident", "prepared"} and probe["socket"] == config["manager_socket"]]
        if len(managers) != 1:
            raise DeployError("RETENTION_CONFIGURATION", "Offline reader has no unique admitted installation")
        manager = read(profile["guarded_components"][managers[0]]["configuration"])
        mode = config["mode"]
        inputs = {name: candidates.get(path, path) for name, path in config["inputs"].items()}
    else:
        manager = config
        tasks = [item for item in environment.preparation_inventory(candidates)["tasks"]
                 if item["component"] == component and item["state"] == "READY"]
        if not tasks:
            return {"schema": "local-hand-retained-readback/v1", "tasks": [], "bytes_verified": 0}
        if any(not isinstance(item.get("policy_path"), str) for item in tasks):
            raise DeployError("RETENTION_CONFIGURATION", "Original task policy route is missing")
        mode, inputs = "policies", {"policies": [item["policy_path"] for item in tasks]}
    if original_policies is not None:
        if not isinstance(original_policies, list) or not 1 <= len(original_policies) <= 256:
            raise DeployError("RETENTION_CONFIGURATION", "Original historical routes exceed their fixed bound")
        mode, inputs = "policies", {"policies": original_policies}
    installation = manager["installation"]
    installed = installation["installed"]
    expected = selected["selection"]["components"][component]["payload_digest"]
    if installed["payload_digest"] != expected:
        raise DeployError("RETENTION_CONFIGURATION", "Offline reader is not the selected MCP payload")
    policy_path = inputs["policies"][0] if mode == "policies" else inputs["config"]
    # Policies belong to the original protected data owner; read_descriptor in
    # the child performs its full original-policy/path validation again.
    data_owner = manager.get("uid", owner)
    policy = read(policy_path, data_owner)
    uid, gid = (policy["process_manager"][key] for key in ("uid", "gid"))
    if any(type(value) is not int or value < 0 for value in (uid, gid)):
        raise DeployError("RETENTION_CONFIGURATION", "Offline data owner is invalid")
    program = installed["programs"]["python"]
    executable = startup.protected_read(program["path"], owner_uid=0, maximum=64 * 1024 * 1024)
    if hashlib.sha256(executable).hexdigest() != program["sha256"]:
        raise DeployError("RETENTION_CONFIGURATION", "Offline interpreter differs from its admitted bytes")
    seconds = min(120, deadline - time.monotonic())
    if seconds <= 0:
        raise DeployError("RETENTION_LIMIT", "Offline verification exhausted its time budget")
    root = installed["package_root"]
    from local_hand.provenance import full_payload_digest
    if full_payload_digest(Path(root)) != expected:
        raise DeployError("RETENTION_CONFIGURATION", "Offline reader payload changed before launch")
    spec = {"mode": mode, "inputs": inputs, "seconds": seconds,
            "reader_identity": {"source_commit": installation["source"]["commit"],
                "installed_payload_digest": expected, "execution_entrypoint": str(Path(root) / "local_hand_jobs/cli.py")}}
    # Root never imports candidate Python. The selected reader runs after
    # dropping to the original data owner, with no groups, listener or shell.
    code = ("import sys,os,resource,ctypes; os.umask(0o077); "
            "resource.setrlimit(resource.RLIMIT_CPU,(120,120)); "
            "resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576)); "
            "assert ctypes.CDLL(None).prctl(38,1,0,0,0)==0; "
            "sys.path.insert(0,sys.argv[1]); from local_hand_jobs.retained_offline import main; main()")
    options = {"user": uid, "group": gid, "extra_groups": []} if os.geteuid() == 0 else {}
    if os.geteuid() != 0 and (uid, gid) != (os.geteuid(), os.getegid()):
        raise DeployError("RETENTION_CONFIGURATION", "Offline reader cannot change to the original data owner")
    lock = getattr(getattr(environment, "store", None), "lock_fd", None)
    with subprocess.Popen([program["path"], "-I", "-B", "-c", code, root],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/",
            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, start_new_session=True,
            pass_fds=(() if lock is None else (lock,)), **options) as child:
        try:
            output, _ = child.communicate(canonical(spec), timeout=seconds)
        except subprocess.TimeoutExpired as error:
            child.kill(); child.communicate()
            raise DeployError("RETENTION_LIMIT", "Offline read-only verifier timed out and exited") from error
        if child.returncode != 0 or len(output) > 1024 * 1024:
            raise DeployError("RETENTION_READ_FAILED", "Selected offline read-only verifier failed")
    response = decode(output)
    if "error" in response or not isinstance(response.get("result"), dict):
        raise DeployError("RETENTION_READ_FAILED", "Selected offline reader rejected original retained data")
    return response["result"]

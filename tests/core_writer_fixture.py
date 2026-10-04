"""Explicit synthetic identities, never observations or field authority."""


def writer():
    return {"schema": "local-hand-q2-core-local-writer/v1",
            "user_namespace": {"dev": 1, "ino": 2},
            "pid_namespace": {"dev": 1, "ino": 3},
            "process": {"pid": 456, "starttime_ticks": 789},
            "uid": dict.fromkeys(("real", "effective", "saved", "filesystem"), 1001),
            "gid": dict.fromkeys(("real", "effective", "saved", "filesystem"), 1002),
            "supplementary_gids": [1002, 1003]}


def host_marker(context):
    from e3_host import q2_core_delivery_entry as entry
    c = entry.contract
    manifest, bind = context["manifest"], context["bind"]
    value = entry.consumption_record(
        implementation=manifest["implementation"], amendment=manifest["amendment"],
        package={"basename": bind["package_basename"], "bytes": bind["package_bytes"],
                 "sha256": bind["package_sha256"],
                 "manifest_sha256": c.sha256(c.canonical(manifest, newline=True))},
        approved_inputs_sha256=manifest["approved_inputs"]["sha256"],
        local_management_binding_sha256=manifest["entry"]["local_management_binding_sha256"],
        writer=manifest["entry"]["writer"],
        carrier_argv_sha256=manifest["entry"]["carrier_argv_sha256"],
        origins={key: bind[key] for key in ("host_boottime_origin_ns", "host_monotonic_origin_ns",
                                           "host_boottime_deadline_ns", "host_monotonic_deadline_ns")})
    raw = c.canonical(value, newline=True, limit=16384)
    return raw, {"basename": c.MARKER_BASENAME, "bytes": len(raw), "sha256": c.sha256(raw)}

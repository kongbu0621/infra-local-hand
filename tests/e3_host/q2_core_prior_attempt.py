"""Fixed consumed F1 preimages for the separately approved next acceptance.

Historical UNKNOWN is retained. The fixed current host capacity condition is
not a complete bill or a reservation. No quiescence or generic prior inputs.
"""
from __future__ import annotations

import base64
import copy
import os
import stat
import struct

from . import q2_core_delivery_contract as c

SCHEMA = "local-hand-q2-core-prior-attempt/v2"
SESSION = "lhqcore-20261003a"
UNIT = "lhqcore20261003a-carrier.service"
IMPLEMENTATION = dict(commit="605a2a38d1db5ef85c961b4d357cafa157bdd7d5",
                      tree="ced38519fe6e3b86973de5ccf0dff60fc62322e4")
PACKAGE_SHA = "a8ca34f3fba3fd370485b522f3c009fa41de70fab1441224b56232885b77380e"
MANIFEST_SHA = "9c05d55ed52dc1e0c04ad340549de6e584a4296b392d84abd07428f179a1989f"
LOADER_SHA = "6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61"
BOOTSTRAP_SHA = "039fe87cc91a64c0327dc404e0ccf9728c32a1cc07e3e6fb11ed74c979f904f3"
PINS = {
    "carrier-consumed.json": (3577, "5d85f8d5c51329bf46eba91d0106a41d449389e16b018bbb30ddbc667e69d502"),
    "stdout": (2852, "bd042a224271b03eadaddb99868e3f0c4cef4f71365482f112577005d8be5e1d"),
    "stderr": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "capture-manifest.json": (1637, "5ab260b4062404991151dd917fd636d4f1cd4ba5dd0ffa45a1578f5cf6bb3db3"),
    "acceptance-receipt.json": (1252, "dd1d4f5c607572fa9eb1527ddb94e2eb839f5ae5e59509042b6d03313cf74700"),
}
TOTAL_BYTES = 9318
SECOND_SESSION = "lhqcore-20261005a"
SECOND_IMPLEMENTATION = dict(commit="59d7c32bbe10d580603b8e5e62dd49ad6a538e56",
                            tree="15bfe2192ced5aad0acf5c74a58b6e865afe34d1")
SECOND_PINS = {
    "carrier-consumed.json": (3577, "126a3fc0c40085c360e6392d06ec286e42f05edc93823fd01f36c0869103d2a6"),
    "stdout": (2852, "3cf4a279a36daeb3348d52544c92bdfeba3f295e0650f2bf49bd204d3e0bd3b9"),
    "stderr": (23, "ef5aad9b8e8b977441ad9ab1e58cd1dc8ad994798f5802d2f6768c241afb8ece"),
    "capture-manifest.json": (None, "081019f289a561839ddf13da0c5bf55150879e998a6b52241864f3813b132d1b"),
    "acceptance-receipt.json": (None, "541198e61811e4b6f2df3d17eb4ade8f91ef567ae4c00e89e7023f5709040f35"),
}
SECOND_TOTAL_BYTES = 9072
ROLE_LIMITS = {"carrier-consumed.json": 16384, "stdout": 4112, "stderr": 4194304,
               "capture-manifest.json": 262144, "acceptance-receipt.json": 65536}


def profile(index):
    require(type(index) is int and index in (0, 1), "PROFILE")
    if index == 0:
        return dict(session=SESSION, unit=UNIT, implementation=IMPLEMENTATION, pins=PINS,
            total=TOTAL_BYTES, package_sha=PACKAGE_SHA, manifest_sha=MANIFEST_SHA,
            package_bytes=18111397, bootstrap_sha=BOOTSTRAP_SHA, sent=False, status=255)
    return dict(session=SECOND_SESSION, unit="lhqcore20261005a-carrier.service",
        implementation=SECOND_IMPLEMENTATION, pins=SECOND_PINS, total=SECOND_TOTAL_BYTES,
        package_sha="da72c862bbcbe4ae43df681f91576d38586eec1eeb550b46e378d3398e07008b",
        manifest_sha="09e7b8ef0df3b3103f0ba87113dfcf2d3470b861ad14f84c83c144a0f6b3c6fb",
        package_bytes=18149835,
        bootstrap_sha="c9f6e89f874d83856552e65810b04a5d88e7ab0687395dfa5dfd80d7affdee83",
        sent=True, status=3)


def read_files(directory_fd, anchor, call, *, index=0, _seen=None):
    """Read the five exact originals relative to an already qualified anchor.

    No writes, old-writer liveness check or remote observation. The same held
    descriptor is retained by the live caller; absence of a sixth result is
    checked without following a name. Permission failure has no fallback.
    """
    def identity(info):
        return info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink
    def parent():
        info = call(os.fstat, directory_fd)
        named = call(os.stat, anchor["path"], follow_symlinks=False)
        require(identity(info) == identity(named)
            and (info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid)
            == tuple(anchor[key] for key in ("dev", "ino", "mode", "uid", "gid"))
            and stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700, "PARENT")
        return identity(info)
    fixed = profile(index)
    name = lambda suffix: basename(suffix, index)
    before_parent = parent()
    files = {}; seen = set() if _seen is None else _seen
    for suffix, (size, digest) in fixed['pins'].items():
        opened = []
        try:
            fd = call(os.open, name(suffix), os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
                      | os.O_NOATIME | os.O_NONBLOCK, dir_fd=directory_fd, returned=opened.append)
            before = call(os.fstat, fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) == 0o600 and before.st_uid == anchor["uid"]
                and before.st_gid == anchor["gid"] and before.st_dev == anchor['dev']
                and (size is None or before.st_size == size) and 0 <= before.st_size <= ROLE_LIMITS[suffix]
                and (before.st_dev, before.st_ino) not in seen, "FILE_IDENTITY")
            seen.add((before.st_dev, before.st_ino))
            size = before.st_size
            chunks = bytearray()
            while len(chunks) <= size:
                part = call(os.read, fd, size + 1 - len(chunks))
                if not part:
                    break
                chunks.extend(part)
            raw = bytes(chunks)
            after = call(os.fstat, fd)
            named = call(os.stat, name(suffix), dir_fd=directory_fd, follow_symlinks=False)
            def stable(info):
                return identity(info) + (info.st_size, info.st_blocks, info.st_atime_ns,
                                          info.st_mtime_ns, info.st_ctime_ns)
            require(stable(before) == stable(after) == stable(named)
                    and len(raw) == size and c.sha256(raw) == digest, "READ_PIN")
            files[name(suffix)] = raw
        finally:
            for held in opened:
                os.close(held)
    try:
        call(os.stat, name("remote-result.json"), dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise c.ContractError("CORE_PRIOR_UNEXPECTED_RESULT")
    require(parent() == before_parent, "PARENT_DRIFT")
    build(files, index=index)
    return files


def read_all_files(directory_fd, anchor, call):
    seen = set()
    files = {}
    for index in (0, 1):
        files.update(read_files(directory_fd, anchor, call, index=index, _seen=seen))
    build_all(files)
    return files


def require(ok, reason):
    c.require(ok, "CORE_PRIOR_" + reason)


def basename(suffix, index=0):
    return "." + profile(index)['session'] + "." + suffix


def build(raw_files, *, index=0):
    fixed = profile(index)
    name = lambda suffix: basename(suffix, index)
    c.exact(raw_files, {name(suffix) for suffix in fixed['pins']}, "CORE_PRIOR_FILES")
    rows = []
    for suffix, (size, digest) in fixed['pins'].items():
        raw = raw_files[name(suffix)]
        require(type(raw) is bytes and (size is None or len(raw) == size)
                and len(raw) <= ROLE_LIMITS[suffix] and c.sha256(raw) == digest, "PIN")
        rows.append(dict(basename=name(suffix), bytes=len(raw), sha256=digest,
                         raw_base64=base64.b64encode(raw).decode("ascii")))
    value = dict(schema=SCHEMA, scope=c.SCOPE, session_id=fixed['session'],
                 implementation=copy.deepcopy(fixed['implementation']), package_sha256=fixed['package_sha'],
                 manifest_sha256=fixed['manifest_sha'], files=sorted(rows, key=lambda row: row["basename"]))
    validate(value, index=index)
    return value


def validate(value, *, index=0):
    """Independently consume embedded bytes, not the builder's conclusions."""
    fixed = profile(index)
    name = lambda suffix: basename(suffix, index)
    c.exact(value, {"schema", "scope", "session_id", "implementation", "package_sha256",
                    "manifest_sha256", "files"}, "CORE_PRIOR_FIELDS")
    require(value["schema"] == SCHEMA and value["scope"] == c.SCOPE
            and value["session_id"] == fixed['session'] and value["implementation"] == fixed['implementation']
            and value["package_sha256"] == fixed['package_sha'] and value["manifest_sha256"] == fixed['manifest_sha'],
            "IDENTITY")
    rows = value["files"]
    require(type(rows) is list and len(rows) == 5, "FILES")
    require([row.get("basename") for row in rows] == sorted(name(suffix) for suffix in fixed['pins']), "ORDER")
    raw_files = {}
    for row in rows:
        c.exact(row, {"basename", "bytes", "sha256", "raw_base64"}, "CORE_PRIOR_FILE_FIELDS")
        suffix = row["basename"][len(fixed['session']) + 2:]
        size, digest = fixed['pins'][suffix]
        require(type(row["bytes"]) is int and (size is None or row["bytes"] == size)
                and 0 <= row['bytes'] <= ROLE_LIMITS[suffix] and row["sha256"] == digest
                and type(row["raw_base64"]) is str and len(row["raw_base64"]) <= 22000, "PIN")
        try:
            raw = base64.b64decode(row["raw_base64"], validate=True)
        except (ValueError, UnicodeError) as error:
            raise c.ContractError("CORE_PRIOR_BASE64") from error
        require(base64.b64encode(raw).decode("ascii") == row["raw_base64"]
                and len(raw) == row['bytes'] and c.sha256(raw) == digest, "RAW")
        raw_files[suffix] = raw
    require(sum(map(len, raw_files.values())) == fixed['total'], "TOTAL")
    return _records(raw_files, index=index)


def build_all(raw_files):
    c.exact(raw_files, {basename(suffix, index) for index in (0, 1)
                       for suffix in profile(index)['pins']}, 'CORE_PRIOR_ALL_FILES')
    return [build({basename(suffix, index): raw_files[basename(suffix, index)]
                   for suffix in profile(index)['pins']}, index=index) for index in (0, 1)]


def validate_all(values):
    require(type(values) is list and len(values) == 2, 'PAIR')
    return [validate(value, index=index) for index, value in enumerate(values)]


def _records(raw_files, *, index):
    fixed = profile(index)
    name = lambda suffix: basename(suffix, index)
    marker = c.document(raw_files["carrier-consumed.json"], limit=16384, newline=True)
    capture = c.document(raw_files["capture-manifest.json"], limit=262144, newline=True)
    receipt = c.document(raw_files["acceptance-receipt.json"], limit=65536, newline=True)
    c.validate_record(marker, c.CONSUMPTION_SCHEMA)
    c.validate_record(capture, "local-hand-q2-core-capture-manifest/v1")
    c.validate_record(receipt, "local-hand-q2-core-local-acceptance-receipt/v1")
    require(all(record["session_id"] == fixed['session'] for record in (marker, capture, receipt)), "SESSION")
    require(marker["scope"] == receipt["scope"] == c.SCOPE and marker["implementation"] == fixed['implementation']
            and marker["baseline"] == c.BASELINE and marker["owner_decision"] == c.OWNER_DECISION
            and marker["closure"] == c.CLOSURE and marker["candidate"] == c.CANDIDATE
            and marker["state"] == "CONSUMPTION_RECORD_COMPLETE", "MARKER")
    c.validate_amendment(marker["amendment"], implementation=fixed['implementation'])
    c.validate_local_writer(marker["writer"])
    c.exact(marker["package"], {"basename", "bytes", "sha256", "manifest_sha256"}, "CORE_PRIOR_PACKAGE")
    require(marker["package"]["sha256"] == fixed['package_sha']
            and marker["package"]["manifest_sha256"] == fixed['manifest_sha']
            and marker["package"]["basename"] == fixed['session'] + '.lhfp'
            and marker["package"]["bytes"] == fixed['package_bytes'], "PACKAGE")
    if index == 1:
        require(marker['approved_inputs_sha256'] ==
            '5bcbf535f6c8d0d2c974756af6815ba95a03da7fadc31c97a0622cdeeaf4846e'
            and raw_files['stderr'] == b'CORE_ADMIT_SUDO_OUTPUT\n', 'SECOND_FAILURE')
    c.validate_package_basename(marker["package"]["basename"])
    for key in ("approved_inputs_sha256", "local_management_binding_sha256", "carrier_argv_sha256"):
        c.digest(marker[key])
    for clock in ("boottime", "monotonic"):
        origin = c.integer(marker["host_" + clock + "_origin_ns"], 1)
        require(marker["host_" + clock + "_deadline_ns"] == origin + 900_000_000_000, "CLOCK")
    raw = raw_files["stdout"]
    require(raw.startswith(c.HELLO_MAGIC) and len(raw) >= 16
            and struct.unpack(">Q", raw[8:16])[0] == len(raw) - 16, "HELLO_FRAME")
    hello = c.document(raw[16:], limit=4096, newline=True)
    unit = hello["carrier_unit"]
    require(unit["name"] == fixed['unit'] and unit["control_group"].endswith("/" + fixed['unit']), "HELLO_UNIT")
    c.absolute_path(unit["control_group"])
    # Both original D HELLO grammars have these unchanged limits. Bind each
    # original unit and source pins; never replace the historical identity.
    c._validate_hello_identity(hello, carrier_unit=fixed['unit'],
        loader_sha256=LOADER_SHA, bootstrap_sha256=fixed['bootstrap_sha'])
    marker_sha = c.sha256(raw_files["carrier-consumed.json"])
    require(receipt["consumption"] == dict(object_created=True, record_complete=True,
        basename=name("carrier-consumed.json"), bytes=len(raw_files["carrier-consumed.json"]),
        sha256=marker_sha), "CONSUMPTION")
    require(capture["consumption_sha256"] == marker_sha, "CAPTURE_MARKER")
    require(receipt["transport"] == dict(execve_succeeded=True, hello_valid=True, bind_written=fixed['sent'],
        package_written=fixed['sent'], stdin_bytes_written=18150763 if fixed['sent'] else 0,
        stdin_eof=fixed['sent']), "TRANSPORT")
    require(receipt["wait"] == dict(status=fixed['status'], stdout_eof=fixed['sent'],
        stderr_eof=fixed['sent'], host_deadline_met=fixed['sent'])
            and capture["wait"] == dict(status=fixed['status'], host_deadline_met=fixed['sent']), "WAIT")
    require(receipt["state"] == "STOP_AND_RETAIN"
            and receipt["real_task_execution"] == receipt["result_evidence_collection"]
            == dict(status="UNKNOWN", evidence_sha256=None), "TRUTH")
    require(receipt["remote_result"] == dict(present=False, sha256=None, frame_sha256=None)
            and capture["output_package"] == dict(present=False, frame_bytes=0,
                manifest_sha256=None, members_sha256=None, valid=False), "OUTPUT")
    for role in ("stdout", "stderr"):
        require(capture[role] == dict(basename=name(role), bytes=len(raw_files[role]),
            sha256=c.sha256(raw_files[role]), eof=fixed['sent']), "STREAM")
    expected_names = sorted(name(role) for role in ("carrier-consumed.json", "stdout", "stderr"))
    require(type(capture["files"]) is list and len(capture["files"]) == 3
            and [row["basename"] for row in capture["files"]] == expected_names, "CAPTURE_FILES")
    identities = set()
    for row in capture["files"]:
        c.exact(row, {"basename", "bytes", "allocated_bytes", "sha256", "dev", "ino", "mode", "nlink"})
        source = raw_files[row["basename"][len(fixed['session']) + 2:]]
        require(row["bytes"] == len(source) and row["sha256"] == c.sha256(source)
                and row["mode"] == 0o600 and row["nlink"] == 1, "CAPTURE_FILE")
        for key in ("dev", "allocated_bytes"):
            c.integer(row[key])
        c.integer(row["ino"], 1)
        identities.add((row["dev"], row["ino"]))
    require(len(identities) == 3 and capture["inodes"] == 3
            and capture["logical_bytes"] == sum(row["bytes"] for row in capture["files"])
            and capture["allocated_bytes"] == sum(row["allocated_bytes"] for row in capture["files"])
            and capture["fsync_complete"] is capture["reread_equal"] is True, "CAPTURE_TOTAL")
    require(receipt["capture"] == dict(bytes=capture["allocated_bytes"], inodes=3,
        manifest_sha256=c.sha256(raw_files["capture-manifest.json"]), fsync_complete=True, reread_equal=True),
        "CAPTURE_RECEIPT")
    missing = {'CORE_OUTPUT_MISSING'} if fixed['sent'] else {'CORE_OUTPUT_MISSING', 'CORE_TRANSPORT_FAILED'}
    require(receipt["missing"] == capture["missing"] and len(receipt["missing"]) == len(missing)
            and {row["code"] for row in receipt["missing"]} == missing,
            "MISSING")
    for row in receipt["missing"]:
        c.exact(row, {"code", "role", "detail_sha256"})
        c.digest(row["detail_sha256"])
    return hello


def commitment(prior, *, index=0):
    validate(prior, index=index)
    return dict(scope=c.SCOPE, session_id=profile(index)['session'], source_attempt_sha256=c.sha256(c.canonical(prior)),
                logical_bytes=289406976, logical_inodes=16512, cpu_seconds=2090,
                host_capture_bytes=67108864, host_capture_inodes=16, released_or_refunded=False)


def _capacity_rows(prior):
    validate_all(prior)
    rows = [commitment(value, index=index) for index, value in enumerate(prior)]
    return [dict(session_id=row['session_id'], bytes=row['host_capture_bytes'],
                 inodes=row['host_capture_inodes']) for row in rows] + [
        dict(session_id=c.SESSION_ID, bytes=c.LIMITS['host_capture_bytes'],
             inodes=c.LIMITS['host_capture_inodes'])]


def _capacity_record(binding, prior, implementation, origins, observation, capacity):
    return dict(schema='local-hand-q2-core-host-capacity-condition/v2',
        scope=c.POST_SUDO_SCOPE, session_id=c.SESSION_ID,
        implementation=copy.deepcopy(implementation),
        local_management_binding_sha256=c.sha256(c.canonical(binding, newline=True)),
        prior_attempts_sha256=c.sha256(c.canonical(prior)), origins=dict(origins),
        observation=observation, dev=binding['anchor']['dev'],
        known_commitments=_capacity_rows(prior), capacity=capacity,
        earlier_host_obligations=dict(coverage='UNKNOWN', bytes=None, inodes=None, shared_pool='UNKNOWN'),
        complete_host_admission_proven=False, exclusive_reservation_proven=False,
        released_bytes=0, released_inodes=0)


def validate_capacity_condition(value, *, binding, prior, implementation, origins):
    """Validate the original live record, never resample or infer a new success."""
    c.exact(implementation, {'commit', 'tree'}, 'CORE_HOST_CAPACITY_IMPLEMENTATION')
    for identity in implementation.values(): c.commit(identity)
    c.exact(value, {'schema', 'scope', 'session_id', 'implementation',
        'local_management_binding_sha256', 'prior_attempts_sha256', 'origins', 'observation',
        'dev', 'known_commitments', 'capacity', 'earlier_host_obligations',
        'complete_host_admission_proven', 'exclusive_reservation_proven',
        'released_bytes', 'released_inodes'}, 'CORE_HOST_CAPACITY_FIELDS')
    c.exact(origins, {'host_' + clock + '_' + point + '_ns'
        for clock in ('boottime', 'monotonic') for point in ('origin', 'deadline')})
    c.exact(value['observation'], {'before', 'after'}, 'CORE_HOST_CAPACITY_CLOCK')
    for point in value['observation'].values():
        c.exact(point, {'boottime_ns', 'monotonic_ns'}, 'CORE_HOST_CAPACITY_CLOCK')
        for number in point.values(): c.integer(number, code='CORE_HOST_CAPACITY_CLOCK')
    for clock in ('boottime', 'monotonic'):
        origin = c.integer(origins['host_' + clock + '_origin_ns'])
        end = c.integer(origins['host_' + clock + '_deadline_ns'])
        require(end == origin + 900_000_000_000
                and origin <= value['observation']['before'][clock + '_ns']
                <= value['observation']['after'][clock + '_ns'] < end, 'HOST_CAPACITY_CLOCK')
    capacity = value['capacity']
    c.exact(capacity, {'frsize', 'blocks_available', 'bytes_available', 'inodes_available',
                      'required_bytes', 'required_inodes'}, 'CORE_HOST_CAPACITY_FIELDS')
    require(all(type(number) is int and number >= 0 for number in capacity.values())
            and capacity['frsize'] > 0, 'HOST_CAPACITY_UNKNOWN')
    rows = _capacity_rows(prior)
    require(capacity['required_bytes'] == sum(row['bytes'] for row in rows) == 201326592
            and capacity['required_inodes'] == sum(row['inodes'] for row in rows) == 48
            and capacity['bytes_available'] == capacity['frsize'] * capacity['blocks_available'],
            'HOST_CAPACITY_ARITHMETIC')
    require(capacity['bytes_available'] >= capacity['required_bytes']
            and capacity['inodes_available'] >= capacity['required_inodes'], 'HOST_CAPACITY_FLOOR')
    expected = _capacity_record(binding, prior, implementation, origins, value['observation'], capacity)
    # Canonical equality also rejects bool-as-int, null-as-zero and extra keys.
    require(c.canonical(value) == c.canonical(expected), 'HOST_CAPACITY_BINDING')
    return value


def observe_capture_condition(directory_fd, *, binding, prior, implementation, deadline, writer_observer):
    """One fstatvfs in the original caller, bracketed by full anchor/writer checks."""
    anchor = binding['anchor']
    c.exact(anchor, {'path', 'dev', 'ino', 'mode', 'uid', 'gid', 'nlink'})
    require(anchor['mode'] == 0o700, 'HOST_CAPACITY_ANCHOR')
    c.validate_local_writer(binding['writer'])
    require(all(value == anchor[key] for key in ('uid', 'gid')
                for value in binding['writer'][key].values()), 'HOST_CAPACITY_WRITER')
    call = deadline.call
    def context():
        def identity(info):
            return info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink
        first = call(os.fstat, directory_fd)
        named = call(os.stat, anchor['path'], follow_symlinks=False)
        last = call(os.fstat, directory_fd)
        expected = (anchor['dev'], anchor['ino'], stat.S_IFDIR | 0o700,
                    anchor['uid'], anchor['gid'], anchor['nlink'])
        require(identity(first) == identity(named) == identity(last) == expected, 'HOST_CAPACITY_ANCHOR')
        require(c.canonical(writer_observer(call)) == c.canonical(binding['writer']),
                'HOST_CAPACITY_WRITER')
        deadline.check()
    # Validate the fixed prior relation before starting any resource observation.
    rows = _capacity_rows(prior)
    context()
    before = deadline.check()
    usage = call(os.fstatvfs, directory_fd)
    after = deadline.check()
    context()
    frsize, blocks, inodes = (getattr(usage, key, None) for key in ('f_frsize', 'f_bavail', 'f_favail'))
    require(all(type(v) is int and v >= 0 for v in (frsize, blocks, inodes))
            and frsize > 0, 'HOST_CAPACITY_UNKNOWN')
    value = _capacity_record(binding, prior, implementation, deadline.origins,
        dict(before=dict(zip(('boottime_ns', 'monotonic_ns'), before)),
             after=dict(zip(('boottime_ns', 'monotonic_ns'), after))),
        dict(frsize=frsize, blocks_available=blocks, bytes_available=blocks * frsize,
             inodes_available=inodes, required_bytes=sum(row['bytes'] for row in rows),
             required_inodes=sum(row['inodes'] for row in rows)))
    validate_capacity_condition(value, binding=binding, prior=prior,
                                implementation=implementation, origins=deadline.origins)
    deadline.check()
    return value

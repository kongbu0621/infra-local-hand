"""Fixed consumed F1 preimages for the separately approved next acceptance.

Historical UNKNOWN is retained. The fixed current host capacity condition is
not a complete bill or a reservation. No quiescence or generic prior inputs.
"""
from __future__ import annotations

import base64
import copy
import re
import os
import posixpath
import stat
import struct
import json

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
THIRD_PINS = {
    "carrier-consumed.json": (3577, "3d38e232e66580d588f03cfd444e5d1729904af801dfeb83af51f87e721d6c20"),
    "stdout": (2852, "cde70ed0b21d2b6cc7c5d9a21652c68f7e0f3b171e7ee03627eb594b56204f3f"),
    "stderr": (24, "7c8bda65cecc5daeba8693865946e37aed794bdb930f1f71e0fe0ddb9c8684de"),
    "capture-manifest.json": (1503, "fd9e85a9b368cfaf58c3138b9860f3d4ba3c4370fa2319e8c992f04d64f23918"),
    "acceptance-receipt.json": (1117, "1274a7522d4f7151f894fbf530618cba12ba8134b1dd162731cb32c72f43929b"),
}
THIRD_TOTAL_BYTES = 9073
ROLE_LIMITS = {"carrier-consumed.json": 16384, "stdout": 4112, "stderr": 4194304,
               "capture-manifest.json": 262144, "acceptance-receipt.json": 65536}


FOURTH_TOTAL_BYTES = 9071
FOURTH_PINS = {'carrier-consumed.json': (3577, 'ac0314d584ce7dfdbe5892f779cfbc01a702459fb31ab539b2752f70c07f7deb'), 'stdout': (2852, 'ff0f1b11037028b766c6bf8d4b6623f84241541f9e9240bf1f90efe3c9d6f7e9'), 'stderr': (22, 'e1c59576e732df777e6542b880a21994430f06f72ca54d9a0319507d1126aa75'), 'capture-manifest.json': (1503, '44398704da222ff3d5200b53dfbc732c1ad23fa4b35bd4d75e4671c5b8d5b406'), 'acceptance-receipt.json': (1117, '184439515c226a8b108b270522800174a7adb476191a606a66b7d451c25e601c')}


def profile(index):
    require(type(index) is int and index in (0, 1, 2, 3), "PROFILE")
    if index == 0:
        return dict(session=SESSION, unit=UNIT, implementation=IMPLEMENTATION, pins=PINS,
            total=TOTAL_BYTES, package_sha=PACKAGE_SHA, manifest_sha=MANIFEST_SHA,
            package_bytes=18111397, bootstrap_sha=BOOTSTRAP_SHA, sent=False, status=255)
    if index == 3:
        return dict(session='lhqcore-20261005c', unit='lhqcore20261005c-carrier.service',
            implementation=dict(commit='657b1bcd749cb4281b0193b2bc9430b0662faf98',
                tree='4bb00b2e9ccbec3c43160159811e51eec76702cd'), pins=FOURTH_PINS,
            total=FOURTH_TOTAL_BYTES, package_bytes=18193664, sent=True, status=3,
            package_sha='0acdfcaad942191b85f9bf24832c08d2c344fee3fe392a41d376a84ec2271184',
            manifest_sha='28cc514a5c622720744dc7633520c2ee326b7a5681276bfbaebb975f882264db',
            bootstrap_sha='7e2d08800951528c81f9078eb772cc4937dc76a3fd1ed7a1ccadde2a12a23cf5')
    if index == 2:
        return dict(session="lhqcore-20261005b", unit="lhqcore20261005b-carrier.service",
            implementation=dict(commit="8704a24b6c3c79ce4a36028ae2182dec2a35843e",
                tree="89a5f221883c11838a10a452be2dcb756abb5a17"), pins=THIRD_PINS, total=THIRD_TOTAL_BYTES,
            package_sha="dc30af5fed782615501df61c601461ca3d214d379e8805d86e4f0dc458b6a498",
            manifest_sha="bb7c854f7279a352064de3f9bb260f92d7a0c8456a636cda747b363ac9481d2a",
            package_bytes=18173610,
            bootstrap_sha="4a58b342ea4fabb95903e9362cc9b0007c6aafda5a5ece3203692c5033982ce3",
            sent=True, status=3)
    return dict(session=SECOND_SESSION, unit="lhqcore20261005a-carrier.service",
        implementation=SECOND_IMPLEMENTATION, pins=SECOND_PINS, total=SECOND_TOTAL_BYTES,
        package_sha="da72c862bbcbe4ae43df681f91576d38586eec1eeb550b46e378d3398e07008b",
        manifest_sha="09e7b8ef0df3b3103f0ba87113dfcf2d3470b861ad14f84c83c144a0f6b3c6fb",
        package_bytes=18149835,
        bootstrap_sha="c9f6e89f874d83856552e65810b04a5d88e7ab0687395dfa5dfd80d7affdee83",
        sent=True, status=3)


def _read_pins(directory_fd, anchor, call, pins, name, limits, seen, *, absent=None):
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
    before_parent = parent()
    files = {}
    for suffix, (size, digest) in pins.items():
        opened = []
        try:
            fd = call(os.open, name(suffix), os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
                      | os.O_NOATIME | os.O_NONBLOCK, dir_fd=directory_fd, returned=opened.append)
            before = call(os.fstat, fd)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and stat.S_IMODE(before.st_mode) == 0o600 and before.st_uid == anchor["uid"]
                and before.st_gid == anchor["gid"] and before.st_dev == anchor['dev']
                and (size is None or before.st_size == size) and 0 <= before.st_size <= limits[suffix]
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
                    and len(raw) == size and (digest is None or c.sha256(raw) == digest), "READ_PIN")
            files[name(suffix)] = raw
        finally:
            for held in opened:
                os.close(held)
    if absent is not None:
        try:
            call(os.stat, absent, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise c.ContractError("CORE_PRIOR_UNEXPECTED_RESULT")
    require(parent() == before_parent, "PARENT_DRIFT")
    return files


def read_files(directory_fd, anchor, call, *, index=0, _seen=None):
    fixed = profile(index)
    seen = set() if _seen is None else _seen
    files = _read_pins(directory_fd, anchor, call, fixed['pins'],
                      lambda suffix: basename(suffix, index), ROLE_LIMITS, seen,
                      absent=basename('remote-result.json', index))
    build(files, index=index)
    return files


def read_all_files(directory_fd, anchor, call, *, _seen=None):
    seen = set() if _seen is None else _seen
    files = {}
    for index in (0, 1, 2, 3):
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
    c.exact(raw_files, {basename(suffix, index) for index in (0, 1, 2, 3)
                       for suffix in profile(index)['pins']}, 'CORE_PRIOR_ALL_FILES')
    return [build({basename(suffix, index): raw_files[basename(suffix, index)]
                   for suffix in profile(index)['pins']}, index=index) for index in (0, 1, 2, 3)]


def validate_all(values):
    require(type(values) is list and len(values) == 4, 'FOUR')
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
    if index == 3:
        require(marker['approved_inputs_sha256'] ==
            '169c6e8cef5a3d6ee94d7cf433996016710b5e5613a7158e57875baad09ee793'
            and raw_files['stderr'] == b'CORE_CAP_INSUFFICIENT\n', 'FOURTH_FAILURE')
    if index == 2:
        require(marker['approved_inputs_sha256'] ==
            '5d227ecbef0eb0b72a3c5ddee998c1505b88ddf70d3c3c506e262144c25198da'
            and raw_files['stderr'] == b'CORE_ADMIT_SSHD_GRAMMAR\n', 'THIRD_FAILURE')
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
        package_written=fixed['sent'], stdin_bytes_written=(0, 18150763, 18174538, 18194592)[index],
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


DIAGNOSTIC_SESSION = 'lhqsshd-20261005a'
DIAGNOSTIC_PINS = {
    'consumed.json': (495, '88f6c88c96d90effc2f06d15693bc04dd23353ef65825331275d0746e87e50a7'),
    'stdout': (7028, '7c22202275cc851bac0707c7a630a4b302d7d347de087b2705af2289ab4a5dcc'),
    'stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'receipt.json': (1259, '1cc9fcdbf3179652d00e5c41cc37070e017f107f2ed96919a5ab0fbd64e5179c'),
}


def diagnostic_retention():
    """Fixed metadata only, not a claim to have observed the private originals."""
    return dict(schema='local-hand-q2-core-diagnostic-retention/v1',
        scope='LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1', session_id=DIAGNOSTIC_SESSION,
        implementation=dict(commit='bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891',
            tree='460acde6c11a7b7555bf9992eb65bff16e822cad'),
        files=sorted([dict(basename='.' + DIAGNOSTIC_SESSION + '.' + suffix, bytes=size, sha256=digest)
            for suffix, (size, digest) in DIAGNOSTIC_PINS.items()], key=lambda row: row['basename']),
        reader_state='READER_REPORTED_COMPLETE', remote_supervision_proven=False,
        remote_exit='UNKNOWN', management_usage='UNKNOWN', reader_cpu_seconds=5,
        reader_address_space_bytes=134217728, host_capture_bytes=4194304,
        host_capture_inodes=8, released_or_refunded=False)


def validate_diagnostic(value):
    require(c.canonical(value) == c.canonical(diagnostic_retention()), 'DIAGNOSTIC_RETENTION')
    return value


def build_diagnostic(raw_files):
    """Bind only original capture records/streams; never parse the snapshot."""
    expected = diagnostic_retention()
    c.exact(raw_files, {row['basename'] for row in expected['files']}, 'CORE_PRIOR_DIAGNOSTIC_FILES')
    for row in expected['files']:
        raw = raw_files[row['basename']]
        require(type(raw) is bytes and len(raw) == row['bytes'] and c.sha256(raw) == row['sha256'],
                'DIAGNOSTIC_PIN')
    prefix = '.' + DIAGNOSTIC_SESSION + '.'
    marker = c.document(raw_files[prefix + 'consumed.json'], limit=4096, newline=True)
    receipt = c.document(raw_files[prefix + 'receipt.json'], limit=65536, newline=True)
    keys = {'schema', 'session', 'R', 'A', 'C', 'D', 'reader_sha256',
            'argv_environment_sha256', 'clock_origins_ns'}
    c.exact(marker, keys, 'CORE_PRIOR_DIAGNOSTIC_MARKER')
    c.exact(receipt, keys | {'state', 'reason', 'requests_attempted', 'marker_creation_attempted',
        'marker_created', 'exit', 'stdout_eof', 'stderr_eof', 'snapshot_complete',
        'remote_supervision_proven', 'remote_exit', 'complete_host_admission_proven',
        'exclusive_reservation_proven', 'old_commitments_refunded', 'files',
        'observed_allocated_peak_before_receipt_bytes', 'host_deadline_met'}, 'CORE_PRIOR_DIAGNOSTIC_RECEIPT')
    require(marker == {key: receipt[key] for key in keys}
        and marker['schema'] == 'lhq-sshd-source-capture-receipt-v1'
        and marker['session'] == DIAGNOSTIC_SESSION and marker['R'] == c.RULE['commit']
        and marker['A'] == 'f2eb31deb3c52d69ccd2079fb7d88608d1a25a62'
        and marker['C'] == 'b346cbd44dd4f376d4386f72d7029b1311788229'
        and marker['D'] == expected['implementation']['commit']
        and marker['reader_sha256'] == '68c594cedbea15768789690b4afd0797bfff1057760a522f931e16a4a7ca3108'
        and marker['argv_environment_sha256'] == '1192ec89516a1297bf6c85dd7911cc01db61032bde335db2f631f86845845eca',
        'DIAGNOSTIC_IDENTITY')
    require(type(marker['clock_origins_ns']) is list and len(marker['clock_origins_ns']) == 2,
            'DIAGNOSTIC_CLOCK')
    for origin in marker['clock_origins_ns']: c.integer(origin, 1)
    c.integer(receipt['observed_allocated_peak_before_receipt_bytes'], 0, 4194304)
    require(receipt['state'] == 'COMPLETE' and receipt['reason'] == 'SNAPSHOT_VERIFIED'
        and type(receipt['exit']) is int and receipt['exit'] == 0
        and type(receipt['requests_attempted']) is int and receipt['requests_attempted'] == 1
        and all(receipt[key] is True for key in ('marker_creation_attempted', 'marker_created',
            'stdout_eof', 'stderr_eof', 'host_deadline_met', 'snapshot_complete'))
        and receipt['remote_exit'] == 'READER_REPORTED_COMPLETE'
        and all(receipt[key] is False for key in ('remote_supervision_proven',
            'complete_host_admission_proven', 'exclusive_reservation_proven', 'old_commitments_refunded')),
        'DIAGNOSTIC_RECEIPT')
    require(receipt['files'] == {role: dict(bytes=len(raw_files[prefix + suffix]),
        sha256=c.sha256(raw_files[prefix + suffix])) for role, suffix in
        (('marker', 'consumed.json'), ('stdout', 'stdout'), ('stderr', 'stderr'))}, 'DIAGNOSTIC_STREAMS')
    return expected


def read_diagnostic_files(directory_fd, anchor, call, *, _seen):
    files = _read_pins(directory_fd, anchor, call, DIAGNOSTIC_PINS,
        lambda suffix: '.' + DIAGNOSTIC_SESSION + '.' + suffix,
        {suffix: size for suffix, (size, _) in DIAGNOSTIC_PINS.items()}, _seen)
    build_diagnostic(files)
    return files


def _capacity_rows(prior, diagnostic):
    validate_all(prior)
    validate_diagnostic(diagnostic)
    return [dict(session_id='lhqjgrow-20261006a',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261007a',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261007b',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261008a',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261008b',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261008c',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261008d',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261008e',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261008f',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261009a',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261009b',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261009c',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261010a',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261010b',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261010c',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqjgrow-20261010d',bytes=1296*1048576,inodes=370),
        dict(session_id='lhqguest-20261010a',bytes=1048576,inodes=32),
        dict(session_id='lhqguest-20261010b',bytes=1048576,inodes=32),
        dict(session_id='lhqsource-20261010a',bytes=1048576,inodes=32),
        *[dict(session_id=session,bytes=1048576,inodes=32) for session in
          ('lhqpaths-20261010a','lhqpaths-20261010b','lhqpaths-source-20261010a',
           'lhqpaths-source-20261010b','lhqsource-20261010d','lhqarchive-20261010d')],
        dict(session_id=c.SESSION_ID,bytes=c.LIMITS['host_capture_bytes'],
             inodes=c.LIMITS['host_capture_inodes'])]


def _capacity_record(binding, prior, diagnostic, journal, implementation, origins, observation, capacity, device_capacity):
    return dict(schema='local-hand-q2-core-host-capacity-condition/v20',
        scope=c.PERSISTENT_PATH_SCOPE, session_id=c.SESSION_ID,
        implementation=copy.deepcopy(implementation),
        local_management_binding_sha256=c.sha256(c.canonical(binding, newline=True)),
        prior_attempts_sha256=c.sha256(c.canonical(prior)), origins=dict(origins),
        diagnostic_retention_sha256=c.sha256(c.canonical(diagnostic)),
        journal_transition_sha256=c.sha256(c.canonical(journal)),
        observation=observation, dev=binding['anchor']['dev'],
        known_commitments=_capacity_rows(prior, diagnostic), capacity=capacity,device_capacity=device_capacity,
        earlier_host_obligations=dict(coverage='UNKNOWN', bytes=None, inodes=None, shared_pool='UNKNOWN'),
        complete_host_admission_proven=False, exclusive_reservation_proven=False,
        released_bytes=0, released_inodes=0)


def validate_capacity_condition(value, *, binding, prior, diagnostic, journal, implementation, origins):
    """Validate the original live record, never resample or infer a new success."""
    c.exact(implementation, {'commit', 'tree'}, 'CORE_HOST_CAPACITY_IMPLEMENTATION')
    for identity in implementation.values(): c.commit(identity)
    c.exact(value, {'schema', 'scope', 'session_id', 'implementation',
        'local_management_binding_sha256', 'prior_attempts_sha256', 'diagnostic_retention_sha256', 'journal_transition_sha256', 'origins', 'observation',
        'dev', 'known_commitments', 'capacity', 'device_capacity', 'earlier_host_obligations',
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
    validate_journal_transition(journal,priors=prior,implementation=implementation)
    capacity = value['capacity']
    c.exact(capacity, {'frsize', 'blocks_available', 'bytes_available', 'inodes_available',
                      'required_bytes', 'required_inodes'}, 'CORE_HOST_CAPACITY_FIELDS')
    require(all(type(number) is int and number >= 0 for number in capacity.values())
            and capacity['frsize'] > 0, 'HOST_CAPACITY_UNKNOWN')
    rows = _capacity_rows(prior, diagnostic)
    require(capacity['required_bytes'] == sum(row['bytes'] for row in rows) == 21819817984
            and capacity['required_inodes'] == sum(row['inodes'] for row in rows) == 6224
            and capacity['bytes_available'] == capacity['frsize'] * capacity['blocks_available'],
            'HOST_CAPACITY_ARITHMETIC')
    require(capacity['bytes_available'] >= capacity['required_bytes']
            and capacity['inodes_available'] >= capacity['required_inodes'], 'HOST_CAPACITY_FLOOR')
    expected_devices=sorted({binding['anchor']['dev'],*(row[0] for row in journal['image_identities'].values())})
    devices=value['device_capacity']
    require(type(devices) is list and [row.get('dev') for row in devices]==expected_devices,'HOST_CAPACITY_DEVICES')
    for row in devices:
        c.exact(row,{'dev','capacity'},'CORE_HOST_CAPACITY_DEVICE_FIELDS');c.integer(row['dev'])
        usage=c.exact(row['capacity'],set(capacity),'CORE_HOST_CAPACITY_FIELDS')
        require(all(type(x) is int and x>=0 for x in usage.values()) and usage['frsize']>0
            and usage['bytes_available']==usage['frsize']*usage['blocks_available']
            and usage['required_bytes']==21819817984 and usage['required_inodes']==6224
            and usage['bytes_available']>=usage['required_bytes']
            and usage['inodes_available']>=usage['required_inodes'],'HOST_CAPACITY_DEVICE_FLOOR')
    require(next(row['capacity'] for row in devices if row['dev']==binding['anchor']['dev'])==capacity,
            'HOST_CAPACITY_DEVICE_BINDING')
    expected = _capacity_record(binding, prior, diagnostic, journal, implementation, origins, value['observation'], capacity, devices)
    # Canonical equality also rejects bool-as-int, null-as-zero and extra keys.
    require(c.canonical(value) == c.canonical(expected), 'HOST_CAPACITY_BINDING')
    return value


def observe_capture_condition(directory_fd, *, binding, prior, diagnostic, journal, journal_files, implementation, deadline, writer_observer):
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
    rows = _capacity_rows(prior, diagnostic)
    validate_journal_transition(journal,priors=prior,implementation=implementation)
    from . import q2_journal_growth as maintenance
    marker=c.document(journal_files['.'+JOURNAL_SESSION+'.consumed.json'],limit=65536,newline=True)
    require(c.sha256(maintenance.canonical(marker['manifest']))==journal['manifest_sha256'],
            'HOST_CAPACITY_JOURNAL_BINDING')
    context()
    before = deadline.check()
    images=maintenance.ImageSet(directory_fd,anchor['path'],marker['manifest']['restart_argv'],deadline.check,activation=journal.get('vm_activation'))
    try:
        require(c.canonical(images.image_keys())==c.canonical(journal['image_identities']),'HOST_CAPACITY_IMAGE_DRIFT')
        grouped={anchor['dev']:directory_fd}
        for role,fd in images.fds.items():grouped.setdefault(journal['image_identities'][role][0],fd)
        devices=[]
        for dev,fd in sorted(grouped.items()):
            usage=call(os.fstatvfs,fd)
            frsize,blocks,inodes=(getattr(usage,key,None) for key in ('f_frsize','f_bavail','f_favail'))
            require(all(type(v) is int and v>=0 for v in (frsize,blocks,inodes))
                and frsize>0,'HOST_CAPACITY_UNKNOWN')
            devices.append(dict(dev=dev,capacity=dict(frsize=frsize,blocks_available=blocks,
                bytes_available=blocks*frsize,inodes_available=inodes,
                required_bytes=sum(row['bytes'] for row in rows),required_inodes=sum(row['inodes'] for row in rows))))
        images.recheck()
        after=deadline.check();context()
    finally:images.close()
    capacity=next(row['capacity'] for row in devices if row['dev']==anchor['dev'])
    value=_capacity_record(binding,prior,diagnostic,journal,implementation,deadline.origins,
        dict(before=dict(zip(('boottime_ns','monotonic_ns'),before)),
            after=dict(zip(('boottime_ns','monotonic_ns'),after))),capacity,devices)
    validate_capacity_condition(value, binding=binding, prior=prior, diagnostic=diagnostic, journal=journal,
                                implementation=implementation, origins=deadline.origins)
    deadline.check()
    return value


# Fixed K2 originals; no capture or maintenance command is executed here.
# Public pins of the consumed 06a originals; no raw machine evidence is embedded.
PREVIOUS_JOURNAL_SESSION = 'lhqjgrow-20261006a'
PREVIOUS_JOURNAL_D = 'a743af326cdff6e4485b69332e2309130d82a915'
PREVIOUS_JOURNAL_PINS = {
    'consumed.json': (34007,'e5c7a9d540be9f1c7a7202039e43d7fc0d3ea359528582033d2fb1d9c5a12734'),
    'events.jsonl': (441,'02d8e0783337c774a44aeccda1f7788c10c5f9f424d479a01a14088d2bf013b2'),
    'pre.stdout': (0,'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'pre.stderr': (517,'4464dd988e5867af7e0f0c7bbd0b4c848391553c65095c5a57b5ff43958321af'),
    'receipt.json': (6577,'9d34abbf1917c5d352961fb8dface00d9b674549bf99f7b85335928d5e204573'),
}
PREVIOUS_JOURNAL_ABSENT = ('post.stdout','post.stderr','vm.pid','journal.backup.qcow2')


SECOND_JOURNAL_SESSION = 'lhqjgrow-20261007a'
SECOND_JOURNAL_D = 'a20bf2a4575df7578341af744630ceaac131a6a7'
# Explicit Owner-approved minimal index; raw originals remain private.
SECOND_JOURNAL_PINS = {'consumed.json': (37083, '8809770315137a0d5376422e2ac8098a9fb6e71cbc06943848a550cddfbbf9ea'),
 'events.jsonl': (441, '5a5e0ce88ac9b4ec72630edb7d96616f2c16c44745071c4846e0fc3d051a1d00'),
 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
 'pre.stderr': (532, '56af6ce2bb3a58df04b6b1bf67d10faff7585878eac6f436769f9e790df0205d'),
 'receipt.json': (7584, 'ff646655c3d0c87f6a112397c3c2d9e82bce8757e6e2581f7f2456d00519412d')}


THIRD_JOURNAL_SESSION = 'lhqjgrow-20261007b'
THIRD_JOURNAL_D = 'b2bc054d0c06526b454cd320f167cc1a40242ab8'
# Owner-approved five-original index; retained bodies and diagnostics stay private.
THIRD_JOURNAL_PINS = {
    'consumed.json': (40860, 'ebf9da98c36649fc957aadff8f06fb89362c694110976212ea39d5b9e4d4e888'),
    'events.jsonl': (441, 'd33e59a2b499982a0fa3c2d84862d9cbba3aa40127c5c669f7fe2b0f180b6555'),
    'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'pre.stderr': (1250, '060b70afbdc653ebe325c0ffab27ae0bad51367187c08d01a431a7ea08b935cc'),
    'receipt.json': (8808, '9c3af36a2d91e0f46bcace05999b93ddd64108f9e9d7721d08c4df0528168ce6'),
}


FOURTH_JOURNAL_SESSION = 'lhqjgrow-20261008a'
FOURTH_JOURNAL_D = 'd5b34316bc93b37442eb5db64ba265b965e68379'
# Owner-approved minimal index; retained originals and diagnostics stay private.
FOURTH_JOURNAL_PINS = {
    'consumed.json': (44154, 'b4b413abef4ff36527decd1731cfe92435df1a6b9c58345c64463cd46b06b557'),
    'events.jsonl': (441, '428dc35e25d521242cdfc4485b8b14687a1d7174eedc8f858158f7d9f53d0969'),
    'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'pre.stderr': (685, '08b9f7866e00edbe02a64bfb05247bdd0cb1ac48064e73c1b6e8485b4ccc8dfa'),
    'receipt.json': (9872, '85e8edadd61f3d66eb6cc6a1992a0f9d691e1c477270cabe44ce18fb75540b8f'),
}


FIFTH_JOURNAL_SESSION = 'lhqjgrow-20261008b'
FIFTH_JOURNAL_D = 'dc538b9034f00c635344defae57b7054319c2184'
# Owner-approved minimal index; raw evidence remains private.
FIFTH_JOURNAL_PINS = {
    'consumed.json': (47434, '711fc817db3a244fa7b9f820712c49691f6cbea1ef148af92201ebddeaf2b683'),
    'events.jsonl': (441, '1d3c5be159e507453897371135c3d7fd880af6bcf7bb1b82cf720e0591b51bca'),
    'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'pre.stderr': (686, '93b3c81cf4a7b9203fc6bd1e344e8ba78015f1eac11927a38be457de2fe3af84'),
    'receipt.json': (10928, '43bef2765b0b7cbe65262d794ac1119339238115b85bfd2c51214921ffd5d04c'),
}


SIXTH_JOURNAL_SESSION = 'lhqjgrow-20261008c'
SIXTH_JOURNAL_D = '064bdd614db4224c8c7e9d3b011af90622c11066'
# Owner-approved minimal index; raw evidence remains private.
SIXTH_JOURNAL_PINS = {
    'consumed.json': (50720, 'c3406555625f1d67cfd62d1208a29c58cbae374dfe4babd29d95b92734b186fa'),
    'events.jsonl': (441, '03829472e564be760a89e41954c1a5de892eb64324b5fb8540ef35878b26680f'),
    'pre.stderr': (605, '1f7bf58d562f5789c3b176e5a6661d3fdd0d1a105c10beed7986369dcadc8b4a'),
    'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'receipt.json': (11988, 'a0b67b05d79db01723c6340cadb7d03fa366fbf8571579e4437f37827e721274'),
}


SEVENTH_JOURNAL_SESSION = 'lhqjgrow-20261008d'
SEVENTH_JOURNAL_D = '341796561a6aaa6f95779f438b57d958a1fd5954'
# Owner-approved 08d minimal index; original capture remains private.
SEVENTH_JOURNAL_PINS = {'consumed.json': (54783, '83a2d8362eb429c0fb1517002196d4e0740cd2ade3dd10b3f71288626de568e7'), 'events.jsonl': (441, '2569845129129856b35a1c22d2d0cb1a8fa1e7cd511fc3abc975fb0a5153191b'), 'pre.stderr': (824, '274ec520be611f366fa0352b751867e9a56a9639b53b694e4585b0ba3d935207'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (13242, 'f646741ff3fff6b237637266daef33f8c21e7c98c524b356aa3f6011d32a0cd1')}


EIGHTH_JOURNAL_SESSION = 'lhqjgrow-20261008e'
EIGHTH_JOURNAL_D = 'fa30146b0a49744b25df0f23969bf96b17eaacad'
# Owner-approved 08e minimal index; raw evidence remains private.
EIGHTH_JOURNAL_PINS = {'consumed.json': (61113, '0b09dc689f602ad36e8be8e3d15df559519b898d9b4419a08eb79194496dcdcb'), 'events.jsonl': (441, 'edca318f7d72d7220220607cd967f25df018d6d5cc6040ad087f035c674ffbf0'), 'pre.stderr': (1332, '2432edcb0e41893a1859538d67124dd266381f0920cb5c63c9d20edf6650fd76'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (14315, 'ad85fadb333c7281e4ab967a5a699537dbee276937daaf5f6739fea972093a7c')}


NINTH_JOURNAL_SESSION = 'lhqjgrow-20261008f'
NINTH_JOURNAL_D = 'db6e7165322da3072ca1fd88a36401e18ebd4a86'
# Owner-approved old08f basename/bytes/SHA-256 index; raw returns remain private.
NINTH_JOURNAL_PINS = {'consumed.json': (64566, '75e0e745f13745d3efd45d52495d13bd8ea5a3ff626316fbf5168a5a493e30af'), 'events.jsonl': (441, '264edd9660fd59ba3b6884ae4df0cdd8846a16a4cc97665a835f5fa691d91749'), 'pre.stderr': (817, 'df134297b8556f6d3939fe17424807a44e275c57470c84d81577d1da30d307b8'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (15447, 'de08569fc6fadccafcf434d842e43ad713fbb4b6fdb7c45d03cf95df5fa3ad4e')}


TENTH_JOURNAL_SESSION = 'lhqjgrow-20261009a'
TENTH_JOURNAL_D = '54d32df2f82fe863e1535ddb8134617c2654e33d'
# Owner-approved old09a minimal index; raw returns remain private.
TENTH_JOURNAL_PINS = {'consumed.json': (59556, '777715c3cbf6d9c9ecef43a63ae1fe2dee6fa4c48170f0114aa883383f55c87d'), 'events.jsonl': (441, '687cce89ef1ef88e44d482655d61e2a8e48d84bb4e2da36d154ccf98accfec60'), 'pre.stderr': (922, '6c40a4e9d0882c80ffb89829be5c52cf9bc861a698d5bd498c1efa434539a88e'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (16482, '1737c6c75c8dc97b80734e94b4d161f33b9893d7ad8e63658acc9514e190d096')}


ELEVENTH_JOURNAL_SESSION = 'lhqjgrow-20261009b'
ELEVENTH_JOURNAL_D = '547bbb05816e17525470b1a3c136b328ff96adc1'
# Owner-approved old09b minimal index; no remote completion is inferred.
ELEVENTH_JOURNAL_PINS = {'consumed.json': (63853, '30aa04638c3682a3317a5e83ba5769a167e98ea0e32053b204812ae0a0c03f45'), 'events.jsonl': (441, '9852dffa8014fd2e1385f7aa1d46b6ec37849773830fa13b3d065af0372aa6fd'), 'pre.stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'pre.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'receipt.json': (17254, 'cd87d061060c3fdbaad785c46f598ec31f5f806f2b0f88a490e1bf4a7a1261e3')}


def previous_journal_profiles():
    return (
        dict(session=PREVIOUS_JOURNAL_SESSION, D=PREVIOUS_JOURNAL_D, pins=PREVIOUS_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.MINIMAL_BASELINE['commit'], C=c.MINIMAL_CLOSURE['commit']),
            version=2, stage='PRE_IDENTITY', reason='GROWTH_JOURNAL_SERIAL'),
        dict(session=SECOND_JOURNAL_SESSION, D=SECOND_JOURNAL_D, pins=SECOND_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.SERIAL_BASELINE['commit'], C=c.SERIAL_CLOSURE['commit']),
            version=3, stage='PRE_QUIESCENCE', reason='GROWTH_SYSTEMCTL_STDERR'),
        dict(session=THIRD_JOURNAL_SESSION, D=THIRD_JOURNAL_D, pins=THIRD_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.SYSTEMCTL_BASELINE['commit'], C=c.SYSTEMCTL_CLOSURE['commit']),
            version=4, stage='PRE_QUIESCENCE', reason='GROWTH_SYSTEMCTL_STDERR'),
        dict(session=FOURTH_JOURNAL_SESSION, D=FOURTH_JOURNAL_D, pins=FOURTH_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.TEMPLATE_BASELINE['commit'], C=c.TEMPLATE_CLOSURE['commit']),
            version=5, stage='PRE_QUIESCENCE', reason='GROWTH_SYSTEMCTL_NAMES'),
        dict(session=FIFTH_JOURNAL_SESSION, D=FIFTH_JOURNAL_D, pins=FIFTH_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.NAMES_BASELINE['commit'], C=c.NAMES_CLOSURE['commit']),
            version=6, stage='PRE_QUIESCENCE', reason='GROWTH_SYSTEMCTL_FORMAT'),
        dict(session=SIXTH_JOURNAL_SESSION, D=SIXTH_JOURNAL_D, pins=SIXTH_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.EXEC_BASELINE['commit'], C=c.EXEC_CLOSURE['commit']),
            version=7, stage='PRE_QUIESCENCE', reason='GROWTH_INDIRECT_STARTUP_UNVERIFIED'),
        dict(session=SEVENTH_JOURNAL_SESSION, D=SEVENTH_JOURNAL_D, pins=SEVENTH_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.GS_BASELINE['commit'], C=c.GS_CLOSURE['commit']),
            version=8, stage='PRE_QUIESCENCE', reason='GROWTH_UNDECLARED_BUSINESS_UNIT'),
        dict(session=EIGHTH_JOURNAL_SESSION, D=EIGHTH_JOURNAL_D, pins=EIGHTH_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.QI_BASELINE['commit'], C=c.QI_CLOSURE['commit']),
            version=9, stage='PRE_QUIESCENCE', reason='GROWTH_UNDECLARED_BUSINESS_UNIT'),
        dict(session=NINTH_JOURNAL_SESSION, D=NINTH_JOURNAL_D, pins=NINTH_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.DS_BASELINE['commit'], C=c.DS_CLOSURE['commit']),
            version=10, stage='PRE_QUIESCENCE', reason='GROWTH_BUSINESS_PROCESS'),
        dict(session=TENTH_JOURNAL_SESSION,D=TENTH_JOURNAL_D,pins=TENTH_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.VM_ADOPTION_BASELINE['commit'], C=c.VM_ADOPTION_CLOSURE['commit']),
            version=11,stage='PRE_QUIESCENCE',reason='GROWTH_GUEST_IO_OR_RUNTIME'),
        dict(session=ELEVENTH_JOURNAL_SESSION,D=ELEVENTH_JOURNAL_D,pins=ELEVENTH_JOURNAL_PINS,
            authority=dict(R=c.RULE['commit'], A=c.RUNTIME_BASELINE['commit'], C=c.RUNTIME_CLOSURE['commit']),version=12,stage='LOCAL_TRANSPORT_CONSTRUCTION',reason='LOCAL_IO_OR_TRANSPORT'))


def previous_maintenance_pins():
    return {'.'+row['session']+'.'+name:pin for row in previous_journal_profiles()
            for name,pin in row['pins'].items()}


def serial_maintenance_resume():
    return dict(scope='LH-Q2-CORE-SERIAL-CONTINUATION-v1',session='lhqjgrow-20261007a',
        previous_session=PREVIOUS_JOURNAL_SESSION,previous_D=PREVIOUS_JOURNAL_D,
        originals=[dict(basename='.'+PREVIOUS_JOURNAL_SESSION+'.'+name,bytes=size,sha256=sha)
            for name,(size,sha) in PREVIOUS_JOURNAL_PINS.items()],
        state='STOP_AND_RETAIN',stage='PRE_IDENTITY',reason='GROWTH_JOURNAL_SERIAL',
        remote_exit='UNKNOWN',old_window_consumed=True)


def systemctl_maintenance_resume():
    return dict(scope=c.SYSTEMCTL_SCOPE, session='lhqjgrow-20261007b',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()[:2]])



def template_maintenance_resume():
    return dict(scope=c.TEMPLATE_SCOPE, session='lhqjgrow-20261008a',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()[:3]])


def names_maintenance_resume():
    return dict(scope=c.NAMES_SCOPE, session='lhqjgrow-20261008b',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()[:4]])


def exec_maintenance_resume():
    return dict(scope=c.EXEC_SCOPE, session='lhqjgrow-20261008c',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()[:5]])


def guest_startup_maintenance_resume():
    return dict(scope=c.GS_SCOPE, session='lhqjgrow-20261008d',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()[:6]])


def q1_maintenance_resume():
    return dict(scope=c.QI_SCOPE, session='lhqjgrow-20261008e',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()[:7]])


def declared_maintenance_resume():
    return dict(scope=c.DS_SCOPE, session='lhqjgrow-20261008f',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()[:8]])


def vm_adoption_maintenance_resume():
    return dict(scope=c.VM_ADOPTION_SCOPE, session='lhqjgrow-20261009a',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()[:9]])


def runtime_maintenance_resume():
    return dict(scope=c.RUNTIME_SCOPE, session='lhqjgrow-20261009b',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()[:10]])



# Only the Owner-approved six local-return pins are public. The other archive
# pins and frozen caller hashes are private inputs, bound by the new caller freeze.
LOCAL_PREFLIGHT_D = '5db76ed8ad6f336dd5daf2401635c6be7a637d3b'
LOCAL_PREFLIGHT_SESSION = 'lhqjgrow-20261009c'
LOCAL_PREFLIGHT_SCOPE = 'LH-Q2-CORE-HOST-FD-CONTINUATION-v1'
LOCAL_PREFLIGHT_CALLERS = ('accept_maintenance.py','core_once.py','maintenance_once.py',
    'offline_maintenance.py','static_inputs.py')
LOCAL_PREFLIGHT_PINS = {'fd2-caller-started.json': (83, 'd48d67b065b1f86baa47b47590ea22ba0c02f4729a3c15477b8dc70330a7fa3f'), 'fd2-caller.stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'fd2-caller.stdout': (313, '27927a51afe50b131a390a649bd37521fbfaaf531cc340a8d502277ec114cf87'), 'fd2-preflight.stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'), 'fd2-preflight.stdout': (339, '4cdba663538b0c930f36f739235361b00894cc0a603384b85b68a0a199b2079e'), 'fd2-summary.json': (313, '27927a51afe50b131a390a649bd37521fbfaaf531cc340a8d502277ec114cf87')}
LOCAL_PREFLIGHT_RECORDS = ('freeze-complete.json','execution-result.json','release-gate.json')


def local_preflight_summary():
    return dict(scope=LOCAL_PREFLIGHT_SCOPE,session=LOCAL_PREFLIGHT_SESSION,D=LOCAL_PREFLIGHT_D,
        originals=[dict(basename=n,bytes=v[0],sha256=v[1]) for n,v in sorted(LOCAL_PREFLIGHT_PINS.items())],
        state='PREFLIGHT_FAILED_STOP_AND_RETAIN',terminal='FD2_PREFLIGHT_FAILED_FD3_NOT_RUN',
        caller_invocations=1,execute_invocations=0,ssh_requests=0,marker_created=False,
        maintenance_window_consumed=False,core_package='NOT_BUILT',core_cases='NOT_RUN',
        reason='GROWTH_USAGE_UNKNOWN',diagnostic_retained=False,old_commitments_refunded=False)


def validate_local_preflight_source(value):
    c.exact(value,{'schema','summary','archive','originals','freeze_sha256','callers'},'LOCAL_PREFLIGHT_FIELDS')
    require(value['schema']=='local-hand-q2-local-preflight-source/v1'
        and c.canonical(value['summary'])==c.canonical(local_preflight_summary()),'LOCAL_PREFLIGHT_SUMMARY')
    c.exact(value['archive'],{'bytes','sha256'},'LOCAL_PREFLIGHT_ARCHIVE_PIN')
    c.integer(value['archive']['bytes'],1,131072);c.digest(value['archive']['sha256'])
    c.digest(value['freeze_sha256'])
    c.exact(value['callers'],LOCAL_PREFLIGHT_CALLERS,'LOCAL_PREFLIGHT_CALLERS')
    for pin in value['callers'].values():c.digest(pin)
    pins=value['originals'];c.exact(pins,(*LOCAL_PREFLIGHT_PINS,*LOCAL_PREFLIGHT_RECORDS),'LOCAL_PREFLIGHT_ORIGINALS')
    for name,row in pins.items():
        c.exact(row,{'bytes','sha256'},'LOCAL_PREFLIGHT_PIN')
        c.integer(row['bytes'],0,65536);c.digest(row['sha256'])
        if name in LOCAL_PREFLIGHT_PINS:
            require((row['bytes'],row['sha256'])==LOCAL_PREFLIGHT_PINS[name],'LOCAL_PREFLIGHT_RETURN_PIN')
    require(pins['freeze-complete.json']['sha256']==value['freeze_sha256'],'LOCAL_PREFLIGHT_FREEZE_PIN')
    return value

def legacy_maintenance_resume():
    return dict(scope=c.PROTECTED_SOURCE_SCOPE, session='lhqjgrow-20261010c',
        previous_local_preflight=local_preflight_summary(),
        previous_transport_failure=transport_failure_summary(),
        previous_host_preflight=host_preflight_summary(),
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()])


def persistent_failure_summary():
    return dict(session='lhqjgrow-20261010c',D='b10cdae51f098b12e62c7ca5fbd971b0dab7b56e',
        state='CONSUMED_FAILED_STOP_AND_RETAIN',reason='GROWTH_REPORT_MISSING',
        original_count=5,ssh_requests=1,marker_created=True,remote_exit='UNKNOWN',
        coordinator_returncode=3,custodian_returncode=0,core_cases='NOT_RUN',
        guest_stage='PRE_RUNTIME_PREPARATION',guest_reason='GROWTH_GUEST_IO_OR_RUNTIME',
        exact_missing_path='NOT_RECORDED',old_commitments_refunded=False)


def maintenance_resume():
    value=legacy_maintenance_resume()
    value.update(scope=c.PERSISTENT_PATH_SCOPE,session='lhqjgrow-20261010d',
        previous_runtime_failure=persistent_failure_summary())
    return value


def encode_maintenance_resume(resume,source):
    validate_maintenance_resume(resume);validate_persistent_source(source)
    return dict(scope=resume['scope'],session=resume['session'],
        previous_reference=copy.deepcopy(source['predecessor']),
        previous_runtime_failure=copy.deepcopy(source['summary']))


def decode_maintenance_resume(value,source,predecessor):
    validate_persistent_source(source)
    require(c.canonical(predecessor)==c.canonical(legacy_maintenance_resume()),'PERSISTENT_PREDECESSOR')
    require(c.canonical(value)==c.canonical(encode_maintenance_resume(maintenance_resume(),source)),
        'PERSISTENT_HISTORY_REFERENCE')
    result=copy.deepcopy(predecessor)
    result.update(scope=value['scope'],session=value['session'],
        previous_runtime_failure=copy.deepcopy(value['previous_runtime_failure']))
    return validate_maintenance_resume(result)


# Old10a pins remain private. The new immutable caller freezes the external
# fifteen-member index; these fixed facts cannot be replaced by that input.
TRANSPORT_FAILURE_D = '8f7a438d8a88c98d85852ebfdb6978c5c7bf9230'
TRANSPORT_FAILURE_TREE = '118aeaad621e7aa88a9b60836f6cacb196db4590'
TRANSPORT_FAILURE_FREEZE = '3f9a4b2941a4926f23345cd8f93efa82e9724070ed10f60d68d836814bed6eee'
TRANSPORT_FAILURE_SESSION = 'lhqjgrow-20261010a'
TRANSPORT_FAILURE_ORIGINALS = tuple('.'+TRANSPORT_FAILURE_SESSION+'.'+suffix
    for suffix in ('consumed.json','events.jsonl','pre.stdout','pre.stderr'))
TRANSPORT_FAILURE_RETURNS = ('uc2-caller-started.json','uc2-caller.stderr','uc2-caller.stdout',
    'uc2-execute.stderr','uc2-execute.stdout','uc2-preflight.stderr','uc2-preflight.stdout','uc2-summary.json')
TRANSPORT_FAILURE_RECORDS = ('freeze-complete.json','uc2-failure-private.json','release-gate.json')
TRANSPORT_FAILURE_MEMBERS = (*TRANSPORT_FAILURE_ORIGINALS,*TRANSPORT_FAILURE_RETURNS,*TRANSPORT_FAILURE_RECORDS)


def transport_failure_summary():
    return dict(scope='LH-Q2-CORE-USAGE-CONTINUATION-v1',session=TRANSPORT_FAILURE_SESSION,
        D=TRANSPORT_FAILURE_D,authority=dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04',
            A='bb75dfd835640ba3fff5d1124b7820b0aecf87e5',C='2a4282800eaae404ff3163446cc06297ce99526a'),
        state='CONSUMED_FAILED_STOP_AND_RETAIN',terminal='UC2_CONSUMED_FAILED_UC3_NOT_RUN',
        originals=list(TRANSPORT_FAILURE_ORIGINALS),
        missing_expected=['.'+TRANSPORT_FAILURE_SESSION+'.receipt.json'],
        caller_invocations=1,execute_invocations=1,ssh_requests=1,marker_created=True,
        maintenance_window_consumed=True,remote_exit='UNKNOWN',guest_progress='UNKNOWN',
        coordinator_completion='NOT_CAPTURED',core_package='NOT_BUILT',core_cases='NOT_RUN',
        reason='GROWTH_USAGE_UNKNOWN',diagnostic_retained=True,old_commitments_refunded=False)


def validate_transport_failure_source(value):
    c.exact(value,{'schema','summary','archive','originals','freeze_sha256','callers','diagnostic_sha256'},
        'TRANSPORT_FAILURE_FIELDS')
    require(value['schema']=='local-hand-q2-transport-failure-source/v1'
        and c.canonical(value['summary'])==c.canonical(transport_failure_summary()),'TRANSPORT_FAILURE_SUMMARY')
    c.exact(value['archive'],{'bytes','sha256'},'TRANSPORT_FAILURE_ARCHIVE_PIN')
    c.integer(value['archive']['bytes'],1,196608);c.digest(value['archive']['sha256'])
    require(value['freeze_sha256']==TRANSPORT_FAILURE_FREEZE,'TRANSPORT_FAILURE_FREEZE_PIN')
    c.digest(value['diagnostic_sha256'])
    c.exact(value['callers'],LOCAL_PREFLIGHT_CALLERS,'TRANSPORT_FAILURE_CALLERS')
    for pin in value['callers'].values():c.digest(pin)
    pins=value['originals'];c.exact(pins,TRANSPORT_FAILURE_MEMBERS,'TRANSPORT_FAILURE_ORIGINALS')
    for name,row in pins.items():
        c.exact(row,{'bytes','sha256'},'TRANSPORT_FAILURE_PIN')
        c.integer(row['bytes'],0,65536);c.digest(row['sha256'])
        if name.endswith(('pre.stdout','pre.stderr','caller.stderr','execute.stderr','preflight.stderr')):
            require(row==dict(bytes=0,sha256=c.sha256(b'')),'TRANSPORT_FAILURE_EMPTY_STREAM')
        else:require(row['bytes']>0,'TRANSPORT_FAILURE_REQUIRED_BYTES')
    require(pins['freeze-complete.json']['sha256']==TRANSPORT_FAILURE_FREEZE
        and pins['uc2-summary.json']==pins['uc2-caller.stdout'],'TRANSPORT_FAILURE_RETURN_PIN')
    return value


def maintenance_commitments():
    return dict(previous_maintenance=maintenance_resume(),
        guest_verification=dict(sessions=["lhqguest-20261010a","lhqguest-20261010b"],host_bytes=2097152,host_inodes=64,host_cpu_seconds=240,guest_cpu_seconds=240,per_attempt_cpu_seconds=120,refunded=False),
        source_preparation=dict(session="lhqsource-20261010a",host_bytes=1048576,host_inodes=32,cpu_seconds=120,refunded=False),
        path_reads=dict(sessions=['lhqpaths-20261010a','lhqpaths-20261010b'],host_bytes=2097152,
            host_inodes=64,host_cpu_seconds=240,guest_cpu_seconds=240,per_attempt_cpu_seconds=120,refunded=False),
        additional_preparation=dict(sessions=['lhqpaths-source-20261010a','lhqpaths-source-20261010b',
            'lhqsource-20261010d','lhqarchive-20261010d'],host_bytes=4194304,host_inodes=128,
            cpu_seconds=480,per_attempt_cpu_seconds=120,refunded=False),
        generations=[dict(session=session,bytes=1296*1048576,inodes=370,cpu_seconds=120)
            for session in (PREVIOUS_JOURNAL_SESSION,SECOND_JOURNAL_SESSION,THIRD_JOURNAL_SESSION,FOURTH_JOURNAL_SESSION,FIFTH_JOURNAL_SESSION,SIXTH_JOURNAL_SESSION,SEVENTH_JOURNAL_SESSION,EIGHTH_JOURNAL_SESSION,NINTH_JOURNAL_SESSION,TENTH_JOURNAL_SESSION,ELEVENTH_JOURNAL_SESSION,'lhqjgrow-20261009c','lhqjgrow-20261010a','lhqjgrow-20261010b','lhqjgrow-20261010c','lhqjgrow-20261010d')],
        released_or_refunded=False)


def validate_maintenance_resume(value):
    require(type(value) is dict and c.canonical(value)==c.canonical(maintenance_resume()),
        'JOURNAL_PREVIOUS_SUMMARY')
    return value


def encode_manifest_inputs(binding):
    require(type(binding) is dict and 'resume' in binding and 'resume_sha256' not in binding,
        'JOURNAL_INPUT_ENCODING')
    validate_maintenance_resume(binding['resume'])
    result=copy.deepcopy(binding)
    result['resume_sha256']=c.sha256(c.canonical(result.pop('resume'),newline=True))
    return result


def decode_manifest_inputs(manifest,predecessor=None):
    require(manifest.get('schema')=='lhq-journal-growth-manifest/v18','JOURNAL_INPUT_VERSION')
    value=manifest['inputs']
    resume=decode_maintenance_resume(manifest['resume'],value['persistent_source'],predecessor)
    require(type(value) is dict and 'resume' not in value and 'resume_sha256' in value
        and value['resume_sha256']==c.sha256(c.canonical(resume,newline=True)), 'JOURNAL_INPUT_REFERENCE')
    result=copy.deepcopy(value);result.pop('resume_sha256');result['resume']=copy.deepcopy(resume)
    return result


def build_previous_maintenance(files):
    """Consume the eleven exact failed generations under their original schemas."""
    c.exact(files, set(previous_maintenance_pins()), 'CORE_JOURNAL_PREVIOUS_FILES')
    for fixed in previous_journal_profiles():
        prefix='.'+fixed['session']+'.'
        _build_previous_generation({prefix+name:files[prefix+name] for name in fixed['pins']},fixed)
    return maintenance_resume()


def _build_previous_generation(files, fixed):
    """Verify the exact failed originals and their internal relation, never adopt success."""
    prefix='.'+fixed['session']+'.'
    c.exact(files,{prefix+name for name in fixed['pins']},'CORE_JOURNAL_PREVIOUS_FILES')
    for name,(size,sha) in fixed['pins'].items():
        raw=files[prefix+name]
        require(type(raw) is bytes and (len(raw),c.sha256(raw))==(size,sha),'JOURNAL_PREVIOUS_PIN')
    parse=lambda raw:c.document(raw,limit=65536,newline=True)
    marker=parse(files[prefix+'consumed.json']);receipt=parse(files[prefix+'receipt.json'])
    manifest=marker['manifest'];desc=marker['pre_description']
    require(manifest['schema']=='lhq-journal-growth-manifest/v'+str(fixed['version'])
        and receipt['schema']=='lhq-journal-growth-receipt/v'+str(fixed['version']),'JOURNAL_PREVIOUS_SCHEMA')
    authority=fixed['authority']
    for row in (manifest,receipt):
        require({key:row[key] for key in authority}==authority,'JOURNAL_PREVIOUS_AUTHORITY')
    for row in (manifest,marker,receipt):
        require(row['D']==fixed['D'] and row['nonce']==marker['nonce']
            and row['access_mode']=='TRUSTED_SINGLE_ADMIN'
            and row['host_writer_observation']=='NOT_PERFORMED'
            and row['continuous_exclusion_proven'] is False,'JOURNAL_PREVIOUS_BINDING')
    c.digest(marker['nonce'])
    require(marker['session']==receipt['session']==desc['session']==fixed['session']
        and marker['manifest_sha256']==receipt['manifest_sha256']==c.sha256(c.canonical(manifest,newline=True))
        and marker['clocks']==receipt['clock_origins_ns']==manifest['window_binding']['origins']
        and desc['nonce']==marker['nonce']
        and desc['original_boot_id']==receipt['original_boot_id']
        and desc['source_binding_sha256']==c.sha256(c.canonical(manifest['inputs'],newline=True))
        and manifest['inventory_sha256']==manifest['inputs']['inventory_sha256'],
        'JOURNAL_PREVIOUS_SOURCE')
    require(receipt['state']==receipt['last_step']=='STOP_AND_RETAIN'
        and receipt['reason']==('LOCAL_IO_OR_TRANSPORT' if fixed['version']==12 else 'GROWTH_REPORT_MISSING')
        and receipt['started']==['CONSUMED','GUEST_QUIET'] and receipt['marker_created'] is True
        and type(receipt['ssh_requests']) is int and receipt['ssh_requests']==1
        and type(receipt['business_cases']) is int and receipt['business_cases']==0
        and receipt['remote_exit']=='UNKNOWN' and receipt['old_commitments_refunded'] is False,
        'JOURNAL_PREVIOUS_FAILURE')
    if fixed['version']==12:
        require(files[prefix+'pre.stdout']==files[prefix+'pre.stderr']==b''
            and receipt['transports']==[] and receipt['errno']==24
            and receipt['error_type']=='OSError','JOURNAL_PREVIOUS_LOCAL_FD')
    else:
        failure=parse(files[prefix+'pre.stderr'])
        require(files[prefix+'pre.stdout']==b'' and failure['schema']=='lhq-journal-growth-guest/v'+('3' if fixed['version'] in (10,11) else '2' if fixed['version'] in (8,9) else '1')
            and failure['session']==fixed['session'] and failure['phase']=='pre'
            and failure['status']=='INCOMPLETE' and failure['stage']==fixed['stage']
            and failure['reason']==fixed['reason'] and failure['actions_started']==[],
            'JOURNAL_PREVIOUS_SERIAL')
    events=[parse(line+b'\n') for line in files[prefix+'events.jsonl'].splitlines()]
    expected=[dict(step='CONSUMED',state='STARTED'),
        dict(step='CONSUMED',state='RETURNED',result=dict(manifest_sha256=marker['manifest_sha256'])),
        dict(step='GUEST_QUIET',state='STARTED'),
        dict(phase='pre',argv_sha256=marker['pre_command_sha256'],
            description_sha256=c.sha256(c.canonical(desc,newline=True)),
            window_seconds=desc['window_seconds'],change_seconds=desc['change_seconds'])]
    require(c.canonical(events)==c.canonical(expected),'JOURNAL_PREVIOUS_ORDER')
    if fixed['version']!=12:
        require(len(receipt['transports'])==1 and receipt['transports'][0]['files']=={
            stream:dict(bytes=len(files[prefix+'pre.'+stream]),sha256=c.sha256(files[prefix+'pre.'+stream]))
            for stream in ('stdout','stderr')},'JOURNAL_PREVIOUS_STREAMS')
    if fixed['version'] == 3:
        for row in (manifest,marker,receipt,manifest['inputs']):
            require(c.canonical(row.get('resume')) == c.canonical(serial_maintenance_resume()),
                    'JOURNAL_PREVIOUS_SERIAL_RESUME')
    if fixed['version'] == 4:
        for row in (manifest,marker,receipt,manifest['inputs']):
            require(c.canonical(row.get('resume')) == c.canonical(systemctl_maintenance_resume()),
                    'JOURNAL_PREVIOUS_SYSTEMCTL_RESUME')
    if fixed['version'] == 5:
        for row in (manifest,marker,receipt,manifest['inputs']):
            require(c.canonical(row.get('resume')) == c.canonical(template_maintenance_resume()),
                    'JOURNAL_PREVIOUS_TEMPLATE_RESUME')
    if fixed['version'] == 6:
        for row in (manifest,marker,receipt,manifest['inputs']):
            require(c.canonical(row.get('resume')) == c.canonical(names_maintenance_resume()),
                    'JOURNAL_PREVIOUS_NAMES_RESUME')
    if fixed['version'] == 7:
        for row in (manifest,marker,receipt,manifest['inputs']):
            require(c.canonical(row.get('resume')) == c.canonical(exec_maintenance_resume()),
                    'JOURNAL_PREVIOUS_EXEC_RESUME')
    if fixed['version'] in (8,9):
        def validate_startup_assurance(value):
            require(type(value) is dict and c.canonical(value)==c.canonical(dict(
                mode='TRUSTED_SINGLE_ADMIN',indirect_startup_observation='NOT_PERFORMED',
                no_undeclared_business_startup=True,continuous_exclusion_proven=False)),
                'JOURNAL_PREVIOUS_GS_PREMISE')
        for row in (manifest, marker, receipt, manifest['inputs']):
            require(c.canonical(row.get('resume')) == c.canonical(guest_startup_maintenance_resume() if fixed['version']==8 else q1_maintenance_resume()),
                    'JOURNAL_PREVIOUS_GS_RESUME')
            validate_startup_assurance(row.get('guest_startup_assurance'))
        require(desc['schema']=='lhq-journal-growth-input/v2','JOURNAL_PREVIOUS_GS_DESCRIPTOR')
        validate_startup_assurance(desc.get('guest_startup_assurance'))
        validate_startup_assurance(failure.get('guest_startup_assurance'))
    if fixed['version'] == 10:
        from .q2_journal_growth_guest import validate_startup_assurance
        for row in (manifest, marker, receipt, manifest['inputs']):
            require(c.canonical(row.get('resume')) == c.canonical(declared_maintenance_resume()),
                    'JOURNAL_PREVIOUS_DS_RESUME')
            validate_startup_assurance(row.get('guest_startup_assurance'))
        require(desc['schema']=='lhq-journal-growth-input/v3','JOURNAL_PREVIOUS_DS_DESCRIPTOR')
        validate_startup_assurance(desc.get('guest_startup_assurance'))
        validate_startup_assurance(failure.get('guest_startup_assurance'))
    if fixed['version'] == 11:
        from .q2_journal_growth_guest import validate_startup_assurance
        resume=vm_adoption_maintenance_resume()
        for row in (manifest,receipt,manifest['inputs']):
            require(c.canonical(row.get('resume'))==c.canonical(resume),'JOURNAL_PREVIOUS_VM_RESUME')
            validate_startup_assurance(row.get('guest_startup_assurance'))
        require(marker.get('resume_sha256')==c.sha256(c.canonical(resume,newline=True))
            and 'resume' not in marker,'JOURNAL_PREVIOUS_VM_MARKER')
        require(desc['schema']=='lhq-journal-growth-input/v3','JOURNAL_PREVIOUS_VM_DESCRIPTOR')
        for row in (marker,desc,failure):validate_startup_assurance(row.get('guest_startup_assurance'))
    if fixed['version'] == 12:
        from .q2_journal_growth_guest import validate_startup_assurance
        resume=runtime_maintenance_resume()
        for row in (manifest,receipt,manifest['inputs']):
            require(c.canonical(row.get('resume'))==c.canonical(resume),'JOURNAL_PREVIOUS_RT_RESUME')
            validate_startup_assurance(row.get('guest_startup_assurance'))
        require(marker.get('resume_sha256')==c.sha256(c.canonical(resume,newline=True))
            and 'resume' not in marker and desc['schema']=='lhq-journal-growth-input/v4',
            'JOURNAL_PREVIOUS_RT_MARKER')
        for row in (marker,desc):validate_startup_assurance(row.get('guest_startup_assurance'))
    return fixed['session']


def read_previous_journal_files(directory_fd,anchor,call,*,_seen=None):
    seen=set() if _seen is None else _seen
    files={}
    for fixed in previous_journal_profiles():
        prefix='.'+fixed['session']+'.'
        files.update(_read_pins(directory_fd,anchor,call,fixed['pins'],
            lambda suffix:prefix+suffix,{name:65536 for name in fixed['pins']},seen))
        for name in PREVIOUS_JOURNAL_ABSENT:
            try:
                call(os.stat,prefix+name,dir_fd=directory_fd,follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise c.ContractError('CORE_JOURNAL_PREVIOUS_LATER_OBJECT')
    build_previous_maintenance(files)
    return files


JOURNAL_SESSION = 'lhqjgrow-20261010d'
JOURNAL_FILES = {'consumed.json': 65536, 'events.jsonl': 1048576,
    'pre.stdout': 1048576, 'pre.stderr': 1048576, 'post.stdout': 1048576,
    'post.stderr': 1048576, 'receipt.json': 65536, 'vm.pid': 64}
JOURNAL_SOURCE_NAMES = ('q2_journal_growth.py', 'q2_journal_growth_guest.py',
    'q2_core_capacity_capture.py', 'q2_core_capacity_reader.py', 'q2_sshd_source_capture.py',
    'q2_sshd_source_reader.py', 'q2_core_obligation_inputs.py', 'q2_core_prior_attempt.py',
    'q2_core_delivery_contract.py', 'q2_local_source_delivery.py', 'q2_core_approved_inputs.py',
    'q2_host_kernel_facts.py', 'q2_journal_retained_fds.py')


CAPACITY_DIAGNOSTIC_PINS = {
    'consumed.json':(939,'537f3f93f47034ae253c735052cbae443eea3aa3f775849698830e4b26cec9ff'),
    'stdout':(3609,'00cc8b744b8d63bf7d83a4044921fc1a80b7a21b289cf62b4e6f33cd9548b8db'),
    'stderr':(0,'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'receipt.json':(1807,'575e74006d530fd562a67d66d5ce066a8e941d914da1f84bec2eb839b7ee4270')}


def read_capacity_diagnostic(directory_fd,anchor,call,*,_seen):
    return _read_pins(directory_fd,anchor,call,CAPACITY_DIAGNOSTIC_PINS,
        lambda name:'.lhqcap-20261006a.'+name,
        {name:size for name,(size,_) in CAPACITY_DIAGNOSTIC_PINS.items()},_seen)


def read_journal_files(directory_fd, anchor, call, *, _seen=None):
    return _read_pins(directory_fd, anchor, call,
        {name: (None, None) for name in JOURNAL_FILES},
        lambda suffix: '.' + JOURNAL_SESSION + '.' + suffix, JOURNAL_FILES,
        set() if _seen is None else _seen)


ACTIVATION_EVENT = 'LH-Q1-QUOTA-REPAIR-ACTIVATION-20261009-03'
ACTIVATION_FILES = ('activate-approved.py','activation-proposal-private.json',
    'current-vm-binding-private.json','endpoint-after.stderr','endpoint-after.stdout',
    'endpoint-before.stderr','endpoint-before.stdout','execution-freeze-private.json',
    'explicit-owner-approval-private.json','independent-return-verification-private.json',
    'index-preparation-note-private.json','launch-consumed-private.json','new-pid-cmdline.raw',
    'new-pid-stat.raw','offline-control-flow-result-private.json','offline-control-flow-test.py',
    'pending-owner-approval-private.json','preparation-pins-private.json',
    'protected-source/q2_sshd_source_capture.py','protected-source/q2_sshd_source_reader.py',
    'qemu-start.stderr','qemu-start.stdout','qemu-version.stderr','qemu-version.stdout',
    'result-private.json','retained-index-private.json','ssh-consumed-private.json',
    'ssh-install.stderr','ssh-install.stdout','started-private.json')
ACTIVATION_PROJECTION_FIELDS = {'schema','event','historical_boot_id','current_boot_id','host_boot_id',
    'vm','image_identities','original_system_identity','system_path','pidfile','serial',
    'index','evidence_sha256','candidate_prelaunch_sha256','candidate_digest_scope',
    'package_verified','quota_verified','old_records_preserved','execution_permission'}


def validate_vm_activation(value):
    """Validate the host-verified projection without asserting unseen originals."""
    require(type(value) is dict,'ACTIVATION_FIELDS')
    resumed = value.get('schema') == 'local-hand-q2-vm-activation/v2'
    c.exact(value, ACTIVATION_PROJECTION_FIELDS | (RESUMPTION_FIELDS if resumed else set()), 'CORE_ACTIVATION_FIELDS')
    require((resumed and value['event']==RESUMPTION_EVENT) or
        (value['schema']=='local-hand-q2-vm-activation/v1' and value['event']==ACTIVATION_EVENT),
        'ACTIVATION_SCHEMA')
    require(len(c.canonical(value))<=4096, 'ACTIVATION_BOUND')
    for key in ('historical_boot_id','current_boot_id','host_boot_id'):
        require(type(value[key]) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value[key]),'ACTIVATION_BOOT')
    require(value['historical_boot_id']!=value['current_boot_id'],'ACTIVATION_BOOT_CHANGE')
    vm=value['vm'];c.exact(vm,{'pid','starttime','argv_sha256'},'CORE_ACTIVATION_VM')
    c.integer(vm['pid'],2);c.integer(vm['starttime'],1);c.digest(vm['argv_sha256'])
    c.exact(value['image_identities'],{'system','quota','journal','evidence','seed'},'CORE_ACTIVATION_IMAGES')
    pairs=list(value['image_identities'].values())+[value['original_system_identity']]
    for pair in pairs:
        require(type(pair) is list and len(pair)==2,'ACTIVATION_IMAGE_IDENTITY')
        c.integer(pair[0]);c.integer(pair[1],1)
    require(len({tuple(v) for v in pairs})==6,'ACTIVATION_IMAGE_ALIAS')
    for key in ('system_path','pidfile','serial'):
        path=value[key]
        require(type(path) is str and re.fullmatch(r'/[A-Za-z0-9_./-]{1,4095}',path)
            and posixpath.normpath(path)==path and '..' not in path.split('/'),'ACTIVATION_PATH')
    require(len({value[k] for k in ('system_path','pidfile','serial')})==3,'ACTIVATION_PATH_ALIAS')
    c.exact(value['index'],{'bytes','sha256'},'CORE_ACTIVATION_INDEX')
    c.integer(value['index']['bytes'],1,65536);c.digest(value['index']['sha256'])
    for key in ('evidence_sha256','candidate_prelaunch_sha256'):c.digest(value[key])
    require(value['candidate_digest_scope']=='PRELAUNCH_ONLY'
        and value['package_verified'] is value['quota_verified'] is value['old_records_preserved'] is True
        and value['execution_permission'] is False,'ACTIVATION_ACCEPTANCE')
    if resumed:
        for key in RESUMPTION_FIELDS - {'previous_host_preflight'}: c.digest(value[key])
        require(c.canonical(value['previous_host_preflight']) == c.canonical(host_preflight_summary()),
            'ACTIVATION_HOST_PREFLIGHT')
    return value


def build_vm_activation(files, index_raw, *, historical_boot):
    """Verify all retained activation bytes; never reads a live VM or image."""
    if 'activation/activate-approved.py' in files:
        return build_vm_resumption(files, index_raw, historical_boot=historical_boot)
    c.exact(files, ACTIVATION_FILES, 'CORE_ACTIVATION_ORIGINALS')
    def parse(raw):
        require(type(raw) is bytes and len(raw)<=262144,'ACTIVATION_INPUT_BOUND')
        def pairs(items):
            require(len(dict(items))==len(items),'ACTIVATION_DUPLICATE_KEY')
            return dict(items)
        return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
    require(len(index_raw)<=65536,'ACTIVATION_INDEX_BOUND')
    index=parse(index_raw)
    pins=[dict(name=name,bytes=len(raw),sha256=c.sha256(raw)) for name,raw in sorted(files.items())]
    require(index['state']=='ACTIVATED_EXACT_PACKAGE_INSTALLED_QUOTA_VERIFIED'
        and index['event']==ACTIVATION_EVENT and index['files']==pins,'ACTIVATION_INDEX_BINDING')
    require(sum(len(raw) for raw in files.values())<=262144,'ACTIVATION_TOTAL_BOUND')
    doc=lambda name:parse(files[name])
    authority=doc('explicit-owner-approval-private.json');freeze=doc('execution-freeze-private.json')
    proposal=doc('activation-proposal-private.json');result=doc('result-private.json')
    launch=doc('launch-consumed-private.json');ssh=doc('ssh-consumed-private.json')
    guest=doc('ssh-install.stdout');binding=doc('current-vm-binding-private.json')
    sha=lambda name:c.sha256(files[name])
    def count(row, key, expected):
        require(type(row[key]) is int and row[key]==expected,'ACTIVATION_COUNT')
    for row, expected in ((authority,{'startup_calls':1,'ssh_calls':1,'retries':0,'stop_or_kill_calls':0}),
            (result,{'startup_calls':1,'ssh_calls':1,'package_install_calls':1,'automatic_retries':0,'stop_calls':0}),
            (guest,{'package_install_calls':1,'network_package_calls':0,'reboots':0})):
        for key, number in expected.items():count(row,key,number)
    # Activation helper canonicalizes without a trailing newline.
    activation_canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
    require(authority['event']==freeze['event']==result['event']==launch['event']==ssh['event']==ACTIVATION_EVENT
        and authority['state']=='APPROVED' and authority['approved_action']=='ACTIVATE_EXACT_PROPOSAL_ONCE'
        and type(authority['owner_reply']) is str and authority['owner_reply'].strip()
        and authority['startup_calls']==authority['ssh_calls']==1,'ACTIVATION_AUTHORITY')
    require(freeze['authority_sha256']==launch['authority_sha256']==sha('explicit-owner-approval-private.json')
        and freeze['proposal_sha256']==authority['proposal_sha256']==launch['proposal_sha256']==sha('activation-proposal-private.json')
        and freeze['helper_sha256']==authority['helper_sha256']==sha('activate-approved.py'),'ACTIVATION_FROZEN_SOURCE')
    require(result['state']=='ACTIVATED_EXACT_PACKAGE_INSTALLED_QUOTA_VERIFIED'
        and result['startup_calls']==result['ssh_calls']==result['package_install_calls']==1
        and result['automatic_retries']==result['stop_calls']==0 and result['errors']==[]
        and result['guest_completion']=='VERIFIED' and result['original_system_and_old_outputs_preserved'] is True,
        'ACTIVATION_RESULT')
    require([row['label'] for row in result['commands']]==['qemu-version','endpoint-before','qemu-start','endpoint-after','ssh-install']
        and all(type(row['returncode']) is int and row['returncode']==0 and row['eof'] is True for row in result['commands']),
        'ACTIVATION_COMMANDS')
    require(all(files[name]==b'' for name in ('endpoint-before.stdout','endpoint-before.stderr',
        'endpoint-after.stderr','qemu-start.stderr','qemu-version.stderr','ssh-install.stderr')),'ACTIVATION_STDERR')
    require(guest['state']=='EXACT_PACKAGE_INSTALLED_QUOTA_MOUNT_VERIFIED'
        and guest['package_install_calls']==1 and guest['network_package_calls']==guest['reboots']==0
        and guest['boot']==result['guest_boot'],'ACTIVATION_GUEST')
    steps=guest['steps'];labels=['modules-dependency','regdb-dependency','quota-mount','module-vermagic',
        'install-exact-local-package','installed-package','package-integrity','module-resolution','quota-mount-after']
    require([row['label'] for row in steps]==labels and all(type(row['exit']) is int and row['exit']==0 for row in steps),'ACTIVATION_INSTALL')
    # Recover the exact staged directory from the already hash-bound helper.
    # Literal AST reads do not execute retained source or disclose machine paths.
    import ast
    def literal_assignment(raw, name):
        try:
            matches=[node.value for node in ast.parse(raw).body
                if isinstance(node,ast.Assign) and len(node.targets)==1
                and isinstance(node.targets[0],ast.Name) and node.targets[0].id==name]
            require(len(matches)==1,'ACTIVATION_HELPER_LITERAL')
            value=ast.literal_eval(matches[0])
        except (SyntaxError,ValueError,TypeError,RecursionError):
            require(False,'ACTIVATION_HELPER_LITERAL')
        require(type(value) is str,'ACTIVATION_HELPER_LITERAL')
        return value
    loader=literal_assignment(files['activate-approved.py'],'LOADER')
    stage=literal_assignment(loader,'base')
    c.absolute_path(stage,'CORE_ACTIVATION_STAGE')
    package=proposal['package']
    require(steps[5]['stdout'].strip()=='install ok installed\t'+package['Version']
        and steps[5]['argv']==['dpkg-query','-W','-f=${Status}\t${Version}',package['Package']]
        and steps[6]['argv']==['dpkg','--verify',package['Package']]
        and steps[4]['argv']==['dpkg','--install',stage+'/'+package['Filename'].rsplit('/',1)[-1]]
        and not steps[6]['stdout'].strip() and ssh['script_sha256']==proposal['reconcile_script_sha256'],
        'ACTIVATION_PACKAGE')
    before=parse(steps[2]['stdout'].encode())['filesystems'];after=parse(steps[8]['stdout'].encode())['filesystems']
    require(before==after and len(before)==1 and before[0]['fstype']=='ext4'
        and {'rw','nodev','nosuid','noexec','prjquota'}<=set(before[0]['options'].split(',')),'ACTIVATION_QUOTA')
    argv=launch['argv'];minimal=proposal['minimal_change'];current=result['new_vm']
    require(argv==minimal['full_argv']==binding['qemu_argv'] and type(argv) is list
        and all(type(word) is str and word.isascii() for word in argv),'ACTIVATION_ARGV')
    raw=b'\0'.join(word.encode('ascii') for word in argv)+b'\0'
    require(files['new-pid-cmdline.raw']==raw and current['argv_sha256']==c.sha256(activation_canonical(argv))
        and current==ssh['new_vm']==binding['new_vm'],'ACTIVATION_PROCESS')
    status=files['new-pid-stat.raw'];tail=status.rpartition(b') ')[2].split()
    require(status.startswith(str(current['pid']).encode()+b' (') and len(tail)>19
        and int(tail[19])==current['starttime'],'ACTIVATION_PID_START')
    require(argv[argv.index('-pidfile')+1]==minimal['new_pidfile']==binding['pidfile']
        and argv[argv.index('-serial')+1]=='file:'+minimal['new_serial']
        and minimal['new_serial']==binding['serial'],'ACTIVATION_LOCATORS')
    require(proposal['candidate']['candidate_path']==binding['active_system_path']==minimal['system_drive_file']
        and 'if=none,id=os,format=qcow2,file='+binding['active_system_path'] in argv,'ACTIVATION_SYSTEM_PATH')
    require(result['host_boot']==binding['host_boot'] and guest['boot']==binding['guest_boot']
        and sha('ssh-install.stdout')==binding['source_guest_stdout']['sha256']
        and sha('result-private.json')==binding['source_result']['sha256'],'ACTIVATION_RETURN_BINDING')
    for key,name in (('authority','explicit-owner-approval-private.json'),('launch_marker','launch-consumed-private.json'),
            ('ssh_marker','ssh-consumed-private.json'),('source_guest_stdout','ssh-install.stdout'),('source_result','result-private.json')):
        require(binding[key]==dict(name=name,bytes=len(files[name]),sha256=sha(name)),'ACTIVATION_BINDING_PIN')
    require(binding['event']==ACTIVATION_EVENT and binding['no_replay_or_new_execution_permission'] is True
        and binding['installed_package']==package['Package'] and binding['installed_package_version']==package['Version']
        and binding['original_system_preserved']==result['original_images_before']['system']
        and binding['active_system_prelaunch_metadata']==result['candidate_before']
        and binding['active_system_prelaunch_sha256']==proposal['candidate']['candidate_sha256'],
        'ACTIVATION_SAVED_IDENTITY')
    images={role:[row['metadata']['dev'],row['metadata']['ino']] for role,row in result['original_images_before'].items()}
    original_system=images['system'];active=result['candidate_before']['metadata']
    images['system']=[active['dev'],active['ino']]
    value=dict(schema='local-hand-q2-vm-activation/v1',event=ACTIVATION_EVENT,
        historical_boot_id=historical_boot,current_boot_id=guest['boot'],host_boot_id=result['host_boot'],
        vm=dict(pid=current['pid'],starttime=current['starttime'],argv_sha256=c.sha256(raw)),
        image_identities=images,original_system_identity=original_system,system_path=binding['active_system_path'],
        pidfile=binding['pidfile'],serial=binding['serial'],index=dict(bytes=len(index_raw),sha256=c.sha256(index_raw)),
        evidence_sha256=c.sha256(c.canonical(pins)),candidate_prelaunch_sha256=proposal['candidate']['candidate_sha256'],
        candidate_digest_scope='PRELAUNCH_ONLY',package_verified=True,quota_verified=True,
        old_records_preserved=True,execution_permission=False)
    return validate_vm_activation(value)


def build_journal_transition(files, *, implementation, sources, frozen, priors):
    """Consume all K2 originals and fixed inputs before projecting a new boot.

    The source-aware freezer separately ties `sources` to implementation Git
    blobs. Guest checks this bounded projection, not unseen original files.
    """
    from . import q2_journal_growth as h
    from . import q2_journal_growth_guest as g
    h.validate_q1_frozen(frozen)
    local_source=build_local_preflight_source(frozen['local_preflight_raw'],frozen['local_preflight_spec'])
    require(local_source==frozen['source_binding']['local_preflight_source']
        and local_source['archive']==frozen['source_binding']['sources']['local_preflight_archive'],
        'LOCAL_PREFLIGHT_SOURCE_BINDING')
    failed_source=build_transport_failure_source(frozen['transport_failure_raw'],frozen['transport_failure_spec'])
    require(failed_source==frozen['source_binding']['transport_failure_source']
        and failed_source['archive']==frozen['source_binding']['sources']['transport_failure_archive'],
        'TRANSPORT_FAILURE_SOURCE_BINDING')
    c.exact(sources, JOURNAL_SOURCE_NAMES, 'CORE_JOURNAL_SOURCE_SET')
    c.exact(files, {'.' + JOURNAL_SESSION + '.' + name for name in JOURNAL_FILES}, 'CORE_JOURNAL_FILES')
    raw = {name: files['.' + JOURNAL_SESSION + '.' + name] for name in JOURNAL_FILES}
    for name, data in raw.items():
        require(type(data) is bytes and len(data) <= JOURNAL_FILES[name], 'JOURNAL_LIMIT')
    parse = lambda data, limit: c.document(data, limit=limit, newline=True)
    marker = parse(raw['consumed.json'], 65536)
    receipt = parse(raw['receipt.json'], 65536)
    c.exact(receipt, {'schema','R','A','C','D','session','nonce','access_mode',
        'host_writer_observation','continuous_exclusion_proven','manifest_sha256',
        'clock_origins_ns','state','reason','last_step','started','marker_created','ssh_requests',
        'business_cases','remote_exit','production_supported','old_commitments_refunded',
        'exclusive_reservation_proven','original_boot_id','new_boot_id','post_transport',
        'transports','new_vm','image_identities','processes','serial_capture','kernel_report',
        'budget','management_usage','resume','guest_startup_assurance','retained_custody'}, 'CORE_JOURNAL_RECEIPT_FIELDS')
    require(receipt['serial_capture']=='NOT_CAPTURED_NULL_BACKEND','JOURNAL_SERIAL')
    usage=receipt['management_usage'];c.exact(usage,{'cpu_nanoseconds','rss_peak_bytes'},'CORE_JOURNAL_USAGE')
    c.integer(usage['cpu_nanoseconds'],1,120000000000);c.integer(usage['rss_peak_bytes'],1,536870912)
    budget=receipt['budget'];c.exact(budget,{'logical_bytes','allocated_bytes','inodes'},'CORE_JOURNAL_BUDGET')
    c.integer(budget['logical_bytes'],1,8388608);c.integer(budget['allocated_bytes'],1,8388608)
    c.integer(budget['inodes'],7,32)
    c.exact(marker, {'manifest_sha256', 'manifest', 'nonce', 'clocks', 'session', 'D',
        'access_mode', 'host_writer_observation', 'continuous_exclusion_proven',
        'pre_command_sha256', 'post_command_derivation', 'pre_description', 'resume_sha256','guest_startup_assurance'}, 'CORE_JOURNAL_MARKER')
    manifest = marker['manifest']
    c.exact(manifest, {'schema','R','A','C','D','nonce','access_mode','host_writer_observation',
        'continuous_exclusion_proven','historical_authority','inputs','window_binding',
        'inventory_sha256','retained_sha256','sources','tools','vm','image_identities',
        'original_argv','restart_argv','image_commands','protocol','resume','guest_startup_assurance','custody_binding'}, 'CORE_JOURNAL_MANIFEST')
    c.exact(frozen['capacity_files'],{'.lhqcap-20261006a.'+name for name in CAPACITY_DIAGNOSTIC_PINS},
        'CORE_JOURNAL_CAPACITY_ORIGINALS')
    for name,(size,digest) in CAPACITY_DIAGNOSTIC_PINS.items():
        data=frozen['capacity_files']['.lhqcap-20261006a.'+name]
        require(type(data) is bytes and (len(data),c.sha256(data))==(size,digest),'JOURNAL_CAPACITY_PIN')
    saved=h.prior.validate_result(frozen['capacity_files']['.lhqcap-20261006a.stdout'],
        c.sha256(sources['q2_core_capacity_reader.py']),frozen['description'])['rows']
    require(saved==frozen['saved_rows'],'JOURNAL_SAVED_ROWS')
    expected_authority = dict(R=h.R, A=(c.PERSISTENT_PATH_BASELINE or {}).get('commit'), C=(c.PERSISTENT_PATH_CLOSURE or {}).get('commit'))
    require(manifest['schema'] == 'lhq-journal-growth-manifest/v18'
        and receipt['schema'] == 'lhq-journal-growth-receipt/v18', 'JOURNAL_SCHEMA')
    for value in (manifest, receipt):
        require({key:value[key] for key in expected_authority} == expected_authority, 'JOURNAL_AUTHORITY')
    previous=build_previous_maintenance(frozen['previous_maintenance_files'])
    decoded=decode_manifest_inputs(manifest,frozen['persistent_predecessor'])
    for value in (decoded, receipt, frozen['source_binding']):
        validate_maintenance_resume(value['resume'])
        require(c.canonical(value['resume'])==c.canonical(previous),'JOURNAL_PREVIOUS_BINDING')
    require(marker['resume_sha256']==h.resume_sha256(previous),'JOURNAL_PREVIOUS_DIGEST')
    for value in (manifest, marker, receipt):
        g.validate_startup_assurance(value.get('guest_startup_assurance'))
        require(value['D'] == implementation['commit'] and value['nonce'] == marker['nonce']
            and value['access_mode'] == 'TRUSTED_SINGLE_ADMIN'
            and value['host_writer_observation'] == 'NOT_PERFORMED'
            and value['continuous_exclusion_proven'] is False, 'JOURNAL_BINDING')
    require(marker['session'] == receipt['session'] == JOURNAL_SESSION
        and marker['manifest_sha256'] == receipt['manifest_sha256'] == c.sha256(h.canonical(manifest))
        and marker['clocks'] == manifest['window_binding']['origins'] == receipt['clock_origins_ns'],
        'JOURNAL_MARKER_BINDING')
    c.digest(marker['nonce'])
    h.make_preflight(implementation['commit'],marker['manifest_sha256'],
        manifest['window_binding'],marker['nonce'],usage,resume=previous)
    require(manifest['historical_authority']==dict(A=h.A,C=h.C,observer_superseded_by=h.MINIMAL_A,minimal_C=h.MINIMAL_C,serial_A=h.SERIAL_A,serial_C=h.SERIAL_C,systemctl_A=h.SYSTEMCTL_A,systemctl_C=h.SYSTEMCTL_C,template_A=h.TEMPLATE_A,template_C=h.TEMPLATE_C,names_A=h.NAMES_A,names_C=h.NAMES_C,exec_A=h.EXEC_A,exec_C=h.EXEC_C)
        and manifest['protocol']=='two fixed phases; post bound to the durably saved pre report; no probe or retry'
        and marker['post_command_derivation']=='same fixed sources; post descriptor bound to saved canonical pre report',
        'JOURNAL_PROTOCOL')
    c.digest(manifest['retained_sha256'])
    g.validate_startup_assurance(frozen.get('guest_startup_assurance'))
    g.validate_startup_assurance(frozen['source_binding'].get('guest_startup_assurance'))
    require(decoded == frozen['source_binding']
        and manifest['inventory_sha256'] == c.sha256(h.canonical(frozen['inventory']))
        and manifest['sources'] == {name:dict(bytes=len(data),sha256=c.sha256(data))
            for name,data in sources.items()}, 'JOURNAL_INPUT_SOURCE')
    g.validate_runtime_binding(frozen['runtime_parent_binding'],frozen['inventory'])
    require(frozen['source_binding']['runtime_parent_binding_sha256']==h.digest(h.canonical(frozen['runtime_parent_binding']))
        and marker['pre_description']['runtime_parent_binding']==frozen['runtime_parent_binding'],'JOURNAL_RUNTIME_SOURCE')
    require(receipt['retained_custody']['originals']==frozen['previous_maintenance_identities'],
        'JOURNAL_CUSTODY_RETAINED_IDENTITIES')
    completion=frozen['coordinator_completion']
    validate_retained_custody(receipt['retained_custody'],implementation=implementation,
        nonce=marker['nonce'],source_files=manifest['sources'])
    require(manifest['custody_binding']==receipt['retained_custody']['binding'],'JOURNAL_CUSTODY_MANIFEST')
    validate_coordinator_completion(completion,receipt['retained_custody'])
    require(completion['receipt_sha256']==c.sha256(raw['receipt.json']),'JOURNAL_COORDINATOR_RECEIPT')
    require(receipt['state'] == 'VERIFIED' and receipt['reason'] == 'MAINTENANCE_COMPLETE'
        and receipt['last_step'] == 'VERIFIED' and receipt['started'] == sorted(h.STATES[1:])
        and receipt['marker_created'] is True and type(receipt['ssh_requests']) is int
        and receipt['ssh_requests'] == 2 and type(receipt['business_cases']) is int
        and receipt['business_cases'] == 0 and receipt['remote_exit'] == 'HELPER_REPORTED_COMPLETE'
        and receipt['production_supported'] is receipt['old_commitments_refunded']
        is receipt['exclusive_reservation_proven'] is False, 'JOURNAL_RECEIPT')
    events = [parse(line + b'\n',65536) for line in raw['events.jsonl'].splitlines()]
    starts = [row.get('step') for row in events if row.get('state') == 'STARTED']
    require(starts == ['CONSUMED','GUEST_QUIET','POWERED_OFF','POWER_OFF_TOKEN',
        'BACKED_UP','IMAGE_GROWN','BOOTED','FILESYSTEM_GROWN','VERIFIED'], 'JOURNAL_ORDER')
    returns = [row for row in events if row.get('state') == 'RETURNED']
    require([row.get('step') for row in returns] == list(h.STATES[1:]), 'JOURNAL_RETURN_ORDER')
    # Exactly sixteen ordered step records, two phase bindings and one poweroff token.
    expected_steps = []
    for step in h.STATES[1:]:
        expected_steps.append((step,'STARTED'))
        if step == 'POWERED_OFF': expected_steps.append(('POWER_OFF_TOKEN','STARTED'))
        expected_steps.append((step,'RETURNED'))
    require([(row['step'],row['state']) for row in events if 'step' in row] == expected_steps,
        'JOURNAL_STEP_SEQUENCE')
    phases=[row for row in events if 'phase' in row]
    require([row.get('phase') for row in phases] == ['pre','post'] and len(events) == 19,
        'JOURNAL_EVENT_COUNT')
    results = {row['step']:row['result'] for row in returns}
    for row in returns: c.exact(row, {'step','state','result'}, 'CORE_JOURNAL_EVENT')
    require(results['CONSUMED']==dict(manifest_sha256=marker['manifest_sha256']), 'JOURNAL_CONSUMED')
    for row in events:
        if row.get('state')=='STARTED':
            c.exact(row, {'step','state','pre_report_sha256'} if row['step']=='POWER_OFF_TOKEN'
                else {'step','state'}, 'CORE_JOURNAL_STARTED')
        elif 'phase' in row:
            c.exact(row, {'phase','argv_sha256','description_sha256','window_seconds','change_seconds'}, 'CORE_JOURNAL_PHASE')
    pre_lines=raw['pre.stdout'].splitlines(keepends=True)
    require(len(pre_lines) == 2, 'JOURNAL_PRE_STREAM')
    pre=parse(pre_lines[0],1048576); ack=parse(pre_lines[1],1048576)
    post=parse(raw['post.stdout'],1048576)
    desc=marker['pre_description']; g.descriptor(h.canonical(desc))
    require(desc['source_binding_sha256'] == c.sha256(h.canonical(frozen['source_binding']))
        and desc['saved_rows'] == frozen['saved_rows'] and desc['paths'] == frozen['paths']
        and desc['original_boot_id'] == frozen['boot_id'] and desc['nonce'] == marker['nonce'],
        'JOURNAL_DESCRIPTION')
    g.validate_pre_report(pre,desc)
    for field in ('window_seconds','change_seconds'):
        c.integer(phases[1][field],1,desc[field])
        require(phases[0][field]==desc[field],'JOURNAL_PHASE_WINDOW')
    post_desc=dict(desc,phase='post',pre_report=pre,pre_report_sha256=c.sha256(h.canonical(pre)),
        window_seconds=phases[1]['window_seconds'],change_seconds=phases[1]['change_seconds'])
    g.descriptor(h.canonical(post_desc))
    require(all(desc[key]==value for key,value in frozen['inventory'].items()),'JOURNAL_INVENTORY')
    g.validate_post_report(post,post_desc)
    require(results['GUEST_QUIET'] == pre and results['FILESYSTEM_GROWN'] == post
        and receipt['original_boot_id'] == pre['boot_id'] and receipt['new_boot_id'] == post['boot_id'],
        'JOURNAL_REPORT_BINDING')
    g.validate_startup_assurance(ack.get('guest_startup_assurance'))
    require(ack == dict(schema=g.REPORT_SCHEMA,session=JOURNAL_SESSION,status='POWER_OFF_REQUESTED',
        nonce=marker['nonce'],pre_report_sha256=c.sha256(h.canonical(pre)),
        guest_startup_assurance=g.guest_startup_assurance()), 'JOURNAL_POWEROFF_ACK')
    transports=(results['POWERED_OFF']['transport'],receipt['post_transport'])
    require(len(receipt['transports']) == 2, 'JOURNAL_TRANSPORTS')
    for index,(phase,transport) in enumerate(zip(('pre','post'),transports)):
        require(type(transport['returncode']) is int
            and transport['returncode'] in ((0,255) if phase=='pre' else (0,))
            and transport['eof'] == dict(stdout=True,stderr=True)
            and all(type(v) is bool for v in transport['eof'].values())
            and receipt['transports'][index]['exit'] == transport['returncode'], 'JOURNAL_EXIT')
        pins={stream:dict(bytes=len(raw[phase+'.'+stream]),sha256=c.sha256(raw[phase+'.'+stream]))
            for stream in ('stdout','stderr')}
        require(transport['files'] == receipt['transports'][index]['files'] == pins, 'JOURNAL_STREAM_PIN')
    require(transports[0]['ack'] == ack and transports[1]['ack'] is None
        and results['POWERED_OFF']['pidfd_exit'] is True, 'JOURNAL_TARGET_EXIT')
    # Original start.sh is pinned by qemu_argv; only the new pidfile and null serial differ.
    original,restart=manifest['original_argv'],manifest['restart_argv']
    require(type(original) is list and type(restart) is list and len(original) == len(restart)
        and all(type(word) is str for word in original+restart)
        and original.count('-pidfile') == original.count('-serial') == 1, 'JOURNAL_ARGV')
    pi,si=original.index('-pidfile')+1,original.index('-serial')+1
    from pathlib import PurePosixPath
    activation=frozen.get('vm_activation')
    anchor=frozen['anchor_path'] if activation else str(PurePosixPath(original[pi]).parent)
    require(original[pi] == (activation['pidfile'] if activation else anchor+'/vm.pid') and original[si].startswith('file:')
        and restart[pi] == anchor+'/.lhqjgrow-20261010d.vm.pid' and restart[si] == 'null'
        and [i for i,(a,b) in enumerate(zip(original,restart)) if a!=b] == sorted((pi,si)),
        'JOURNAL_RESTART_ARGV')
    # Reconstruct the expected original argv from the protected fixed input start script.
    require((original,restart) == h.qemu_argv(frozen['start_raw'],anchor,original[si][5:],activation=activation),
        'JOURNAL_ORIGINAL_START')
    for phase,phase_desc,row in zip(('pre','post'),(desc,post_desc),phases):
        argv=h.remote_argv(anchor,sources,phase_desc)
        require(row==dict(phase=phase,argv_sha256=c.sha256(h.canonical(argv)),
            description_sha256=c.sha256(h.canonical(phase_desc)),window_seconds=phase_desc['window_seconds'],
            change_seconds=phase_desc['change_seconds']), 'JOURNAL_PHASE_BINDING')
    require(marker['pre_command_sha256']==phases[0]['argv_sha256']
        and next(row for row in events if row.get('step')=='POWER_OFF_TOKEN')['pre_report_sha256']
            ==c.sha256(h.canonical(pre)), 'JOURNAL_POWER_TOKEN')
    require(manifest['image_commands']==h.image_commands(anchor+'/journal.qcow2',
        anchor+'/.lhqjgrow-20261010d.journal.backup.qcow2'),'JOURNAL_IMAGE_COMMANDS')
    old,new=manifest['vm'],receipt['new_vm']
    for value,argv in ((old,original),(new,restart)):
        c.exact(value, {'pid','starttime','argv_sha256'}, 'CORE_JOURNAL_VM')
        c.integer(value['pid'],2);c.integer(value['starttime'],1)
        require(value['argv_sha256'] == c.sha256(b'\0'.join(word.encode('ascii') for word in argv)+b'\0'),
            'JOURNAL_VM_ARGV')
    require(raw['vm.pid'].strip() == str(new['pid']).encode('ascii')
        and results['BOOTED']['process'] == new and results['BOOTED']['returncode'] == 0
        and results['BOOTED']['passive_wait_seconds'] == 60
        and receipt['image_identities'] == manifest['image_identities'], 'JOURNAL_NEW_VM')
    for stage,size in (('POWERED_OFF',268435456),('IMAGE_GROWN',536870912)):
        image=results[stage]['image'] if stage=='POWERED_OFF' else results[stage]
        h.validate_image_info(h.canonical(image['info']),size)
        require(all(image['check'].get(key,0)==0 for key in ('check-errors','corruptions','leaks'))
            and image['check_returncode']==0 and image['check_eof']==dict(stdout=True,stderr=True),
            'JOURNAL_IMAGE_CHECK')
    require(results['IMAGE_GROWN']['logical_compare']==dict(returncode=0,eof=dict(stdout=True,stderr=True)),
        'JOURNAL_LOGICAL_CONTENT')
    verified=results['VERIFIED']
    comparison=h.prior.compare(dict(rows=post['rows']),frozen['horizon'])
    require(verified==dict(comparison=comparison,tree=post['tree'],rows=post['rows'])
        and all(row[field]['deficit']==0 for row in comparison['pools'] for field in ('bytes','inodes')),
        'JOURNAL_CAPACITY')
    transport_pids=[row['pid'] for row in receipt['transports']]
    for pid in transport_pids:c.integer(pid,2,2147483647)
    require(len(set(transport_pids))==2,'JOURNAL_TRANSPORT_PID')
    matched=set()
    for process in receipt['processes']:
        pid=process['identity']['pid'];c.integer(pid,2,2147483647)
        expected=receipt['transports'][transport_pids.index(pid)]['exit'] if pid in transport_pids else 0
        require(type(process['vm']) is bool and type(process['exit']) is int
            and process['exit']==expected,'JOURNAL_PROCESS_EXIT')
        if pid in transport_pids:
            require(process['vm'] is False and pid not in matched,'JOURNAL_TRANSPORT_PROCESS')
            matched.add(pid)
    require(matched==set(transport_pids),'JOURNAL_TRANSPORT_PROCESS')
    backup=results['BACKED_UP'];c.exact(backup,{'bytes','sha256'},'CORE_JOURNAL_BACKUP')
    c.integer(backup['bytes'],1,320*1048576);c.digest(backup['sha256'])
    journal=next(row for row in post['rows'] if row['role']=='journal')
    value=dict(schema='local-hand-q2-core-journal-transition/v18', authority=expected_authority,
        persistent_source=copy.deepcopy(frozen['source_binding']['persistent_source']),
        local_preflight_source=copy.deepcopy(local_source),
        transport_failure_source=copy.deepcopy(failed_source),
        retained_custody=copy.deepcopy(receipt['retained_custody']),coordinator_completion=copy.deepcopy(completion),
        runtime_parent_binding=copy.deepcopy(frozen['runtime_parent_binding']),
        runtime_preparation={phase:g.runtime_summary(report) for phase,report in (('pre',pre),('post',post))},
        guest_startup_assurance=g.guest_startup_assurance(),
        previous_maintenance=previous, implementation=copy.deepcopy(implementation), session=JOURNAL_SESSION, nonce=marker['nonce'],
        access_mode='TRUSTED_SINGLE_ADMIN',host_writer_observation='NOT_PERFORMED',
        continuous_exclusion_proven=False, input_sha256=desc['source_binding_sha256'],
        manifest_sha256=marker['manifest_sha256'], source_files=manifest['sources'],
        originals=[dict(basename='.'+JOURNAL_SESSION+'.'+name,bytes=len(data),sha256=c.sha256(data))
            for name,data in sorted(raw.items())],
        old_boot_id=pre['boot_id'],new_boot_id=post['boot_id'],vm_activation=copy.deepcopy(activation),
        old_vm=old,new_vm=new,image_identities=manifest['image_identities'],old_pidfd_exited=True,
        original_argv_sha256=c.sha256(h.canonical(original)),restart_argv_sha256=c.sha256(h.canonical(restart)),
        backup=backup,virtual_bytes=dict(before=268435456,after=536870912),
        filesystem=dict(uuid=journal['filesystem']['uuid'],before_bytes=pre['journal_device']['superblock']['filesystem_bytes'],
            after_bytes=post['journal_device']['superblock']['filesystem_bytes'],available=journal['available']),
        content={key:post['tree'][key] for key in ('entries','content_bytes','sha256')},
        reports={phase:dict(bytes=len(h.canonical(report)),sha256=c.sha256(h.canonical(report)))
            for phase,report in (('pre',pre),('post',post))},
        completed_steps=list(h.STATES[1:]),transport_exits=[item['returncode'] for item in transports],
        image_checks=[results['POWERED_OFF']['image']['check_returncode'],results['IMAGE_GROWN']['check_returncode']],
        logical_compare_exit=results['IMAGE_GROWN']['logical_compare']['returncode'],
        resize_exit=post['resize_result']['returncode'], all_streams_eof=True,
        historical_exit='UNKNOWN', old_commitments_refunded=False)
    value['retained_identity']=dict(schema='lhq-retained-quota-identity/v1',
        source_plan_sha256=RETAINED_PLAN_SHA,roots_sha256=g.RETAINED_QUOTA_SHA,
        pre=copy.deepcopy(g.retained_sample(pre,desc)),post=copy.deepcopy(g.retained_sample(post,desc)),
        reports=copy.deepcopy(value['reports']))
    validate_journal_transition(value, priors=priors, implementation=implementation)
    return value


RUNTIME_BINDING_SHA="8593dcfdf2b169176b8f7025e392a9942589ee19d3cc9d3c04a5692a5f6ccd9b"
RUNTIME_SOURCES={
 "original_plan":"efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c",
 "retry_preparation":"586f0fd79ceb869a8e1ed238d925b6cdbf2cceaddf233687df81ea320bded4fb",
 "system_plan":"85633b837718282ba6590b7a6679d51aa60addfb0f5be39ea929af83de4a45c1",
 "q2_prepare.py":"763ac7a7fcfb59f534f5752767cb7b84791cd5538b693fed232248d24da1904b",
 "q2_prepare_contract.py":"dd2e459798edcfa73742ffea453dd54b81cfaa07cdac9700adf46752ab0af0c5"}
RUNTIME_ROLES=("controller","management","supervisor","query","ordinary","retained_ordinary")
def validate_runtime_binding(value):
 c.exact(value,{'schema','sources','account','parents','manager'})
 require(len(c.canonical(value,newline=True))<=8192 and
 c.sha256(c.canonical(value,newline=True))==RUNTIME_BINDING_SHA,'RUNTIME_BINDING_PIN')
 return value
def runtime_parent_binding(original,retry,system):
 """Project roles only from the already pin-verified original three documents."""
 parents,observed=original["parents"],retry["facts"]["parents"]
 account=original["account"]
 require(account==system["account"] and account["uid"]==account["gid"]==1100,"GROWTH_RUNTIME_SOURCE_ACCOUNT")
 rows={}
 for role in ("controller","management","supervisor","query","ordinary"):
  row=parents[role]
  require(all(observed[role][key]==value for key,value in row.items()),"GROWTH_RUNTIME_SOURCE_PARENT")
  if role!="ordinary":
   require(system["parents"][role]==row and observed[role]["path"]=="/"+row["unit"],"GROWTH_RUNTIME_SOURCE_SYSTEM")
  target="retained_ordinary" if role=="ordinary" else role
  rows[target]=dict(row,manager="user" if role=="ordinary" else "system",control_group=observed[role]["path"])
 retained=system["retained_ordinary_parent"]
 require(retained["path"]==observed["ordinary"]["path"],"GROWTH_RUNTIME_SOURCE_RETAINED")
 row=system["parents"]["ordinary"]
 rows["ordinary"]=dict(row,manager="system",control_group="/"+rows["controller"]["unit"]+"/"+row["unit"])
 manager=observed["manager"]
 require(manager["unit"]==manager["Id"] and manager["User"]=="1100" and manager["Delegate"]=="yes",
 "GROWTH_RUNTIME_SOURCE_MANAGER")
 value=dict(schema="lhq-runtime-parent-binding/v1",sources=dict(RUNTIME_SOURCES),account=account,parents=rows,
 manager=dict(unit=manager["unit"],control_group=manager["ControlGroup"],fragment=manager["FragmentPath"],
 dropins=manager["DropInPaths"].split()))
 return validate_runtime_binding(value)
def validate_runtime_summaries(value,binding,nonce,boots,reports):
 validate_runtime_binding(binding)
 require(type(value) is dict and set(value)=={"pre","post"},"GROWTH_RUNTIME_SUMMARIES")
 for phase,row in value.items():
  require(type(row) is dict and set(row)=={"schema","binding_sha256","nonce","phase","boot_id","report_sha256",
 "runtime_sha256","commands_sha256","configs_sha256","elapsed_ns","parents","manager","pools"}
 and row["schema"]=="lhq-runtime-transition/v1" and row["binding_sha256"]==c.sha256(c.canonical(binding,newline=True))
 and row["nonce"]==nonce and row["phase"]==phase and row["boot_id"]==boots[phase]
 and row["report_sha256"]==reports[phase]["sha256"],"GROWTH_RUNTIME_SUMMARY_BINDING")
  for name in ("runtime_sha256","commands_sha256","configs_sha256"):c.digest(row[name])
  c.integer(row["elapsed_ns"],0,60000000000)
  require(type(row["parents"]) is dict and set(row["parents"])==set(RUNTIME_ROLES),"GROWTH_RUNTIME_SUMMARY_PARENTS")
  for role,item in row["parents"].items():
   require(type(item) is dict and set(item)=={"unit","control_group","invocation_id","identity"}
 and all(item[key]==binding["parents"][role][key] for key in ("unit","control_group"))
 and re.fullmatch(r"[0-9a-f]{32}",item["invocation_id"] or ""),"GROWTH_RUNTIME_SUMMARY_PARENT")
   require(type(item["identity"]) is dict and set(item["identity"])=={'dev','ino','mode','uid','gid'},"GROWTH_RUNTIME_SUMMARY_IDENTITY")
   for v in item["identity"].values():c.integer(v)
  require(type(row["manager"]) is dict and set(row["manager"])=={"Id","ControlGroup","InvocationID"}
 and row["manager"]["Id"]==binding["manager"]["unit"] and row["manager"]["ControlGroup"]==binding["manager"]["control_group"]
 and re.fullmatch(r"[0-9a-f]{32}",row["manager"]["InvocationID"] or ""),"GROWTH_RUNTIME_SUMMARY_MANAGER")
  require(type(row["pools"]) is list and 1<=len(row["pools"])<=2,"GROWTH_RUNTIME_SUMMARY_POOLS")
  for pool in row["pools"]:
   require(type(pool) is dict and set(pool)=={"dev","reserved_bytes","reserved_inodes","before","after"}
 and pool["reserved_bytes"]==8192*(1 if phase=="pre" else 2)
 and pool["reserved_inodes"]==32*(1 if phase=="pre" else 2),"GROWTH_RUNTIME_SUMMARY_POOL")
   c.integer(pool["dev"])
   for key in ("before","after"):
    require(type(pool[key]) is list and len(pool[key])==2 and all(type(n) is int for n in pool[key])
 and pool[key][0]>=pool["reserved_bytes"] and pool[key][1]>=pool["reserved_inodes"],"GROWTH_RUNTIME_SUMMARY_CAPACITY")
 return value

def validate_retained_custody(value, *, implementation, nonce, source_files):
    check=lambda ok,reason:require(ok,'JOURNAL_'+reason)
    check(type(value) is dict and set(value)=={'schema','binding','pid','starttime','count','checks',
        'originals','ipc_bytes','cpu_nanoseconds','rss_bytes','state'},'CUSTODY_FIELDS')
    check(value['schema']=='lhq-retained-custody/v1' and value['state']=='HELD_UNTIL_TEARDOWN'
        and value['count']==55,'CUSTODY_SCHEMA')
    for name,low,high in (('pid',2,2147483647),('starttime',1,2**63-1),('checks',1,64),
        ('ipc_bytes',1,2097152),('cpu_nanoseconds',0,120000000000),('rss_bytes',1,536870912)):
        check(type(value[name]) is int and low<=value[name]<=high,'CUSTODY_BOUNDS')
    pins={'.'+row['session']+'.'+name:(size,digest) for row in previous_journal_profiles()
        for name,(size,digest) in row['pins'].items()}
    originals=value['originals']
    check(type(originals) is list and len(originals)==55,'CUSTODY_ORIGINALS')
    check([row['basename'] for row in originals]==list(pins),'CUSTODY_SET_ORDER')
    seen=set();owner=None
    for row in originals:
        check(type(row) is dict and set(row)=={'basename','metadata','bytes','sha256'}
            and (row['bytes'],row['sha256'])==pins[row['basename']],'CUSTODY_PIN')
        info=row['metadata']
        check(type(info) is dict and set(info)=={'dev','ino','mode','uid','gid','nlink','size','blocks','mtime_ns','ctime_ns'}
            and all(type(v) is int and v>=0 for v in info.values()),'CUSTODY_METADATA')
        check(info['mode']==33152 and info['nlink']==1 and info['uid']>0 and info['gid']>0
            and info['size']==row['bytes'],'CUSTODY_PROTECTION')
        key=(info['dev'],info['ino']);check(key not in seen,'CUSTODY_ALIAS');seen.add(key)
        current=(info['uid'],info['gid'],info['dev'])
        if owner is None:owner=current
        check(current==owner,'CUSTODY_OWNER')
    check(value['binding']==dict(D=implementation['commit'],nonce=nonce,
        source_sha256=source_files['q2_journal_retained_fds.py']['sha256'],
        history_sha256=c.sha256(c.canonical(maintenance_resume())+b'\n'),set_sha256=c.sha256(c.canonical(originals)+b'\n')),'CUSTODY_BINDING')
    return value


def validate_coordinator_completion(value, custody):
    check=lambda ok,reason:require(ok,'JOURNAL_'+reason)
    check(type(value) is dict and set(value)=={'returncode','receipt_sha256','child','usage'}
        and type(value['returncode']) is int and value['returncode']==0,'COORDINATOR_EXIT')
    check(type(value['receipt_sha256']) is str and re.fullmatch(r'[0-9a-f]{64}',value['receipt_sha256']) is not None,
        'COORDINATOR_RECEIPT')
    child=value['child'];usage=value['usage']
    check(type(child) is dict and set(child)=={'returncode','cpu_nanoseconds','rss_peak_bytes'}
        and type(child['returncode']) is int and child['returncode']==0,'CUSTODY_EXIT')
    check(type(usage) is dict and set(usage)=={'cpu_nanoseconds','rss_peak_bytes'},'COORDINATOR_USAGE')
    for key,low,high in (('cpu_nanoseconds',custody['cpu_nanoseconds'],120000000000),
        ('rss_peak_bytes',custody['rss_bytes'],536870912)):
        check(type(child[key]) is int and low<=child[key]<=high
            and type(usage[key]) is int and child[key]<=usage[key]<=high,'CUSTODY_FINAL_USAGE')
    return value


RETAINED_PLAN_SHA="efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c"
RETAINED_QUOTA_SHA="b782a2de862b038347d8b224ed55c3e9dff06179f901b06a2506fa542a0357d5"


def validate_retained_identity(value,reports):
    c.exact(value,{'schema','source_plan_sha256','roots_sha256','pre','post','reports'})
    require(value['schema']=='lhq-retained-quota-identity/v1'
        and value['source_plan_sha256']==RETAINED_PLAN_SHA and value['roots_sha256']==RETAINED_QUOTA_SHA
        and value['reports']==reports,'RETAINED_IDENTITY_SOURCE')
    for phase in ('pre','post'):
        c.exact(value[phase],{'count','sha256'})
        c.integer(value[phase]['count'],4,4);c.digest(value[phase]['sha256'])
    require(value['pre']==value['post'],'RETAINED_IDENTITY_DRIFT')
    return value


def validate_journal_transition(value, *, priors, implementation, current_boot=None):
    """Check the fixed host-verified projection; this does not reread host originals."""
    c.exact(value, {'schema','authority','implementation','session','nonce','access_mode',
        'host_writer_observation','continuous_exclusion_proven','input_sha256','manifest_sha256','runtime_parent_binding','runtime_preparation',
        'source_files','originals','old_boot_id','new_boot_id','vm_activation','old_vm','new_vm','image_identities',
        'old_pidfd_exited','original_argv_sha256','restart_argv_sha256','backup','virtual_bytes',
        'filesystem','content','reports','completed_steps','transport_exits','image_checks',
        'logical_compare_exit','resize_exit','all_streams_eof','historical_exit','old_commitments_refunded','previous_maintenance','guest_startup_assurance','retained_custody','coordinator_completion','local_preflight_source','transport_failure_source','persistent_source','retained_identity'},
        'CORE_JOURNAL_FIELDS')
    require(len(c.canonical(value)) <= 65536 and value['schema']=='local-hand-q2-core-journal-transition/v18'
        and value['session']=='lhqjgrow-20261010d', 'JOURNAL_SCHEMA')
    require(value['authority']==dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04',
        A=(c.PERSISTENT_PATH_BASELINE or {}).get('commit'),C=(c.PERSISTENT_PATH_CLOSURE or {}).get('commit'))
        and value['implementation']==implementation, 'JOURNAL_AUTHORITY')
    require(type(value['guest_startup_assurance']) is dict
        and c.canonical(value['guest_startup_assurance']) == c.canonical(dict(
            mode='TRUSTED_SINGLE_ADMIN',indirect_startup_observation='NOT_PERFORMED',
            undeclared_unit_inventory_observation='NOT_PERFORMED',
            no_undeclared_business_startup=True,continuous_exclusion_proven=False)),
        'GUEST_STARTUP_PREMISE')
    validate_retained_custody(value['retained_custody'],implementation=implementation,
        nonce=value['nonce'],source_files=value['source_files'])
    validate_coordinator_completion(value['coordinator_completion'],value['retained_custody'])
    validate_maintenance_resume(value['previous_maintenance'])
    validate_local_preflight_source(value['local_preflight_source'])
    validate_transport_failure_source(value['transport_failure_source'])
    validate_persistent_source(value['persistent_source'])
    validate_retained_identity(value['retained_identity'],value['reports'])
    validate_runtime_summaries(value['runtime_preparation'],value['runtime_parent_binding'],value['nonce'],
        dict(pre=value['old_boot_id'],post=value['new_boot_id']),value['reports'])
    c.exact(implementation,{'commit','tree'},'CORE_JOURNAL_IMPLEMENTATION')
    for item in implementation.values(): c.commit(item)
    require(value['access_mode']=='TRUSTED_SINGLE_ADMIN' and value['host_writer_observation']=='NOT_PERFORMED'
        and value['continuous_exclusion_proven'] is value['old_commitments_refunded'] is False
        and value['historical_exit']=='UNKNOWN', 'JOURNAL_ACCESS')
    for key in ('nonce','input_sha256','manifest_sha256','original_argv_sha256','restart_argv_sha256'):
        c.digest(value[key])
    for key in ('old_boot_id','new_boot_id'):
        require(type(value[key]) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value[key]),
            'JOURNAL_BOOT')
    activation=value['vm_activation']
    require(type(activation) is dict and activation.get('schema')=='local-hand-q2-vm-activation/v2',
        'CURRENT_GUEST_REQUIRED')
    if activation is not None:
        validate_vm_activation(activation)
        require(activation['current_boot_id']==value['old_boot_id'] and activation['vm']==value['old_vm']
            and activation['image_identities']==value['image_identities'], 'ACTIVATION_MAINTENANCE_BINDING')
    history_boot=activation['historical_boot_id'] if activation else value['old_boot_id']
    require(value['old_boot_id']!=value['new_boot_id']
        and all(hello['guest_boot_id']==history_boot for hello in validate_all(priors))
        and (current_boot is None or current_boot==value['new_boot_id']), 'JOURNAL_BOOT_BINDING')
    rows=value['originals']
    require(type(rows) is list and len(rows)==8 and [row.get('basename') for row in rows]
        == sorted('.lhqjgrow-20261010d.'+name for name in JOURNAL_FILES), 'JOURNAL_ORIGINALS')
    require(next(row['sha256'] for row in value['originals'] if row['basename'].endswith('.receipt.json'))
        ==value['coordinator_completion']['receipt_sha256'],'JOURNAL_COMPLETION_RECEIPT')
    for row in rows:
        c.exact(row,{'basename','bytes','sha256'},'CORE_JOURNAL_ORIGINAL')
        c.integer(row['bytes'],0,JOURNAL_FILES[row['basename'][len('.lhqjgrow-20261010d.'):]])
        c.digest(row['sha256'])
    c.exact(value['source_files'],JOURNAL_SOURCE_NAMES,'CORE_JOURNAL_SOURCES')
    for name,row in value['source_files'].items():
        c.exact(row,{'bytes','sha256'},'CORE_JOURNAL_SOURCE')
        c.integer(row['bytes'],1,16384 if name=='q2_journal_retained_fds.py' else 98304 if name.startswith('q2_journal_growth') else 524288);c.digest(row['sha256'])
    for key in ('old_vm','new_vm'):
        row=value[key];c.exact(row,{'pid','starttime','argv_sha256'},'CORE_JOURNAL_VM')
        c.integer(row['pid'],2);c.integer(row['starttime'],1);c.digest(row['argv_sha256'])
    require(value['old_vm']!=value['new_vm'] and value['old_pidfd_exited'] is True,'JOURNAL_VM_EXIT')
    images=value['image_identities'];c.exact(images,{'system','quota','journal','evidence','seed'},'CORE_JOURNAL_IMAGES')
    for row in images.values():
        require(type(row) in (list,tuple) and len(row)==2,'JOURNAL_IMAGE_IDENTITY')
        c.integer(row[0]);c.integer(row[1],1)
    require(len({tuple(row) for row in images.values()})==5,'JOURNAL_IMAGE_ALIAS')
    c.exact(value['backup'],{'bytes','sha256'},'CORE_JOURNAL_BACKUP')
    c.integer(value['backup']['bytes'],1,335544320);c.digest(value['backup']['sha256'])
    require(c.canonical(value['virtual_bytes'])==c.canonical(dict(before=268435456,after=536870912)),
        'JOURNAL_SIZE')
    fs=value['filesystem'];c.exact(fs,{'uuid','before_bytes','after_bytes','available'},'CORE_JOURNAL_FILESYSTEM')
    require(type(fs['uuid']) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',fs['uuid']),
        'JOURNAL_UUID')
    require(type(fs['before_bytes']) is type(fs['after_bytes']) is int
        and fs['before_bytes']==268435456 and fs['after_bytes']==536870912,'JOURNAL_FILESYSTEM_SIZE')
    c.exact(fs['available'],{'bytes','inodes'},'CORE_JOURNAL_CAPACITY')
    c.integer(fs['available']['bytes'],419430400);c.integer(fs['available']['inodes'],32768)
    content=value['content'];c.exact(content,{'entries','content_bytes','sha256'},'CORE_JOURNAL_CONTENT')
    c.integer(content['entries'],1,32768);c.integer(content['content_bytes'],0,268435456);c.digest(content['sha256'])
    c.exact(value['reports'],{'pre','post'},'CORE_JOURNAL_REPORTS')
    for row in value['reports'].values():
        c.exact(row,{'bytes','sha256'},'CORE_JOURNAL_REPORT');c.integer(row['bytes'],1,1048576);c.digest(row['sha256'])
    require(value['completed_steps']==['CONSUMED','GUEST_QUIET','POWERED_OFF','BACKED_UP','IMAGE_GROWN',
        'BOOTED','FILESYSTEM_GROWN','VERIFIED'] and value['all_streams_eof'] is True,'JOURNAL_COMPLETION')
    require(type(value['transport_exits']) is list and len(value['transport_exits'])==2
        and all(type(v) is int for v in value['transport_exits'])
        and value['transport_exits'][0] in (0,255) and value['transport_exits'][1]==0,'JOURNAL_TRANSPORT')
    require(c.canonical(value['image_checks'])==b'[0,0]' and type(value['logical_compare_exit']) is int
        and value['logical_compare_exit']==0 and type(value['resize_exit']) is int and value['resize_exit']==0,
        'JOURNAL_CHECKS')
    return value


def build_local_preflight_source(raw,spec):
    """Validate the fixed local failure archive; never import or execute old callers."""
    import io,tarfile
    c.exact(spec,{'path','bytes','sha256','freeze_sha256','callers'},'LOCAL_PREFLIGHT_SPEC')
    c.absolute_path(spec['path'],'LOCAL_PREFLIGHT_PATH')
    c.integer(spec['bytes'],1,131072);c.digest(spec['sha256']);c.digest(spec['freeze_sha256'])
    c.exact(spec['callers'],LOCAL_PREFLIGHT_CALLERS,'LOCAL_PREFLIGHT_CALLERS')
    for pin in spec['callers'].values():c.digest(pin)
    require(type(raw) is bytes and len(raw)==spec['bytes'] and c.sha256(raw)==spec['sha256'],
        'LOCAL_PREFLIGHT_ARCHIVE_PIN')
    files={};end=0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as archive:
            for member in archive:
                require(member.type in (tarfile.REGTYPE,tarfile.AREGTYPE)
                    and member.offset==end and raw[member.offset+257:member.offset+263]==b'ustar\0'
                    and not member.pax_headers and member.name not in files
                    and member.name in (*LOCAL_PREFLIGHT_PINS,*LOCAL_PREFLIGHT_RECORDS)
                    and 0<=member.size<=65536,'LOCAL_PREFLIGHT_MEMBER')
                with archive.extractfile(member) as stream:data=stream.read(65537)
                require(len(data)==member.size,'LOCAL_PREFLIGHT_MEMBER_BOUND')
                files[member.name]=data
                end=member.offset_data+(member.size+511)//512*512
        require(len(raw)%512==0 and len(raw)-end>=1024 and not any(raw[end:]),'LOCAL_PREFLIGHT_TRAILING')
    except (tarfile.TarError,ValueError,OSError) as error:
        raise c.ContractError('LOCAL_PREFLIGHT_ARCHIVE') from error
    c.exact(files,(*LOCAL_PREFLIGHT_PINS,*LOCAL_PREFLIGHT_RECORDS),'LOCAL_PREFLIGHT_ORIGINALS')
    pins={n:dict(bytes=len(b),sha256=c.sha256(b)) for n,b in files.items()}
    projection=dict(schema='local-hand-q2-local-preflight-source/v1',summary=local_preflight_summary(),
        archive={k:spec[k] for k in ('bytes','sha256')},originals=pins,
        freeze_sha256=spec['freeze_sha256'],callers=copy.deepcopy(spec['callers']))
    validate_local_preflight_source(projection)
    def parse(name):
        try: value=json.loads(files[name].decode('ascii'),object_pairs_hook=c._pairs,parse_constant=c._constant)
        except (UnicodeError,ValueError) as error:raise c.ContractError('LOCAL_PREFLIGHT_JSON') from error
        c._shape(value);require(type(value) is dict,'LOCAL_PREFLIGHT_JSON');return value
    freeze,result,gate=(parse(n) for n in LOCAL_PREFLIGHT_RECORDS)
    require(freeze['R']==c.RULE['commit'] and freeze['A']==c.HOST_FD_BASELINE['commit']
        and freeze['C']==c.HOST_FD_CLOSURE['commit'] and freeze['scope']==LOCAL_PREFLIGHT_SCOPE
        and freeze['state']=='FROZEN_FD1_VERIFIED' and freeze['implementation']==dict(
            commit=LOCAL_PREFLIGHT_D,tree='a20bf680b8f3d975248a91b251fc7502729b5f46')
        and freeze['callers']==spec['callers']
        and freeze['fd2']==dict(session=LOCAL_PREFLIGHT_SESSION,state='NOT_STARTED')
        and freeze['fd3']==dict(session='lhqcore-20261007a',state='NOT_RUN'),'LOCAL_PREFLIGHT_FREEZE')
    require(gate==dict(freeze,state='FD2_PREFLIGHT_FAILED_FD3_NOT_RUN',fd2=result),'LOCAL_PREFLIGHT_TERMINAL')
    require(result['D']==LOCAL_PREFLIGHT_D and result['session']==LOCAL_PREFLIGHT_SESSION
        and result['freeze_sha256']==spec['freeze_sha256']
        and result['state']=='PREFLIGHT_FAILED_STOP_AND_RETAIN'
        and result['retained']=={n:pins[n] for n in LOCAL_PREFLIGHT_PINS}
        and result['core_package']=='NOT_BUILT'
        and all(result[k]=='NOT_RUN' for k in ('FD3','H01','Q4','H11'))
        and result['reason']=='GROWTH_USAGE_UNKNOWN' and result['diagnostic']=={}
        and result['errno'] is None and result['error_type']=='ObservationError'
        and result['maintenance_marker_created'] is result['maintenance_actions_started'] is False
        and result['eleven_historical_generations_still_consumed'] is True
        and result['failed_sample_measurements']=='NOT_RETAINED'
        and result['process_identity']=='NOT_IDENTIFIED_BY_RETURN','LOCAL_PREFLIGHT_RESULT')
    for key,want in (('caller_invocations',1),('execute_invocations',0),('ssh_requests',0)):
        require(type(result[key]) is int and result[key]==want,'LOCAL_PREFLIGHT_COUNTS')
    started=parse('fd2-caller-started.json');summary=parse('fd2-summary.json');pre=parse('fd2-preflight.stdout')
    require(started==dict(D=LOCAL_PREFLIGHT_D,session=LOCAL_PREFLIGHT_SESSION)
        and files['fd2-caller.stdout']==files['fd2-summary.json']
        and files['fd2-caller.stderr']==files['fd2-preflight.stderr']==b'', 'LOCAL_PREFLIGHT_CALLER_RETURN')
    require(summary['D']==LOCAL_PREFLIGHT_D and summary['phase']=='preflight'
        and type(summary['exit_code']) is int and summary['exit_code']==3
        and pre['management_usage']==result['last_valid_management_usage'], 'LOCAL_PREFLIGHT_RETURN')
    for v in (pre,summary):
        require(v['state']=='BLOCKED' and v['reason']=='GROWTH_USAGE_UNKNOWN'
            and v['diagnostic']=={} and v['marker_created'] is False
            and type(v['ssh_requests']) is int and v['ssh_requests']==0
            and v['errno'] is None and v['error_type']=='ObservationError','LOCAL_PREFLIGHT_RETURN')
    return projection


def adopt_local_preflight(inputs,frozen,spec):
    # Inputs.read retains exactly one parent FD with all original path protections.
    c.exact(spec,{'path','bytes','sha256','freeze_sha256','callers'},'LOCAL_PREFLIGHT_SPEC')
    c.integer(spec['bytes'],1,131072)
    raw=inputs.read(spec['path'],spec['bytes'],spec['sha256'],'local_preflight_archive')
    value=build_local_preflight_source(raw,spec)
    frozen.update(local_preflight_raw=raw,local_preflight_spec=copy.deepcopy(spec))
    binding=frozen['source_binding'];binding['local_preflight_source']=value
    binding['sources']['local_preflight_archive']=copy.deepcopy(value['archive'])
    frozen['source_binding_sha256']=c.sha256(c.canonical(binding,newline=True))
    return value


def recheck_local_preflight(inputs,frozen,check):
    from . import q2_journal_growth as h
    spec=frozen['local_preflight_spec'];check()
    fd=next(fd for path,fd,_ in inputs.held if path==spec['path'])
    os.lseek(fd,0,os.SEEK_SET);raw,_=h.local.stable_read(fd,spec['bytes'],check)
    require(build_local_preflight_source(raw,spec)==frozen['source_binding']['local_preflight_source']
        and raw==frozen['local_preflight_raw'],'LOCAL_PREFLIGHT_SOURCE_DRIFT')
    inputs.recheck(check)


def build_transport_failure_source(raw,spec):
    """Read the fixed old10a archive without inventing a receipt or new evidence."""
    import io,tarfile
    c.exact(spec,{'path','bytes','sha256','freeze_sha256','callers','originals'},'TRANSPORT_FAILURE_SPEC')
    c.absolute_path(spec['path'],'TRANSPORT_FAILURE_PATH')
    c.integer(spec['bytes'],1,196608);c.digest(spec['sha256'])
    require(spec['freeze_sha256']==TRANSPORT_FAILURE_FREEZE,'TRANSPORT_FAILURE_FREEZE_PIN')
    c.exact(spec['originals'],TRANSPORT_FAILURE_MEMBERS,'TRANSPORT_FAILURE_ORIGINALS')
    require(type(raw) is bytes and len(raw)==spec['bytes'] and c.sha256(raw)==spec['sha256'],
        'TRANSPORT_FAILURE_ARCHIVE_PIN')
    files={};end=0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as archive:
            for member in archive:
                require(member.type in (tarfile.REGTYPE,tarfile.AREGTYPE)
                    and member.offset==end and raw[member.offset+257:member.offset+263]==b'ustar\0'
                    and not member.pax_headers and member.name not in files
                    and member.name in TRANSPORT_FAILURE_MEMBERS
                    and 0<=member.size<=65536,'TRANSPORT_FAILURE_MEMBER')
                with archive.extractfile(member) as stream:data=stream.read(65537)
                require(len(data)==member.size,'TRANSPORT_FAILURE_MEMBER_BOUND')
                files[member.name]=data
                end=member.offset_data+(member.size+511)//512*512
        require(len(raw)%512==0 and len(raw)-end>=1024 and not any(raw[end:]),'TRANSPORT_FAILURE_TRAILING')
    except (tarfile.TarError,ValueError,OSError) as error:
        raise c.ContractError('TRANSPORT_FAILURE_ARCHIVE') from error
    c.exact(files,TRANSPORT_FAILURE_MEMBERS,'TRANSPORT_FAILURE_ORIGINALS')
    pins={n:dict(bytes=len(data),sha256=c.sha256(data)) for n,data in files.items()}
    require(c.canonical(pins)==c.canonical(spec['originals']),'TRANSPORT_FAILURE_EXTERNAL_PINS')
    def parse(name):
        try:value=json.loads(files[name].decode('ascii'),object_pairs_hook=c._pairs,parse_constant=c._constant)
        except (UnicodeError,ValueError) as error:raise c.ContractError('TRANSPORT_FAILURE_JSON') from error
        c._shape(value);require(type(value) is dict,'TRANSPORT_FAILURE_JSON');return value
    freeze,result,gate=(parse(n) for n in TRANSPORT_FAILURE_RECORDS)
    prefix='.'+TRANSPORT_FAILURE_SESSION+'.'
    marker=parse(prefix+'consumed.json');manifest=marker['manifest'];desc=marker['pre_description']
    pre,execute,summary,started=(parse(n) for n in ('uc2-preflight.stdout','uc2-execute.stdout',
        'uc2-summary.json','uc2-caller-started.json'))
    diagnostic=execute['diagnostic']
    value=dict(schema='local-hand-q2-transport-failure-source/v1',summary=transport_failure_summary(),
        archive={k:spec[k] for k in ('bytes','sha256')},originals=pins,freeze_sha256=spec['freeze_sha256'],
        callers=copy.deepcopy(spec['callers']),diagnostic_sha256=c.sha256(c.canonical(diagnostic,newline=True)))
    validate_transport_failure_source(value)
    authority=value['summary']['authority'];old_D=TRANSPORT_FAILURE_D
    require(all(freeze[k]==authority[k] for k in authority)
        and freeze['scope']==value['summary']['scope'] and freeze['state']=='FROZEN_UC1_VERIFIED'
        and freeze['implementation']==dict(commit=old_D,tree=TRANSPORT_FAILURE_TREE)
        and freeze['callers']==spec['callers']
        and freeze['uc2']==dict(state='NOT_STARTED',session=TRANSPORT_FAILURE_SESSION)
        and freeze['uc3']==dict(state='NOT_RUN',session='lhqcore-20261007a'),'TRANSPORT_FAILURE_FREEZE')
    require(c.canonical(gate)==c.canonical(dict(freeze,state='UC2_CONSUMED_FAILED_UC3_NOT_RUN',uc2=result,
        uc3=dict(core_package='NOT_BUILT',reason='INCOMPLETE_UC2',state='NOT_RUN'))),'TRANSPORT_FAILURE_TERMINAL')
    require(result['state']=='UC2_CONSUMED_FAILED_UC3_NOT_RUN' and result['D']==old_D
        and result['session']==TRANSPORT_FAILURE_SESSION and result['frozen_sha256']==TRANSPORT_FAILURE_FREEZE
        and result['originals']=={n:pins[n] for n in TRANSPORT_FAILURE_ORIGINALS}
        and result['local_returns']=={n:pins[n] for n in TRANSPORT_FAILURE_RETURNS}
        and result['missing_expected']==value['summary']['missing_expected']
        and result['remote_exit']=='UNKNOWN' and result['coordinator_completion']=='NOT_CAPTURED'
        and result['core']=='NOT_RUN' and result['core_package']=='NOT_BUILT'
        and type(result['caller_exit']) is int and result['caller_exit']==3,'TRANSPORT_FAILURE_RESULT')
    require(started==dict(D=old_D,session=TRANSPORT_FAILURE_SESSION)
        and summary['D']==old_D and summary['phase']=='execute'
        and type(summary['exit_code']) is int and summary['exit_code']==3
        and result['returned_state']==execute['state']==summary['state']=='UNKNOWN'
        and result['diagnostic']==diagnostic==summary['diagnostic'],'TRANSPORT_FAILURE_RETURN')
    for row in (result,execute,summary):
        require(row['marker_created'] is True and type(row['ssh_requests']) is int and row['ssh_requests']==1
            and row['reason']=='GROWTH_USAGE_UNKNOWN','TRANSPORT_FAILURE_COUNTS')
    for row in (execute,summary):
        require(row['error_type']=='ObservationError' and row['errno'] is None,'TRANSPORT_FAILURE_ERROR')
    c.exact(diagnostic,{'complete','failed_children','live_children','operation','stage'},'TRANSPORT_FAILURE_DIAGNOSTIC')
    require(diagnostic['complete'] is False and diagnostic['operation']=='management_usage'
        and diagnostic['stage']=='live_child_observation' and type(diagnostic['live_children']) is int
        and diagnostic['live_children']==1 and type(diagnostic['failed_children']) is list
        and len(diagnostic['failed_children'])==1,'TRANSPORT_FAILURE_DIAGNOSTIC')
    failed=diagnostic['failed_children'][0]
    c.exact(failed,{'errno','error_type','identity','pid','reason','stage'},'TRANSPORT_FAILURE_CHILD')
    c.integer(failed['pid'],2,2147483647)
    require(failed['errno'] is None and failed['error_type']=='ObservationError'
        and failed['identity']==dict(argv_sha256=None,starttime=None)
        and failed['reason']=='GROWTH_USAGE_IDENTITY' and failed['stage']=='process_identity',
        'TRANSPORT_FAILURE_CHILD')
    require(pre['D']==old_D and pre['state']=='LOCAL_PREFLIGHT_PASSED' and pre['marker_created'] is False
        and all(type(pre[k]) is int and pre[k]==0 for k in ('ssh_requests','business_cases'))
        and pre['manifest']==manifest and pre['manifest_sha256']==marker['manifest_sha256']
        ==c.sha256(c.canonical(manifest,newline=True)),'TRANSPORT_FAILURE_PREFLIGHT')
    old_resume=dict(legacy_maintenance_resume(),scope='LH-Q2-CORE-USAGE-CONTINUATION-v1',session=TRANSPORT_FAILURE_SESSION)
    old_resume.pop('previous_transport_failure')
    old_resume.pop('previous_host_preflight')
    resume_sha=c.sha256(c.canonical(old_resume,newline=True));handoff=pre['preflight']
    require(manifest['schema']=='lhq-journal-growth-manifest/v14'
        and handoff['schema']=='lhq-journal-growth-preflight/v13'
        and c.canonical(manifest['resume'])==c.canonical(old_resume)
        and marker['resume_sha256']==handoff['resume_sha256']==resume_sha,'TRANSPORT_FAILURE_HISTORY')
    restored=copy.deepcopy(manifest['inputs'])
    require('resume' not in restored and restored.pop('resume_sha256',None)==resume_sha,'TRANSPORT_FAILURE_HISTORY')
    restored['resume']=old_resume
    require(restored['local_preflight_source']==freeze['local_preflight_source']
        and desc['source_binding_sha256']==c.sha256(c.canonical(restored,newline=True))
        and manifest['inventory_sha256']==restored['inventory_sha256'],'TRANSPORT_FAILURE_SOURCE')
    validate_local_preflight_source(restored['local_preflight_source'])
    require(all(manifest[k]==handoff[k]==authority[k] for k in authority)
        and marker['D']==manifest['D']==handoff['D']==old_D
        and marker['session']==desc['session']==TRANSPORT_FAILURE_SESSION
        and marker['nonce']==manifest['nonce']==handoff['nonce']==desc['nonce']
        and handoff['manifest_sha256']==marker['manifest_sha256']
        and pre['window_binding']==manifest['window_binding']==handoff['window_binding']==execute['window_binding']
        and marker['clocks']==pre['window_binding']['origins'],'TRANSPORT_FAILURE_BINDING')
    c.digest(marker['nonce'])
    for row in (manifest,marker):
        require(row['access_mode']=='TRUSTED_SINGLE_ADMIN' and row['host_writer_observation']=='NOT_PERFORMED'
            and row['continuous_exclusion_proven'] is False,'TRANSPORT_FAILURE_ACCESS')
    events=[c.document(line+b'\n',limit=65536,newline=True) for line in files[prefix+'events.jsonl'].splitlines()]
    require(c.canonical(events)==c.canonical([dict(step='CONSUMED',state='STARTED'),
        dict(step='CONSUMED',state='RETURNED',result=dict(manifest_sha256=marker['manifest_sha256'])),
        dict(step='GUEST_QUIET',state='STARTED'),dict(phase='pre',argv_sha256=marker['pre_command_sha256'],
            description_sha256=c.sha256(c.canonical(desc,newline=True)),window_seconds=desc['window_seconds'],
            change_seconds=desc['change_seconds'])]),'TRANSPORT_FAILURE_EVENTS')
    return value


def adopt_transport_failure(inputs,frozen,spec):
    # Caller opens this only after custody READY/identity/usage and FD handoff.
    c.exact(spec,{'path','bytes','sha256','freeze_sha256','callers','originals'},'TRANSPORT_FAILURE_SPEC')
    c.integer(spec['bytes'],1,196608)
    raw=inputs.read(spec['path'],spec['bytes'],spec['sha256'],'transport_failure_archive')
    value=build_transport_failure_source(raw,spec)
    frozen.update(transport_failure_raw=raw,transport_failure_spec=copy.deepcopy(spec))
    binding=frozen['source_binding'];binding['transport_failure_source']=value
    binding['sources']['transport_failure_archive']=copy.deepcopy(value['archive'])
    frozen['source_binding_sha256']=c.sha256(c.canonical(binding,newline=True))
    return value


def recheck_transport_failure(inputs,frozen,check):
    from . import q2_journal_growth as h
    spec=frozen['transport_failure_spec'];check()
    fd=next(fd for path,fd,_ in inputs.held if path==spec['path'])
    os.lseek(fd,0,os.SEEK_SET);raw,_=h.local.stable_read(fd,spec['bytes'],check)
    require(build_transport_failure_source(raw,spec)==frozen['source_binding']['transport_failure_source']
        and raw==frozen['transport_failure_raw'],'TRANSPORT_FAILURE_SOURCE_DRIFT')
    inputs.recheck(check)


# Current runtime identity is independently proven; the historical install is
# never edited to pretend it took place in this boot.
RESUMPTION_EVENT = 'LH-Q2-CORE-PROTECTED-SOURCE-CLOSURE-20261010-01'
STARTUP_EVENT = 'LH-Q1-VM-RESUME-20261010-01'
RESUMPTION_FIELDS = {'historical_activation_sha256', 'startup_evidence_sha256',
    'guest_evidence_sha256', 'previous_host_preflight', 'protected_source_evidence_sha256'}
STARTUP_FILES = ('control-flow-result-private.json','execution-freeze-private.json',
    'explicit-owner-approval-private.json','launch-consumed-private.json','listener.stderr','listener.stdout',
    'new-pid-cmdline.raw','new-pid-stat.raw','new-pidfile.raw','prepared-index-private.json',
    'protected-source/q2_sshd_source_capture.py','protected-source/q2_sshd_source_reader.py',
    'qemu-start.stderr','qemu-start.stdout','qemu-version.stderr','qemu-version.stdout',
    'result-private.json','start-once.py','start-proposal-private.json','started-private.json',
    'startup-caller.stderr','startup-caller.stdout')
HOST_PREFLIGHT_FILES = ('tc2-caller-started.json','tc2-preflight.stdout','tc2-preflight.stderr',
    'tc2-summary.json','tc2-caller.stdout','tc2-caller.stderr','freeze-complete.json',
    'tc2-failure-private.json','release-gate.json')
GUEST_VERIFICATION_FILES = ('check-approved.py','proposal.json','freeze.json','approval.json',
    'consumed.json','guest.stdout','guest.stderr','result.json','caller.stdout','caller.stderr')
GUEST_VERIFICATION_CAPS = {'check-approved.py':16384,'proposal.json':8192,'approval.json':4096,
    'freeze.json':4096,'consumed.json':4096,'guest.stdout':65536,'guest.stderr':65536,
    'result.json':8192,'caller.stdout':4096,'caller.stderr':4096}
RESUMPTION_MEMBERS = tuple('activation/'+n for n in (*ACTIVATION_FILES,'execution-return-index-private.json')) + tuple(
    'startup/'+n for n in (*STARTUP_FILES,'execution-return-index-private.json')) + tuple(
    'old10b/'+n for n in HOST_PREFLIGHT_FILES) + tuple('guest/'+n for n in GUEST_VERIFICATION_FILES)


RESUMPTION_REFERENCES = {
    'startup/protected-source/q2_sshd_source_capture.py': 'activation/protected-source/q2_sshd_source_capture.py',
    'startup/protected-source/q2_sshd_source_reader.py': 'activation/protected-source/q2_sshd_source_reader.py',
}
RESUMPTION_STORAGE_MEMBERS = tuple(n for n in RESUMPTION_MEMBERS if n not in RESUMPTION_REFERENCES)


def validate_protected_source_binding(authority, freeze):
    # Old local failure stays outside the archive and the maintenance custodian.
    # These pins bind the offline retention check, not continuous FD ownership.
    failure=authority['previous_guest_failure'];prep=authority['source_preparation']
    require(failure==freeze['previous_guest_failure'] and prep==freeze['source_preparation'],
        'PROTECTED_SOURCE_APPROVAL_BINDING')
    c.exact(failure,{'event','D','state','reason','ssh_calls','marker_created',
        'guest_streams','remote_exit','index','freeze','terminal'},'PREVIOUS_GUEST_FAILURE')
    require(failure['event']==c.RESUMED_VM_OWNER_DECISION['event']
        and failure['D']=='0eece27637930dfc31f724c7dd1392e11a47cad9'
        and failure['state']=='INVOKED_FAILED_UNCONSUMED' and failure['reason']=='LOCAL_PARENT'
        and type(failure['ssh_calls']) is int and failure['ssh_calls']==0
        and failure['marker_created'] is False and failure['guest_streams']=='ABSENT'
        and failure['remote_exit']=='UNKNOWN','PREVIOUS_GUEST_FAILURE')
    for name in ('index','freeze','terminal'):
        c.exact(failure[name],{'bytes','sha256'},'PREVIOUS_GUEST_PIN')
        c.integer(failure[name]['bytes'],1,65536);c.digest(failure[name]['sha256'])
    pins=freeze['source_pins']
    c.exact(pins,{*JOURNAL_SOURCE_NAMES,'q2_current_guest_verification.py'},'PROTECTED_SOURCE_NAMES')
    for pin in pins.values():
        c.exact(pin,{'bytes','sha256'},'PROTECTED_SOURCE_PIN')
        c.integer(pin['bytes'],1,1048576);c.digest(pin['sha256'])
    c.exact(prep,{'state','source_index_sha256','source_bytes','allocated_bytes','inodes',
        'cpu_nanoseconds','rss_peak_bytes','elapsed_nanoseconds'},'SOURCE_PREPARATION')
    require(prep['state']=='PREPARED' and prep['source_index_sha256']==c.sha256(c.canonical(pins))
        and prep['source_bytes']==sum(pin['bytes'] for pin in pins.values()),'SOURCE_PREPARATION_BINDING')
    c.integer(prep['source_bytes'],1,1048576)
    c.integer(prep['allocated_bytes'],prep['source_bytes'],1048576);c.integer(prep['inodes'],15,32)
    c.integer(prep['cpu_nanoseconds'],1,120000000000)
    c.integer(prep['rss_peak_bytes'],1,536870912);c.integer(prep['elapsed_nanoseconds'],1,120000000000)
    return c.sha256(c.canonical(dict(previous_guest_failure=failure,source_preparation=prep)))


def host_preflight_summary():
    return dict(session='lhqjgrow-20261010b',D='776b9810ec07ed8e1d37d4a740eeff5190c1c15c',
        state='PREFLIGHT_FAILED',phase='preflight',reason='GROWTH_ACTIVATION_HOST_BOOT',
        invoked=True,window_consumed=False,ssh_requests=0,marker_created=False,
        execute='NOT_CALLED',core='NOT_RUN',old_commitments_refunded=False)


def _resume_json(raw, limit=262144):
    require(type(raw) is bytes and len(raw)<=limit, 'RESUME_INPUT_BOUND')
    def pairs(items):
        require(len(dict(items))==len(items),'RESUME_DUPLICATE_KEY')
        return dict(items)
    try:
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,
            parse_constant=lambda _:require(False,'RESUME_JSON_CONSTANT'))
    except (ValueError,UnicodeError,RecursionError) as error:
        raise c.ContractError('RESUME_JSON') from error
    # Retained startup originals contain elapsed-time floats. Accept only finite
    # JSON numbers here; the outgoing core protocol still forbids all floats.
    def shape(item, depth=0):
        import math
        require(depth<=48,'RESUME_JSON_DEPTH')
        if isinstance(item,dict):
            require(len(item)<=4096,'RESUME_JSON_WIDTH')
            for child in item.values():shape(child,depth+1)
        elif isinstance(item,list):
            require(len(item)<=4096,'RESUME_JSON_WIDTH')
            for child in item:shape(child,depth+1)
        elif isinstance(item,float):require(math.isfinite(item),'RESUME_JSON_FLOAT')
    shape(value)
    require(type(value) is dict,'RESUME_DOCUMENT')
    return value


def _resume_pins(files):
    return {name:dict(bytes=len(raw),sha256=c.sha256(raw)) for name,raw in sorted(files.items())}


def _resume_process(vm, argv, raw_stat, raw_cmdline, *, canonical_digest=False):
    require(type(argv) is list and all(type(s) is str and s.isascii() for s in argv),'RESUME_ARGV')
    raw=b'\0'.join(s.encode('ascii') for s in argv)+b'\0'
    require(raw_cmdline==raw and vm['argv_sha256']==c.sha256(
        json.dumps(argv,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')+b'\n'
        if canonical_digest else raw),'RESUME_PROCESS_ARGV')
    c.integer(vm['pid'],2);c.integer(vm['starttime'],1)
    tail=raw_stat.rpartition(b') ')[2].split()
    require(raw_stat.startswith(str(vm['pid']).encode()+b' (') and len(tail)>19
        and tail[19].isdigit() and int(tail[19])==vm['starttime'],'RESUME_PROCESS_START')
    return dict(pid=vm['pid'],starttime=vm['starttime'],argv_sha256=c.sha256(raw))


def _resume_startup(files, historical):
    c.exact(files,(*STARTUP_FILES,'execution-return-index-private.json'),'RESUME_STARTUP_FILES')
    doc=lambda name:_resume_json(files[name])
    index=doc('execution-return-index-private.json');result=doc('result-private.json')
    proposal=doc('start-proposal-private.json');authority=doc('explicit-owner-approval-private.json')
    freeze=doc('execution-freeze-private.json');launch=doc('launch-consumed-private.json')
    pin=lambda name:_resume_pins({name:files[name]})[name]
    require(index['files']==_resume_pins({n:files[n] for n in STARTUP_FILES}),'RESUME_STARTUP_INDEX')
    require(all(v['event']==STARTUP_EVENT for v in (index,result,authority,freeze,launch))
        and proposal['event']=='LH-Q1-VM-RESUME-PROPOSAL-20261010-01', 'RESUME_STARTUP_EVENT')
    require(authority['state']=='APPROVED' and authority['owner_reply']=='批准'
        and type(authority['startup_attempts']) is int and authority['startup_attempts']==1
        and type(authority['ssh_attempts']) is int and authority['ssh_attempts']==0,
        'RESUME_STARTUP_AUTHORITY')
    require(authority['proposal_sha256']==freeze['proposal_sha256']==launch['proposal_sha256']==pin('start-proposal-private.json')['sha256']
        and authority['source_sha256']==pin('start-once.py')['sha256']
        and freeze['approval_sha256']==launch['authority_sha256']==pin('explicit-owner-approval-private.json')['sha256'],
        'RESUME_STARTUP_FREEZE')
    nonruntime=index['nonruntime_test_source_reference']
    require(nonruntime['name']=='check_control_flow.py' and nonruntime['not_reread_or_executed'] is True,
        'RESUME_STARTUP_NONRUNTIME')
    for name,row in freeze['files'].items():
        require(row==(nonruntime['preparation_pin'] if name=='check_control_flow.py' else pin(name)),
            'RESUME_STARTUP_SOURCE')
    require(result['state']==index['result_state']=='STARTED_AND_HOST_ENDPOINT_VERIFIED'
        and result['startup_calls']==1 and type(result['startup_calls']) is int
        and result['ssh_calls']==0 and type(result['ssh_calls']) is int
        and result['listener_queries']==1 and result['listener']=='PRESENT'
        and result['errors']==[] and result['original_system_and_old_serial_preserved'] is True
        and result['guest_boot_id']==result['guest_ssh_ready']=='UNKNOWN','RESUME_STARTUP_RESULT')
    checks=result['identity_checks']
    require(len(checks)==49 and all(row['actual']==row['expected'] and row['differences']=={} for row in checks),
        'RESUME_STARTUP_IDENTITIES')
    commands=result['commands']
    require([row['label'] for row in commands]==['qemu-version','qemu-start','listener']
        and all(row['eof'] is True and type(row['returncode']) is int and row['returncode']==0 for row in commands)
        and all(files[n]==b'' for n in ('qemu-version.stderr','qemu-start.stderr','listener.stderr','startup-caller.stderr')),
        'RESUME_STARTUP_COMMANDS')
    argv=proposal['proposed_argv'];old=list(proposal['original_argv'])
    old[old.index('-serial')+1]='file:'+proposal['output_directory']+'/console.log'
    old[old.index('-pidfile')+1]=proposal['output_directory']+'/vm.pid'
    require(argv==old==launch['argv'] and result['host_boot_id']==proposal['host_boot_id']==launch['host_boot_id'],
        'RESUME_STARTUP_BINDING')
    require(result['new_vm']['namespace']==proposal['network_namespace'],'RESUME_STARTUP_NAMESPACE')
    vm=_resume_process(result['new_vm'],argv,files['new-pid-stat.raw'],files['new-pid-cmdline.raw'],canonical_digest=True)
    require(files['new-pidfile.raw'].strip()==str(vm['pid']).encode(),'RESUME_PIDFILE')
    images=result['images_before'];c.exact(images,{'system','quota','journal','evidence','seed','original_system'},'RESUME_IMAGES')
    expected=dict(historical['image_identities'],original_system=historical['original_system_identity'])
    require({name:[row['metadata']['dev'],row['metadata']['ino']] for name,row in images.items()}==expected
        and images==proposal['images'] and launch['image_bindings']==images,
        'RESUME_IMAGE_BINDING')
    require(images['system']['path']==historical['system_path']
        and 'if=none,id=os,format=qcow2,file='+historical['system_path'] in argv,'RESUME_SYSTEM_IMAGE')
    return proposal,result,vm


def _resume_host_preflight(files):
    c.exact(files,HOST_PREFLIGHT_FILES,'RESUME_PREFLIGHT_FILES')
    doc=lambda name:_resume_json(files[name],65536)
    frozen=doc('freeze-complete.json');failed=doc('tc2-failure-private.json');gate=doc('release-gate.json')
    expected=host_preflight_summary();summary=doc('tc2-summary.json');preflight=doc('tc2-preflight.stdout')
    require(files['tc2-summary.json']==files['tc2-caller.stdout']
        and files['tc2-preflight.stderr']==files['tc2-caller.stderr']==b'','RESUME_PREFLIGHT_STREAMS')
    require(doc('tc2-caller-started.json')==dict(D=expected['D'],session=expected['session']), 'RESUME_PREFLIGHT_START')
    require(frozen['implementation']['commit']==expected['D']
        and failed['frozen_sha256']==c.sha256(files['freeze-complete.json'])
        and failed['session']==expected['session'] and failed['D']==expected['D']
        and failed['originals']=={} and failed['maintenance_window_consumed'] is False
        and failed['core']=='NOT_RUN' and failed['coordinator_completion']=='NOT_CAPTURED'
        and failed['core_package']=='NOT_BUILT' and failed['caller_exit']==3
        and failed['remote_exit']=='UNKNOWN','RESUME_PREFLIGHT_FAILURE')
    expected_returns={name:_resume_pins(files)[name] for name in HOST_PREFLIGHT_FILES[:6]}
    require(failed['local_returns']==expected_returns,'RESUME_PREFLIGHT_PINS')
    for row in (failed,summary,preflight):
        require(row['reason']==expected['reason'] and row['ssh_requests']==0
            and type(row['ssh_requests']) is int and row['marker_created'] is False
            and row['diagnostic']=={},'RESUME_PREFLIGHT_FACTS')
    require(summary['state']==preflight['state']=='BLOCKED' and summary['phase']=='preflight'
        and summary['D']==expected['D'] and summary['exit_code']==3 and summary['started'] is None
        and summary['last_step'] is None and summary['business_cases'] is None, 'RESUME_PREFLIGHT_RETURN')
    # The terminal gate may shorten its frozen preparation fields, but must
    # retain the exact frozen caller/source bindings and actual terminal result.
    require(gate['state']==failed['state']=='TC2_PREFLIGHT_FAILED_TC3_NOT_RUN'
        and gate['tc2']==failed and gate['tc3']==dict(core_package='NOT_BUILT',reason='INCOMPLETE_TC2',state='NOT_RUN'),
        'RESUME_PREFLIGHT_TERMINAL')
    for key in ('implementation','callers'):
        require(gate[key]==frozen[key],'RESUME_PREFLIGHT_FROZEN')
    return expected


def current_guest_commands(package, mountpoint):
    name=package['Package'];version=package['Version']
    require(type(name) is str and re.fullmatch(r'linux-modules-extra-[0-9][a-zA-Z0-9.+-]*',name)
        and type(version) is str and re.fullmatch(r'[a-zA-Z0-9.+:~_-]+',version),'RESUME_PACKAGE_NAME')
    c.absolute_path(mountpoint,'RESUME_QUOTA_TARGET')
    return [('kernel',['uname','-r']),
        ('installed-package',['dpkg-query','-W','-f=${Status}\t${Version}',name]),
        ('package-integrity',['dpkg','--verify',name]),
        ('module-vermagic',['modinfo','-F','vermagic','quota_v2']),
        ('module-resolution',['modprobe','--show-depends','quota_v2']),
        ('quota-mount',['findmnt','--json','--mountpoint',mountpoint,'-o','UUID,FSTYPE,OPTIONS'])]


def validate_current_guest(value, *, package, quota, nonce):
    c.exact(value,{'schema','status','nonce','boot_id','boot_end','steps','package_install_calls',
        'module_load_calls','reboots','management_usage'},'RESUME_GUEST_FIELDS')
    require(value['schema']=='local-hand-q2-current-guest/v1' and value['status']=='VERIFIED'
        and value['nonce']==nonce and value['boot_id']==value['boot_end']
        and type(value['boot_id']) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['boot_id']),
        'RESUME_GUEST_IDENTITY')
    for key in ('package_install_calls','module_load_calls','reboots'):
        require(type(value[key]) is int and value[key]==0,'RESUME_GUEST_MUTATION')
    steps=value['steps'];commands=current_guest_commands(package,quota['target'])
    require(type(steps) is list and len(steps)==len(commands),'RESUME_GUEST_COMMANDS')
    for row,(label,argv) in zip(steps,commands):
        c.exact(row,{'label','argv','exit','stdout','stderr','eof'},'RESUME_GUEST_STEP')
        require(row['label']==label and row['argv']==argv and type(row['exit']) is int
            and row['exit']==0 and row['eof'] is True and row['stderr']==''
            and type(row['stdout']) is str and len(row['stdout'].encode())<=16384,'RESUME_GUEST_STEP')
    kernel=steps[0]['stdout'].strip()
    require(package['Package']=='linux-modules-extra-'+kernel
        and steps[1]['stdout'].strip()=='install ok installed\t'+package['Version']
        and steps[2]['stdout']=='' and steps[3]['stdout'].startswith(kernel+' '),'RESUME_GUEST_PACKAGE')
    modules=steps[4]['stdout'].splitlines()
    require(modules and all(re.fullmatch(r'insmod /(?:usr/)?lib/modules/'+re.escape(kernel)+r'/[a-zA-Z0-9_./-]+\.ko(?:\.(?:zst|xz|gz))?\s*',s) for s in modules)
        and any('/quota_v2.ko' in s for s in modules),'RESUME_GUEST_MODULES')
    mounts=_resume_json(steps[5]['stdout'].encode(),16384)['filesystems']
    require(type(mounts) is list and len(mounts)==1,'RESUME_GUEST_MOUNT')
    mount=mounts[0]
    require(all(mount.get(k)==quota[k] for k in ('fstype','uuid'))
        and mount['fstype']=='ext4' and {'rw','nodev','nosuid','noexec','prjquota'}<=set(mount['options'].split(',')),
        'RESUME_GUEST_QUOTA')
    usage=value['management_usage'];c.exact(usage,{'cpu_nanoseconds','rss_peak_bytes','elapsed_nanoseconds'},'RESUME_GUEST_USAGE')
    for key,limit in (('cpu_nanoseconds',120000000000),('rss_peak_bytes',512*1048576),('elapsed_nanoseconds',120000000000)):
        c.integer(usage[key],1,limit,'RESUME_GUEST_USAGE')
    return value


def build_vm_resumption(files, index_raw, *, historical_boot):
    c.exact(files,RESUMPTION_MEMBERS,'RESUME_FILES')
    index=_resume_json(index_raw,65536)
    c.exact(index,{'schema','event','files','references','guest_caller_completion'},'RESUME_INDEX_FIELDS')
    require(index['schema']=='local-hand-q2-vm-resumption-sources/v1' and index['event']==RESUMPTION_EVENT
        and index['files']==_resume_pins(files) and index['references']==RESUMPTION_REFERENCES
        and all(files[name]==files[target] for name,target in RESUMPTION_REFERENCES.items()),'RESUME_INDEX')
    group=lambda prefix:{name[len(prefix)+1:]:raw for name,raw in files.items() if name.startswith(prefix+'/')}
    old=group('activation');old_index=old.pop('execution-return-index-private.json')
    historical=build_vm_activation(old,old_index,historical_boot=historical_boot)
    startup=group('startup');start,result,vm=_resume_startup(startup,historical)
    preflight=_resume_host_preflight(group('old10b'))
    guest=group('guest')
    require(all(type(guest[n]) is bytes and len(guest[n])<=cap for n,cap in GUEST_VERIFICATION_CAPS.items()),'RESUME_GUEST_FILE_BOUND')
    doc=lambda name:_resume_json(guest[name],GUEST_VERIFICATION_CAPS[name])
    proposal=doc('proposal.json');freeze=doc('freeze.json');authority=doc('approval.json')
    marker=doc('consumed.json');returned=doc('result.json')
    pin=lambda name:_resume_pins({name:guest[name]})[name]
    old_proposal=_resume_json(old['activation-proposal-private.json'])
    old_guest=_resume_json(old['ssh-install.stdout'])
    old_result=_resume_json(old['result-private.json'])
    quota=dict(_resume_json(old_guest['steps'][2]['stdout'].encode())['filesystems'][0])
    mount_argv=old_guest['steps'][2]['argv']
    require(mount_argv==old_guest['steps'][8]['argv'] and mount_argv[:3]==['findmnt','--json','--mountpoint']
        and mount_argv[4:]==['-o','UUID,FSTYPE,OPTIONS'],'RESUME_OLD_QUOTA_COMMAND')
    quota['target']=mount_argv[3]
    require(proposal['historical_activation_sha256']==c.sha256(c.canonical(historical))
        and proposal['startup_index_sha256']==c.sha256(startup['execution-return-index-private.json'])
        and proposal['host_preflight_index_sha256']==c.sha256(c.canonical(_resume_pins(group('old10b'))))
        and proposal['expected_host_boot_id']==result['host_boot_id']
        and proposal['expected_vm']==result['new_vm'] and proposal['package']==old_proposal['package']
        and proposal['quota']==quota
        and proposal['ssh_prefix']==old_result['commands'][-1]['argv'][:-1], 'RESUME_GUEST_PROPOSAL')
    implementation=proposal['implementation'];c.exact(implementation,{'commit','tree'},'RESUME_IMPLEMENTATION')
    for value in implementation.values():c.commit(value)
    c.digest(proposal['guest_source_sha256'])
    require(freeze['implementation']==returned['implementation']==implementation
        and returned['guest_source_sha256']==proposal['guest_source_sha256'],'RESUME_SOURCE_BINDING')
    require(all(row['event']==RESUMPTION_EVENT for row in (proposal,freeze,authority,marker,returned))
        and authority['owner_reply']=='批准' and authority['A']==c.PROTECTED_SOURCE_BASELINE['commit']
        and authority['C']==c.PROTECTED_SOURCE_CLOSURE['commit'] and authority['R']==c.RULE['commit']
        and authority['state']=='APPROVED','RESUME_GUEST_AUTHORITY')
    protected_sha=validate_protected_source_binding(authority,freeze)
    require(freeze['source_pins']['q2_current_guest_verification.py']['sha256']==proposal['guest_source_sha256'],
        'RESUME_GUEST_SOURCE_PIN')
    require(freeze['proposal']==pin('proposal.json') and freeze['caller']==pin('check-approved.py')
        and freeze['approval']==pin('approval.json') and marker['freeze_sha256']==pin('freeze.json')['sha256']
        and returned['marker_sha256']==pin('consumed.json')['sha256'], 'RESUME_GUEST_FREEZE')
    c.digest(marker['nonce'])
    require(c.canonical(index['guest_caller_completion'])==c.canonical(dict(returncode=0,stdout_eof=True,stderr_eof=True,stdout=pin('caller.stdout'),stderr=pin('caller.stderr'))),'RESUME_CALLER_EXIT')
    require(doc('caller.stdout')==dict(event=RESUMPTION_EVENT,state='CURRENT_GUEST_VERIFIED',result_sha256=pin('result.json')['sha256']), 'RESUME_CALLER_COMPLETION')
    require(c.canonical([returned[k] for k in ('startup_calls','package_install_calls','retries')])==b'[0,0,0]', 'RESUME_GUEST_COUNTS')
    usage=returned['management_usage'];c.exact(usage,{'cpu_nanoseconds','rss_peak_bytes'},'RESUME_HOST_USAGE')
    c.integer(usage['cpu_nanoseconds'],1,120000000000);c.integer(usage['rss_peak_bytes'],1,536870912)
    require(returned['state']=='CURRENT_GUEST_VERIFIED' and returned['nonce']==marker['nonce']
        and returned['ssh_calls']==1 and type(returned['ssh_calls']) is int
        and returned['startup_calls']==returned['package_install_calls']==returned['retries']==0
        and returned['guest_returncode']==0 and type(returned['guest_returncode']) is int
        and returned['guest_eof'] is True and returned['errors']==[]
        and returned['guest_stdout']==pin('guest.stdout') and returned['guest_stderr']==pin('guest.stderr')
        and guest['guest.stderr']==guest['caller.stderr']==b'', 'RESUME_GUEST_COMPLETION')
    require(returned['host_before']==returned['host_after']==dict(boot_id=result['host_boot_id'],vm=result['new_vm'])
        and returned['image_identities']==dict(historical['image_identities'],original_system=historical['original_system_identity']),
        'RESUME_GUEST_HOST_BINDING')
    current=validate_current_guest(doc('guest.stdout'),package=proposal['package'],quota=quota,nonce=marker['nonce'])
    require(current['boot_id']!=historical['current_boot_id'] and returned['guest_boot_id']==current['boot_id'],
        'RESUME_GUEST_BOOT_CHANGE')
    value=dict(historical,schema='local-hand-q2-vm-activation/v2',event=RESUMPTION_EVENT,
        current_boot_id=current['boot_id'],host_boot_id=result['host_boot_id'],vm=vm,
        pidfile=start['output_directory']+'/vm.pid',serial=start['output_directory']+'/console.log',
        index=dict(bytes=len(index_raw),sha256=c.sha256(index_raw)),evidence_sha256=c.sha256(c.canonical(_resume_pins(files))),
        historical_activation_sha256=c.sha256(c.canonical(historical)),
        startup_evidence_sha256=c.sha256(startup['execution-return-index-private.json']),
        guest_evidence_sha256=c.sha256(c.canonical(_resume_pins(guest))),previous_host_preflight=preflight,
        protected_source_evidence_sha256=protected_sha)
    return validate_vm_activation(value)


def activation_archive_files(raw):
    """Read only the fixed USTAR namespace; never extract paths to disk."""
    import io,tarfile
    require(type(raw) is bytes and 0<len(raw)<=524288,'RESUME_ARCHIVE_BOUND')
    permitted=set(ACTIVATION_FILES)|set(RESUMPTION_STORAGE_MEMBERS)|{'execution-return-index-private.json'}
    files={};end=0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as archive:
            for member in archive:
                require(member.type in (tarfile.REGTYPE,tarfile.AREGTYPE)
                    and member.offset==end and raw[member.offset+257:member.offset+263]==b'ustar\0'
                    and not member.pax_headers and not member.linkname and member.name not in files
                    and member.name in permitted and 0<=member.size<=262144,'RESUME_ARCHIVE_MEMBER')
                with archive.extractfile(member) as stream:data=stream.read(262145)
                require(len(data)==member.size,'RESUME_ARCHIVE_MEMBER_BOUND')
                end=member.offset_data+(member.size+511)//512*512
                require(not any(raw[member.offset_data+member.size:end]),'RESUME_ARCHIVE_PADDING')
                files[member.name]=data
        require(len(raw)%512==0 and len(raw)-end>=1024 and not any(raw[end:]),'RESUME_ARCHIVE_TRAILING')
    except (tarfile.TarError,ValueError,OSError) as error:
        raise c.ContractError('RESUME_ARCHIVE') from error
    require(set(files) in (set(ACTIVATION_FILES)|{'execution-return-index-private.json'},
        set(RESUMPTION_STORAGE_MEMBERS)|{'execution-return-index-private.json'}),'RESUME_ARCHIVE_FILES')
    if 'activation/activate-approved.py' in files:
        index=_resume_json(files['execution-return-index-private.json'],65536)
        require(index.get('references')==RESUMPTION_REFERENCES,'RESUME_ARCHIVE_REFERENCES')
        for name,target in RESUMPTION_REFERENCES.items():files[name]=files[target]
    return files


PERSISTENT_ARCHIVE_BYTES = 522240
PERSISTENT_INNER = 'prior/activation-retained-input.tar'
PERSISTENT_OLD_SESSION = 'lhqjgrow-20261010c'
PERSISTENT_ORIGINALS = tuple('.'+PERSISTENT_OLD_SESSION+'.'+n for n in
    ('consumed.json','events.jsonl','pre.stderr','pre.stdout','receipt.json'))
PERSISTENT_RECORDS = ('ps3-maintenance-originals-index-private.json','ps1-freeze.json',
    'release-gate.json','rc3-summary.json','ps3-field-review-private.json')
PERSISTENT_MEMBERS = (PERSISTENT_INNER,*( 'old10c/'+n for n in
    (*PERSISTENT_ORIGINALS,*PERSISTENT_RECORDS)), 'continuation-index-private.json')


def validate_persistent_source(value):
    c.exact(value,{'schema','archive','index_sha256','records_sha256','predecessor','summary'},
        'PERSISTENT_SOURCE_FIELDS')
    require(value['schema']=='local-hand-q2-persistent-continuation-archive/v1'
        and c.canonical(value['summary'])==c.canonical(persistent_failure_summary()),'PERSISTENT_SOURCE_SUMMARY')
    c.exact(value['archive'],{'bytes','sha256'},'PERSISTENT_ARCHIVE_PIN')
    require(type(value['archive']['bytes']) is int and value['archive']['bytes']==PERSISTENT_ARCHIVE_BYTES,
        'PERSISTENT_ARCHIVE_BOUND')
    for digest in (value['archive']['sha256'],value['index_sha256'],value['records_sha256']):c.digest(digest)
    reference=value['predecessor']
    c.exact(reference,{'member','marker','field','resume_sha256'},'PERSISTENT_REFERENCE_FIELDS')
    require(reference['member']=='old10c/.'+PERSISTENT_OLD_SESSION+'.consumed.json'
        and reference['field']=='manifest.resume'
        and reference['resume_sha256']==c.sha256(c.canonical(legacy_maintenance_resume(),newline=True)),
        'PERSISTENT_REFERENCE_TARGET')
    c.exact(reference['marker'],{'bytes','sha256'},'PERSISTENT_MARKER_PIN')
    c.integer(reference['marker']['bytes'],1,65536);c.digest(reference['marker']['sha256'])
    return value


def persistent_archive_files(raw):
    """One fixed envelope, one existing archive reader; never extract to disk."""
    import io,tarfile
    require(type(raw) is bytes and len(raw)==PERSISTENT_ARCHIVE_BYTES<=524288,'PERSISTENT_ARCHIVE_BOUND')
    files={};end=0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as archive:
            for number,member in enumerate(archive):
                require(number<len(PERSISTENT_MEMBERS) and member.name==PERSISTENT_MEMBERS[number]
                    and member.type in (tarfile.REGTYPE,tarfile.AREGTYPE) and not member.linkname
                    and not member.pax_headers and member.offset==end
                    and raw[member.offset+257:member.offset+263]==b'ustar\0'
                    and 0<=member.size<=(348160 if member.name==PERSISTENT_INNER else 65536),
                    'PERSISTENT_ARCHIVE_MEMBER')
                with archive.extractfile(member) as stream:data=stream.read(member.size+1)
                require(len(data)==member.size,'PERSISTENT_ARCHIVE_SIZE')
                end=member.offset_data+(member.size+511)//512*512
                require(not any(raw[member.offset_data+member.size:end]),'PERSISTENT_ARCHIVE_PADDING')
                files[member.name]=data
        require(tuple(files)==PERSISTENT_MEMBERS and len(raw)-end>=1024 and not any(raw[end:]),
            'PERSISTENT_ARCHIVE_TRAILING')
    except (tarfile.TarError,OSError,ValueError) as error:
        raise c.ContractError('PERSISTENT_ARCHIVE') from error
    index=c.document(files['continuation-index-private.json'],limit=65536,newline=True)
    c.exact(index,{'files'},'PERSISTENT_INDEX_FIELDS')
    pins=_resume_pins({n:b for n,b in files.items() if n!='continuation-index-private.json'})
    require(c.canonical(index['files'])==c.canonical(pins),'PERSISTENT_INDEX_PINS')
    return files,pins


def build_persistent_source(raw):
    files,pins=persistent_archive_files(raw)
    old={n:files['old10c/'+n] for n in (*PERSISTENT_ORIGINALS,*PERSISTENT_RECORDS)}
    doc=lambda name:_resume_json(old[name],65536)
    marker=doc(PERSISTENT_ORIGINALS[0]);receipt=doc(PERSISTENT_ORIGINALS[-1]);manifest=marker['manifest']
    legacy=legacy_maintenance_resume()
    authority=dict(R=c.RULE['commit'],A=c.PROTECTED_SOURCE_BASELINE['commit'],C=c.PROTECTED_SOURCE_CLOSURE['commit'])
    for row in (manifest,receipt):
        require({k:row[k] for k in authority}==authority and row['D']==persistent_failure_summary()['D'],
            'PERSISTENT_OLD_AUTHORITY')
        require(c.canonical(row['resume'])==c.canonical(legacy),'PERSISTENT_OLD_HISTORY')
    require(manifest['schema']=='lhq-journal-growth-manifest/v17'
        and receipt['schema']=='lhq-journal-growth-receipt/v17','PERSISTENT_OLD_SCHEMA')
    inputs=copy.deepcopy(manifest['inputs'])
    require('resume' not in inputs and inputs.pop('resume_sha256')==c.sha256(c.canonical(legacy,newline=True)),
        'PERSISTENT_OLD_REFERENCE')
    inputs['resume']=copy.deepcopy(legacy)
    require(marker['manifest_sha256']==receipt['manifest_sha256']==c.sha256(c.canonical(manifest,newline=True))
        and marker['pre_description']['source_binding_sha256']==c.sha256(c.canonical(inputs,newline=True))
        and marker['resume_sha256']==c.sha256(c.canonical(legacy,newline=True))
        and marker['session']==receipt['session']==marker['pre_description']['session']==PERSISTENT_OLD_SESSION
        and marker['D']==receipt['D'] and marker['nonce']==manifest['nonce']==receipt['nonce']
        and marker['clocks']==receipt['clock_origins_ns']==manifest['window_binding']['origins'],
        'PERSISTENT_OLD_BINDING')
    require(receipt['state']==receipt['last_step']=='STOP_AND_RETAIN'
        and receipt['reason']=='GROWTH_REPORT_MISSING' and receipt['remote_exit']=='UNKNOWN'
        and receipt['marker_created'] is True and type(receipt['ssh_requests']) is int
        and receipt['ssh_requests']==1 and receipt['started']==['CONSUMED','GUEST_QUIET']
        and old['.'+PERSISTENT_OLD_SESSION+'.pre.stdout']==b'', 'PERSISTENT_OLD_FAILURE')
    events=[_resume_json(line) for line in old['.'+PERSISTENT_OLD_SESSION+'.events.jsonl'].splitlines()]
    require([e['step'] for e in events if e.get('state')=='STARTED']==['CONSUMED','GUEST_QUIET']
        and [e['step'] for e in events if e.get('state')=='RETURNED']==['CONSUMED']
        and [e.get('phase') for e in events if 'phase' in e]==['pre'],'PERSISTENT_OLD_EVENTS')
    guest=doc('.'+PERSISTENT_OLD_SESSION+'.pre.stderr')
    require(guest['schema']=='lhq-journal-growth-guest/v4' and guest['session']==PERSISTENT_OLD_SESSION
        and guest['phase']=='pre' and guest['status']=='INCOMPLETE'
        and guest['stage']=='PRE_RUNTIME_PREPARATION' and guest['reason']=='GROWTH_GUEST_IO_OR_RUNTIME',
        'PERSISTENT_OLD_GUEST')
    idx=doc(PERSISTENT_RECORDS[0]);freeze=doc('ps1-freeze.json');terminal=doc('release-gate.json')
    require(idx['event']==c.PROTECTED_SOURCE_OWNER_DECISION['event'] and idx['session']==PERSISTENT_OLD_SESSION
        and idx['files']=={n:dict(bytes=len(old[n]),sha256=c.sha256(old[n])) for n in PERSISTENT_ORIGINALS}
        and idx['absent']==['.'+PERSISTENT_OLD_SESSION+'.'+n for n in
            ('post.stdout','post.stderr','vm.pid','journal.backup.qcow2')], 'PERSISTENT_OLD_INDEX')
    for record in (freeze,terminal):
        require({k:record[k] for k in authority}==authority
            and record['implementation']['commit']==receipt['D']
            and record['scope']==c.PROTECTED_SOURCE_SCOPE,'PERSISTENT_OLD_FREEZE')
    require(freeze['state']=='FROZEN_PS1_VERIFIED' and freeze['rc3']['state']=='NOT_ISSUED'
        and terminal['state']=='PS3_MAINTENANCE_CONSUMED_FAILED_CORE_NOT_RUN'
        and terminal['callers']==freeze['callers'],'PERSISTENT_OLD_TERMINAL')
    complete=terminal['rc3']['coordinator_completion']
    require(type(complete['returncode']) is int and complete['returncode']==3
        and type(complete['child']['returncode']) is int and complete['child']['returncode']==0
        and complete['receipt_sha256']==c.sha256(old[PERSISTENT_ORIGINALS[-1]])
        and terminal['rc3']['originals_index']==pins['old10c/'+PERSISTENT_RECORDS[0]],'PERSISTENT_OLD_COMPLETION')
    for key,cap in (('cpu_nanoseconds',120000000000),('rss_peak_bytes',536870912)):
        c.integer(complete['child'][key],1,cap)
        c.integer(complete['usage'][key],complete['child'][key],cap)
    summary=doc('rc3-summary.json');review=doc('ps3-field-review-private.json')
    require(summary['exit_code']==3 and type(summary['exit_code']) is int
        and summary['state']=='STOP_AND_RETAIN' and summary['reason']==receipt['reason']
        and summary['marker_created'] is True and summary['ssh_requests']==1
        and review['freeze_sha256']==pins['old10c/ps1-freeze.json']['sha256']
        and all(review[k]=='NOT_RUN' for k in ('H01','Q4','H11')),'PERSISTENT_OLD_RETURN')
    source=dict(schema='local-hand-q2-persistent-continuation-archive/v1',
        archive=dict(bytes=len(raw),sha256=c.sha256(raw)),
        index_sha256=c.sha256(files['continuation-index-private.json']),records_sha256=c.sha256(c.canonical(pins)),
        predecessor=dict(member='old10c/'+PERSISTENT_ORIGINALS[0],marker=pins['old10c/'+PERSISTENT_ORIGINALS[0]],
            field='manifest.resume',resume_sha256=c.sha256(c.canonical(legacy,newline=True))),
        summary=persistent_failure_summary())
    validate_persistent_source(source)
    activation_files=activation_archive_files(files[PERSISTENT_INNER])
    activation=build_vm_activation({n:b for n,b in activation_files.items()
        if n!='execution-return-index-private.json'},activation_files['execution-return-index-private.json'],
        historical_boot=freeze['historical_boot_id'])
    require(activation==terminal['vm_activation']==inputs['vm_activation']
        and activation['current_boot_id']==receipt['original_boot_id']==marker['pre_description']['original_boot_id']
        and activation['vm']==manifest['vm'] and activation['image_identities']==manifest['image_identities'],
        'PERSISTENT_OLD_ACTIVATION')
    return source,activation_files,copy.deepcopy(manifest['resume'])


def adopt_persistent_vm(inputs,frozen,spec):
    from . import q2_journal_growth as h
    h.require(type(spec) is dict and set(spec)=={'path','bytes','sha256'},'GROWTH_ACTIVATION_SPEC')
    h.prior.r.path_value(spec['path']);h.prior.r.integer(spec['bytes'],1,524288)
    raw=inputs.read(spec['path'],spec['bytes'],spec['sha256'],'vm_activation_archive')
    try:source,files,previous=build_persistent_source(raw)
    except c.ContractError as error:raise h.prior.r.ObservationError('GROWTH_ACTIVATION_ARCHIVE') from error
    index=files.pop('execution-return-index-private.json')
    activation=build_vm_activation(files,index,historical_boot=frozen['boot_id'])
    frozen.update(vm_activation=activation,activation_files=files,activation_index=index,activation_archive=spec,
        persistent_raw=raw,persistent_predecessor=previous)
    frozen['source_binding'].update(vm_activation=activation,persistent_source=source)
    frozen['source_binding']['sources']['vm_activation_archive']=source['archive']
    frozen['boot_id']=activation['current_boot_id']
    frozen['source_binding_sha256']=h.digest(h.canonical(frozen['source_binding']))
    h.validate_q1_frozen(frozen)
    return activation


def validate_persistent_frozen(frozen):
    source,files,previous=build_persistent_source(frozen['persistent_raw'])
    index=files.pop('execution-return-index-private.json')
    require(source==frozen['source_binding']['persistent_source']
        and source['archive']==frozen['source_binding']['sources']['vm_activation_archive']
        and files==frozen['activation_files'] and index==frozen['activation_index']
        and previous==frozen['persistent_predecessor'],'PERSISTENT_FROZEN_BINDING')
    return source


def make_growth_preflight(commit,manifest,window,nonce,usage,*,resume):
 from . import q2_journal_growth as h
 value=dict(schema="lhq-journal-growth-preflight/v17",R=h.R,A=h.PP_A,C=h.PP_C,D=commit,manifest_sha256=manifest,
window_binding=window,nonce=nonce,usage=usage,window_seconds=900,change_seconds=780,resume_sha256=h.resume_sha256(resume))
 return parse_growth_preflight(h.canonical(value))
def parse_growth_preflight(raw):
 from . import q2_journal_growth as h
 value=h.prior.r.parse(raw,4096)
 h.require(type(value) is dict and set(value)=={"schema","R","A","C","D","manifest_sha256","window_binding",
"nonce","usage","window_seconds","change_seconds","resume_sha256"} and value["schema"]=="lhq-journal-growth-preflight/v17",
"GROWTH_PREFLIGHT_SCHEMA")
 h.require(value["R"]==h.R and value["A"]==h.PP_A and value["C"]==h.PP_C,"GROWTH_PREFLIGHT_AUTHORITY")
 h.require(type(value["D"]) is str and re.fullmatch("[0-9a-f]{40}",value["D"]),"GROWTH_PREFLIGHT_D")
 for field in ("manifest_sha256","nonce","resume_sha256"):
  h.require(type(value[field]) is str and re.fullmatch("[0-9a-f]{64}",value[field]),"GROWTH_PREFLIGHT_DIGEST")
 h.require(value["window_seconds"]==900 and type(value["window_seconds"]) is int
and value["change_seconds"]==780 and type(value["change_seconds"]) is int,"GROWTH_PREFLIGHT_DEADLINE")
 h.require(value["resume_sha256"]==h.resume_sha256(maintenance_resume()),"GROWTH_PREFLIGHT_HISTORY")
 usage=value["usage"]
 h.require(type(usage) is dict and set(usage)=={"cpu_nanoseconds","rss_peak_bytes"},"GROWTH_PREFLIGHT_USAGE")
 for key,cap in (("cpu_nanoseconds",120000000000),("rss_peak_bytes",512*h.MIB)):
  h.require(type(usage[key]) is int and 0<usage[key]<=cap,"GROWTH_PREFLIGHT_USAGE")
 window=value["window_binding"]
 h.require(type(window) is dict and set(window)=={"boot_id","origins"}
and type(window["origins"]) is list and len(window["origins"])==2
and all(type(x) is int and x>0 for x in window["origins"]),"GROWTH_PREFLIGHT_WINDOW")
 from e3_host.q2_journal_growth_guest import uuid_value
 uuid_value(window["boot_id"])
 return value

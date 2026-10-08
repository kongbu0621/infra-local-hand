"""Fixed consumed F1 preimages for the separately approved next acceptance.

Historical UNKNOWN is retained. The fixed current host capacity condition is
not a complete bill or a reservation. No quiescence or generic prior inputs.
"""
from __future__ import annotations

import base64
import copy
import re
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
        dict(session_id=c.SESSION_ID,bytes=c.LIMITS['host_capture_bytes'],
             inodes=c.LIMITS['host_capture_inodes'])]


def _capacity_record(binding, prior, diagnostic, journal, implementation, origins, observation, capacity, device_capacity):
    return dict(schema='local-hand-q2-core-host-capacity-condition/v10',
        scope=c.GS_SCOPE, session_id=c.SESSION_ID,
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
    require(capacity['required_bytes'] == sum(row['bytes'] for row in rows) == 9579790336
            and capacity['required_inodes'] == sum(row['inodes'] for row in rows) == 2606
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
            and usage['required_bytes']==9579790336 and usage['required_inodes']==2606
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
    images=maintenance.ImageSet(directory_fd,anchor['path'],marker['manifest']['restart_argv'],deadline.check)
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
            version=7, stage='PRE_QUIESCENCE', reason='GROWTH_INDIRECT_STARTUP_UNVERIFIED'))


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


def maintenance_resume():
    return dict(scope=c.GS_SCOPE, session='lhqjgrow-20261008d',
        previous_maintenance=[dict(session=row['session'], D=row['D'], authority=row['authority'],
            originals=[dict(basename='.'+row['session']+'.'+name, bytes=size, sha256=sha)
                       for name,(size,sha) in row['pins'].items()],
            state='STOP_AND_RETAIN', stage=row['stage'], reason=row['reason'],
            remote_exit='UNKNOWN', window_consumed=True) for row in previous_journal_profiles()])


def maintenance_commitments():
    return dict(previous_maintenance=maintenance_resume(),
        generations=[dict(session=session,bytes=1296*1048576,inodes=370,cpu_seconds=120)
            for session in (PREVIOUS_JOURNAL_SESSION,SECOND_JOURNAL_SESSION,THIRD_JOURNAL_SESSION,FOURTH_JOURNAL_SESSION,FIFTH_JOURNAL_SESSION,SIXTH_JOURNAL_SESSION,'lhqjgrow-20261008d')],
        released_or_refunded=False)


def validate_maintenance_resume(value):
    require(type(value) is dict and c.canonical(value)==c.canonical(maintenance_resume()),
        'JOURNAL_PREVIOUS_SUMMARY')
    return value


def build_previous_maintenance(files):
    """Consume all six exact failed generations under their original schemas and authority."""
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
        and receipt['reason']=='GROWTH_REPORT_MISSING'
        and receipt['started']==['CONSUMED','GUEST_QUIET'] and receipt['marker_created'] is True
        and type(receipt['ssh_requests']) is int and receipt['ssh_requests']==1
        and type(receipt['business_cases']) is int and receipt['business_cases']==0
        and receipt['remote_exit']=='UNKNOWN' and receipt['old_commitments_refunded'] is False,
        'JOURNAL_PREVIOUS_FAILURE')
    failure=parse(files[prefix+'pre.stderr'])
    require(files[prefix+'pre.stdout']==b'' and failure['schema']=='lhq-journal-growth-guest/v1'
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


JOURNAL_SESSION = 'lhqjgrow-20261008d'
JOURNAL_FILES = {'consumed.json': 65536, 'events.jsonl': 1048576,
    'pre.stdout': 1048576, 'pre.stderr': 1048576, 'post.stdout': 1048576,
    'post.stderr': 1048576, 'receipt.json': 65536, 'vm.pid': 64}
JOURNAL_SOURCE_NAMES = ('q2_journal_growth.py', 'q2_journal_growth_guest.py',
    'q2_core_capacity_capture.py', 'q2_core_capacity_reader.py', 'q2_sshd_source_capture.py',
    'q2_sshd_source_reader.py', 'q2_core_obligation_inputs.py', 'q2_core_prior_attempt.py',
    'q2_core_delivery_contract.py', 'q2_local_source_delivery.py', 'q2_core_approved_inputs.py',
    'q2_host_kernel_facts.py')


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


def build_journal_transition(files, *, implementation, sources, frozen, priors):
    """Consume all K2 originals and fixed inputs before projecting a new boot.

    The source-aware freezer separately ties `sources` to implementation Git
    blobs. Guest checks this bounded projection, not unseen original files.
    """
    from . import q2_journal_growth as h
    from . import q2_journal_growth_guest as g
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
        'budget','management_usage','resume','guest_startup_assurance'}, 'CORE_JOURNAL_RECEIPT_FIELDS')
    require(receipt['serial_capture']=='NOT_CAPTURED_NULL_BACKEND','JOURNAL_SERIAL')
    usage=receipt['management_usage'];c.exact(usage,{'cpu_nanoseconds','rss_peak_bytes'},'CORE_JOURNAL_USAGE')
    c.integer(usage['cpu_nanoseconds'],1,120000000000);c.integer(usage['rss_peak_bytes'],1,536870912)
    budget=receipt['budget'];c.exact(budget,{'logical_bytes','allocated_bytes','inodes'},'CORE_JOURNAL_BUDGET')
    c.integer(budget['logical_bytes'],1,8388608);c.integer(budget['allocated_bytes'],1,8388608)
    c.integer(budget['inodes'],7,32)
    c.exact(marker, {'manifest_sha256', 'manifest', 'nonce', 'clocks', 'session', 'D',
        'access_mode', 'host_writer_observation', 'continuous_exclusion_proven',
        'pre_command_sha256', 'post_command_derivation', 'pre_description', 'resume','guest_startup_assurance'}, 'CORE_JOURNAL_MARKER')
    manifest = marker['manifest']
    c.exact(manifest, {'schema','R','A','C','D','nonce','access_mode','host_writer_observation',
        'continuous_exclusion_proven','historical_authority','inputs','window_binding',
        'inventory_sha256','retained_sha256','sources','tools','vm','image_identities',
        'original_argv','restart_argv','image_commands','protocol','resume','guest_startup_assurance'}, 'CORE_JOURNAL_MANIFEST')
    c.exact(frozen['capacity_files'],{'.lhqcap-20261006a.'+name for name in CAPACITY_DIAGNOSTIC_PINS},
        'CORE_JOURNAL_CAPACITY_ORIGINALS')
    for name,(size,digest) in CAPACITY_DIAGNOSTIC_PINS.items():
        data=frozen['capacity_files']['.lhqcap-20261006a.'+name]
        require(type(data) is bytes and (len(data),c.sha256(data))==(size,digest),'JOURNAL_CAPACITY_PIN')
    saved=h.prior.validate_result(frozen['capacity_files']['.lhqcap-20261006a.stdout'],
        c.sha256(sources['q2_core_capacity_reader.py']),frozen['description'])['rows']
    require(saved==frozen['saved_rows'],'JOURNAL_SAVED_ROWS')
    expected_authority = dict(R=h.R, A=c.GS_BASELINE['commit'], C=c.GS_CLOSURE['commit'])
    require(manifest['schema'] == 'lhq-journal-growth-manifest/v8'
        and receipt['schema'] == 'lhq-journal-growth-receipt/v8', 'JOURNAL_SCHEMA')
    for value in (manifest, receipt):
        require({key:value[key] for key in expected_authority} == expected_authority, 'JOURNAL_AUTHORITY')
    previous=build_previous_maintenance(frozen['previous_maintenance_files'])
    for value in (manifest, marker, receipt, frozen['source_binding']):
        validate_maintenance_resume(value['resume'])
        require(c.canonical(value['resume'])==c.canonical(previous),'JOURNAL_PREVIOUS_BINDING')
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
        manifest['window_binding'],marker['nonce'],usage,resume=manifest['resume'])
    require(manifest['historical_authority']==dict(A=h.A,C=h.C,observer_superseded_by=h.MINIMAL_A,minimal_C=h.MINIMAL_C,serial_A=h.SERIAL_A,serial_C=h.SERIAL_C,systemctl_A=h.SYSTEMCTL_A,systemctl_C=h.SYSTEMCTL_C,template_A=h.TEMPLATE_A,template_C=h.TEMPLATE_C,names_A=h.NAMES_A,names_C=h.NAMES_C,exec_A=h.EXEC_A,exec_C=h.EXEC_C)
        and manifest['protocol']=='two fixed phases; post bound to the durably saved pre report; no probe or retry'
        and marker['post_command_derivation']=='same fixed sources; post descriptor bound to saved canonical pre report',
        'JOURNAL_PROTOCOL')
    c.digest(manifest['retained_sha256'])
    g.validate_startup_assurance(frozen.get('guest_startup_assurance'))
    g.validate_startup_assurance(frozen['source_binding'].get('guest_startup_assurance'))
    require(manifest['inputs'] == frozen['source_binding']
        and manifest['inventory_sha256'] == c.sha256(h.canonical(frozen['inventory']))
        and manifest['sources'] == {name:dict(bytes=len(data),sha256=c.sha256(data))
            for name,data in sources.items()}, 'JOURNAL_INPUT_SOURCE')
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
    anchor=str(PurePosixPath(original[pi]).parent)
    require(original[pi] == anchor+'/vm.pid' and original[si].startswith('file:')
        and restart[pi] == anchor+'/.lhqjgrow-20261008d.vm.pid' and restart[si] == 'null'
        and [i for i,(a,b) in enumerate(zip(original,restart)) if a!=b] == sorted((pi,si)),
        'JOURNAL_RESTART_ARGV')
    # Reconstruct the expected original argv from the protected fixed input start script.
    require((original,restart) == h.qemu_argv(frozen['start_raw'],anchor,original[si][5:]),
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
        anchor+'/.lhqjgrow-20261008d.journal.backup.qcow2'),'JOURNAL_IMAGE_COMMANDS')
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
    for process in receipt['processes']:
        require(type(process['vm']) is bool and type(process['exit']) is int and process['exit']==0,
            'JOURNAL_PROCESS_EXIT')
    backup=results['BACKED_UP'];c.exact(backup,{'bytes','sha256'},'CORE_JOURNAL_BACKUP')
    c.integer(backup['bytes'],1,320*1048576);c.digest(backup['sha256'])
    journal=next(row for row in post['rows'] if row['role']=='journal')
    value=dict(schema='local-hand-q2-core-journal-transition/v7', authority=expected_authority,
        guest_startup_assurance=g.guest_startup_assurance(),
        previous_maintenance=previous, implementation=copy.deepcopy(implementation), session=JOURNAL_SESSION, nonce=marker['nonce'],
        access_mode='TRUSTED_SINGLE_ADMIN',host_writer_observation='NOT_PERFORMED',
        continuous_exclusion_proven=False, input_sha256=desc['source_binding_sha256'],
        manifest_sha256=marker['manifest_sha256'], source_files=manifest['sources'],
        originals=[dict(basename='.'+JOURNAL_SESSION+'.'+name,bytes=len(data),sha256=c.sha256(data))
            for name,data in sorted(raw.items())],
        old_boot_id=pre['boot_id'],new_boot_id=post['boot_id'],
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
    validate_journal_transition(value, priors=priors, implementation=implementation)
    return value


def validate_journal_transition(value, *, priors, implementation, current_boot=None):
    """Check the fixed host-verified projection; this does not reread host originals."""
    c.exact(value, {'schema','authority','implementation','session','nonce','access_mode',
        'host_writer_observation','continuous_exclusion_proven','input_sha256','manifest_sha256',
        'source_files','originals','old_boot_id','new_boot_id','old_vm','new_vm','image_identities',
        'old_pidfd_exited','original_argv_sha256','restart_argv_sha256','backup','virtual_bytes',
        'filesystem','content','reports','completed_steps','transport_exits','image_checks',
        'logical_compare_exit','resize_exit','all_streams_eof','historical_exit','old_commitments_refunded','previous_maintenance','guest_startup_assurance'},
        'CORE_JOURNAL_FIELDS')
    require(len(c.canonical(value)) <= 65536 and value['schema']=='local-hand-q2-core-journal-transition/v7'
        and value['session']=='lhqjgrow-20261008d', 'JOURNAL_SCHEMA')
    require(value['authority']==dict(R='10d2a5c827964989f41ca6e8eeac3d44de6d0f04',
        A=c.GS_BASELINE['commit'],C=c.GS_CLOSURE['commit'])
        and value['implementation']==implementation, 'JOURNAL_AUTHORITY')
    require(type(value['guest_startup_assurance']) is dict
        and c.canonical(value['guest_startup_assurance']) == c.canonical(dict(
            mode='TRUSTED_SINGLE_ADMIN',indirect_startup_observation='NOT_PERFORMED',
            no_undeclared_business_startup=True,continuous_exclusion_proven=False)),
        'GUEST_STARTUP_PREMISE')
    validate_maintenance_resume(value['previous_maintenance'])
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
    require(value['old_boot_id']!=value['new_boot_id']
        and all(hello['guest_boot_id']==value['old_boot_id'] for hello in validate_all(priors))
        and (current_boot is None or current_boot==value['new_boot_id']), 'JOURNAL_BOOT_BINDING')
    rows=value['originals']
    require(type(rows) is list and len(rows)==8 and [row.get('basename') for row in rows]
        == sorted('.lhqjgrow-20261008d.'+name for name in JOURNAL_FILES), 'JOURNAL_ORIGINALS')
    for row in rows:
        c.exact(row,{'basename','bytes','sha256'},'CORE_JOURNAL_ORIGINAL')
        c.integer(row['bytes'],0,JOURNAL_FILES[row['basename'][len('.lhqjgrow-20261008d.'):]])
        c.digest(row['sha256'])
    c.exact(value['source_files'],JOURNAL_SOURCE_NAMES,'CORE_JOURNAL_SOURCES')
    for name,row in value['source_files'].items():
        c.exact(row,{'bytes','sha256'},'CORE_JOURNAL_SOURCE')
        c.integer(row['bytes'],1,98304 if name.startswith('q2_journal_growth') else 524288);c.digest(row['sha256'])
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

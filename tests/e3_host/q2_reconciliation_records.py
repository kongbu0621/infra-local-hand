"""Create-only five-file amendment record, with bounded durable sealing.

This persistence component grants no execution authority. The amendment driver
validates the documents' semantic contract and live admission before calling it.
Replay is read-only, and any partial output is retained without repair/retry.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat


def _sibling(name):
    spec = importlib.util.spec_from_file_location("_reconciliation_records_" + name,
                                               Path(__file__).with_name(name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


io = _sibling("q2_reconciliation_io")
require = io.require
LIMITS = {"evidence-adoption.json": 256 * 1024,
          "reconciliation-intent.json": 16 * 1024,
          "live-attestation.json": 512 * 1024,
          "reconciliation-record.json": 64 * 1024,
          "reconciliation-seal.json": 4 * 1024}
SEAL_NAME = "reconciliation-seal.json"
DOCUMENT_NAMES = tuple(name for name in LIMITS if name != SEAL_NAME)
BYTE_LIMIT, INODE_LIMIT = 1024**2, 16
SCHEMA = "local-hand-q2-installation-reconciliation-seal/v1"


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "RECONCILIATION_DUPLICATE_KEY")
        result[key] = value
    return result


def _value(value, depth=0):
    require(depth <= 64, "RECONCILIATION_JSON_DEPTH")
    if type(value) is dict:
        require(len(value) <= 32768, "RECONCILIATION_JSON_MEMBERS")
        for key, child in value.items():
            require(len(key.encode("utf-8")) <= 4096, "RECONCILIATION_JSON_STRING")
            _value(child, depth + 1)
    elif type(value) is list:
        require(len(value) <= 32768, "RECONCILIATION_JSON_MEMBERS")
        for child in value:
            _value(child, depth + 1)
    elif type(value) is str:
        require(len(value.encode("utf-8")) <= 4096, "RECONCILIATION_JSON_STRING")
    elif type(value) is int:
        require(0 <= value <= 2**63 - 1, "RECONCILIATION_JSON_INTEGER")
    else:
        require(value is None or type(value) is bool, "RECONCILIATION_JSON_TYPE")


def _json(raw):
    require(type(raw) is bytes, "RECONCILIATION_DOCUMENT_BYTES")
    result = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                        parse_constant=lambda _: require(False, "RECONCILIATION_JSON_TYPE"))
    require(type(result) is dict, "RECONCILIATION_DOCUMENT_OBJECT")
    _value(result)
    return result


def _documents(documents):
    require(type(documents) is dict and set(documents) == set(DOCUMENT_NAMES),
            "RECONCILIATION_DOCUMENT_NAMES")
    result = {}
    for name in DOCUMENT_NAMES:
        raw = documents[name]
        require(type(raw) is bytes and len(raw) <= LIMITS[name], "RECONCILIATION_DOCUMENT_LIMIT")
        _json(raw)
        result[name] = raw
    return result


def make_seal(documents):
    documents = _documents(documents)
    files = {name: dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
             for name, raw in documents.items()}
    seal = dict(schema=SCHEMA, status="RECONCILIATION_SEALED", files=files,
                intent_sha256=files["reconciliation-intent.json"]["sha256"],
                record_sha256=files["reconciliation-record.json"]["sha256"])
    raw = encoded(seal)
    require(len(raw) <= LIMITS[SEAL_NAME], "RECONCILIATION_DOCUMENT_LIMIT")
    return seal, raw


def _names(fd, guard):
    names = set()
    with os.scandir(fd) as children:
        for child in children:
            guard()
            names.add(child.name)
            require(len(names) <= len(LIMITS), "RECONCILIATION_RECORD_MEMBERS")
    return names


def _allocation(held, opened, guard):
    guard()
    require(_names(held.fd, guard) == set(opened), "RECONCILIATION_RECORD_MEMBERS")
    directory = os.fstat(held.fd)
    total, identities = directory.st_blocks * 512, {(directory.st_dev, directory.st_ino)}
    for name, (fd, expected, raw) in opened.items():
        guard()
        actual = os.fstat(fd)
        io.protected(actual)
        require(io.metadata(actual) == expected and io.metadata(os.stat(
            name, dir_fd=held.fd, follow_symlinks=False)) == expected, "RECONCILIATION_RECORD_CHANGED")
        require(actual.st_dev == directory.st_dev and (actual.st_dev, actual.st_ino) not in identities,
                "RECONCILIATION_RECORD_ALIAS")
        identities.add((actual.st_dev, actual.st_ino))
        total += actual.st_blocks * 512
        require(io._read(fd, guard, LIMITS[name]) == raw, "RECONCILIATION_RECORD_CHANGED")
    require(total <= BYTE_LIMIT and len(identities) <= INODE_LIMIT, "RECONCILIATION_RECORD_BUDGET")
    held.verify()
    return dict(bytes=total, inodes=len(identities), device=directory.st_dev)


def _result(seal, allocation, replay):
    return dict(state="RECONCILIATION_SEALED", replay=replay, allow_run=False,
                seal=seal, allocation=allocation)


def verify_sealed(directory, documents, guard):
    """Verify exact expected bytes and complete membership; never issue anything."""
    documents = _documents(documents)
    seal, raw_seal = make_seal(documents)
    documents[SEAL_NAME] = raw_seal
    opened = {}
    with io.HeldPath(directory, guard, directory=True) as held:
        try:
            require(_names(held.fd, guard) == set(LIMITS), "RECONCILIATION_PARTIAL_RETAINED")
            for name, raw in documents.items():
                guard()
                fd = os.open(name, io.flags(), dir_fd=held.fd)
                opened[name] = fd, io.metadata(os.fstat(fd)), raw
                require(io._read(fd, guard, LIMITS[name]) == raw, "RECONCILIATION_RECORD_CHANGED")
            allocation = _allocation(held, opened, guard)
            return _result(seal, allocation, True)
        finally:
            for fd, _, _ in opened.values():
                os.close(fd)


verify_once = verify_sealed


def write_once(directory, documents, guard):
    """One exclusive directory; errors retain every partial byte and inode.

    Directory and file fsync are mandatory. The driver accounts the full 1 MiB /
    16 inode sub-reservation before this function; actual blocks are checked at
    every file boundary, including the seal and partially allocated objects.
    """
    documents = _documents(documents)
    seal, raw_seal = make_seal(documents)
    directory = io.absolute(directory)
    require(directory != "/", "RECONCILIATION_RECORD_DIRECTORY")
    parent, _, name = directory.rpartition("/")
    opened = {}
    with io.HeldPath(parent or "/", guard, directory=True) as ancestry:
        guard()
        geometry = os.fstatvfs(ancestry.fd)
        block = geometry.f_frsize
        require(type(block) is int and 512 <= block <= BYTE_LIMIT and block & (block - 1) == 0,
                "RECONCILIATION_ALLOCATION_UNSUPPORTED")
        projected = block + sum(((len(raw) + block - 1) // block) * block
                                for raw in (*documents.values(), raw_seal))
        require(projected <= BYTE_LIMIT and len(LIMITS) + 1 <= INODE_LIMIT,
                "RECONCILIATION_RECORD_BUDGET")
        ancestry.verify()
        try:
            os.mkdir(name, 0o700, dir_fd=ancestry.fd)
        except FileExistsError:
            ancestry.verify()
            return verify_sealed(directory, documents, guard)
        created = io.metadata(os.stat(name, dir_fd=ancestry.fd, follow_symlinks=False))
        # Own mkdir changes only the parent directory's content metadata.
        ancestry.refresh_written_directory()
        guard()
        os.fsync(ancestry.fd)
        ancestry.verify()
        with io.HeldPath(directory, guard, directory=True) as held:
            try:
                require(io.metadata(os.fstat(held.fd)) == created, "RECONCILIATION_PATH_CHANGED")
                require(stat.S_IMODE(os.fstat(held.fd).st_mode) == 0o700,
                        "RECONCILIATION_RECORD_MODE")
                _allocation(held, opened, guard)
                for filename, raw in (*documents.items(), (SEAL_NAME, raw_seal)):
                    guard()
                    ancestry.verify()
                    held.verify()
                    _allocation(held, opened, guard)
                    fd = os.open(filename, io.flags() | os.O_RDWR | os.O_CREAT | os.O_EXCL,
                                 0o600, dir_fd=held.fd)
                    opened[filename] = fd, io.metadata(os.fstat(fd)), b""
                    info = os.fstat(fd)
                    io.protected(info)
                    require(stat.S_IMODE(info.st_mode) == 0o600, "RECONCILIATION_RECORD_MODE")
                    held.refresh_written_directory()
                    for offset in range(0, len(raw), 65536):
                        guard()
                        chunk = raw[offset:offset + 65536]
                        require(os.write(fd, chunk) == len(chunk), "RECONCILIATION_SHORT_WRITE")
                        require(sum(os.fstat(item[0]).st_blocks * 512 for item in opened.values())
                                + os.fstat(held.fd).st_blocks * 512 <= BYTE_LIMIT,
                                "RECONCILIATION_RECORD_BUDGET")
                    guard()
                    os.fsync(fd)
                    opened[filename] = fd, io.metadata(os.fstat(fd)), raw
                    guard()
                    os.fsync(held.fd)
                    _allocation(held, opened, guard)
                    ancestry.verify()
                # A returned new seal is durable only after all fds, contents,
                # directory membership and ancestor names have been checked.
                guard()
                os.fsync(ancestry.fd)
                allocation = _allocation(held, opened, guard)
                ancestry.verify()
                return _result(seal, allocation, False)
            finally:
                for fd, _, _ in opened.values():
                    os.close(fd)

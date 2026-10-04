"""Recover exactly pinned historical inputs from a retained later carrier.

This host-only D1 transform does not execute any archive member or import old
tools. Its output is input for the separately Git-pinned legacy verifier, not
an approved-input artifact, release seal or execution permission.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
from pathlib import PurePosixPath
import zipfile

from . import q2_core_obligation_inputs as horizon


c = horizon.c
FRAME_PIN = (7494251, "807f774bfe6716ae404d360698adb5f6d5190c18d8f8b6be4e74d7691b8eefe3")
LATER_MANIFEST_PIN = (34978, "5900f95acd4fd67ebdad759334d2a403aa83d978e2b691770798e7964ca798f0")
MANIFEST_PIN = (34010, "f705d3c77885887c7b6f799f4721dfefd0e9c588dbd11085cc8456fe623c6d40")
LEGACY_COMMIT = "8fd84521cdd25b455ff148e0c0fed6b5d8e39fe1"
LEGACY_TREE = "5fb64e578d06e2954c1eedbc1b15e00069dc32a4"


def _require(condition, code):
    c.require(condition, "CORE_LEGACY_INPUT_" + code)


def restore_manifest(later_raw, historical_tools):
    """Restore only D/source pins, then demand the original whole-file digest.

    ``historical_tools`` is the 42-file closure obtained from exact legacy D.
    The final fixed hash checks every resulting byte, including all retained
    private locators and sources. A plausible replacement is not sufficient.
    """
    horizon._pin(later_raw, *LATER_MANIFEST_PIN, "LEGACY_LATER_MANIFEST_PIN")
    _require(type(historical_tools) is dict and len(historical_tools) == 42,
             "TOOL_CLOSURE")
    for name, raw in historical_tools.items():
        _require(type(name) is str and name.isascii() and "/" not in name
                 and name.endswith(".py") and type(raw) is bytes and raw,
                 "TOOL_INPUT")
    manifest = copy.deepcopy(horizon._json(later_raw))
    manifest["implementation_commit"] = LEGACY_COMMIT
    source = manifest["execution"]["source"]
    c.exact(source, {"commit", "tree", "files"})
    source["commit"], source["tree"] = LEGACY_COMMIT, LEGACY_TREE
    restored, used = {}, set()
    for path in source["files"]:
        name = PurePosixPath(path).name
        if name in historical_tools:
            _require(name not in used, "TOOL_ALIAS")
            used.add(name)
            restored[path] = hashlib.sha256(historical_tools[name]).hexdigest()
    _require(used == set(historical_tools), "TOOL_SET")
    source["files"] = restored
    raw = c.canonical(manifest, newline=True)
    return horizon._pin(raw, *MANIFEST_PIN, "LEGACY_ORIGINAL_MANIFEST_PIN")


def recover_inputs(frame_raw, historical_tools):
    """Decode saved data in RAM, restore the exact manifest, verify blob bytes.

    No paths are opened here; the caller must read the fixed retained frame
    through held descriptors. The frame's historical entry point is never run.
    Metadata drift and the two prospective source adoptions remain for the
    original verifier; this function does not relabel their provenance.
    """
    horizon._pin(frame_raw, *FRAME_PIN, "LEGACY_FRAME_PIN")
    lines = frame_raw.splitlines()
    _require(len(lines) > 2 and lines[0].startswith(b"#Q2-LOCAL-PREFLIGHT ")
             and lines[-1] == b"#END-Q2-LOCAL-PREFLIGHT", "FRAME")
    try:
        archive_raw = base64.b64decode(b"".join(line[1:] for line in lines[1:-1]), validate=True)
        with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
            entries = archive.infolist()
            names = [item.filename for item in entries]
            _require(len(names) == len(set(names)), "DUPLICATE_MEMBER")
            member = archive.getinfo("inputs.json")
            _require(member.file_size == 7632574 and not member.is_dir()
                     and not member.flag_bits & 1, "INPUT_MEMBER")
            with archive.open(member) as stream:
                inputs_raw = stream.read(member.file_size + 1)
            _require(len(inputs_raw) == member.file_size, "INPUT_LENGTH")
        inputs = horizon._json(inputs_raw)
        c.exact(inputs, {"blobs", "implementation_commit", "manifest_raw", "manifest_sha256"})
        later = base64.b64decode(inputs["manifest_raw"], validate=True)
        _require(hashlib.sha256(later).hexdigest() == inputs["manifest_sha256"], "LATER_BINDING")
        manifest = restore_manifest(later, historical_tools)
        _require(type(inputs["blobs"]) is dict and len(inputs["blobs"]) == 48, "BLOB_COUNT")
        blobs = {}
        for digest, encoded in inputs["blobs"].items():
            c.digest(digest)
            raw = base64.b64decode(encoded, validate=True)
            _require(hashlib.sha256(raw).hexdigest() == digest, "BLOB_DIGEST")
            blobs[digest] = raw
        _require(sum(map(len, blobs.values())) == 5686734, "BLOB_TOTAL")
        return manifest, blobs
    except c.ContractError:
        raise
    except (KeyError, TypeError, ValueError, OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise c.ContractError("CORE_LEGACY_INPUT_ENCODING") from error

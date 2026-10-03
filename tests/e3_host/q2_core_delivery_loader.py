"""Strict in-memory loader for the approved core-delivery bootstrap.

The source of this file is passed directly to ``python -c``.  It decodes one
canonical base64 argument, verifies the separately supplied digest, and
executes the bootstrap bytes.  It intentionally has no filesystem or package
access.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import sys

BOOTSTRAP_LIMIT = 49152
ARGUMENT_LIMIT = 65536


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def decode_bootstrap(encoded, expected_sha256):
    _require(type(encoded) is str and encoded.isascii() and 0 < len(encoded) <= ARGUMENT_LIMIT
             and "\0" not in encoded, "CORE_LOADER_ARGUMENT")
    _require(type(expected_sha256) is str
             and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
             "CORE_LOADER_DIGEST")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("CORE_LOADER_BASE64") from error
    _require(0 < len(raw) <= BOOTSTRAP_LIMIT
             and base64.b64encode(raw).decode("ascii") == encoded,
             "CORE_LOADER_BASE64")
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256,
             "CORE_LOADER_DIGEST")
    return raw


def main(argv=None, namespace=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    _require(sys.platform.startswith("linux") and sys.flags.isolated
             and sys.dont_write_bytecode, "CORE_LOADER_RUNTIME")
    _require(len(argv) == 2, "CORE_LOADER_ARGUMENTS")
    raw = decode_bootstrap(argv[0], argv[1])
    target = {"__name__": "__main__", "__file__": "field/bootstrap.py",
              "__builtins__": __builtins__, "BOOTSTRAP_SHA256": argv[1]}
    if namespace is not None:
        _require(type(namespace) is dict, "CORE_LOADER_NAMESPACE")
        target.update(namespace)
    code = compile(raw, "field/bootstrap.py", "exec", flags=0, dont_inherit=True,
                   optimize=0)
    exec(code, target, target)
    return target


if __name__ == "__main__":
    main()

"""Compare CPython cache structure without loading untrusted code objects.

marshal reference flags depend on process-local refcounts, so byte-for-byte
equality is not a code identity check. This bounded reader hashes immutable
compiler values and every code field, normalizing only sharing and string/tuple
encodings. It never calls marshal.load(s), creates CodeType, or executes input.
The code layout is CPython 3.12--3.14 Python/marshal.c; unknown layouts fail closed.
"""
from __future__ import annotations

import hashlib
import sys


MAX_CACHE_BYTES = 16 * 1024 * 1024
MAX_VALUES = 250_000


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0
        self.refs: list[bytes | None] = []
        self.remaining = MAX_VALUES

    def take(self, size: int) -> bytes:
        if size < 0 or size > len(self.data) - self.offset:
            raise ValueError("truncated bytecode structure")
        start = self.offset
        self.offset += size
        return self.data[start:self.offset]

    def integer(self) -> int:
        return int.from_bytes(self.take(4), "little", signed=True)

    def value(self, depth: int = 0) -> bytes:
        if depth > 256 or self.remaining <= 0:
            raise ValueError("bytecode structure exceeds limit")
        self.remaining -= 1
        tag = self.take(1)[0]
        flag, kind = tag & 128, chr(tag & 127)
        if kind == "r":
            index = self.integer()
            if flag or not 0 <= index < len(self.refs) or self.refs[index] is None:
                raise ValueError("invalid or cyclic bytecode reference")
            return self.refs[index]
        if kind in "NFT." and flag:
            # CPython does not register references for these singleton tags.
            raise ValueError("invalid singleton reference flag")
        index = len(self.refs)
        if flag:
            self.refs.append(None)
        digest = hashlib.sha256()
        if kind in "NFT.":
            digest.update(kind.encode("ascii"))
        elif kind in "igy":
            digest.update(kind.encode("ascii") + self.take({"i": 4, "g": 8, "y": 16}[kind]))
        elif kind == "l":
            count = self.take(4)
            size = abs(int.from_bytes(count, "little", signed=True)) * 2
            digest.update(b"l" + count + self.take(size))
        elif kind in "stuaAzZ":
            size = self.take(1)[0] if kind in "zZ" else self.integer()
            raw = self.take(size)
            if kind != "s":
                raw.decode("ascii" if kind in "aAzZ" else "utf-8", errors="surrogatepass")
            digest.update((b"s" if kind == "s" else b"u") + len(raw).to_bytes(4, "little") + raw)
        elif kind in "()>":
            size = self.take(1)[0] if kind == ")" else self.integer()
            # Every serialized member consumes at least one byte. Reference
            # expansion retains only a fixed-size digest, never a copied tree.
            if not 0 <= size <= min(self.remaining, len(self.data) - self.offset):
                raise ValueError("invalid bytecode container size")
            digest.update((b">" if kind == ">" else b"(") + size.to_bytes(4, "little"))
            if kind == ">":
                for child in sorted(self.value(depth + 1) for _ in range(size)):
                    digest.update(child)
            else:
                for _ in range(size):
                    digest.update(self.value(depth + 1))
        elif kind == "c":
            digest.update(b"c" + self.take(20))  # arguments, stack size, flags
            for _ in range(8):  # bytecode, constants, names, locals, filename/name/qualname
                digest.update(self.value(depth + 1))
            digest.update(self.take(4))  # first line
            for _ in range(2):  # line table and exception table
                digest.update(self.value(depth + 1))
        elif kind == ":" and sys.version_info[:2] == (3, 14):
            digest.update(b":")  # immutable slice constants in marshal v5
            for _ in range(3):
                digest.update(self.value(depth + 1))
        else:
            raise ValueError("unsupported bytecode value")
        result = digest.digest()
        if flag:
            self.refs[index] = result
        return result


def code_fingerprint(data: bytes) -> bytes:
    """Return a structural digest of one complete current-interpreter code body.

    Input size and depth are bounded; references cannot allocate expanded trees
    or recurse. Code fields remain byte-sensitive, including debugging metadata.
    This is an internal drift check, not a loader or a general marshal decoder.
    """
    if (sys.implementation.name != "cpython" or sys.version_info[:2] not in
            ((3, 12), (3, 13), (3, 14))):
        raise ValueError("unsupported bytecode layout")
    if not data or len(data) > MAX_CACHE_BYTES or data[0] & 127 != ord("c"):
        raise ValueError("invalid bytecode body")
    reader = _Reader(data)
    result = reader.value()
    if reader.offset != len(data):
        raise ValueError("trailing bytecode data")
    return result

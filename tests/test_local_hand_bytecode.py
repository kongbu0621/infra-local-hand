"""Cache identity ignores marshal sharing, never executable or diagnostic fields."""
import marshal
import sys
import unittest
from unittest import mock

from local_hand import bytecode


class BytecodeTests(unittest.TestCase):
    def setUp(self):
        self.code = compile("""
def outer(pos, /, *, kw=3):
    text = 'a synthetic non identifier'
    data = (None, True, False, ..., 2147483649, -2147483649, 1.25, 2j, b'bytes', '汉字')
    def inner():
        try:
            return pos + kw, text, data, pos in {'a', 'b', 'c'}
        except TypeError:
            return None
    return inner
""", "fixture.py", "exec")

    def fingerprint(self, code):
        return bytecode.code_fingerprint(marshal.dumps(code))

    def test_shared_and_unshared_serializations_match_without_native_loads(self):
        plain = marshal.dumps(self.code, 2)
        shared = marshal.dumps(self.code, 4)
        self.assertNotEqual(plain, shared)
        with mock.patch.object(marshal, "loads", side_effect=AssertionError("untrusted load")):
            self.assertEqual(bytecode.code_fingerprint(plain), bytecode.code_fingerprint(shared))

    def test_live_reference_count_does_not_change_identity(self):
        code = compile("value = 'a unique synthetic non identifier'", "fixture.py", "exec")
        first = marshal.dumps(code)
        retained = code.co_consts[0]
        second = marshal.dumps(code)
        if sys.version_info[:2] == (3, 12):
            self.assertNotEqual(first, second)  # reproduce the original false rejection
        self.assertEqual(bytecode.code_fingerprint(first), bytecode.code_fingerprint(second))
        self.assertEqual(retained, "a unique synthetic non identifier")

    def test_every_code_field_remains_bound(self):
        code = next(item for item in self.code.co_consts if hasattr(item, "co_code"))
        expected = self.fingerprint(code)
        replacements = {
            "co_argcount": code.co_argcount + 1, "co_posonlyargcount": 0, "co_kwonlyargcount": 0,
            "co_stacksize": code.co_stacksize + 1, "co_flags": code.co_flags ^ 1,
            "co_code": b"\x09\x00" + code.co_code[2:],
            "co_consts": code.co_consts + ("different",), "co_names": ("different",),
            "co_varnames": tuple("changed_" + name for name in code.co_varnames),
            "co_cellvars": tuple("changed_" + name for name in code.co_cellvars),
            "co_filename": "different.py", "co_name": "different", "co_qualname": "different",
            "co_firstlineno": code.co_firstlineno + 1, "co_linetable": b"", "co_exceptiontable": b"x",
        }
        for field, value in replacements.items():
            with self.subTest(field=field):
                self.assertNotEqual(expected, self.fingerprint(code.replace(**{field: value})))
        inner = next(item for item in code.co_consts if hasattr(item, "co_code"))
        self.assertNotEqual(self.fingerprint(inner), self.fingerprint(inner.replace(co_exceptiontable=b"")))
        self.assertNotEqual(self.fingerprint(inner), self.fingerprint(inner.replace(co_freevars=("other",) * len(inner.co_freevars))))

    def test_constant_types_and_signed_float_bits_are_not_equal(self):
        code = compile("pass", "fixture.py", "exec")
        pairs = [(True, 1), (False, 0), (0, 0.0), (0.0, -0.0), ("abc", b"abc"),
                 ((1, 2), (2, 1)), ((1, 2), frozenset({1, 2}))]
        for first, second in pairs:
            with self.subTest(pair=(first, second)):
                self.assertNotEqual(self.fingerprint(code.replace(co_consts=(first,))),
                                    self.fingerprint(code.replace(co_consts=(second,))))

    def test_truncated_trailing_unknown_and_oversize_structures_rejected(self):
        body = marshal.dumps(self.code)
        for size in range(len(body)):
            with self.assertRaises(ValueError):
                bytecode.code_fingerprint(body[:size])
        for bad in (body + b"N", b"N", b"c" + bytes(20) + b"?",
                    b"c" + bytes(20) + b"s\xff\xff\xff\x7f",
                    b"c" + bytes(20) + b"s\xff\xff\xff\xff"):
            with self.subTest(bad=bad[:30]), self.assertRaises(ValueError):
                bytecode.code_fingerprint(bad)
        with mock.patch.object(bytecode, "MAX_CACHE_BYTES", len(body) - 1):
            with self.assertRaises(ValueError):
                bytecode.code_fingerprint(body)
        with mock.patch.object(bytecode, "MAX_VALUES", 4):
            with self.assertRaises(ValueError):
                bytecode.code_fingerprint(body)

    def test_invalid_references_cycles_and_excessive_depth_rejected(self):
        for value in (b"r\x00\x00\x00\x00", b"r\xff\xff\xff\xff",
                      bytes([ord("r") | 128]) + bytes(4),
                      bytes([ord("N") | 128]),
                      bytes([ord(")") | 128, 1]) + b"r" + bytes(4),
                      b")\x01" * 258 + b"N"):
            with self.subTest(value=value[:15]), self.assertRaises(ValueError):
                bytecode.code_fingerprint(b"c" + bytes(20) + value)


if __name__ == "__main__":
    unittest.main()

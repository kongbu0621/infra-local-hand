"""Validate actual archive member names before accepting a retained wheel."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from local_hand import installation
from local_hand.protocol import LocalHandError


class RetainedWheelNames(unittest.TestCase):
    def test_nul_member_suffix_cannot_alias_an_admitted_wheel_entry(self):
        payload = b"# retained payload\n"
        metadata = {"product_version": "0.2.0a1", "files": {
            "local_hand/worker.py": hashlib.sha256(payload).hexdigest()}}
        encoded = json.dumps(metadata, sort_keys=True).encode()
        members = {"local_hand/worker.py": payload,
                   "local_hand/_build_metadata.json": encoded,
                   "infra_local_hand-0.2.0a1.dist-info/METADATA": b"Metadata-Version: 2.1\n"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "_build_metadata.json").write_bytes(encoded)
            with mock.patch.object(installation, "__file__", str(root / "installation.py")):
                healthy = root / "healthy.whl"
                with zipfile.ZipFile(healthy, "w") as archive:
                    for name, content in members.items():
                        archive.writestr(name, content)
                self.assertEqual(installation.verify_wheel(healthy, metadata),
                                 hashlib.sha256(healthy.read_bytes()).hexdigest())
                for index, target in enumerate(members):
                    with self.subTest(member=target):
                        wheel = root / f"ambiguous-{index}.whl"
                        original = (target + "?unbound").encode()
                        hidden = (target + "\0unbound").encode()
                        with zipfile.ZipFile(wheel, "w") as archive:
                            for name, content in members.items():
                                archive.writestr(name + "?unbound" if name == target else name, content)
                        raw = wheel.read_bytes()
                        self.assertEqual(raw.count(original), 2)
                        wheel.write_bytes(raw.replace(original, hidden))
                        with zipfile.ZipFile(wheel) as archive:
                            info = archive.getinfo(target)
                            self.assertNotEqual(info.orig_filename, info.filename)
                        with self.assertRaises(LocalHandError) as rejected:
                            installation.verify_wheel(wheel, metadata)
                        self.assertEqual(rejected.exception.code, "installation_mismatch")


if __name__ == "__main__":
    unittest.main()

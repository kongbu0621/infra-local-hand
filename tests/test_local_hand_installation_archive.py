"""Validate actual archive member names before accepting a retained wheel."""
import hashlib
import json
import io
import os
import zlib
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


class RetainedWheelCompression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = b'# verified payload\n'
        self.metadata = {'product_version': '0.2.0a1', 'files': {'local_hand/worker.py': hashlib.sha256(self.payload).hexdigest()}}
        self.encoded = json.dumps(self.metadata, sort_keys=True).encode()
        (self.root / '_build_metadata.json').write_bytes(self.encoded)
        patch = mock.patch.object(installation, '__file__', str(self.root / 'installation.py'))
        patch.start(); self.addCleanup(patch.stop)

    def wheel(self, name, compression=zipfile.ZIP_DEFLATED, payload=None):
        path = self.root / name
        with zipfile.ZipFile(path, 'w', compression=compression) as archive:
            archive.writestr('local_hand/worker.py', self.payload if payload is None else payload)
            archive.writestr('local_hand/_build_metadata.json', self.encoded)
            archive.writestr('infra_local_hand-0.2.0a1.dist-info/METADATA', b'Metadata-Version: 2.1\n')
        return path

    def rejected(self, path):
        with self.assertRaises(LocalHandError) as caught:
            installation.verify_wheel(path, self.metadata)
        self.assertEqual(caught.exception.code, 'installation_mismatch')

    def test_declared_prefix_does_not_hide_real_expansion(self):
        for codec in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            with self.subTest(codec=codec):
                path = self.wheel(str(codec)+'.whl', codec, self.payload + b'x' * 65536)
                raw = bytearray(path.read_bytes()); central = raw.index(b'PK\x01\x02')
                for start in (14, central+16): raw[start:start+4] = zlib.crc32(self.payload).to_bytes(4, 'little')
                for start in (22, central+24): raw[start:start+4] = len(self.payload).to_bytes(4, 'little')
                path.write_bytes(raw)
                with zipfile.ZipFile(path) as archive: self.assertEqual(archive.read('local_hand/worker.py'), self.payload)
                self.rejected(path)

    def test_corrupt_deflate_is_structured(self):
        path = self.wheel('corrupt.whl'); raw = bytearray(path.read_bytes())
        offset = 30 + len('local_hand/worker.py'); raw[offset] = 6
        path.write_bytes(raw); self.rejected(path)

    def test_incomplete_deflate_end_is_rejected(self):
        path = self.wheel('truncated.whl'); raw = bytearray(path.read_bytes()); central=raw.index(b'PK\x01\x02')
        size=int.from_bytes(raw[18:22], 'little')-1
        for start in (18,central+20):raw[start:start+4]=size.to_bytes(4,'little')
        path.write_bytes(raw)
        with zipfile.ZipFile(path) as archive:self.assertEqual(archive.read('local_hand/worker.py'),self.payload)
        self.rejected(path)

    def test_healthy_stored_and_deflate(self):
        class StreamingBuffer(io.BytesIO):
            def seekable(self): return False
            def seek(self, *_): raise OSError('streaming ZIP writer')

        read_sizes=[]
        original_read=zipfile.ZipExtFile.read
        def bounded_read(member,n=-1):
            read_sizes.append(n)
            self.assertGreater(n,0)
            self.assertLessEqual(n,65536)
            return original_read(member,n)
        for codec in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
            for payload in (b'', b'x'*200000, os.urandom(150000)):
                for streaming in (False,True):
                    with self.subTest(codec=codec,size=len(payload),streaming=streaming):
                        metadata=dict(self.metadata,files={'local_hand/worker.py':hashlib.sha256(payload).hexdigest()})
                        encoded=json.dumps(metadata,sort_keys=True).encode()
                        (self.root/'_build_metadata.json').write_bytes(encoded)
                        buffer=StreamingBuffer() if streaming else io.BytesIO()
                        with zipfile.ZipFile(buffer,'w',compression=codec) as archive:
                            info=zipfile.ZipInfo('local_hand/worker.py');info.compress_type=codec
                            with archive.open(info,'w',force_zip64=True) as writer:writer.write(payload)
                            archive.writestr('local_hand/_build_metadata.json',encoded)
                        path=self.root/'healthy.whl';path.write_bytes(buffer.getvalue())
                        with mock.patch.object(zipfile.ZipExtFile,'read',bounded_read):
                            self.assertEqual(installation.verify_wheel(path,metadata),hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertTrue(read_sizes)

    def test_optional_metadata_is_checked_and_alternative_codecs_fail_before_decode(self):
        for codec in (zipfile.ZIP_BZIP2,zipfile.ZIP_LZMA):
            with self.subTest(codec=codec):
                path=self.wheel('alternative-'+str(codec)+'.whl',codec)
                with mock.patch.object(zipfile,'_get_decompressor',side_effect=AssertionError('unsupported codec decoded')):
                    self.rejected(path)
        path=self.wheel('metadata-corrupt.whl',zipfile.ZIP_STORED)
        with zipfile.ZipFile(path) as archive:
            info=archive.getinfo('infra_local_hand-0.2.0a1.dist-info/METADATA')
        raw=bytearray(path.read_bytes());offset=info.header_offset+30+len(info.filename.encode())
        raw[offset]^=1;path.write_bytes(raw)
        self.rejected(path)



if __name__ == "__main__":
    unittest.main()

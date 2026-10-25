"""Preserve actual offline protocol refusals without exposing private messages."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

from admin.local_hand_deploy.model import DeployError
from admin.local_hand_deploy.retained_reader import reader_result
from local_hand_jobs import retained_offline
from local_hand_jobs.contract import JobError


class ReaderResponseTests(unittest.TestCase):
    def test_real_reader_refusal_survives_administrative_boundary(self):
        root = str(Path(retained_offline.__file__).resolve().parents[1])
        child = subprocess.run([sys.executable, '-I', '-B', '-c',
            'import sys; sys.path.insert(0,sys.argv[1]); '
            'from local_hand_jobs.retained_offline import main; main()', root],
            input=b'{"mode":"read_only","inputs":{},"reader_identity":{},"seconds":0}',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
        self.assertEqual(child.stderr, b'')
        original = json.loads(child.stdout)['error']
        with self.assertRaises(DeployError) as caught:
            reader_result(child.stdout)
        self.assertEqual(caught.exception.code, 'RETENTION_READ_FAILED')
        self.assertIn(original['code'], str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, JobError)
        self.assertEqual(caught.exception.__cause__.as_dict(), original)

    def test_private_message_is_retained_only_in_cause(self):
        message = 'original private route /private/fixture refused'
        with self.assertRaises(DeployError) as caught:
            reader_result(json.dumps({'error': {'code': 'UNAUTHORIZED', 'message': message}}).encode())
        self.assertNotIn('/private/fixture', str(caught.exception))
        self.assertEqual(caught.exception.__cause__.message, message)

    def test_ambiguous_success_never_hides_an_error(self):
        for value in ({'result': {}, 'error': {'code': 'CONFLICT', 'message': 'refused'}},
                      [], None, {'result': []}, {'result': {}, 'extra': True}):
            with self.subTest(value=value), self.assertRaises(DeployError):
                reader_result(json.dumps(value).encode())

    def test_error_text_cannot_enter_public_summary_through_code(self):
        for error in ({'code': 'CONFLICT\nprivate', 'message': 'refused'},
                      {'code': 'X'*65, 'message': 'refused'},
                      {'code': 'CONFLICT', 'message': 'x'*2049},
                      {'code': ['CONFLICT'], 'message': 'refused'}):
            with self.subTest(error=error), self.assertRaises(DeployError) as caught:
                reader_result(json.dumps({'error': error}).encode())
            self.assertIsNone(caught.exception.__cause__)

    def test_duplicate_error_keys_and_oversized_report_refused(self):
        for output in (b'{"error":{},"error":{}}', b' '*(1024*1024+1)):
            with self.assertRaises(DeployError):
                reader_result(output)

    def test_success_is_preserved(self):
        result = {'schema': 'local-hand-retained-readback/v1', 'tasks': [], 'bytes_verified': 0}
        self.assertEqual(reader_result(json.dumps({'result': result}).encode()), result)


if __name__ == '__main__':
    unittest.main()

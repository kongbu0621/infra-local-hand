"""Raw decoder, interoperable identity and fixed seven-tool boundary tests."""
import copy
import hashlib
import json
import shutil
import subprocess
import unittest

from local_hand_jobs.contract import (KINDS, SUITES, Principal, JobError, MAX_SAFE_INTEGER,
    TOOL_SCHEMAS, TOOL_SCHEMA_DIGEST, canonical_bytes, request_digest, strict_loads,
    validate_submit, validate_tool_args)


def submit_fixture(kind="host.inspect", **inputs):
    request = {"schema_version": "lh-job-v1", "operation_id": "12345678-1234-4234-9234-123456789abc",
        "kind": kind, "profile_ref": "fixture", "expected": {"node_id": "node",
        "install_uuid": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee", "deployment_epoch": 1,
        "profile_digest": "1" * 64, "policy_digest": "2" * 64, "registry_digest": "3" * 64},
        "inputs": inputs, "expires_at": 1800000000}
    request["request_digest"] = request_digest(request)
    return request


class StrictJobContractTests(unittest.TestCase):
    def test_all_six_kinds_have_exact_input_contract(self):
        inputs = ({}, {"source_ref": "source", "build_cache_ref": "cache"},
            {"prepared_ref": "prepared"}, {"prepared_ref": "prepared", "suite": "a1_resources"},
            {"prepared_ref": "prepared"}, {"prepared_ref": "prepared", "storage_ref": "storage"})
        for kind, values in zip(KINDS, inputs):
            with self.subTest(kind=kind):
                request = submit_fixture(kind, **values)
                self.assertEqual(validate_submit(request), request)
                injected = copy.deepcopy(request)
                injected["inputs"]["argv"] = "id"
                with self.assertRaises(JobError):
                    request_digest(injected)
                if values:
                    incomplete = copy.deepcopy(request)
                    incomplete["inputs"].pop(next(iter(values)))
                    with self.assertRaises(JobError):
                        request_digest(incomplete)

    def test_every_layer_rejects_extra_fields_and_client_identity(self):
        for key in ("principal", "owner", "budget", "state_root", "command", "environment"):
            request = submit_fixture()
            request[key] = "fixture"
            with self.subTest(key=key), self.assertRaises(JobError):
                request_digest(request)
        request = submit_fixture()
        request["expected"]["node_path"] = "/tmp"
        with self.assertRaises(JobError):
            request_digest(request)

    def test_raw_duplicate_utf8_surrogate_and_nonfinite_values_fail(self):
        invalid = (b'{"a":1,"a":2}', b'{"x":{"a":1,"a":1}}', b'{"a":"\xff"}',
            b'{"x":"\\ud800"}', b'{"x":"\\udfff"}', b'{"x":NaN}', b'{"x":Infinity}',
            b'{"x":-Infinity}', b'{"x":1.0}', b'{"x":1e2}', b'\xef\xbb\xbf{}')
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(JobError):
                strict_loads(raw)
        self.assertEqual(strict_loads(b'{"text":"\\ud83d\\ude00"}'), {"text": "\U0001f600"})

    def test_nested_size_and_integer_limits_are_enforced_before_large_parse(self):
        self.assertEqual(strict_loads("[" * 8 + "0" + "]" * 8), [[[[[[[[0]]]]]]]])
        for raw in ("[" * 9 + "0" + "]" * 9, " " * 65537, '{"a":9007199254740992}',
                    '{"a":' + "9" * 10000 + '}'):
            with self.subTest(length=len(raw)), self.assertRaises(JobError):
                strict_loads(raw)
        self.assertEqual(strict_loads('{"a":9007199254740991}')["a"], MAX_SAFE_INTEGER)
        self.assertEqual(strict_loads('{"a":"[\\\"{\\\"}]"}')["a"], '["{"}]')

    def test_booleans_null_arrays_and_unsafe_numbers_never_become_submit_values(self):
        for value in (True, False, None, [], {}, 1.0, -1, MAX_SAFE_INTEGER + 1):
            request = submit_fixture()
            request["expires_at"] = value
            with self.subTest(value=value), self.assertRaises(JobError):
                request_digest(request)
        request = submit_fixture()
        request["expected"]["deployment_epoch"] = 0
        with self.assertRaises(JobError):
            request_digest(request)

    def test_identity_is_canonical_ascii_and_v4_only_for_request_ids(self):
        for value in ("12345678-1234-1234-9234-123456789abc", "12345678-1234-4234-7234-123456789abc",
                      "12345678-1234-4234-9234-123456789ABC", "12345678123442349234123456789abc"):
            request = submit_fixture()
            request["operation_id"] = value
            with self.subTest(value=value), self.assertRaises(JobError):
                request_digest(request)
        for value in ("../source", "source/name", "A", "\u0430", "source\\name", "a\n", "x" * 129):
            request = submit_fixture()
            request["profile_ref"] = value
            with self.subTest(value=value), self.assertRaises(JobError):
                request_digest(request)

    def test_digest_golden_vector_and_detached_validation(self):
        value = submit_fixture()
        self.assertEqual(value["request_digest"], "f448a31399e97146a39d5272e98fd5146e5b6424febf7273e1de17e64a33ea54")
        self.assertEqual(request_digest(dict(reversed(list(value.items())))), value["request_digest"])
        checked = validate_submit(value)
        checked["expected"]["deployment_epoch"] = 9
        self.assertEqual(value["expected"]["deployment_epoch"], 1)
        value["expires_at"] += 1
        with self.assertRaises(JobError) as raised:
            validate_submit(value)
        self.assertEqual(raised.exception.code, "CONFLICT")

    @unittest.skipUnless(shutil.which("node"), "JavaScript runtime unavailable; vector remains unverified in JS")
    def test_javascript_canonical_bytes_and_digest_match_python_golden_vector(self):
        request = submit_fixture()
        unsigned = {key: value for key, value in request.items() if key != "request_digest"}
        script = """const fs=require('fs'),crypto=require('crypto');
const value=JSON.parse(fs.readFileSync(0,'utf8'));
function canonical(v){if(v!==null&&typeof v==='object'&&!Array.isArray(v)){return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';}return JSON.stringify(v);}
const bytes=canonical(value);process.stdout.write(JSON.stringify({bytes,digest:crypto.createHash('sha256').update(bytes,'utf8').digest('hex')}));"""
        completed = subprocess.run([shutil.which("node"), "-e", script], input=json.dumps(unsigned),
            text=True, capture_output=True, check=True, timeout=10)
        actual = json.loads(completed.stdout)
        self.assertEqual(actual["bytes"].encode(), canonical_bytes(unsigned))
        self.assertEqual(actual["digest"], request["request_digest"])

    def test_cancel_explicit_target_never_infers_latest_reconcile(self):
        request = submit_fixture()
        base = {"operation_id": request["operation_id"], "expected_request_digest": request["request_digest"]}
        for target in ({"kind": "job"}, {"kind": "reconcile", "reconcile_id": request["operation_id"]}):
            validate_tool_args("lh_job_cancel", {**base, "target": target})
        for target in (None, {}, {"kind": "latest"}, {"kind": "reconcile"},
                       {"kind": "job", "reconcile_id": request["operation_id"]}):
            with self.subTest(target=target), self.assertRaises(JobError):
                validate_tool_args("lh_job_cancel", {**base, "target": target})
        with self.assertRaises(JobError):
            validate_tool_args("lh_job_cancel", base)

    def test_seven_tools_reject_extras_and_bounded_evidence_chunk(self):
        operation = submit_fixture()["operation_id"]
        valid = {"lh_capabilities": {}, "lh_job_submit": submit_fixture(),
            "lh_job_status": {"operation_id": operation},
            "lh_job_cancel": {"operation_id": operation, "expected_request_digest": "0" * 64, "target": {"kind": "job"}},
            "lh_job_reconcile": {"operation_id": operation, "expected_request_digest": "0" * 64, "reconcile_id": operation},
            "lh_evidence_manifest": {"operation_id": operation},
            "lh_evidence_read_chunk": {"artifact_id": "artifact", "offset": 0, "expected_sha256": "a" * 64}}
        self.assertEqual(set(valid), set(TOOL_SCHEMAS))
        for tool, args in valid.items():
            validate_tool_args(tool, args)
            with self.subTest(tool=tool), self.assertRaises(JobError):
                validate_tool_args(tool, {**args, "extra": "x"})
        for length in (True, 0, -1, 262145):
            with self.subTest(length=length), self.assertRaises(JobError):
                validate_tool_args("lh_evidence_read_chunk", {**valid["lh_evidence_read_chunk"], "length": length})
        validate_tool_args("lh_evidence_read_chunk", {**valid["lh_evidence_read_chunk"], "length": 262144})
        self.assertEqual(hashlib.sha256(canonical_bytes(TOOL_SCHEMAS)).hexdigest(), TOOL_SCHEMA_DIGEST)

    def test_authenticated_principal_is_separate_and_immutable(self):
        principal = Principal("fixture-owner", frozenset({"lh:read"}))
        with self.assertRaises(AttributeError):
            principal.principal_id = "other"
        with self.assertRaises(JobError):
            Principal("fixture-owner", ["lh:read"])


if __name__ == "__main__":
    unittest.main()

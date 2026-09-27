"""Pure host source/authority contract checks; no field observation or dispatch."""
import copy
import unittest
from unittest.mock import patch

from e3_host import q2_host_window_contract as c


class HostWindowContract(unittest.TestCase):
    def sources(self, carrier=None, attestation=None):
        carrier=carrier or b'HOST_RESULT="/root/example/result"\nHOST_OLD="/root/example/old"\nraise RuntimeError("must not execute")\n'
        attestation=attestation or b'{"boot_id":"11111111-2222-3333-4444-555555555555"}\n'
        with patch.multiple(c,CARRIER_SHA256=c.sha(carrier),CARRIER_BYTES=len(carrier),
                ATTESTATION_SHA256=c.sha(attestation),ATTESTATION_BYTES=len(attestation)):
            return c.sources(carrier,attestation)

    def location(self):
        return dict(schema=c.SOURCES_SCHEMA,parent="/root/example",
            directory="/root/example/"+c.DIRECTORY_NAME,
            expected_boot_id="11111111-2222-3333-4444-555555555555",
            startup_closure=c.STARTUP_AUTHORITY["closure"],carrier_sha256=c.CARRIER_SHA256,
            carrier_bytes=c.CARRIER_BYTES,host_attestation_sha256=c.ATTESTATION_SHA256,
            host_attestation_bytes=c.ATTESTATION_BYTES)

    def binding(self):
        return c.make_binding(implementation_commit="a"*40,source_tree="b"*40,
            source_files_sha256="c"*64,attempt_id="fixed-attempt-01",plan_sha256="d"*64,
            amendment_sha256="e"*64,configuration_sha256="f"*64,wrapper_sha256="1"*64,
            location=self.location())

    def test_fixed_source_ast_is_never_executed_and_key_is_original_startup_closure(self):
        location=self.sources()
        self.assertEqual("/root/example",location["parent"])
        self.assertEqual("q2-startup-window-ff236aad9a4dc238a640080af3364634ca902099bdb2ad7941246dd5fdd99d5f",
            c.DIRECTORY_NAME)
        self.assertTrue(location["directory"].endswith(c.DIRECTORY_NAME))

    def test_source_raw_pin_must_match_before_ast_parse(self):
        with self.assertRaisesRegex(ValueError,"CARRIER_PIN"):
            c.sources(b'HOST_RESULT="/caller/chosen"',b'{}')

    def test_source_alias_dynamic_constant_duplicate_and_different_parents_rejected(self):
        for carrier in (
            b'HOST_RESULT="/root/a/result"\nHOST_OLD="/root/b/old"',
            b'HOST_RESULT="/root/a/../result"\nHOST_OLD="/root/a/old"',
            b'HOST_RESULT=str("/root/a/result")\nHOST_OLD="/root/a/old"',
            b'HOST_RESULT="/root/a/result"\nHOST_RESULT="/root/a/result"\nHOST_OLD="/root/a/old"',
            b'HOST_RESULT="/root/a/result"'):
            with self.subTest(carrier=carrier),self.assertRaises(ValueError):
                self.sources(carrier=carrier)

    def test_boot_duplicate_key_and_noncanonical_uuid_rejected(self):
        for raw in (b'{"boot_id":"11111111-2222-3333-4444-555555555555","boot_id":"11111111-2222-3333-4444-555555555555"}',
                    b'{"boot_id":"not-a-boot"}',b'{}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                self.sources(attestation=raw)

    def test_three_authorities_and_exact_binding_fields(self):
        value=self.binding()
        self.assertEqual(value,c.validate_binding(value,self.location()))
        changes={"baseline":c.prior.BASELINE,"closure":c.prior.CLOSURE,
            "rule":"0"*40,"owner_decision":"caller-approval","implementation_commit":c.BASELINE,
            "run_permission":"retry","startup_authority":c.RECONCILIATION_AUTHORITY,
            "source_files_sha256":True,"unknown":False}
        for key,replacement in changes.items():
            changed=copy.deepcopy(value);changed[key]=replacement
            with self.subTest(key=key),self.assertRaises(ValueError):
                c.validate_binding(changed,self.location())

    def test_directory_key_cannot_be_changed_with_attempt_or_caller_prefix(self):
        location=self.location()
        for key,value in (("directory","/root/example/q2-other-attempt"),
                          ("startup_closure",c.CLOSURE),("carrier_bytes",5426690)):
            changed=copy.deepcopy(location);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):c.validate_location(changed)

    def test_both_original_deadlines_exact_300_seconds_no_bool_or_unknown(self):
        value=dict(issued_ns=10,deadline_ns=300*c.NS+10,
            boottime_issued_ns=20,boottime_deadline_ns=300*c.NS+20)
        self.assertEqual(value,c.validate_window(value))
        for key,changed in (("deadline_ns",301*c.NS+10),("issued_ns",True),("unknown",1)):
            other=dict(value);other[key]=changed
            with self.subTest(key=key),self.assertRaises(ValueError):c.validate_window(other)

    def test_closed_scope_does_not_turn_caller_claims_into_field_readiness(self):
        for value in (None,True,{"ready":True},{"scope":c.SCOPE,"closure":c.CLOSURE},self.binding()):
            with self.subTest(value=type(value).__name__),self.assertRaisesRegex(ValueError,"FIELD_READINESS_UNPROVEN"):
                c.require_field_readiness(value)


if __name__=="__main__":unittest.main()

"""Real Unix HTTP and supervisor recovery; no Docker daemon or live services."""
import copy
import fcntl
import http.client
from http.server import BaseHTTPRequestHandler
import io
import json
import os
from pathlib import Path
import signal
import socketserver
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from admin.local_hand_deploy.coordinator import Coordinator
from admin.local_hand_deploy.runtime import ConcreteEnvironment
from admin.local_hand_deploy.gateway import DockerEngine, DockerHTTPError, GatewayAdapter
from admin.local_hand_deploy.model import Limits, PLAN_SCHEMA, digest, seal_plan
from admin.local_hand_deploy.store import Store
from admin.local_hand_deploy.supervision import SupervisedRunner, boot_id
from local_hand_jobs.maintenance import MaintenanceGate
from test_local_hand_deploy_coordinator import Effects


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, value, *, extra_length=0):
        raw = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(raw) + extra_length))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.endswith("/info"):
            self.reply(200, {"ID": "response-fixture"})
        elif "/images/" in self.path:
            self.reply(200, {"Id": "sha256:" + "a" * 64, "Config": {}})
        elif self.server.container is None:
            self.reply(404, {"message": "No such container"})
        else:
            self.reply(200, self.server.container)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with self.server.requests.open("a") as stream:
            stream.write(self.path + "\n")
        mode = self.server.mode.read_text()
        if mode == "disconnect":
            return
        if mode == "truncated":
            self.reply(400, {"message": "rejected"}, extra_length=10)
            return
        if mode == "oversized":
            self.reply(400, {"message": "x" * 8192})
            return
        if mode == "reject":
            self.reply(400, {"message": "rejected"})
            return
        identifier = 'created-' + str(len(self.server.requests.read_text().splitlines()))
        self.server.container = {
            "Id": identifier, "Image": body["Image"], "Config": {
                "Labels": body["Labels"], "Env": body["Env"], "Cmd": None,
                "Entrypoint": None, "User": None},
            "HostConfig": body["HostConfig"], "State": {"Running": False},
            "Mounts": [], "NetworkSettings": {"Networks": {"none": {}}}}
        if mode == "effect_then_error":
            self.reply(500, {"message": "failure after creating the object"})
        else:
            self.reply(201, {"Id": identifier})


class GatewayResponseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.mode = self.root / "mode"
        self.mode.write_text("reject")
        self.requests = self.root / "requests"
        server = socketserver.UnixStreamServer(str(self.root / "engine.sock"), Handler)
        server.mode, server.requests, server.container = self.mode, self.requests, None
        child = os.fork()
        if child == 0:
            try:
                server.serve_forever(poll_interval=0.05)
            finally:
                os._exit(0)
        server.server_close()
        self.addCleanup(self.stop_server, child)
        self.fd = os.open(self.root / "lock", os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, self.fd)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.runner = SupervisedRunner(self.root / "calls", timeout=2)
        profile = {"project": "response", "service": "gateway", "container_name": "response-gateway",
            "daemon_id": "response-fixture", "compose": {"services": {"gateway": {
                "image": "sha256:" + "a" * 64, "networks": {}, "restart": "no"}}}}
        self.adapter = GatewayAdapter(profile, self.runner,
            engine=DockerEngine(str(self.root / "engine.sock"), timeout=1, maximum=4096),
            guard_check=lambda _, target: {**target, "descriptor_digest": "d" * 64,
                "mode": "candidate", "target_running": False, "boot": boot_id()})
        self.action = self.adapter.plan({"present": True, "running": False,
            "config_digest": "b" * 64, "deployment_digest": "c" * 64})[0]
        self.intents = []

    @staticmethod
    def stop_server(pid):
        os.kill(pid, signal.SIGTERM)
        os.waitpid(pid, 0)

    def execute(self, name, previous=None):
        return self.adapter.execute(self.action, attempt_id=name, lock_fd=self.fd,
                                    persist_intent=self.intents.append, previous=previous)

    def count(self):
        return len(self.requests.read_text().splitlines())

    def test_rejected_request_closes_and_explicit_retry_can_finish(self):
        first = self.execute("rejected")
        self.assertTrue(first["supervision"]["closed"])
        self.assertEqual("DOCKER_HTTP_400", first["supervision"]["result"]["error"])
        self.assertTrue(first["closed"])
        self.assertEqual("original", first["outcome"])
        self.assertFalse(first["postcondition"])
        self.mode.write_text("success")
        self.execute("rejected", first["attempt"])
        self.assertEqual(1, self.count())
        final = self.execute("retry", first["attempt"])
        self.assertTrue(final["postcondition"])
        self.assertEqual(2, self.count())

    def test_error_with_actual_target_preserves_receipt_without_repeating(self):
        self.mode.write_text("effect_then_error")
        result = self.execute("partial-error")
        self.assertTrue(result["postcondition"])
        responses = [e for e in result["supervision"]["events"] if e["kind"] == "engine_response"]
        self.assertEqual(1, len(responses))
        self.assertEqual(500, responses[0]["response"]["status"])
        self.assertEqual("DOCKER_HTTP_500", result["supervision"]["result"]["error"])
        self.execute("another", result["attempt"])
        self.assertEqual(1, self.count())

    def independent_create(self, attempt='independent-admin'):
        self.mode.write_text('success')
        return self.adapter.engine.request('POST', '/containers/create?name=' + self.adapter.name,
                                           self.adapter._create_body(self.action['after'], attempt))

    def compensation(self, result):
        environment = ConcreteEnvironment({'profile': {}}, SimpleNamespace(lock_fd=self.fd), None)
        environment._gateway = self.adapter
        environment._runner = self.runner
        op = {'id': 'creation', 'plan': {'steps': [{'id': 'create', 'kind': 'gateway', 'action': self.action}]},
              'steps': [{'prepared': self.action, 'effective': True, 'state': 'VERIFIED',
                         'attempts': [{'binding': result['attempt']['binding']}]}]}
        return environment.prepare_compensation(op)

    def test_unrequested_matching_container_is_not_an_adoptable_create(self):
        self.independent_create()
        observed = self.adapter.observe_action(self.action, lock_fd=self.fd)
        self.assertEqual('conflict', observed['outcome'])
        self.assertFalse(ConcreteEnvironment._observation(observed, self.action)['effective'])
        coordinator, plan, gate = self.coordinator()
        refused = coordinator.apply(plan)
        self.assertIsNone(refused['decision'])
        self.assertEqual([], refused['steps'][0]['attempts'])
        abandoned = coordinator.rollback(refused['id'])
        self.assertEqual('ABORTED_NO_CHANGE', abandoned['decision'])
        self.assertEqual(1, self.count())
        self.assertEqual('independent-admin', self.adapter.observe()['labels']['local-hand.deploy.attempt'])

    def test_returned_creation_id_cannot_be_replaced_even_with_copied_labels(self):
        self.mode.write_text('success')
        original = self.execute('original-create')
        original_id = original['observation']['id']
        replacement = self.independent_create('original-create')
        self.assertNotEqual(original_id, replacement['Id'])
        observed = self.adapter.observe_action(self.action, original['attempt'], lock_fd=self.fd)
        self.assertEqual('conflict', observed['outcome'])
        self.assertTrue(ConcreteEnvironment._observation(observed, self.action)['effective'])
        with self.assertRaisesRegex(Exception, 'RESTORE_GATEWAY_IDENTITY'):
            self.compensation(original)
        self.assertEqual(replacement['Id'], self.adapter.observe()['id'])

    def test_original_created_container_can_be_compensated(self):
        self.mode.write_text('success')
        original = self.execute('owned-create')
        actions = self.compensation(original)
        self.assertEqual(['gateway_remove'], [item['prepared']['kind'] for item in actions])
        self.assertEqual(original['observation']['id'], actions[0]['prepared']['before']['id'])

    def test_recorded_response_survives_missing_final_supervisor_report(self):
        first = self.execute("reported-error")
        (Path(first["attempt"]["binding"]["result_directory"]) / "result.json").unlink()
        observed = self.adapter.observe_action(self.action, first["attempt"], lock_fd=self.fd)
        self.assertTrue(observed["closed"])
        self.assertEqual("original", observed["outcome"])
        self.assertIsNone(observed["supervision"]["result"])
        self.assertEqual(1, self.count())

    def test_mismatched_response_does_not_close_an_unknown_request(self):
        first = self.execute("bound-error")
        supervised = first["supervision"]
        self.assertTrue(any(e["kind"] == "engine_response" for e in supervised["events"]))
        for field, wrong in (("action", "gateway_stop"), ("name", "other")):
            bad = copy.deepcopy(supervised)
            for event in bad["events"]:
                if event["kind"] == "engine_response":
                    event[field] = wrong
            with self.subTest(field=field), patch.object(self.runner, "observe", return_value=bad):
                self.assertFalse(self.adapter.observe_action(self.action, first["attempt"], lock_fd=self.fd)["closed"])
        for field, wrong in (("path", "/containers/other/start"), ("method", "GET")):
            bad = copy.deepcopy(supervised)
            for event in bad["events"]:
                if event["kind"] == "engine_response":
                    event["response"][field] = wrong
            with self.subTest(field=field), patch.object(self.runner, "observe", return_value=bad):
                self.assertFalse(self.adapter.observe_action(self.action, first["attempt"], lock_fd=self.fd)["closed"])

    def test_response_record_failure_does_not_invent_a_completion_receipt(self):
        from admin.local_hand_deploy import supervision
        original = supervision._write_once
        def fail_response(path, value, maximum):
            if value.get("kind") == "engine_response":
                raise OSError("response journal unavailable")
            return original(path, value, maximum)
        with patch.object(supervision, "_write_once", side_effect=fail_response):
            result = self.execute("missing-receipt")
        self.assertFalse(result["closed"])
        self.assertFalse(any(e["kind"] == "engine_response" for e in result["supervision"]["events"]))
        self.assertIn("DOCKER_HTTP_400", result["supervision"]["result"]["error"])

    def check_not_sent(self, failure, name):
        with failure:
            first = self.execute(name)
        self.assertTrue(first["closed"])
        self.assertEqual("original", first["outcome"])
        self.assertFalse(first["dispatched"])
        self.assertFalse(first["postcondition"])
        self.assertFalse(self.requests.exists())
        self.mode.write_text("success")
        self.execute(name, first["attempt"])
        self.assertFalse(self.requests.exists())
        completed = self.execute(name + "-retry", first["attempt"])
        self.assertTrue(completed["postcondition"])
        self.assertEqual(1, self.count())
        return first

    def test_local_request_bound_failure_is_not_a_dispatched_operation(self):
        self.check_not_sent(patch.object(self.adapter.engine, "maximum", 256), "request-bound")

    def test_serialization_failure_is_not_a_dispatched_operation(self):
        self.check_not_sent(patch.object(self.adapter, "_create_body", return_value={"invalid": object()}),
                            "request-encoding")

    def connect_failure(self):
        from admin.local_hand_deploy import gateway
        request = self.adapter.engine.request
        def fail_connect(method, path, body=None, **kwargs):
            if method == "POST":
                with patch.object(gateway._UnixHTTP, "connect", side_effect=ConnectionRefusedError("connect refused")):
                    return request(method, path, body, **kwargs)
            return request(method, path, body, **kwargs)
        return patch.object(self.adapter.engine, "request", side_effect=fail_connect)

    def test_connect_failure_before_http_bytes_is_not_dispatched(self):
        self.check_not_sent(self.connect_failure(), "request-connect")

    def test_not_sent_proof_recording_failure_keeps_uncertainty(self):
        from admin.local_hand_deploy import supervision
        original = supervision._write_once
        def fail_proof(path, value, maximum):
            if value.get("kind") == "engine_not_sent":
                raise OSError("unsent proof unavailable")
            return original(path, value, maximum)
        with self.connect_failure(), patch.object(supervision, "_write_once", side_effect=fail_proof):
            result = self.execute("unsent-unrecorded")
        self.assertFalse(result["closed"])
        self.assertTrue(result["dispatched"])
        self.assertEqual("unknown", result["outcome"])
        self.assertFalse(self.requests.exists())
        self.assertIn("connect refused", result["supervision"]["result"]["error"])
        self.assertIn("PROOF_RECORD_FAILED", result["supervision"]["result"]["error"])

    def test_not_sent_proof_must_match_original_mutation(self):
        with self.connect_failure():
            first = self.execute("bound-unsent")
        self.assertFalse(first["dispatched"])
        supervised = first["supervision"]
        for field, wrong in (("method", "GET"), ("path", "/other"), ("stage", "response")):
            bad = copy.deepcopy(supervised)
            for event in bad["events"]:
                if event["kind"] == "engine_not_sent":
                    event["request"][field] = wrong
            with self.subTest(field=field), patch.object(self.runner, "observe", return_value=bad):
                observed = self.adapter.observe_action(self.action, first["attempt"], lock_fd=self.fd)
                self.assertFalse(observed["closed"])
                self.assertTrue(observed["dispatched"])

    def test_not_sent_proof_survives_missing_final_report(self):
        with self.connect_failure():
            first = self.execute("unsent-no-report")
        (Path(first["attempt"]["binding"]["result_directory"]) / "result.json").unlink()
        observed = self.adapter.observe_action(self.action, first["attempt"], lock_fd=self.fd)
        self.assertTrue(observed["closed"])
        self.assertFalse(observed["dispatched"])
        self.assertIsNone(observed["supervision"]["result"])
        self.assertFalse(self.requests.exists())

    def test_connect_error_type_after_request_is_still_unknown(self):
        from admin.local_hand_deploy import gateway
        request, receive = self.adapter.engine.request, gateway._UnixHTTP.getresponse
        def failed_reply(method, path, body=None, **kwargs):
            def received(connection):
                receive(connection)
                raise ConnectionRefusedError("transport failed after HTTP request was sent")
            if method == "POST":
                with patch.object(gateway._UnixHTTP, "getresponse", received):
                    return request(method, path, body, **kwargs)
            return request(method, path, body, **kwargs)
        with patch.object(self.adapter.engine, "request", side_effect=failed_reply):
            result = self.execute("sent-connect-error")
        self.assertFalse(result["closed"])
        self.assertTrue(result["dispatched"])
        self.assertEqual("unknown", result["outcome"])
        self.assertEqual(1, self.count())
        self.mode.write_text("success")
        repeated = self.execute("must-not-repeat", result["attempt"])
        self.assertFalse(repeated["closed"])
        self.assertEqual(1, self.count())

    def test_all_mutations_bind_responses_and_legacy_success_to_original_dispatch(self):
        for kind, method, suffix in (("gateway_start", "POST", "/start"),
                                     ("gateway_stop", "POST", "/stop?t=10"),
                                     ("gateway_remove", "DELETE", "?force=false&v=false")):
            action = {**self.action, "kind": kind, "before": {"id": "selected"}}
            dispatch = {"kind": "engine_dispatch", "action": kind, "container_id": "selected"}
            reply = {"kind": "engine_response", "action": kind, "container_id": "selected",
                     "response": DockerHTTPError(method, "/containers/selected" + suffix, 500, b"error").response}
            with self.subTest(kind=kind):
                self.assertTrue(self.adapter._response_closed(action, [dispatch, reply]))
                self.assertFalse(self.adapter._response_closed(action, [reply, dispatch]))
                self.assertFalse(self.adapter._response_closed(action, [dispatch, {**reply, "container_id": "other"}]))
                legacy = {"kind": "engine_returned", "action": kind, "container_id": "selected"}
                self.assertTrue(self.adapter._response_closed(action, [dispatch, legacy]))
                self.assertFalse(self.adapter._response_closed(action, [dispatch, {**legacy, "container_id": "other"}]))
        create = {"kind": "engine_dispatch", "action": "gateway_create", "name": self.adapter.name}
        created = {"kind": "engine_returned", "action": "gateway_create", "container_id": "created-container"}
        self.assertTrue(self.adapter._response_closed(self.action, [create, created]))
        self.assertFalse(self.adapter._response_closed(self.action, [{**create, "name": "other"}, created]))

    def check_unknown(self, mode):
        self.mode.write_text(mode)
        result = self.execute(mode)
        self.assertTrue(result["supervision"]["closed"])
        self.assertFalse(result["closed"])
        self.assertEqual("unknown", result["outcome"])
        self.mode.write_text("success")
        self.execute("cannot-repeat", result["attempt"])
        self.assertEqual(1, self.count())

    def test_disconnected_request_stays_unknown(self):
        self.check_unknown("disconnect")

    def test_truncated_error_response_stays_unknown(self):
        self.check_unknown("truncated")

    def test_oversized_error_response_stays_unknown(self):
        self.check_unknown("oversized")

    def coordinator(self, *, limits=Limits()):
        store = Store(self.root / "deployments", "response-node", limits=limits)
        store.initialize()
        gate_root = self.root / "admission"
        gate_root.mkdir(mode=0o700)
        gate = MaintenanceGate(gate_root, "response-node", owner_uid=os.geteuid())
        gate.initialize(digest("old"), "bootstrap", bootstrap=True)
        adapter = self.adapter
        class GatewayEffects(Effects):
            def effect_key(self, step):
                return "gateway"

            def observe(self, step, prepared, attempt=None):
                value = adapter.observe_action(prepared, attempt.get("binding") if attempt else None,
                                               lock_fd=store.lock_fd)
                return {**value, "state": value["outcome"], "effective": value["postcondition"]}

            def execute(self, step, prepared, op, attempt_id, persist_intent, previous=None):
                value = adapter.execute(prepared, attempt_id=attempt_id, lock_fd=store.lock_fd,
                    persist_intent=persist_intent, previous=previous.get("binding") if previous else None)
                return {**value, "state": value["outcome"], "effective": value["postcondition"]}
        plan = seal_plan({"schema": PLAN_SCHEMA, "request_id": "response-recovery", "node_id": "response-node",
            "source": {"deployment_digest": digest("old")}, "target": {"deployment_digest": "c" * 64},
            "steps": [{"id": "gateway", "kind": "gateway", "action": self.action}], "profile": {}})
        return Coordinator(store, gate, GatewayEffects()), plan, gate

    def test_coordinator_resumes_same_operation_after_explicit_failure(self):
        coordinator, plan, gate = self.coordinator()
        original = coordinator.apply(plan)
        self.assertIsNone(original["decision"])
        self.assertEqual("CLOSED", gate.snapshot()["state"])
        self.mode.write_text("success")
        completed = coordinator.resume(original["id"])
        self.assertEqual("COMMITTED", completed["decision"])
        self.assertTrue(completed["released"])
        self.assertEqual("OPEN", gate.snapshot()["state"])
        coordinator.resume(original["id"])
        self.assertEqual(2, self.count())

    def test_coordinator_can_abandon_rejected_request_without_new_mutations(self):
        coordinator, plan, gate = self.coordinator()
        original = coordinator.apply(plan)
        finished = coordinator.rollback(original["id"])
        self.assertEqual("ABORTED_NO_CHANGE", finished["decision"])
        self.assertTrue(finished["released"])
        self.assertEqual("OPEN", gate.snapshot()["state"])
        self.assertEqual(1, self.count())

    def test_unsent_attempt_does_not_consume_coordinator_dispatch_budget(self):
        coordinator, plan, gate = self.coordinator(limits=Limits(max_attempts=1))
        with self.connect_failure():
            original = coordinator.apply(plan)
        first = copy.deepcopy(original["steps"][0]["attempts"][0])
        self.assertFalse(first["dispatched"])
        self.assertIsNone(original["decision"])
        self.assertFalse(self.requests.exists())
        self.mode.write_text("success")
        completed = coordinator.resume(original["id"])
        self.assertEqual("COMMITTED", completed["decision"])
        self.assertTrue(completed["released"])
        self.assertEqual("OPEN", gate.snapshot()["state"])
        attempts = completed["steps"][0]["attempts"]
        self.assertEqual(2, len(attempts))
        self.assertEqual(first, attempts[0])
        self.assertTrue(attempts[1]["dispatched"])
        coordinator.resume(original["id"])
        self.assertEqual(1, self.count())


class ResponseFramingTests(unittest.TestCase):
    def request(self, raw):
        class Socket:
            def makefile(self, *_):
                return io.BytesIO(raw)
        response = http.client.HTTPResponse(Socket())
        response.begin()
        with patch("admin.local_hand_deploy.gateway._UnixHTTP") as connection:
            connection.return_value.getresponse.return_value = response
            return DockerEngine("/unused/test.sock").request("POST", "/containers/test/start")

    def test_complete_chunked_error_is_a_receipt(self):
        with self.assertRaises(DockerHTTPError) as failure:
            self.request(b"HTTP/1.1 500 Error\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nerror\r\n0\r\n\r\n")
        self.assertEqual(5, failure.exception.response["bytes"])

    def test_truncated_chunked_error_is_not_a_receipt(self):
        with self.assertRaises(http.client.IncompleteRead):
            self.request(b"HTTP/1.1 500 Error\r\nTransfer-Encoding: chunked\r\n\r\n8\r\nshort")

    def test_connection_closed_body_is_complete(self):
        with self.assertRaises(DockerHTTPError):
            self.request(b"HTTP/1.0 400 Error\r\n\r\nerror")


if __name__ == "__main__":
    unittest.main()

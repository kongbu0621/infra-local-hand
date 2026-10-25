"""Original policy identity stays separate from privileged startup controls.

The same tests exercise real mixed ownership when run as root; ordinary runs
also check explicit owner enforcement without mocking filesystem metadata.
"""
import copy
import hashlib
import os
from pathlib import Path
import pwd
import socket
import tempfile
import threading
import unittest

from admin.local_hand_deploy.model import DeployError
from admin.local_hand_deploy.runtime import PlanningEnvironment
from local_hand_jobs import maintenance, startup
from local_hand_jobs.contract import JobError


class StartupOwnershipTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.root.chmod(0o755)
        self.owner = os.geteuid()
        self.data_owner = pwd.getpwnam("nobody").pw_uid if self.owner == 0 else self.owner
        self.data = self.root / "task"; self.data.mkdir(mode=0o700)
        self.policy = self.data / "policy.json"; self.policy.write_bytes(b'{"original":true}')
        self.policy.chmod(0o600)
        if self.owner == 0:
            os.chown(self.data, self.data_owner, -1); os.chown(self.policy, self.data_owner, -1)
        self.manager_path = str(self.root / "manager.json")
        self.mcp_path = str(self.root / "mcp.json")
        self.auth = self.root / "auth.json"; self.auth.write_bytes(b'{}'); self.auth.chmod(0o600)
        self.descriptor = self.root / "selection.json"
        (self.root / "gate").mkdir(mode=0o700)
        self.gate = maintenance.MaintenanceGate(self.root / "gate", "node", owner_uid=self.owner)
        self.gate.initialize("a" * 64, "initial", bootstrap=True)
        self.manager = {"uid": self.data_owner, "socket": str(self.root / "manager.sock"),
            "installation": {"installed": {"payload_digest": "b" * 64}},
            "maintenance": {"schema": maintenance.CONFIG_SCHEMA, "node_id": "node",
                "deployment_digest": "a" * 64, "directory": str(self.root / "gate"),
                "startup_descriptor": str(self.descriptor)}}
        self.mcp = {"schema": "local-hand-mcp-startup/v1", "node_id": "node",
            "deployment_digest": "a" * 64, "payload_digest": "b" * 64,
            "manager_socket": self.manager["socket"], "mode": "read_only", "port": 8181,
            "inputs": {"config": str(self.policy), "auth_config": str(self.auth)}}
        self.profile = {"owner_uid": self.owner, "startup_descriptor": str(self.descriptor),
            "maintenance_directory": str(self.root / "gate"), "guarded_components": {
                "manager": {"configuration": self.manager_path}, "mcp": {"configuration": self.mcp_path}},
            "probes": {"manager": {"kind": "resident", "socket": self.manager["socket"]},
                       "mcp": {"kind": "mcp", "socket": self.manager["socket"]}}}
        self.environment = PlanningEnvironment(self.profile)
        self.rebind()

    def rebind(self):
        for path, config in ((self.manager_path, self.manager), (self.mcp_path, self.mcp)):
            Path(path).write_bytes(startup.canonical(config)); Path(path).chmod(0o600)
        paths = [self.manager_path, self.mcp_path, str(self.policy), str(self.auth)]
        self.selection = {"schema": startup.SCHEMA, "node_id": "node", "deployment_digest": "a" * 64,
            "decision_id": "initial", "mode": "stable", "owner": None, "permit": None,
            "members": [{"path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                         **({"owner_uid": self.data_owner} if path == str(self.policy) else {})} for path in paths],
            "components": {"manager": {"configuration_digest": maintenance.digest(
                {k: v for k, v in self.manager.items() if k != "maintenance"}),
                "payload_digest": "b" * 64, "entry": "local", "running": True},
                "mcp": {"configuration_digest": startup.digest({"inputs": {name: {
                    "path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                    for name, path in self.mcp["inputs"].items()}, "mode": "read_only", "port": 8181}),
                    "payload_digest": "b" * 64, "entry": "local", "running": False}}}

    def test_original_policy_passes_planning_publication_and_actual_admission(self):
        before = self.policy.read_bytes(), self.policy.stat().st_ino, self.policy.stat().st_uid
        self.environment._verify_components(self.selection)
        startup.publish(self.descriptor, self.selection, self.gate, expected_digest=None, owner_uid=self.owner)
        with self.gate.admission_lock() as state:
            value = startup._admit_selection(self.descriptor, state, "manager", os.getpid(), owner_uid=self.owner)
        self.assertEqual(self.selection, value)
        self.assertEqual(before, (self.policy.read_bytes(), self.policy.stat().st_ino, self.policy.stat().st_uid))
        self.policy.write_bytes(b'{"changed":true}')
        with self.assertRaises(JobError):
            with self.gate.admission_lock() as state:
                startup._admit_selection(self.descriptor, state, "manager", os.getpid(), owner_uid=self.owner)

    def test_explicit_data_owner_works_with_privileged_read_boundary(self):
        startup.verify_members(self.selection, owner_uid=0 if self.owner == 0 else self.owner)
        member = copy.deepcopy(self.selection["members"][2])
        selected = copy.deepcopy(self.selection); selected["members"] = [member]
        # This reproduces the production failure even as an ordinary user:
        # the file is in a data-owned directory, not an administrator directory.
        startup.verify_members(selected, owner_uid=0)
        del member["owner_uid"]
        with self.assertRaises(JobError): startup.verify_members(selected, owner_uid=0)

    def test_wrong_owner_is_rejected_without_relying_only_on_hash(self):
        self.selection["members"][2]["owner_uid"] = self.data_owner + 1
        with self.assertRaises(JobError): startup.verify_members(self.selection, owner_uid=self.owner)
        with self.assertRaises(DeployError): self.environment._verify_components(self.selection)

    def test_control_or_unrelated_member_cannot_delegate_owner(self):
        foreign = self.owner + 1
        for index in (0, 1, 3):
            selected = copy.deepcopy(self.selection); selected["members"][index]["owner_uid"] = foreign
            with self.subTest(index=index), self.assertRaises(DeployError):
                self.environment._verify_components(selected)
        extra = self.root / "unrelated"; extra.write_bytes(b'{}'); extra.chmod(0o600)
        self.selection["members"].append({"path": str(extra), "sha256": hashlib.sha256(b'{}').hexdigest(), "owner_uid": foreign})
        with self.assertRaises(DeployError): self.environment._verify_components(self.selection)

    def test_policy_owner_must_match_selected_manager(self):
        self.manager["uid"] = self.data_owner + 1; self.rebind()
        # Explicit policy owner must be checked even when equal to the
        # coordinator uid in an ordinary-user fixture.
        with self.assertRaises(DeployError): self.environment._verify_components(self.selection)

    def test_private_policy_cannot_double_as_authentication_control(self):
        self.mcp["inputs"]["auth_config"] = str(self.policy); self.rebind()
        with self.assertRaises(DeployError): self.environment._verify_components(self.selection)

    def test_owner_declaration_does_not_allow_links_or_writable_ancestors(self):
        original = self.policy.read_bytes()
        self.data.chmod(0o777)
        try:
            with self.assertRaises(JobError): startup.verify_members(self.selection, owner_uid=self.owner)
        finally: self.data.chmod(0o700)
        self.policy.unlink(); self.policy.symlink_to(self.auth)
        with self.assertRaises(JobError): startup.verify_members(self.selection, owner_uid=self.owner)
        self.assertEqual(b'{}', self.auth.read_bytes()); self.assertNotEqual(original, self.auth.read_bytes())

    def test_invalid_owner_and_legacy_omission(self):
        for uid in (True, -1, 2**32-1, "1000", None):
            selected = copy.deepcopy(self.selection); selected["members"][2]["owner_uid"] = uid
            with self.subTest(uid=uid), self.assertRaises(ValueError): startup.validate(selected)
        # Old root-only selections retain their original format and behavior.
        self.selection["members"] = self.selection["members"][:2]
        startup.verify_members(self.selection, owner_uid=self.owner)

    def test_mcp_probe_uses_actual_peer_directory_and_never_the_manager_socket(self):
        from local_hand_jobs import cli
        path = self.root / "maintenance.sock"
        environment = PlanningEnvironment({"owner_uid": 0, "timeout_seconds": 2,
            "probes": {"mcp": {"kind": "mcp", "socket": str(path), "peer_uid": os.geteuid()}}})
        proof = {**startup.instance(os.getpid()), "component": "mcp", "protocol_ready": True}
        errors = []
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(path)); listener.listen(); listener.settimeout(2)
            def respond():
                try:
                    with listener.accept()[0] as peer:
                        peer.settimeout(2)
                        request = cli._read_frame(peer, 4096)
                        self.assertEqual(startup.canonical({"action": "deployment_observe"}), request)
                        cli._send_frame(peer, {"result": proof})
                except BaseException as error: errors.append(error)
            worker = threading.Thread(target=respond); worker.start()
            try: self.assertEqual(proof, environment._probe("mcp")["loaded"])
            finally: worker.join(3)
            self.assertEqual([], errors); self.assertFalse(worker.is_alive())
            environment.profile["probes"]["mcp"]["peer_uid"] = os.geteuid() + 1
            with self.assertRaises(DeployError): environment._probe("mcp")


if __name__ == "__main__":
    unittest.main()

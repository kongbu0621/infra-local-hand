from __future__ import annotations

import gc
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from local_hand import act, git_safety, observe, validate, worker
from local_hand.paths import load_profile, repository_target
from config_fixtures import profile_v2
from local_hand.protocol import LocalHandError, MAX_TASK_JSON_BYTES, MAX_TEXT_BYTES, task_digest

MAILBOX_BRANCH = "fixture/mailbox-v1"


class LocalHandHardeningBTests(unittest.TestCase):
    def setUp(self) -> None:
        admission = mock.patch.object(worker, "validate_worker_mailbox")
        admission.start(); self.addCleanup(admission.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.projects = self.root / "projects"
        self.repo = self.projects / "scratch-local-hand"
        self.repo.mkdir(parents=True)
        self._git(self.repo, "init", "-q")
        self._git(self.repo, "config", "user.email", "test@example.invalid")
        self._git(self.repo, "config", "user.name", "Local Hand Hardening")
        (self.repo / "sample.txt").write_text("before\n", encoding="utf-8")
        self._git(self.repo, "add", "."); self._git(self.repo, "commit", "-qm", "baseline")
        profile = {
            "node_id": "test-node",
            "projects_root": str(self.projects),
            "repositories": {"scratch-local-hand": {
                "path": "scratch-local-hand", "single_writer": True,
                "validations": {
                    "pass": {"argv": [sys.executable, "-c", "print('PASS')"], "timeout_seconds": 5, "replay_safe": True},
                    "flood": {"argv": [sys.executable, "-c", "import sys; sys.stdout.write('x'*20000)"], "timeout_seconds": 5, "replay_safe": True},
                },
            }},
        }
        self.profile_path = self.root / "profile.json"
        self.profile_path.write_text(json.dumps(profile_v2(profile)), encoding="utf-8")
        self.profile = load_profile(self.profile_path)
        self.runtime = self.root / "runtime"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def task(self, task_id: str, action: str = "node.status", params: dict | None = None) -> dict:
        return {"schema_version":"local-hand-task/v1","task_id":task_id,"target_node":"test-node","action":action,"params":params or {}}

    def _init_mailbox(self) -> tuple[Path, Path]:
        origin=self.root/"mailbox-origin.git"; seed=self.root/"mailbox-seed"; mailbox=self.root/"mailbox-worker"
        self._git(self.root,"init","--bare","-q",str(origin)); seed.mkdir(); self._git(seed,"init","-q"); self._git(seed,"config","user.email","mailbox@example.invalid"); self._git(seed,"config","user.name","Mailbox Test")
        for name in ("tasks","results","conflicts"):
            d=seed/"_executor_spike"/name; d.mkdir(parents=True); (d/".keep").write_text("keep\n",encoding="utf-8")
        self._git(seed,"add","."); self._git(seed,"commit","-qm","baseline"); self._git(seed,"branch","-M",MAILBOX_BRANCH); self._git(seed,"remote","add","origin",str(origin)); self._git(seed,"push","-q","-u","origin",MAILBOX_BRANCH); self._git(self.root,"clone","-q","--branch",MAILBOX_BRANCH,str(origin),str(mailbox)); return seed,mailbox

    def _commit_raw(self, seed: Path, files: dict[str,str], message: str) -> None:
        for rel,content in files.items(): p=seed/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding="utf-8")
        self._git(seed,"add","."); self._git(seed,"commit","-qm",message); self._git(seed,"push","-q","origin",MAILBOX_BRANCH)

    def test_windows_alias_and_separator_forms_are_rejected_everywhere(self) -> None:
        original=(self.repo/"sample.txt").read_bytes(); digest=hashlib.sha256(original).hexdigest()
        cases={
            ".git\\config":"path_separator_rejected",
            "..\\outside.txt":"path_separator_rejected",
            "C:/Windows/system.ini":"windows_path_alias_rejected",
            "sample.txt:stream":"windows_path_alias_rejected",
            "NUL":"windows_path_alias_rejected",
            "CONIN$":"windows_path_alias_rejected",
            "CONOUT$.txt":"windows_path_alias_rejected",
            "CON .txt":"windows_path_alias_rejected",
            "COM1 .log":"windows_path_alias_rejected",
            "COM\u00b9.txt":"windows_path_alias_rejected",
            "LPT\u00b2.txt":"windows_path_alias_rejected",
            "trailing.":"windows_path_alias_rejected",
            "trailing ":"windows_path_alias_rejected",
            "bad?.txt":"windows_path_alias_rejected",
            "bad*.txt":"windows_path_alias_rejected",
            "bad<name>.txt":"windows_path_alias_rejected",
            'bad"name.txt':"windows_path_alias_rejected",
            "bad|name.txt":"windows_path_alias_rejected",
            "bad\x1fname.txt":"path_syntax_rejected",
            "a//sample.txt":"path_not_canonical",
            "a/./sample.txt":"path_not_canonical",
            "./sample.txt":"path_not_canonical",
            "sample.txt/":"path_not_canonical",
            "cafe\u0301.txt":"path_unicode_normalization_rejected",
        }
        for bad,code in cases.items():
            with self.subTest(bad=bad):
                with self.assertRaises(LocalHandError) as ctx: observe.fs_read_text(self.profile,"scratch-local-hand",bad)
                self.assertEqual(ctx.exception.code,code)
                with self.assertRaises(LocalHandError) as ctx: act.fs_write_text_cas(self.profile,"scratch-local-hand",bad,digest,"blocked\n",lease_root=self.runtime/"leases")
                self.assertEqual(ctx.exception.code,code)
        self.assertEqual((self.repo/"sample.txt").read_bytes(),original)

    def test_native_path_spelling_mismatch_is_rejected_without_write(self) -> None:
        exact = self.repo / "CaseOnly.txt"
        exact.write_bytes(b"case-sensitive identity\n")
        digest = hashlib.sha256(exact.read_bytes()).hexdigest()
        expected_code = "path_identity_mismatch" if os.name == "nt" else "path_missing"
        with self.assertRaises(LocalHandError) as ctx:
            observe.fs_read_text(self.profile, "scratch-local-hand", "caseonly.txt")
        self.assertEqual(ctx.exception.code, expected_code)
        with self.assertRaises(LocalHandError) as ctx:
            act.fs_write_text_cas(
                self.profile, "scratch-local-hand", "caseonly.txt", digest, "blocked\n",
                lease_root=self.runtime / "leases",
            )
        self.assertEqual(ctx.exception.code, expected_code)
        self.assertEqual(exact.read_bytes(), b"case-sensitive identity\n")

    def test_repository_target_preflight_is_canonical_confined_and_nonmutating(self) -> None:
        self.assertEqual(repository_target(self.projects, "scratch-local-hand"), self.repo.resolve())
        canonical_projects = self.projects.resolve()
        self.assertEqual(repository_target(self.projects, "space name"), canonical_projects / "space name")
        case_parent = self.projects / "CaseParent"
        case_parent.mkdir()
        if (self.projects / "caseparent").exists():
            with self.assertRaises(LocalHandError) as ctx:
                repository_target(self.projects, "caseparent/not-created-yet")
            self.assertEqual(ctx.exception.code, "path_identity_mismatch")
        else:
            self.assertEqual(
                repository_target(self.projects, "caseparent/not-created-yet"),
                canonical_projects / "caseparent" / "not-created-yet",
            )
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        for bad, code in (("./scratch-local-hand", "path_not_canonical"), ("bad?.git", "windows_path_alias_rejected")):
            with self.subTest(bad=bad):
                with self.assertRaises(LocalHandError) as ctx:
                    repository_target(self.projects, bad)
                self.assertEqual(ctx.exception.code, code)
        after = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        self.assertEqual(after, before)

    @unittest.skipIf(os.name == "nt", "POSIX symlink construction proof")
    def test_repository_target_preflight_rejects_symlink_escape(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (self.projects / "alias").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(LocalHandError) as ctx:
            repository_target(self.projects, "alias/repository")
        self.assertEqual(ctx.exception.code, "path_escape")

    def test_noncanonical_profile_repository_paths_are_rejected(self) -> None:
        base = json.loads(self.profile_path.read_text(encoding="utf-8"))
        for index, bad in enumerate(("./scratch-local-hand", "scratch-local-hand/", "scratch//local-hand", "cafe\u0301")):
            with self.subTest(bad=bad):
                value = json.loads(json.dumps(base))
                value["repositories"]["scratch-local-hand"]["path"] = bad
                candidate = self.root / f"bad-profile-{index}.json"
                candidate.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(LocalHandError) as ctx:
                    load_profile(candidate)
                self.assertEqual(ctx.exception.code, "invalid_profile")

    def test_noncanonical_task_is_rejected_with_original_digest_and_no_queue_wedge(self) -> None:
        seed, mailbox = self._init_mailbox()
        before = (self.repo / "sample.txt").read_bytes()
        bad = self.task("LH0210", "fs.write_text_cas", {
            "repository": "scratch-local-hand",
            "relative_path": "./sample.txt",
            "expected_sha256": hashlib.sha256(before).hexdigest(),
            "content": "must-not-write\n",
        })
        later = self.task("LH0211")
        self._commit_raw(seed, {
            "_executor_spike/tasks/LH0210.json": json.dumps(bad) + "\n",
            "_executor_spike/tasks/LH0211.json": json.dumps(later) + "\n",
        }, "noncanonical path")
        state = self.runtime / "state"
        worker.process_once(mailbox, MAILBOX_BRANCH, self.profile, state)
        worker.sync_mailbox(mailbox, MAILBOX_BRANCH)
        rejected = json.loads((mailbox / "_executor_spike/results/LH0210.json").read_text(encoding="utf-8"))
        succeeded = json.loads((mailbox / "_executor_spike/results/LH0211.json").read_text(encoding="utf-8"))
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error_code"], "path_not_canonical")
        self.assertEqual(rejected["task_digest"], task_digest(bad))
        self.assertEqual(succeeded["status"], "succeeded")
        self.assertEqual((self.repo / "sample.txt").read_bytes(), before)

    def test_repo_audit_redacts_remote_credentials_and_unknown_helpers(self) -> None:
        self._git(self.repo,"remote","add","secret","https://alice:sekrit@example.com/repo.git?token=abc123#fragment")
        self._git(self.repo,"remote","add","helper","ext::sh -c echo-super-secret")
        audit=observe.repo_audit(self.profile,"scratch-local-hand"); rendered="\n".join(audit["remotes"])
        for secret in ("alice","sekrit","abc123","fragment","echo-super-secret"): self.assertNotIn(secret,rendered)
        self.assertIn("https://example.com/repo.git",rendered); self.assertIn("<redacted-remote-helper>",rendered); self.assertTrue(audit["git_helpers_disabled"]["bounded_output"])

    def test_git_read_actions_disable_execution_capable_helpers(self) -> None:
        status=observe.git_status(self.profile,"scratch-local-hand"); diff=observe.git_diff(self.profile,"scratch-local-hand")
        self.assertTrue(status["fsmonitor_disabled"]); self.assertTrue(status["execution_filters_rejected"]); self.assertTrue(status["bounded_output"])
        self.assertTrue(diff["ext_diff_disabled"]); self.assertTrue(diff["textconv_disabled"]); self.assertTrue(diff["execution_filters_rejected"]); self.assertTrue(diff["bounded_output"])

    def test_ambient_git_dir_cannot_redirect_allowlisted_read(self) -> None:
        other=self.root/"other"; other.mkdir(); self._git(other,"init","-q"); self._git(other,"config","user.email","o@x.invalid"); self._git(other,"config","user.name","Other"); (other/"x").write_text("x"); self._git(other,"add","."); self._git(other,"commit","-qm","o")
        expected=self._git(self.repo,"rev-parse","HEAD").stdout.strip()
        with mock.patch.dict(os.environ,{"GIT_DIR":str(other/".git"),"GIT_WORK_TREE":str(other),"GIT_INDEX_FILE":str(other/".git"/"index")},clear=False): audit=observe.repo_audit(self.profile,"scratch-local-hand")
        self.assertEqual(audit["head"],expected)

    def test_sanitized_mailbox_git_env_overrides_ambient_ssh_and_config(self) -> None:
        with mock.patch.dict(os.environ,{"GIT_DIR":"evil","GIT_CONFIG_COUNT":"9","GIT_SSH_COMMAND":"evil","SSH_AUTH_SOCK":"agent"},clear=False): env=git_safety.sanitized_git_env(allow_ssh=True)
        for key in ("GIT_DIR","GIT_CONFIG_COUNT","SSH_AUTH_SOCK"): self.assertNotIn(key,env)
        self.assertNotEqual(env["GIT_SSH_COMMAND"],"evil"); self.assertIn("IdentityAgent=none",env["GIT_SSH_COMMAND"])

    def test_configured_clean_filter_is_rejected_without_marker_execution(self) -> None:
        marker=self.root/"marker"; (self.repo/".gitattributes").write_text("sample.txt filter=marker\n"); self._git(self.repo,"config","filter.marker.clean",f'echo FILTER_RAN > "{marker}"'); (self.repo/"sample.txt").write_text("changed\n")
        with self.assertRaises(LocalHandError) as ctx: observe.git_diff(self.profile,"scratch-local-hand")
        self.assertEqual(ctx.exception.code,"git_filter_rejected"); self.assertFalse(marker.exists())

    @unittest.skipIf(os.name=="nt","POSIX hook execution proof")
    def test_mailbox_precommit_hook_is_not_executed(self) -> None:
        _,mailbox=self._init_mailbox(); marker=self.root/"hook-marker"; hook=mailbox/".git"/"hooks"/"pre-commit"; hook.write_text(f"#!/bin/sh\nprintf hit > '{marker}'\n"); hook.chmod(0o755); (mailbox/"hook-test.txt").write_text("x\n")
        worker.run_git(["add","--","hook-test.txt"],mailbox); worker.run_git(["-c","user.name=local-hand","-c","user.email=local@invalid","commit","-m","hook-test"],mailbox); self.assertFalse(marker.exists())

    def test_write_limit_is_symmetric_and_zero_side_effect(self) -> None:
        before=(self.repo/"sample.txt").read_bytes(); digest=hashlib.sha256(before).hexdigest()
        with self.assertRaises(LocalHandError) as ctx: act.fs_write_text_cas(self.profile,"scratch-local-hand","sample.txt",digest,"x"*(MAX_TEXT_BYTES+1),lease_root=self.runtime/"leases")
        self.assertEqual(ctx.exception.code,"write_too_large"); self.assertEqual((self.repo/"sample.txt").read_bytes(),before)

    def test_task_json_limit_and_parser_failure_are_typed(self) -> None:
        p=self.root/"LH0999.json"; p.write_bytes(b"{"+b"x"*MAX_TASK_JSON_BYTES+b"}")
        with self.assertRaises(LocalHandError) as ctx: worker.load_json_bounded(p,MAX_TASK_JSON_BYTES,"task_file_invalid")
        self.assertEqual(ctx.exception.code,"task_file_invalid")
        p.write_text("[]")
        with mock.patch("local_hand.worker.json.loads",side_effect=RecursionError("deep")):
            with self.assertRaises(LocalHandError) as ctx: worker.load_json_bounded(p,MAX_TASK_JSON_BYTES,"task_file_invalid")
        self.assertEqual(ctx.exception.status,"indeterminate")

    def test_malformed_canonical_remote_result_is_quarantined_without_queue_wedge(self) -> None:
        seed,mailbox=self._init_mailbox(); first=self.task("LH0201"); later=self.task("LH0202")
        self._commit_raw(seed,{"_executor_spike/tasks/LH0201.json":json.dumps(first)+"\n","_executor_spike/tasks/LH0202.json":json.dumps(later)+"\n","_executor_spike/results/LH0201.json":"{not-json\n"},"bad remote")
        state=self.runtime/"state"; worker.process_once(mailbox,MAILBOX_BRANCH,self.profile,state); worker.sync_mailbox(mailbox,MAILBOX_BRANCH)
        later_result=json.loads((mailbox/"_executor_spike/results/LH0202.json").read_text()); self.assertEqual(later_result["status"],"succeeded")
        conflict = mailbox / "_executor_spike/conflicts" / worker._conflict_filename("LH0201", task_digest(first))
        self.assertTrue(conflict.exists()); self.assertEqual(json.loads(conflict.read_text())["error_code"],"remote_result_invalid")

    def test_remote_result_minimum_schema_and_identity_validation(self) -> None:
        with self.assertRaises(LocalHandError): worker.validate_remote_result({"schema_version":"local-hand-result/v1"},"LH0203")
        task=self.task("LH0203"); valid=worker.result_success(task,"test-node",{},worker.build_provenance(self.profile)); forged=dict(valid); forged["action"]="git.status"
        with self.assertRaises(LocalHandError): worker.validate_remote_result(forged,"LH0203","node.status","test-node",task_digest(task))

    def test_conflict_marker_recovers_after_outbox_write_failure_without_replay(self) -> None:
        seed, mailbox = self._init_mailbox()
        task, later = self.task("LH0250"), self.task("LH0251")
        self._commit_raw(seed, {
            "_executor_spike/tasks/LH0250.json": json.dumps(task),
            "_executor_spike/tasks/LH0251.json": json.dumps(later),
            "_executor_spike/results/LH0250.json": "{invalid fixture result\n",
        }, "fixture recovery interruption")
        state = self.runtime / "state"
        original_write = worker.write_json_atomic

        def fail_outbox(path, *args, **kwargs):
            if path.parent == state / "outbox" and path.name.startswith("CONFLICT-"):
                raise OSError("injected outbox persistence failure")
            return original_write(path, *args, **kwargs)

        with mock.patch.object(worker, "write_json_atomic", side_effect=fail_outbox):
            with self.assertRaises(OSError):
                worker.process_once(mailbox, MAILBOX_BRANCH, self.profile, state)
        name = worker._conflict_filename(task["task_id"], task_digest(task))
        marker = state / "conflicts" / name
        preserved = marker.read_bytes()
        with mock.patch.object(worker, "execute_task", wraps=worker.execute_task) as execute:
            worker.process_once(mailbox, MAILBOX_BRANCH, self.profile, state)
            self.assertEqual([call.args[0]["task_id"] for call in execute.call_args_list], [later["task_id"]])
        worker.sync_mailbox(mailbox, MAILBOX_BRANCH)
        self.assertEqual(marker.read_bytes(), preserved)
        self.assertEqual(json.loads((mailbox / "_executor_spike/conflicts" / name).read_text()), json.loads(preserved))
        self.assertFalse((state / "receipts/LH0250.json").exists())
        self.assertEqual(json.loads((mailbox / "_executor_spike/results/LH0251.json").read_text())["status"], "succeeded")
        before = self._git(mailbox, "rev-parse", "HEAD").stdout
        with mock.patch.object(worker, "execute_task") as execute:
            worker.process_once(mailbox, MAILBOX_BRANCH, self.profile, state)
            execute.assert_not_called()
        self.assertEqual(self._git(mailbox, "rev-parse", "HEAD").stdout, before)
        self.assertEqual(marker.read_bytes(), preserved)

    def test_repeated_result_collision_retains_each_original_byte_stream(self) -> None:
        seed, mailbox = self._init_mailbox()
        task = self.task("LH0252")
        identity = worker.build_provenance(self.profile)
        remote = worker.result_success(task, self.profile.node_id, {"origin": "remote"}, identity)
        local = worker.result_success(task, self.profile.node_id, {"origin": "local"}, identity)
        self._commit_raw(seed, {"_executor_spike/results/LH0252.json": json.dumps(remote)}, "fixture collision")
        outbox = self.runtime / "outbox"
        outbox.mkdir(parents=True)
        originals = (json.dumps(local, indent=2).encode(), json.dumps(local, separators=(",", ":")).encode())
        for raw in originals:
            (outbox / "LH0252.json").write_bytes(raw)
            worker.publish_outbox(mailbox, MAILBOX_BRANCH, outbox)
        archives = list((outbox.parent / "quarantine").glob("LH0252.json.*.conflict"))
        self.assertEqual(len(archives), 2)
        self.assertEqual({path.read_bytes() for path in archives}, set(originals))
        self.assertEqual(json.loads((mailbox / "_executor_spike/results/LH0252.json").read_text()), remote)

    def test_malformed_local_outbox_is_quarantined_not_published(self) -> None:
        _,mailbox=self._init_mailbox(); outbox=self.runtime/"out"; outbox.mkdir(parents=True); bad={"schema_version":"local-hand-result/v1","task_id":"../../bad","task_digest":"a"*64,"target_node":"test-node","action":"node.status","status":"succeeded"}; (outbox/"LH0204.json").write_text(json.dumps(bad))
        worker.publish_outbox(mailbox,MAILBOX_BRANCH,outbox); self.assertFalse((outbox/"LH0204.json").exists())
        second=dict(bad);second["action"]="git.status";(outbox/"LH0204.json").write_text(json.dumps(second))
        worker.publish_outbox(mailbox,MAILBOX_BRANCH,outbox)
        quarantined=list((outbox.parent/"quarantine").glob("LH0204.json.*.invalid"))
        self.assertEqual(len(quarantined),2);self.assertEqual({path.read_text() for path in quarantined},{json.dumps(bad),json.dumps(second)})

    def test_validation_output_is_resource_bounded_while_drained(self) -> None:
        old=validate.MAX_OUTPUT_BYTES; validate.MAX_OUTPUT_BYTES=1024
        try:
            with self.assertRaises(validate.ValidationFailed) as ctx: validate.run_profile(self.profile,"scratch-local-hand","flood")
        finally: validate.MAX_OUTPUT_BYTES=old
        self.assertEqual(ctx.exception.code,"validation_output_too_large"); self.assertLessEqual(ctx.exception.details["stdout_captured_bytes"],1024); self.assertGreater(ctx.exception.details["stdout_observed_bytes"],1024)

    def test_validation_closes_parent_pipe_descriptors_without_resourcewarning(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always",ResourceWarning); details=validate.run_profile(self.profile,"scratch-local-hand","pass"); gc.collect()
        self.assertTrue(details["pipes_closed"]); self.assertEqual([x for x in caught if issubclass(x.category,ResourceWarning)],[])

    def test_worker_instance_lock_rejects_second_process(self) -> None:
        state=self.runtime/"instance"; marker=self.root/"locked"; code="from pathlib import Path; import sys,time; from local_hand.runtime_lock import worker_instance_lock; c=worker_instance_lock(Path(sys.argv[1])); c.__enter__(); Path(sys.argv[2]).write_text('x'); time.sleep(4)"
        env=dict(os.environ); env["PYTHONPATH"]=str(TOOLS_ROOT); proc=subprocess.Popen([sys.executable,"-c",code,str(state),str(marker)],env=env)
        try:
            deadline=time.time()+5
            while not marker.exists() and time.time()<deadline: time.sleep(.05)
            self.assertTrue(marker.exists())
            with self.assertRaises(LocalHandError) as ctx:
                with worker.worker_instance_lock(state): pass
            self.assertEqual(ctx.exception.code,"worker_instance_busy")
        finally:
            proc.terminate(); proc.wait(timeout=3)

    def test_bootstrap_scripts_are_versioned_staged_and_health_checked(self) -> None:
        root=Path(__file__).resolve().parents[1]; linux=(root/"tools/local_hand/bootstrap_linux.sh").read_text(); windows=(root/"tools/local_hand/bootstrap_windows.ps1").read_text(); paths=(root/"tools/local_hand/paths.py").read_text()
        for text in (linux,windows):
            for marker in ("implementation commit mismatch","source tree is dirty","deployments","git_safety.py","runtime_lock.py","bounded_io.py","mailbox_safety.py","INDEPENDENT_MAILBOX=true","DEDICATED_OS_IDENTITY=true"): self.assertIn(marker,text)
        self.assertIn("NFC-normalized Unicode", paths)
        self.assertIn("systemctl is-active --quiet",linux); self.assertIn("SERVICE_ACTIVE=true",linux); self.assertIn("attempting rollback",linux); self.assertIn("ProtectSystem=strict",linux)
        self.assertIn("Stop-ScheduledTask",windows); self.assertIn("Export-ScheduledTask",windows); self.assertIn("TASK_RUNNING=true",windows); self.assertIn("failed running-state health check",windows); self.assertIn("New-ScheduledTaskPrincipal",windows)
        self.assertIn("repository_root(p,sys.argv[2])", windows)
        for text in (linux, windows):
            preflight = text.index("validate-repository-target")
            self.assertLess(preflight, text.index("ensure-root-marker"))
            self.assertGreaterEqual(text.count("validate-repository-target"), 2)
        self.assertLess(linux.index("validate-repository-target"), linux.index("sudo chown"))
        self.assertLess(windows.index("validate-repository-target"), windows.index("Set-WritableAcl $RuntimeState"))
        self.assertNotIn("IsControl", windows)

    def test_docs_only_changes_do_not_trigger_full_local_hand_matrix(self) -> None:
        workflow=(Path(__file__).resolve().parents[1]/".github/workflows/local-hand-v0-1-validation.yml").read_text()
        self.assertNotIn('docs/experiments/local-hand/**',workflow); self.assertIn("classify-change:",workflow); self.assertIn("runtime_changed",workflow); self.assertIn("needs: classify-change",workflow)


if __name__ == "__main__": unittest.main()

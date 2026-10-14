"""One bounded edit and fixed validation in a task-owned project copy.

The admitted source stays read-only. No caller command, checkout path, Git
remote or validation command enters this executor. Results are sealed by the
same broker/runner as the other core jobs.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from local_hand import act, observe
from local_hand.git_safety import run_hardened_git
from local_hand.paths import NodeProfile, RepositorySpec, _canonical_relative_posix
from . import ledger_jobs
from .contract import JobError, canonical_bytes

KIND = "workspace.edit"


def build_plan(request, profile):
    inputs, source = request["inputs"], profile["source"]
    relative = inputs["relative_path"]
    _canonical_relative_posix(relative, "relative_path")
    if relative not in source["blobs"]:
        raise ValueError("edit target is not in the admitted source")
    modules = source["validations"][inputs["validation_ref"]]
    base = ledger_jobs.build_plan(dict(request, kind="host.inspect"), profile)
    destination = str(Path(base["roots"]["work"]) / "source")
    code = ("import pathlib,sys,unittest; root=pathlib.Path.cwd(); "
            "sys.path[:0]=[str(root),str(root/'tools'),str(root/'tests')]; "
            "compile((root/sys.argv[1]).read_bytes(),sys.argv[1],'exec') if sys.argv[1].endswith('.py') else None; "
            "suite=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[2:]); "
            "result=unittest.TextTestRunner(verbosity=2).run(suite); "
            "sys.exit(0 if result.wasSuccessful() and result.testsRun>0 else 1)")
    base.update(kind=KIND, source=source, bindings={"source_commit": source["commit"]},
        workspace_git=profile["workspace_git"],
        stages=[dict(name="workspace-validation", argv=[base["python"], "-I", "-B", "-c", code, relative, *modules],
                     cwd=destination, env=base["environment"])])
    if "manifest" in source:
        # Keep the existing 64 KiB helper transport bound even for a complete
        # project. The held inventory is bound by the policy's exact digest.
        base['source']={key:source[key] for key in ('root','commit','manifest')}
        base['readonly'].append(source['manifest']['path'])
    return base


def _source(plan):
    source=dict(plan['source'])
    if 'manifest' in source:
        raw=ledger_jobs.bounded_regular_bytes(source['manifest']['path'],2*1024**2)
        if hashlib.sha256(raw).hexdigest()!=source['manifest']['sha256']:
            raise ValueError('workspace inventory changed')
        inventory=json.loads(raw)
        if set(inventory)!={'commit','blobs'} or inventory['commit']!=source['commit']:
            raise ValueError('workspace inventory identity changed')
        source['blobs']=inventory['blobs']
    return source


def verify_inputs(plan):
    source = _source(plan)
    # Git metadata is manufactured only inside this job. The source inventory
    # cannot inject hooks, config, links or an alternate object store.
    for name in source["blobs"]:
        _canonical_relative_posix(name, "source member")
    digest = ledger_jobs.verify_manifest(source["root"], source["blobs"], git_blobs=True, exact=True)
    git = plan["workspace_git"]
    if hashlib.sha256(ledger_jobs._regular_bytes(git["path"])).hexdigest() != git["sha256"]:
        raise ValueError("workspace Git executable changed")
    target = ledger_jobs._regular_bytes(Path(source["root"]) / plan["inputs"]["relative_path"])
    if hashlib.sha256(target).hexdigest() != plan["inputs"]["expected_sha256"]:
        raise JobError("CONFLICT", "Workspace file differs from the observed source digest")
    return dict(inputs_stable=True, source_commit=source["commit"], source_digest=digest)


def _profile(plan):
    return NodeProfile(node_id="task-workspace", projects_root=Path(plan["roots"]["work"]),
        repositories={"source": RepositorySpec("source", "source", {}, True)},
        profile_sha256=hashlib.sha256(canonical_bytes(plan["source"])).hexdigest(), transport_policy=None)


def _git(plan, args):
    os.environ["LOCAL_HAND_GIT_EXECUTABLE"] = plan["workspace_git"]["path"]
    result = run_hardened_git(Path(plan["roots"]["work"]) / "source", args,
        allow_ssh=False, timeout=10, max_stdout=plan["budgets"]["log_bytes"],
        max_stderr=plan["budgets"]["log_bytes"], text=True,
        extra_env={"GIT_AUTHOR_NAME": "Local Hand", "GIT_AUTHOR_EMAIL": "local-hand@localhost",
                   "GIT_COMMITTER_NAME": "Local Hand", "GIT_COMMITTER_EMAIL": "local-hand@localhost"})
    if result.returncode != 0:
        raise JobError("IO_UNCERTAIN", "Workspace Git operation did not complete")
    return result.stdout


def _save(directory, name, raw):
    path = Path(directory) / name
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def prepare_edit(plan, directory):
    verify_inputs(plan)
    source = _source(plan)
    # Reuse the bounded source copier, with its Git blob verification, for the
    # exact admitted files. This is a new copy, never the original checkout.
    ledger_jobs.copy_verified_source(dict(plan,source=source))
    _git(plan, ["init", "--quiet", "--template=", "--initial-branch=main"])
    _git(plan, ["add", "--force", "--all"])
    _git(plan, ["-c", "user.useConfigOnly=false", "commit", "--quiet", "--no-gpg-sign", "-m", "Admitted workspace baseline"])
    if _git(plan, ["status", "--porcelain"]):
        raise ValueError("workspace baseline is not clean")
    profile = _profile(plan)
    inputs = plan["inputs"]
    before = observe.fs_read_text(profile, "source", inputs["relative_path"])
    _save(directory, "workspace-before.txt", before["content"].encode("utf-8"))
    changed = act.fs_write_text_cas(profile, "source", inputs["relative_path"],
        inputs["expected_sha256"], inputs["content"], lease_root=Path(plan["roots"]["temporary"]) / "write-leases")
    after = observe.fs_read_text(profile, "source", inputs["relative_path"])
    _save(directory, "workspace-after.txt", after["content"].encode("utf-8"))
    # Capture the proposed patch before validation can change any work files.
    patch = _git(plan, ["diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--"])
    _save(directory, "workspace.patch", patch.encode("utf-8"))
    result = dict(schema_version="lh-workspace-edit-v1", source_ref=inputs["source_ref"],
        source_commit=source["commit"], relative_path=inputs["relative_path"],
        before_sha256=before["sha256"], after_sha256=after["sha256"],
        read_back_verified=changed["read_back_verified"], validation_ref=inputs["validation_ref"],
        scope="TASK_OWNED_COPY", original_modified=False)
    _save(directory, "workspace-edit.json", canonical_bytes(result))
    return result


def finish_edit(plan, directory, result, succeeded):
    # A test may write into its private checkout. Return that fact explicitly
    # instead of presenting a pre-test patch as the final project contents.
    observed = observe.fs_read_text(_profile(plan), "source", plan["inputs"]["relative_path"])
    status = _git(plan, ["status", "--porcelain"])
    diff = _git(plan, ["diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--"])
    _save(directory, "workspace-final.patch", diff.encode("utf-8"))
    finished = dict(result, validation_succeeded=succeeded,
        edited_file_unchanged_by_validation=observed["sha256"] == result["after_sha256"], git_status=status)
    _save(directory, "workspace-result.json", canonical_bytes(finished))
    return finished


def local_effects_only(plan):
    """Cancellation may retain this private copy without replaying its edit."""
    execution = plan.get("execution", {})
    return (plan.get("kind") == KIND and execution.get("kind") == KIND
            and not any(execution.get(key) for key in ("storage", "build_cache", "prepared"))
            and sorted(execution.get("writable", [])) == sorted(execution.get("roots", {}).values()))

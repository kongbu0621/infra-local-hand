"""Apply one verified workspace result locally, without submitting another job.

The caller supplies workspace-result.json and before/after bytes extracted from
already verified evidence. result_sha256 must come from that verified manifest,
not from an untrusted result file. This local entry point does not authenticate
or download evidence and is not exposed through MCP. It reuses the repository's
single-writer CAS, hardened Git and fixed validation profiles.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from . import act, observe, validate
from .bounded_io import read_regular_file_bounded
from .paths import load_profile, repository_root, safe_existing_path, _canonical_relative_posix
from .protocol import LocalHandError, MAX_TEXT_BYTES


# Returned patches must be consumable by ordinary git apply, regardless of the
# repository's human-facing color, prefix and context preferences. These options
# also keep checkout comparisons independent of those display settings.
_PATCH_DIFF_ARGS = ("diff", "--no-ext-diff", "--no-textconv", "--binary",
                    "--no-color", "--src-prefix=a/", "--dst-prefix=b/", "--unified=3")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _sync_directory(path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _save(root, name, raw):
    # Never expose a truncated JSON report as the final record. A failed
    # publication retains its pending bytes and cannot overwrite an old record.
    pending = root / ("." + name + ".pending")
    with pending.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(pending, root / name)
    _sync_directory(root)
    pending.unlink()
    _sync_directory(root)


def _directory_identity(path):
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
        raise OSError("Attempt output is no longer a regular directory")
    return info.st_dev, info.st_ino, path.resolve(strict=True)


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate result key")
            result[key] = value
        return result
    def invalid_constant(_value):
        raise ValueError("non-finite result value")
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def _run_git(repo, args):
    # Bind stored objects and ancestry, without local replace/graft overlays.
    return observe._run_git(repo, args, stored_objects=True)


def _git(repo, args):
    result = _run_git(repo, ["--literal-pathspecs", *args])
    if result.returncode:
        raise LocalHandError("git_failed", "Local repository Git check failed")
    return result.stdout


def _conflict(message):
    raise LocalHandError("workspace_conflict", message, "stale")


def _checkout_state(repo, target):
    worktree = Path(os.fsdecode(_git(repo, ["rev-parse", "--show-toplevel"])).rstrip("\n")).resolve(strict=True)
    # The exclude is built here with literal matching, never caller Git syntax.
    other = _run_git(repo, [*_PATCH_DIFF_ARGS, "HEAD",
        "--", ".", ":(top,exclude,literal)" + target])
    if other.returncode:
        raise LocalHandError("git_failed", "Cannot observe unrelated tracked changes")
    names = _git(repo, ["ls-files", "--others", "--exclude-standard", "-z"]).split(b"\0")
    if len(names) > 1001:
        raise LocalHandError("workspace_snapshot_too_large", "Untracked entry observation exceeds 1000 files")
    untracked = {}
    for name in filter(None, names):
        info = (repo / os.fsdecode(name)).lstat()
        untracked[name.hex()] = (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                                info.st_mtime_ns, info.st_ctime_ns)
    return dict(worktree=str(worktree), head=_git(repo, ["rev-parse", "HEAD"]).decode().strip(),
        index_sha256=_sha(_git(repo, ["ls-files", "--stage", "-v", "-z"])),
        other_diff_sha256=_sha(other.stdout), untracked=untracked)


def _confirm_existing(repo, target, expected_sha256, expected_mode=None):
    """A matching after-image alone cannot repair an earlier failed fsync."""
    path = safe_existing_path(repo, target, expect="file")
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags)
        try:
            before = os.fstat(fd)
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if not stat.S_ISREG(before.st_mode) or identity(before) != identity(path.lstat()):
                _conflict("Existing target identity changed before synchronization")
            if expected_mode is not None and stat.S_IMODE(before.st_mode) != expected_mode:
                _conflict("Existing target mode changed before synchronization")
            os.fsync(fd)
            _sync_directory(path.parent)
            # Keep the synchronized inode open until read-back and named identity
            # agree. Equal bytes from a replacement file do not prove its fsync.
            if _sha(read_regular_file_bounded(path, MAX_TEXT_BYTES, "existing_target_unconfirmed")) != expected_sha256:
                _conflict("Existing target bytes changed during synchronization")
            if identity(os.fstat(fd)) != identity(before) or identity(path.lstat()) != identity(before):
                _conflict("Existing target changed during synchronization")
        finally:
            os.close(fd)
    except OSError as exc:
        raise LocalHandError("write_durability_unconfirmed",
            "Matching target bytes could not be synchronized; retain the file", "indeterminate") from exc


def apply_result(profile, repository, *, result_path, result_sha256, before_path,
                 after_path, expected_head, output, lease_root=None):
    """Retain a fresh local attempt; never rollback or replay a remote task.

    Unrelated dirty files are permitted. A matching after-image skips the write
    but still runs local validation, allowing recovery after a prior validation
    failure. Changed target bytes, index entries or HEAD are never merged here.
    The cooperative CAS assumes profile.single_writer, as other local writes do.
    """
    repo = repository_root(profile, repository)
    output = Path(output).absolute()
    if output.resolve().is_relative_to(repo):
        raise LocalHandError("invalid_output", "Attempt output must be outside the target repository")
    # A linked worktree's actual metadata is outside its checkout directory.
    for option in ("--git-dir", "--git-common-dir"):
        git_dir = Path(_git(repo, ["rev-parse", "--path-format=absolute", option]).decode().strip()).resolve()
        if output.resolve().is_relative_to(git_dir):
            raise LocalHandError("invalid_output", "Attempt output cannot be inside Git metadata")
    output.mkdir(mode=0o700, exist_ok=False)
    output_identity = _directory_identity(output)
    _sync_directory(output.parent)

    def save(name, raw):
        def check():
            if _directory_identity(output) != output_identity:
                raise OSError("Attempt output directory identity changed; original records retained")
        check()
        _save(output, name, raw)
        check()

    report = dict(schema_version="lh-workspace-apply-v1", repository=repository,
                  profile_sha256=profile.profile_sha256, expected_head=expected_head,
                  result_sha256=result_sha256, status="FAILED", phase="input",
                  write_attempted=False, validation=None)
    target = baseline = None
    guards = ExitStack()
    try:
        if not isinstance(expected_head, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", expected_head):
            raise ValueError("expected_head must be a full commit ID")
        if not isinstance(result_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", result_sha256):
            raise ValueError("result_sha256 must be a SHA-256 digest")
        raw = read_regular_file_bounded(Path(result_path), 65536, "invalid_result")
        if _sha(raw) != result_sha256:
            _conflict("Workspace result differs from the verified manifest digest")
        result = _json(raw)
        required = {"schema_version", "source_ref", "source_commit", "relative_path",
                    "before_sha256", "after_sha256", "read_back_verified", "validation_ref",
                    "scope", "original_modified", "validation_succeeded",
                    "edited_file_unchanged_by_validation", "git_status"}
        if not isinstance(result, dict) or set(result) != required:
            raise ValueError("invalid workspace result fields")
        if not isinstance(result["git_status"], str):
            raise ValueError("invalid workspace Git status")
        if (result["schema_version"] != "lh-workspace-edit-v1"
                or result["scope"] != "TASK_OWNED_COPY"
                or result["source_ref"] != repository
                or result["original_modified"] is not False
                or any(result[key] is not True for key in
                       ("read_back_verified", "validation_succeeded", "edited_file_unchanged_by_validation"))):
            raise ValueError("workspace result does not describe a validated private edit")
        if not isinstance(result["relative_path"], str):
            raise ValueError("invalid target")
        _canonical_relative_posix(result["relative_path"], "relative_path")
        target = result["relative_path"]
        if not isinstance(result["source_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", result["source_commit"]):
            raise ValueError("invalid source commit")
        before = read_regular_file_bounded(Path(before_path), MAX_TEXT_BYTES, "invalid_before")
        after = read_regular_file_bounded(Path(after_path), MAX_TEXT_BYTES, "invalid_after")
        if _sha(before) != result["before_sha256"] or _sha(after) != result["after_sha256"]:
            _conflict("Before/after content differs from the verified workspace result")
        content = after.decode("utf-8")
        before.decode("utf-8")
        spec = profile.repositories[repository]
        if not spec.single_writer:
            raise LocalHandError("workspace_not_single_writer", "Local apply requires a single-writer repository")
        validation_id = result["validation_ref"]
        if not isinstance(validation_id, str) or validation_id not in spec.validations:
            raise ValueError("validation is not present in the local profile")
        if not spec.validations[validation_id].replay_safe:
            raise ValueError("local validation must be explicitly replay-safe")
        lease = guards.enter_context(act._repository_write_lease(repo, lease_root))
        report.update(relative_path=target, source_commit=result["source_commit"],
                      before_sha256=_sha(before), after_sha256=_sha(after), validation_ref=validation_id)
        save("workspace-result.json", raw)
        save("before.txt", before)
        save("after.txt", after)
        report["phase"] = "precheck"
        head = _git(repo, ["rev-parse", "HEAD"]).decode().strip()
        report["observed_head"] = head
        if head != expected_head:
            _conflict("Repository HEAD changed since observation")
        ancestry = _run_git(repo, ["merge-base", "--is-ancestor", result["source_commit"], head])
        if ancestry.returncode == 1:
            _conflict("Verified source commit is not an ancestor of the target HEAD")
        if ancestry.returncode != 0:
            raise LocalHandError("git_failed", "Cannot verify the stored source ancestry")
        source = _git(repo, ["cat-file", "blob", result["source_commit"] + ":" + target])
        if source != before:
            _conflict("Verified before-image does not match the source commit")
        head_content = _git(repo, ["cat-file", "blob", head + ":" + target])
        if head_content not in (before, after):
            _conflict("HEAD contains a newer target version, even if index/worktree reverted it")
        index = _git(repo, ["ls-files", "--stage", "-v", "-z", "--", target])
        entries = index.rstrip(b"\0").split(b"\0")
        if len(entries) != 1 or not entries[0]:
            _conflict("Target must have one tracked, unconflicted index entry")
        metadata, index_name = entries[0].split(b"\t", 1)
        tag, mode, blob, stage = metadata.split()
        if tag != b"H":
            _conflict("Target index flags hide working-copy changes; retain the index flags without writing")
        if mode not in (b"100644", b"100755") or stage != b"0" or index_name != target.encode():
            _conflict("Target index entry is not a regular tracked file")
        head_entry = _git(repo, ["ls-tree", "-z", head, "--", target])
        if not head_entry or head_entry.split(b" ", 1)[0] != mode:
            _conflict("Target has a staged mode/type change outside the verified text edit")
        index_content = _git(repo, ["cat-file", "blob", blob.decode()])
        current = observe.fs_read_text(profile, repository, target)
        target_mode = act._regular_mode_no_follow(safe_existing_path(repo, target, expect="file"))
        report["target_mode"] = target_mode
        save("observed-before.txt", current["content"].encode())
        save("status-before.json", json.dumps(observe.git_status(profile, repository, stored_objects=True)).encode())
        baseline = _checkout_state(repo, target)
        if baseline["worktree"] != str(repo):
            _conflict("Git working tree differs from the registered repository directory")
        if baseline["head"] != expected_head:
            _conflict("HEAD changed during initial observation")
        already = current["sha256"] == _sha(after)
        if current["sha256"] not in (_sha(before), _sha(after)):
            _conflict("Target has newer or local changes; retained without applying the old edit")
        if index_content != before and not (already and index_content == after):
            _conflict("Target has staged changes that differ from the verified edit")
        if head_content == after and index_content != after:
            _conflict("Target index reverts the already committed edit; retain the staged change")
        if not already and head_content != before:
            _conflict("The verified edit is committed but the working copy reverts it")
        if (_git(repo, ["rev-parse", "HEAD"]).decode().strip() != expected_head
                or _git(repo, ["ls-files", "--stage", "-v", "-z", "--", target]) != index):
            _conflict("HEAD or target index changed during precheck")
        report["phase"] = "write"
        intent = dict(report, status="PREPARED", write_planned=not already)
        del intent["write_attempted"]  # Intent does not prove that CAS was called.
        save("intent.json", json.dumps(intent, sort_keys=True).encode())
        if not lease.held_for(repo) or _checkout_state(repo, target) != baseline:
            _conflict("Checkout changed before applying the verified edit")
        # CAS independently rechecks the target immediately before replacement.
        if not already:
            report["write_attempted"] = True
            report["write"] = act.fs_write_text_cas(profile, repository, target,
                _sha(before), content, _lease=lease)
            already = report["write"]["already_applied"]
        report["already_applied"] = already
        if already:
            _confirm_existing(repo, target, _sha(after))
        if (not lease.held_for(repo)
                or observe.fs_read_text(profile, repository, target)["sha256"] != _sha(after)
                or act._regular_mode_no_follow(safe_existing_path(repo, target, expect="file")) != target_mode
                or _checkout_state(repo, target) != baseline):
            _conflict("Checkout changed before local validation; files retained")
        report["phase"] = "validation"
        report["validation"] = validate.run_profile(profile, repository, validation_id)
        if observe.fs_read_text(profile, repository, target)["sha256"] != _sha(after):
            _conflict("Target changed during local validation; files retained")
        if (_git(repo, ["rev-parse", "HEAD"]).decode().strip() != expected_head
                or _git(repo, ["ls-files", "--stage", "-v", "-z", "--", target]) != index):
            _conflict("HEAD or target index changed during apply/validation; files retained")
        report.update(status="ALREADY_APPLIED" if already else "APPLIED", phase="collect")
    except (KeyboardInterrupt, SystemExit) as exc:
        report.update(status="UNCONFIRMED", error=dict(code="interrupted", message=type(exc).__name__))
        raise
    except (LocalHandError, ValueError, TypeError, KeyError, OSError, RecursionError) as exc:
        if isinstance(exc, validate.ValidationFailed):
            report["validation"] = exc.details
        code = exc.code if isinstance(exc, LocalHandError) else "invalid_input"
        report["error"] = dict(code=code, message=str(exc))
        report["status"] = ("VALIDATION_FAILED" if isinstance(exc, validate.ValidationFailed)
                            else "CONFLICT" if code in ("workspace_conflict", "stale_write") else "FAILED")
        if isinstance(exc, LocalHandError) and exc.status == "indeterminate":
            report["status"] = "UNCONFIRMED"
    except Exception as exc:
        report.update(status="UNCONFIRMED", error=dict(code="unexpected_error", message=str(exc)))
        raise
    finally:
        # Capture the actual checkout even on failure. No rollback can overwrite
        # edits made by a validator or an external writer.
        observation_interrupt = None
        try:
            save("status-after.json", json.dumps(observe.git_status(profile, repository, stored_objects=True)).encode())
            if target is not None:
                _canonical_relative_posix(target, "relative_path")
                diff = _git(repo, [*_PATCH_DIFF_ARGS, "HEAD", "--", target])
                save("final.patch", diff)
                report["final_diff_sha256"] = _sha(diff)
                report["final_target_sha256"] = observe.fs_read_text(profile, repository, target)["sha256"]
                report["final_target_mode"] = act._regular_mode_no_follow(safe_existing_path(repo, target, expect="file"))
                if (report["status"] in ("APPLIED", "ALREADY_APPLIED")
                        and (not lease.held_for(repo)
                             or report["final_target_sha256"] != report["after_sha256"]
                             or report["final_target_mode"] != report["target_mode"]
                             or _checkout_state(repo, target) != baseline)):
                    _conflict("HEAD, index or workspace changed during validation/final observation; files retained")
            if report["status"] in ("APPLIED", "ALREADY_APPLIED"):
                # A validator can replace the file with identical bytes. Confirm
                # the final file, not just the inode synchronized before validation.
                _confirm_existing(repo, target, report["after_sha256"], report["target_mode"])
                if not lease.held_for(repo):
                    _conflict("Checkout identity changed during final synchronization")
                report["phase"] = "complete"
        except (KeyboardInterrupt, SystemExit) as exc:
            observation_interrupt = exc
            report.update(status="UNCONFIRMED", error=dict(code="interrupted", message=type(exc).__name__))
        except Exception as exc:
            report["observation_error"] = str(exc)
            if report["status"] in ("APPLIED", "ALREADY_APPLIED"):
                report["status"] = "CONFLICT" if isinstance(exc, LocalHandError) and exc.code == "workspace_conflict" else "UNCONFIRMED"
                report["error"] = dict(code=getattr(exc, "code", "final_observation_unconfirmed"), message=str(exc))
        try:
            guards.close()
        except OSError as exc:
            report.update(status="UNCONFIRMED", lease_release_error=str(exc))
        try:
            save("report.json", json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2).encode())
        except OSError as exc:
            report.update(status="UNCONFIRMED", report_save_error=str(exc))
        if observation_interrupt is not None:
            raise observation_interrupt
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("profile", "repository", "result", "result-sha256", "before", "after", "expected-head", "output"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--lease-root", type=Path, help="Shared lease directory used by other Local Hand writers")
    args = parser.parse_args(argv)
    try:
        result = apply_result(load_profile(Path(args.profile)), args.repository,
            result_path=args.result, result_sha256=args.result_sha256,
            before_path=args.before, after_path=args.after, expected_head=args.expected_head, output=args.output,
            lease_root=args.lease_root)
    except (LocalHandError, OSError, ValueError) as exc:
        print(json.dumps(dict(status="FAILED", error=str(exc))))
        return 1
    print(json.dumps({key: result.get(key) for key in
        ("status", "phase", "relative_path", "write_attempted", "already_applied", "error", "report_save_error")}))
    return 0 if result["status"] in ("APPLIED", "ALREADY_APPLIED") else 1


if __name__ == "__main__":
    raise SystemExit(main())

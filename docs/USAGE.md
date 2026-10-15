# Local usage and verification

## Land a verified workspace edit locally

After verifying a completed `workspace.edit` evidence bundle, extract its
`workspace-result.json`, `workspace-before.txt` and `workspace-after.txt`.
Use the result member's SHA-256 from the verified manifest. The local entry
point consumes these verified files; it does not authenticate evidence itself.
The local Node Profile repository name must match `source_ref`, and its fixed
validation with the returned `validation_ref` must be explicitly replay-safe.

```sh
python -m local_hand.workspace_apply --profile LOCAL_PROFILE --repository SOURCE_REF \
  --result workspace-result.json --result-sha256 VERIFIED_RESULT_SHA256 \
  --before workspace-before.txt --after workspace-after.txt \
  --expected-head OBSERVED_FULL_HEAD --output NEW_PRIVATE_ATTEMPT_DIRECTORY
```

This single-file local operation checks source ancestry, HEAD, index and file
digests against stored Git objects, ignoring local replace refs and grafts, then
uses the existing CAS writer and fixed validation runner. Unrelated
dirty files are allowed. A matching after-image skips the write and validates
locally after confirming file synchronization. Changed targets and staged reverts
remain conflicts; no merge or rollback overwrites them.
Successful completion also synchronizes the final target after validation and
binds read-back to that same file. Identical bytes from a validator's replacement
file alone do not confirm that the replacement has been synchronized.
On Windows the final synchronization requires a writable handle; failure to open
or flush that handle remains `UNCONFIRMED` without changing file permissions.
Git's working tree must match the registered repository directory throughout
the attempt. Linked worktrees are supported; redirecting `core.worktree` to a
different directory is a conflict, even when HEAD and file contents match.
Targets marked `assume-unchanged` or `skip-worktree` are rejected before writing
because Git can hide their actual changes. The flags are retained; once the
caller resolves them, a fresh attempt can proceed. Flag changes made during
validation are also conflicts.
Each attempt retains before/after content, final diff, validation output and
`report.json` outside the repository. The final Git diff uses no color, standard
`a/` and `b/` prefixes and three context lines so repository display preferences
do not make the patch unusable by ordinary `git apply`; Git configuration is retained.
A retry uses a fresh output directory and
checks current bytes first. No remote task is submitted, and no commit or push
is performed. The output parent must already exist; each attempt directory is new.

The cooperative write lease spans precheck, write, validation and final observation.
Use `--lease-root` when other Local Hand writers use a configured lease directory;
all cooperating writers must use the same root. Final checks cover HEAD, index
entries and their assume-unchanged/skip-worktree flags, target bytes/mode,
other tracked Git differences, and nonignored untracked
entry metadata (up to 1000 files). Git observations retain the existing 2 MiB
output bounds. Validation is trusted local code, not a filesystem sandbox; ignored
outputs and effects outside the checkout are not covered by these comparisons.
Pre-existing hidden flags on unrelated paths are retained; those paths do not
receive independent byte comparisons beyond what Git reports.
The held lease's repository identity is rechecked before writing, before validation
and at final observation. Replacing the checkout cannot yield a successful result
even when its contents match. Attempt directory identity is checked around each
record publication; detected replacement stops publication and leaves the original
records in place. These checks do not sandbox a hostile concurrent filesystem writer.

Interruptions, incomplete synchronization and report-storage failures remain
`UNCONFIRMED`. If publishing a report fails, the CLI return retains the write state
and error; a pending or visible candidate file is not a persistence acknowledgment.
Previously completed remote tasks and failed local attempt records are retained.

## Build and install

Use Python 3.12 and a clean committed checkout. Build and runtime environments
must be newly created directories. Choose a new absolute work directory first;
the following names are examples, not live deployment defaults.

```sh
python3.12 -m venv /absolute/new-work/build-venv
/absolute/new-work/build-venv/bin/python -m pip install -r requirements-build.txt
/absolute/new-work/build-venv/bin/python -m pytest -q
/absolute/new-work/build-venv/bin/python -m compileall -q tools tests
/absolute/new-work/build-venv/bin/python -m build --wheel --no-isolation --outdir /absolute/new-work/dist
python3.12 -m venv /absolute/new-work/runtime-venv
/absolute/new-work/runtime-venv/bin/python -m pip install --no-deps /absolute/new-work/dist/infra_local_hand-0.2.0a1-py3-none-any.whl
cd /absolute/new-work
/absolute/new-work/runtime-venv/bin/python -I /absolute/checkout/tools/verify_installed.py --wheel /absolute/new-work/dist/infra_local_hand-0.2.0a1-py3-none-any.whl --run-root /absolute/new-work/acceptance
```

On Windows, venv Python is `Scripts/python.exe`. The source test suite and
installed direct-action tests are portable; the installed CLI transport fixture
is POSIX-specific and reports SKIP on Windows. Preserve its report and logs.
For a second candidate, retain prior artifacts and use new build/runtime paths.

## Explicit admission

Node Profile requires exactly `profile_schema`, `node_id`, `projects_root`,
`repositories`, `transport_policy`. The schema is `local-hand-profile/v2`.
Each repository requires `path`, boolean `single_writer`, and `validations`.
Each validation has fixed `argv`, finite numeric `timeout_seconds` in (0,3600],
and boolean `replay_safe`. Missing and unknown keys are rejected.

Transport policy requires exactly `schema_version`, `remote_url`,
`allowed_remote_urls`, `branch`; schema is `local-hand-git-mailbox/v1`.
Supported remotes are explicit `user@host:owner/repository.git` or
`ssh://user@host[:port]/owner/repository.git`. Every admitted spelling must be
listed and name the same SSH user/host/port/repository. No local/file/HTTP remote
or implicit branch is accepted. Synthetic examples are in the test fixtures.

Use `python -m local_hand.config --profile PROFILE --repository NAME` to check
a profile before installation. Controller `init`, `submit`, `wait`, and `call`
require `--policy FILE`. `build` remains offline. A controller mailbox has a
create-only admission marker; changing policy requires a newly admitted clone.
Worker's optional `--mailbox-branch` is an assertion against the profile.
`wait` and `call` additionally require `--expected-provenance-file`; that file
must contain the exact admitted `implementation_commit`, `package_digest`, and
`profile_digest`. A result is never accepted without this source policy.
`call` rejects invalid wait timing before submitting a task. When the fetched
mailbox contains both a canonical result and a conflict for the exact task
digest, `wait`/`call` validate and return the conflict first. Invalid conflict
identity, provenance, or a conflict claiming success fails closed.

## Installation provenance

An installed worker requires a create-only record from
`python -m local_hand.installation --help`. Supply the retained original wheel,
profile, installation UUID, runtime Git/SSH/key/known_hosts absolute paths,
state and mailbox roots. Match these bindings at startup using
`LOCAL_HAND_INSTALL_RECORD`, `LOCAL_HAND_INSTALL_INSTANCE_ID`, and the runtime
path variables shown in that module. Do not modify an existing installation
record to migrate an environment. Every returned result binds the actual build
commit, core digest and raw profile digest.

The Linux/Windows service bootstrap scripts remain source-staging installers:
they require a clean Git checkout and stamp copied source, not a wheel install.
Their required profile/repository/state/run-user inputs replace deployment
defaults. Their presence inside the wheel does not make them wheel installers.
Do not invoke them for S1 live deployment; service cutover is S2 scope.

Old profiles, controller markers and state directories are not silently
upgraded. Preserve them and use an explicit separately authorized migration.

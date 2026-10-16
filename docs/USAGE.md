# Local usage and verification

## Archive and read a completed result locally

`local-hand-archive` is an optional Linux caller-side consumer of Artifact Ledger.
It accepts an already completed `SUCCEEDED / SEALED` task and retains the exact
ZIP, external manifest, seal, original status response and source information.
For `workspace.edit`, the ZIP includes the patch, before/after bytes and fixed
validation output. Nothing in the bundle is executed or applied.

Install a verified `infra-artifact-ledger` wheel alongside this package in an
independent Python 3.12 environment. This integration uses the public
`bounded-local-v0.1` library API, verified with Ledger `0.2.0a1` from commit
`6707a1b521c9c4718674620e6c584656bd434e4c`. Build that fixed source using its
declared build dependencies; install the resulting local wheel with
`python -m pip install --no-index --no-deps /path/to/verified-ledger.whl`.
Ledger is not downloaded automatically or required for normal Local Hand use.

Retain the **raw authenticated `lh_job_status` response** (either the result
object or its successful `structuredContent` wrapper), plus the downloaded
`evidence.zip`, `evidence.manifest`, and `evidence.seal`. The caller must obtain
the status SHA-256 from that trusted response; hashing an arbitrary file does
not authenticate it. The archive verifies its identity, seal, manifest, ZIP
members and content digests against this supplied trust anchor.

```sh
local-hand-archive archive --store /absolute/private/archive \
  --producer local-hand:my-instance --status /absolute/retained/status.json \
  --status-sha256 TRUSTED_STATUS_SHA256 --evidence-dir /absolute/retained/evidence

local-hand-archive read --store /absolute/private/archive \
  --artifact-id RETURNED_ARTIFACT_ID --version-id RETURNED_VERSION_ID \
  --output /absolute/private/new-readback

local-hand-archive resume --store /absolute/private/archive \
  --producer local-hand:my-instance --operation-id ORIGINAL_OPERATION_ID
```

The store is a dedicated local directory, separate from execution ledgers and
source evidence. Use a persistent local filesystem supporting SQLite, directory
fsync and Linux create-only rename. All cooperating calls take a bounded,
nonblocking store lock. Do not point another writer directly at `ledger.sqlite`
or place the store on shared network storage. The output parent must exist;
read-back publishes a new directory and refuses to overwrite existing output.

`archive` returns one explicit Artifact ID and Version ID. This first consumer
maps each `(producer, operation_id)` to one immutable completed bundle, with
random owned IDs retained before either Ledger write. A later observation of
the same task/seal reuses the first status snapshot; changed request or evidence
bindings are conflicts. It does not choose a "latest" version, combine different
tasks into a version history or infer identity from filenames/digests.

If a response is lost, `resume` uses the saved original requests and bytes,
queries both original operations and checks their fingerprints before continuing.
It needs no original download directory. Create and append are separate Ledger
transactions: failure can leave the artifact identity committed without a version.
Keep the entire store, including pending directories, after errors. Nonzero exit
does not imply rollback; repeated successful calls return the same IDs and timestamp
without another version. A missing initialized database or corrupt payload is an
error, never an instruction to initialize again, repair history or rerun business.
The store also binds the database file identity and keeps a separate task
reservation before writing. Missing recovery directories and replaced databases
are conflicts; restoring the originals allows the same request to continue.
An existing task reservation is checked before database initialization, even
when the global marker is missing. Each confirmed create/append also gets an
immutable receipt outside SQLite before the caller reports success. If that
operation subsequently disappears or its timestamp changes, recovery rejects
the inconsistency instead of replaying it, including after an in-place database
rollback that preserves the file identity. The Artifact/Version record must also
retain the same timestamp as its own create/append operation; a disagreement is
rejected before continuing with another write. A failed receipt publication can
resume by querying the original operation; it does not require another commit.
New requests use a stable per-task idempotency scope as a second guard against
lost recovery files. Copying/replacing a database is not a supported store move.
Existing v1 requests keep their original bytes and operation identities; their
first archive/resume adds guards without rewriting Ledger records. These guards
cannot establish whether a legacy database was replaced before that first use.
Receipts similarly preserve commits first confirmed by this consumer; losing
both the database history and its external receipts cannot prove an earlier
commit. Keep the whole store and retain failed attempts.

`read` needs only the store and explicit IDs. It verifies the actual bytes and
source bindings, then returns the original evidence files and `source.json`.
JSON responses go to stdout; errors retain the relevant Ledger `commit_state`
where known. Archival success concerns preservation and read-back, not new
authentication, task execution, validation execution or knowledge admission.
This local consumer does not establish A2 NAS recovery, A3's two consumer classes,
Windows archive support or the full Code Driver loop.

To run the affected checks with the verified optional wheel installed:
`python -B -m pytest -q tests/test_local_hand_artifact_archive.py tests/test_local_hand_jobs_evidence_client.py`.
Without that wheel, the consumer integration tests are explicitly skipped;
the local bundle validation tests still run on Linux.

## Run the installed Ledger A2 local check

`ledger.test.local_a2` is an optional fixed job for continuing Ledger's installed
snapshot/recovery acceptance with an existing runtime. It executes the pinned
`tests/installed_snapshot_walkthrough.py` once, using that venv's Python with
`-I -B`, a new task-owned `local-parent`, and the registered source commit. It
passes no storage configuration and does not enable NAS jobs. The eight required
calls are API and CLI `create`, `verify`, `restore`, and `check_restore`.

Before preparing a new task, reuse any retained result that already covers the
same installation and execution environment. Keep an uncertain attempt on its
original operation ID and query it; do not prepare a replacement just because a
response was lost. A failed run retains its synthetic directories and logs.

The operator registers the existing runtime in the protected resident manager
configuration under `local_a2.runtimes[REF]`. Each descriptor has these fields:

| Fields | Binding |
| --- | --- |
| `source_root`, `source_commit`, `source_blobs` | Retained Ledger source and actual build-source SHA; all 17 runtime modules plus the fixed smoke script, using `local_a2_jobs.SOURCE_BLOBS` |
| `runtime_root`, `runtime_python`, `runtime_python_realpath`, `runtime_python_sha256` | Existing isolated venv, its original Python invocation path, and the explicitly resolved interpreter bytes |
| `venv_config_sha256`, `console_script_sha256` | Existing `pyvenv.cfg` and `bin/artifact-ledger` entry point |
| `package_root` | Installed `infra_artifact_ledger` package directory inside that venv |
| `wheel`, `wheel_sha256` | Retained wheel file and SHA-256, compared with source and installed payload |

The descriptor is a trusted operator registration, not a caller claim that an
arbitrary venv was produced by `ledger.prepare`. The source commit must come from
the retained build record; the smoke script itself does not attest a Git commit.
Preflight verifies fixed source bytes, wheel and installed module contents,
interpreter and entry point. A bounded probe uses the same interpreter with
`-I -S -B` to verify that the interpreter's actual import search selects the
registered package before enabling site processing or importing Ledger. It
compares the 17 modules' current-interpreter, unoptimized bytecode candidates
with compilation of the verified source, including nested code fields such as
stack size and qualified names that normal Python code-object equality omits.
Other interpreter and optimization caches are left unread and unchanged; neither
fixed business command enables optimization. The runtime must exclude system site packages
and unregistered startup hooks. The sole permitted `.pth` file is the exact
standard `distutils-precedence.pth`; the fixed environment sets
`SETUPTOOLS_USE_DISTUTILS=stdlib` for both the walkthrough and its CLI children,
so that file does not load `_distutils_hack`. On Debian/Ubuntu Python 3.11/3.12,
the probe restores the verified venv prefixes before asking the interpreter for
site directories, without running site initialization. The exact standard-library
Apport `sitecustomize.py` is also admitted only when `apport_python_hook` is absent
from the actual import search and its selected bytecode matches the inert source;
other startup modules remain rejected. A shadow `bin/pyvenv.cfg` or an
`._pth` search-path override beside the invoked or resolved interpreter is
rejected before starting that interpreter. The base interpreter and its standard
library remain trusted deployment inputs. Original files remain read-only; the
venv is not rebuilt, copied, or cleaned. Private paths and build receipts stay in
the deployment.

The same manager `local_a2` object supplies explicit `budgets`, `limits`, and
per-role `quotas` in the existing resident preparation format. `budgets.nas_bytes`
must be zero; the existing three-phase resource checks remain in force. The ordinary MCP
adapter descriptor has only `local_a2: {"runtime_refs": [REF], "budgets": BUDGET}`;
it never receives the private runtime descriptor. Preparation creates a task
policy with only the selected runtime and grants `runtime_refs` for that task.
Old deployment descriptors need no new field. Omitting this registration leaves
the capability unavailable for new attempts. The resident registration is shared
by principals admitted by the manager and authorized for submit by the entry
policy; historical task-specific kind/runtime grants do not define this dynamic
registry. Each generated task policy grants only its selected runtime to its
owner. Entry scope checks and durable revocations remain effective.

Removing a runtime registration prevents new attempts. Polling an existing
preparation with its original owner, UUID and inputs still returns the original
READY request or retained preparation state, including after an interrupted
response or restart. This does not refresh an expired request or rerun a failed
attempt; a new attempt requires the current registration again.

Use the existing private maintenance procedure to install the reviewed Hand
revision and update these two configurations, preserving historical installs,
task catalogs, ledgers and evidence. Refresh the connected tool schema after the
service update. Do not use `workspace.edit` to change the running service or to
execute a shell command. No new maintenance endpoint is required.

Then use the direct MCP tools:

1. Read `lh_capabilities`; require `ledger.test.local_a2` and the intended
   `runtime_ref` in the returned profile.
2. Call `lh_job_prepare` with a new UUID, that `profile_ref`,
   `kind="ledger.test.local_a2"`, and `inputs={"runtime_ref": REF}`. Poll
   `PREPARING` with the same inputs and UUID. Preparation does not run Ledger.
3. Submit the exact `READY.request` once, and query that operation until exit and
   durable sealing. Cancellation and interrupted-response recovery use the
   existing task tools and original request digest.
4. Fetch and verify the complete evidence bundle. Require the fixed script's
   strict PASS report, all eight calls, matching installed identity, and the
   actual execution filesystem. Record `nas_publish_flow=NOT_RUN` and
   `nas_loss_exercise=NOT_RUN` separately from the local result.

The scratch parent **inside the execution namespace** must be actual ext4, XFS,
or Btrfs supported by Ledger. Its production filesystem check rejects overlay
and tmpfs before creating synthetic data. The registered outer task deadline and
resource limits remain authoritative; the script's per-operation timeout is not
a promise about whole-task elapsed time. Source tests and modeled quota/service
tests do not establish this installed or field result. This job does not replace
the separate Ledger resource-boundary or NAS acceptance work.

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

# S1 implementation candidate

This implementation descends from the separate Owner closure record C. The
approved REQUIREMENTS, ARCHITECTURE and IMPLEMENTATION_PLAN documents retain
their exact baseline A bytes; their historical DRAFT labels do not replace C.

## Extraction and test continuity

The fixed upstream selection is in SOURCE_SELECTION.json. The raw SHA-256,
Git blob identity and byte count of each of the 30 extracted files are retained
in EXTRACTION_BYTES_MANIFEST.json. No upstream Git history is imported. The
machine-specific cutover script/test and controlled_executor remain excluded.
The initial, unmodified extraction passed all 123 inherited tests.

All 123 test cases remain. Fixture changes replace private deployment identity,
add the required v2 profile and explicit transport policy, and assert verified
source identity instead of an invented environment commit. File-transport unit
fixtures explicitly patch SSH admission; new configuration cases exercise the
real admission path. These unit fixtures do not prove production SSH behavior.

New coverage checks configuration rejection, two independent deployments,
policy/marker drift, worker rejection before state mutation, clean-source
provenance, and crash/receipt persistence. The installed acceptance harness
exercises the eight actions and controller/Git/worker/result round trips.

## Recovery correction

The inherited worker executed a handler before persisting its first receipt.
A process crash after a side effect could therefore replay the handler. The
worker now persists an execution-intent receipt first. If recovery finds this
receipt without a result, it emits outcome_unknown / indeterminate and refuses
to execute again. Receipt write failure prevents handler execution. POSIX
directory fsync failures now propagate rather than being silently ignored.
This is deliberately conservative, including a crash before the side effect.
It does not claim filesystem/power-loss certification or Windows durability.

## GX10 recheck correction

Fault injection against the original `b763bd6714721d22278086db559fa3f6684aad7b`
candidate found that CAS could report success after directory synchronization
failed, or report failed/rejected when post-replacement read-back failed. Once
replacement has occurred, these failures now return indeterminate; persisted
receipts retain that result and prevent duplicate execution. Pre-write rejection
and the existing read-back mismatch behavior remain unchanged.

The recheck also found that worker Task/Result ingress accepted envelope fields
that the controller rejected. Worker Tasks now enforce the existing five-field
contract after target filtering. Both sides share the existing fourteen-field
Result shape and status/error consistency checks. This corrects implementation
of the approved v1 contract; it adds no action or permission and does not extend
the deferred strict-JSON, nested-root or multi-controller scope. The original
candidate and the corrected commit require separate evidence and fresh build
and runtime environments. Machine evidence remains outside this repository.

## Configuration and artifact identity

Worker, controller and both bootstraps use the shared strict JSON admission
module. Node, project, branch, remote, service identity and validation commands
are explicit installation inputs. Task/Result v1 and mailbox layout are retained.
Legacy profiles and implicit deployment defaults are rejected.

A wheel is built only from a clean source commit. Its metadata binds that
commit and hashes both Python packages plus the shipped platform scripts.
The build also compares the exact payload file set and bytes against committed
Git blobs, rejecting ignored extras and changes hidden by skip-worktree. LF
checkout attributes preserve these bytes across platforms.
The historical core package_digest algorithm is unchanged and has narrower
coverage. An installation record additionally binds the retained wheel hash,
metadata hash, raw profile hash, Python, Git/SSH/key/known_hosts paths,
installation UUID, package root, state root, mailbox root and projects root.
Environment commit values are assertions, never substitutes for artifact facts.
These are integrity checks within the approved trusted deployment boundary,
not signatures against an administrator able to replace code and records.

## Verification boundaries

The local S1 environment is Linux x86_64 / Python 3.12, not a physical target
node. The installed harness uses a local, explicitly constrained SSH-shaped
fixture to call Git upload-pack/receive-pack. It proves mailbox correlation and
recovery without contacting a real SSH server, using live credentials or
submitting real tasks. Service installation and physical-node proof are separate.

Windows / PowerShell 7 service, ACL, process and transport behavior remains
UNVERIFIED until the platform job actually runs. A committed CI workflow is
not evidence of a successful run. The Windows installed harness explicitly
skips its POSIX transport fixture. Missing-platform checks must remain visible;
S1 cross-platform acceptance cannot be declared complete on Linux alone.

Evidence uses fresh checkouts, build/runtime venvs and fixture directories.
Command records retain argv, cwd, UTC times, duration, exit status, log hashes
and measured RSS where supported. Linux wait4 ru_maxrss is a peak statistic
for the reaped child and its waited descendants, not simultaneous aggregate
tree memory. No numerical resource budget is invented.
The installed harness drains stdout/stderr concurrently through bounded pipes;
the parent persists logs and verifies every saved digest before declaring PASS.

Publication was separately authorized first for exact original candidate
b763bd6 and later for repaired candidate 1e2f9dc to be pushed directly to
`main`; see the two Owner decisions under `docs/governance/`. The Owner decided
not to add a license. Disclosure does not approve equivalence/adoption. S2 live
cutover and S3 artifact-ledger A2 remain outside this implementation authority.

## GX10 second fault/contract review

The second review found two additional fail-open edges. CAS now requires the
replacement file's original POSIX mode to be applied and verified before the
atomic replace, and its final file sync occurs after that metadata change.
Controller `wait`/`call` now require an explicit three-field expected
provenance policy before call submission or result acceptance; the CLI no
longer treats the provenance policy as optional.

## GX10 build and recovery provenance review

A later adversarial build probe demonstrated that `git status` alone can call
a checkout clean while an index `skip-worktree` bit hides a changed build
configuration file. Build admission now hashes every tracked regular worktree
file as a Git blob and compares it with the exact HEAD tree, in addition to the
existing status and staged-package checks. Consequently, build-controlling
files and package payload are both bound to the commit stamped into the wheel.

Expected-provenance policy files now use the same strict JSON decoder as other
new deployment configuration, so duplicate keys and non-finite constants fail
closed. This does not change the explicitly deferred Task/Result v1 parser.

Recovery now completes an execution-intent receipt from an already validated,
digest-bound canonical remote result. If a durable local result and the remote
result have the same task digest but different complete content, the worker
keeps the local receipt, quarantines any local outbox original, and emits a
conflict record with hashes of both results. It does not replay the action or
overwrite either side's canonical evidence.

# Q2 supervisor startup evidence and source repair

This is a sanitized record of the one authorized CPUQuota retry and follow-up
repairs within the existing CLOSED Q2 development scope. Raw machine records,
private paths, process identities and plans remain private. It is not an
authorization to replay the consumed attempt or replace its frozen candidate.

## Preserved execution

The attempted runtime was public commit
`9a556322183f0fa80d4edeada4b03c74a26524a5`, tree
`0687d7cd8eaf6a901d565a60b99042827437354c`, using the previously recorded wheel.
Orchestration was public commit `15af5f19b27211f237f1d66f7e11c9aeef59a3a5`,
tree `a300cd9888960bf9d25eef61cc4098242e1a7f70`. Approved A, its three original
documents, CLOSED C and all previous runtime installations remain unchanged.

| Evidence | Verified result |
| --- | --- |
| Upload integrity | Core archive matches its completion record; nested compressed/raw hashes and 638 embedded guest file hashes match |
| External window | Core evidence was durably written about 16.77 seconds after the original host anchor, within the single 300-second deadline |
| Original guest and owner captures | Both streams reached EOF, with actual exit 3 and no capture error; a captured failure is not a successful run |
| Preparation | New protected installation and isolated state reached `RETRY_PREPARED` |
| Supervisor | Actually executed and returned `BLOCKED / PermissionError`; original stderr was empty |
| Owner observation | Encountered loaded/inactive/dead with a pending start job and no process/invocation yet; rejected as `SUPERVISOR_DELIVERY_UNCERTAIN` |
| Target and new ledger | Target was not created; initialized ledger generation remained 1 and all operation/event/lease/revocation/sequence tables were empty |
| Preserved inputs | The collected old file/tree/ledger and Q1 preservation checks passed; all seven prepared roots remained empty. These historical checks did not prove every access timestamp unchanged; see the read-path repair below |
| Later runtime observation | Owner and supervisor had exited, no jobs or process IDs remained, and all five parent trees were empty |
| Missing original proof | No invocation declaration or seal was published, and the original independent-stop record was empty; later inspection cannot replace those facts |

The original result remains **INCOMPLETE**, with all acceptance/support flags
false. No old deadline, reservation, ledger, payload or failure is amended.

## Diagnosis and bounded repair

Two independent defects affect the existing source path:

1. `observe_start()` rejected the real queued-start state before a service had
   acquired its process and invocation identities. Waiting must stay inside
   the existing finite observations, control-output budget and deadline. A
   pending job is never treated as a running or stopped service.
2. Restricted Q2 roles dereferenced PID 1's user-namespace link even though
   their exact capabilities need not permit inspecting PID 1. The first such
   call before bound-supervisor publication is in controller identity checking;
   the fixture checker, launcher and runtime roles contain the same assumption.

The original guest exception omitted its errno, filename and stack. Its exact
failing syscall therefore is **not proven** by the returned records. A local
restricted-root reproduction did obtain `EACCES` for the PID 1 namespace link
while the self namespace remained readable. This is a reproduced source defect
and a strongly matching explanation, not a fabricated guest traceback.
Linux [ptrace access rules](https://www.man7.org/linux/man-pages/man2/ptrace.2.html)
describe the capability and dumpability checks applied to these proc accesses;
UID 0 and DAC read permission alone do not establish access.

The Q2 correction uses the already protected, boot-bound initial namespace pin
and the restricted process's actual self namespace. Administrator preparation
and owner entry still attest PID 1 against self. The original Q1 guard retains
its two-process check. No capability is added and no namespace/boot check is
optional. All process, cgroup, manager, pipe, deadline and storage checks remain.
This preserves QH-R01/R03 and the existing fixture trust boundary; it does not
introduce another trusted component or a public bypass.

Bounded failure diagnostics retain a static execution stage, exception type,
errno and selected source frames. Arbitrary exception messages, input contents,
local variables and unrestricted filenames are excluded. They cannot change
the original result or turn a failed capture into acceptance.
The original failure reason is retained separately when cleanup changes the
final reason, so the diagnostic remains attributable to its primary failure.

## Read preservation and platform boundary

The public orchestration baseline's actual CI run
[36291609770](https://github.com/kongbu0621/infra-local-hand/actions/runs/36291609770)
failed with four Linux and seventeen Windows source-test failures; installed
acceptance was consequently not reached. These are retained failures, not
successful verification of the retry implementation.

The Linux defect applies `O_NOATIME` to root-owned ancestor directories during
an ordinary user's path traversal. Ancestors are only opened and inspected;
the final file or enumerated directory needs `O_NOATIME`. Failure to obtain that
flag on the final object remains a hard failure, with no ordinary-open fallback.
The Windows changes distinguish Linux-only ownership, directory-fd and allocated
block tests from pure contract tests. An inert or unsupported recovery entry
must reject before acquiring a Linux-only clock.

An additional real access-time regression reproduced a preservation defect:
SQLite reopening `/proc/self/fd/...` loses the held descriptor's `O_NOATIME`.
The correction validates an in-memory copy read through the bounded original
descriptor, retaining the raw-byte digest, identity, sidecar, schema and empty
ledger checks. Any journal-header adjustment affects only the RAM copy. Old
directory enumerations on the preservation chain likewise use protected final
noatime descriptors. Historical preservation booleans are not retroactively
promoted to proof of unchanged atime.

Linux documents the owner/capability condition for this flag in
[open(2)](https://man7.org/linux/man-pages/man2/open.2.html).

## Verification boundary

The frozen repair worktree passed 171 targeted supervisor/namespace tests with
one explicit AF_UNIX environment skip, and 76 read-preservation/recovery tests.
These include a real local restricted-process namespace reproduction, a real
SQLite access-time regression, queued-state identity regressions and retention
of the primary failure when cleanup also fails. A Linux-hosted Windows-branch
model passed 20 tests and skipped 14 Linux-only cases; it is not native Windows
verification. The executor could not switch to an ordinary UID, so the
ancestor-permission regression combines real descriptors with an explicit
permission-denial model. Native Linux ordinary-user and Windows outcomes must
come from the new candidate's CI.

Full source, packaging and independent-install results will be recorded against
the completed exact public candidate. None substitutes for execution on the
original guest. The cloud executor has no access to that host's management
connection, and no new guest run has been issued.

The existing source-repair authority permits these unchanged-boundary repairs,
their tests and publication. The CPUQuota retry's T05 and final implementation
paragraph authorize one batch with a fixed candidate and forbid automatic
replay. A replacement runtime and another guest window therefore require a
separate concrete scope and Owner decision after the repaired candidate is
reviewable; they cannot be inferred from an empty ledger or a short failed run.

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

Two independent defects affected the original source path:

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

## Retained repair-candidate findings

The first repair candidate `eb8a54ab413396df26a393ff730e958e68fac00a` completed
local full-source testing with **3 failed, 1744 passed and 16 environment skips**.
Two capacity tests still intercepted the old first namespace read; the corrected
identity chain reads the fixed boot ID first. Their sentinel now follows that
read while continuing to reject filesystem/process side effects and requiring
capacity refusal before subsequent host admission. The third failure was a
test fixture aliasing a copied venv executable outside its `pyvenv.cfg`; the
alias now uses the actual base interpreter. Production log budgets are unchanged.

Following the complete controller path also found a repair-draft defect: the
launcher's local management-budget dictionary shadowed its imported management
module. A distinct module alias fixes the resulting `AttributeError`.
A full controller-flow regression reproduced that failure before the fix and
then verified both repeated identity checks and identity-change rejection.
The post-fix Q2/controller-guard suite passed **523 tests with 2 explicit
environment skips**. The two changed test modules' focused rerun passed 5 tests.
The first candidate's failures remain recorded; its full-source run is not
reported as a passing result of the successor candidate.

## Exact repaired candidate and verification

- Public source commit: `b49d3df3d1e76813faf08e59ab4975e25279c2fc`.
- Exact tree: `2d957ccf1d9cbdf5e538189c6b68d56f34590a42`.
- Frozen wheel: `infra_local_hand-0.2.0a1-py3-none-any.whl`, 266010 bytes,
  SHA-256 `c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b`.
- Independently sealed, unconfigured Plugin SHA-256:
  `f27c638bed416344f61921df55a49c494c00763c75c0d04915400a54939e25a6`.

The public Git commit object was reconstructed and hash-checked locally; the
clean tree exactly matches the public tree. The pinned build dependencies passed
`pip check`. The wheel was built without network or build isolation from that
exact clean commit. Its metadata binds the same source commit, and all 53 payload
file digests match both the wheel and source. It was installed with `--no-deps`
into a fresh runtime and tested with `python -I` outside the checkout.

| Verification | Actual result |
| --- | --- |
| Source compilation and diff checks | PASS |
| Full local source suite, Python 3.12.14 | **1748 passed, 16 skipped, zero failures** |
| Full Q2/controller-guard regression after launcher correction | 523 passed, 2 environment skips; included in the subsequent full suite |
| Local frozen-wheel acceptance | **PASS: 94 checks, 292 commands**, exact frozen wheel and source identity |
| Native Windows CI | **PASS: 361 passed, 703 platform skips**; installed acceptance 10 checks/10 commands; Windows bootstrap, ACL, Local Service, exit propagation and junction checks passed |
| Native Linux CI | **PASS: 1751 passed, 13 explicit skips**; installed acceptance 94 checks/292 commands; Linux bootstrap checks passed |
| Exact-candidate workflow | [36295204218](https://github.com/kongbu0621/infra-local-hand/actions/runs/36295204218) |

The 16 local skips explicitly retain unavailable ordinary-UID mapping, AF_UNIX
and real systemd/cgroup integration. They do not become passing guest evidence.
The targeted namespace tests include a real restricted local child, while full
controller facts remain modeled. The first local installed run at the earlier
`eb8a54ab...` candidate stopped after 273 completed captured commands: the parent
made no further progress and a synthetic target expected to be regular was
observed as FIFO. It was externally interrupted and retained as INCOMPLETE;
the cross-process cause was not proven. The final candidate's independent run
completed all 292 commands using the byte-identical verifier. No test fixture
was altered to turn that earlier stalled run into PASS.

Retained final local evidence digests:

| Record | SHA-256 |
| --- | --- |
| Complete source-test log | `b88d3bd387222e94cefc5c39924fb0472e57e614569c8bdaf70abe09c8b56528` |
| Exact frozen-wheel installed report | `466777d99be58a3186d37fabea5ec47a1734e5cf3e7cffcd374c36b4bd21439d` |

Native CI builds its own wheel from the same exact source commit; its wheel
bytes are not substituted for the separately frozen local wheel above. Local
and CI checks establish source/packaging behavior, not original-guest Q2
acceptance. No new guest run was issued and no original installation was changed.
All Q2/Q3/production acceptance flags remain false.

## New execution boundary

The existing source-repair authority permits these unchanged-boundary repairs,
their tests and publication. The consumed CPUQuota retry's T05 and final
implementation paragraph authorize one batch with a fixed candidate and forbid
automatic replay. A replacement runtime and another guest window require the
separate concrete scope and exact Owner decision described in
[the new proposed baseline](../governance/Q2_SUPERVISOR_STARTUP_RETRY_BASELINE.md).
The new scope remains OPEN; its three documents are reviewable, but its new
orchestration, configuration and actual one-shot batch follow Owner B and a
separate CLOSED C. Unaffected source repairs need no repeated approval.

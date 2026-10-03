# Execution guidance

## Publication and GX10 handoff

Owner approved public disclosure of exact original candidate `b763bd6714721d22278086db559fa3f6684aad7b` and its governance excerpt, with no license added and no SOP history or raw machine evidence. See [PUBLICATION_OWNER_DECISION.md](docs/governance/PUBLICATION_OWNER_DECISION.md). After the authorized GX10 S1 verification found and repaired defects, Owner separately directed repaired candidate `1e2f9dce87e57c34a35fe3a6a75a8c784181ba83` to be committed and pushed directly to `main`; see [Q6_MAIN_PUBLICATION_OWNER_DECISION.md](docs/governance/Q6_MAIN_PUBLICATION_OWNER_DECISION.md). These are disclosure decisions, not replacements for the S1 closure below. Equivalence/adoption of the public governance excerpt remains pending. Windows is deferred. Owner subsequently directed “全部提交推送。 你直接继续修复”; the follow-up S1 repair/publication record and exact verified candidate are in [S1_FOLLOWUP_REVIEW.md](docs/S1_FOLLOWUP_REVIEW.md). This does not expand S1 closure or authorize live cutover. The subsequent Owner-directed chain-only review is recorded in [S1_CONFLICT_CHAIN_REVIEW.md](docs/S1_CONFLICT_CHAIN_REVIEW.md); its exact candidate and scoped validation are separate from earlier full-suite results. The earlier delivery/receipt recovery repair and chain-only evidence are recorded in [S1_DELIVERY_RECOVERY_REVIEW.md](docs/S1_DELIVERY_RECOVERY_REVIEW.md). The subsequent process-lifetime and bounded-capture repair is recorded in [S1_PROCESS_LIFETIME_REVIEW.md](docs/S1_PROCESS_LIFETIME_REVIEW.md), with targeted source and installed-chain evidence. The subsequent Result size and durable recovery repair is recorded in [S1_RESULT_BUDGET_REVIEW.md](docs/S1_RESULT_BUDGET_REVIEW.md), with exact source and installed-chain evidence. The subsequent committed-mailbox snapshot and interrupted publication repair is recorded in [S1_MAILBOX_SNAPSHOT_REVIEW.md](docs/S1_MAILBOX_SNAPSHOT_REVIEW.md), with scoped source and installed-chain evidence. The subsequent verified-branch fetch and snapshot consistency repair is recorded in [S1_FETCH_SNAPSHOT_REVIEW.md](docs/S1_FETCH_SNAPSHOT_REVIEW.md), with scoped source and installed-chain evidence. The subsequent filesystem state lookup and replay barrier repair is recorded in [S1_STATE_LOOKUP_REVIEW.md](docs/S1_STATE_LOOKUP_REVIEW.md), with scoped source and installed-chain evidence. The subsequent persistence and post-reset recovery repair is recorded in [S1_STATE_PERSISTENCE_REVIEW.md](docs/S1_STATE_PERSISTENCE_REVIEW.md), including targeted verification and the retained first-attempt failure. The subsequent content-read failure and automatic Git maintenance repair is recorded in [S1_READ_FAILURE_REVIEW.md](docs/S1_READ_FAILURE_REVIEW.md), with targeted source and installed-chain evidence and the retained first-attempt pack-scan failure.
 The subsequent input, controller publication and installed payload boundary repairs are recorded in [S1_BOUNDARY_REVIEW.md](docs/S1_BOUNDARY_REVIEW.md), including exact chain verification and the Owner-authorized full source run.

The subsequent capture-start containment, UTF-8 Task identity and acceptance-report publication repairs are recorded in [S1_STARTUP_IDENTITY_REVIEW.md](docs/S1_STARTUP_IDENTITY_REVIEW.md), with full source testing, installed-chain evidence and independent audit.

The subsequent Result UTF-8 containment review is recorded in [S1_RESULT_ENCODING_REVIEW.md](docs/S1_RESULT_ENCODING_REVIEW.md), with full source testing, retained failed installation attempts and explicit publication status.

The GX10 S1 physical-host revalidation defined by [GX10_S1_89D6B8D_RUNBOOK.md](docs/GX10_S1_89D6B8D_RUNBOOK.md) has now completed. Its sanitized result, repaired candidate identity, Public-main byte-equivalence mapping, evidence seal digests and retained limits are recorded in [GX10_S1_89D6B8D_REVALIDATION.md](docs/GX10_S1_89D6B8D_REVALIDATION.md). Raw machine evidence remains private. This result does not authorize live cutover, S2 or artifact-ledger A2.

## Program Repository Documentation Gate

- Gate rule status: Provisional.
- Gate rule source: kongbu0621/engineering-sop (Private companion source).
- Gate rule baseline R: `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`.
- Accessible Gate rule source: [pinned upstream rule](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md).
- Gate rule source integrity: direct pinned source; source bytes additionally SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`.
- Gate adoption mandate: Owner-mandated for all program repositories.
- Gate decision authority: Owner.
- Gate adoption exceptions: none.
- Gate adoption change rule: no automatic upgrade, weakening, revocation, or new exception; Owner decision required.
- Gate state: **CLOSED for S1 under this declaration**; later scopes have separate declarations below.
- Requirements document: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md).
- Architecture document: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- Implementation plan: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).
- Documentation baseline A: `7246b850ffdc2709e359b09cac99f0fb88bda209`.
- Authorized implementation scope: S1 only, as defined in IMPLEMENTATION_PLAN.md: isolated extraction, parameterization, packaging and verification. Publication, live-node cutover and artifact-ledger A2 are outside this closure.
- Owner closure decision B: [S1_OWNER_DECISION.md](docs/governance/S1_OWNER_DECISION.md), local event `S1-OWNER-CLOSURE-20260921-01`; exact Owner text retained. The three documents' DRAFT/OPEN labels describe baseline A before this decision; this record approves those exact versions without changing their semantics.
- Reopen conditions: material changes to requirements, architecture, phase plan, scope, R/A, accessible source, integrity/equivalence/approval, mandate, authority, exceptions or adoption change rule.

The current executor must read the direct pinned rule. If it cannot, it treats this Gate as OPEN. [The public excerpt](docs/governance/PUBLIC_GATE_CANDIDATE.md) and [its manifest](docs/governance/GATE_SNAPSHOT_MANIFEST.json) are approved for disclosure only; equivalence/adoption remain proposed. S1 may be closed against the readable direct source without claiming that the public excerpt has already been adopted. Public adoption later requires its own accurate baseline and decision if it materially changes adoption evidence.

Preserve the order **R → A → B → C → D**: upstream rule, documentation commit, exact Owner decision, separate CLOSED record commit, implementation descending from that record. C includes closure bookkeeping only. Preserve these boundaries when merging; do not squash C with implementation. B must identify Owner, exact decision, time or event ID, stable reference, R, A and scope; retain a verifiable decision copy if the source is mutable. Do not synthesize an Owner decision.

Before closure, documentation, read-only inspection and isolated checks of existing code are allowed. New production or test source, executable prototypes, implementation scaffolds, dependencies, runtime configuration and migrations are not. Existing code and emergency wording do not create a forward-implementation exception. Use the pinned rule for operational containment, spikes and change-control details.

## Project constraints

### S2 preparation status

S2 is **OPEN**. Its proposed requirements, architecture and implementation plan are
[docs/s2/REQUIREMENTS.md](docs/s2/REQUIREMENTS.md),
[docs/s2/ARCHITECTURE.md](docs/s2/ARCHITECTURE.md) and
[docs/s2/IMPLEMENTATION_PLAN.md](docs/s2/IMPLEMENTATION_PLAN.md).
[READINESS.md](docs/s2/READINESS.md) records the newly verified old-deployment
read-only mailbox results and unresolved live inventory. The existing S1 R/A/B/C
record above remains scoped to S1. No S2 closure decision or authorized implementation
scope is recorded. The earlier proposed S2 baseline
`8cb081d9cdf316fd4eb80f5811078d1804d6be3f` is superseded by this documented route update.
The previous proposed S2 baseline `9cc628c9679e1530a2be3c7e7efec829d559d438`
is superseded by this design recheck's explicit dual-protocol cutover and recovery requirements.
The new proposed S2 documentation baseline A is `bc54edc503a6a88aaca1d98276e403b9d97c6743`;
any closure must identify this exact baseline and its scope.
S2 remains OPEN. This record is not a closure commit.
The downstream goal is artifact-ledger GX10 A2. The route now includes a reused
GitHub Connector, restricted-job MCP and Plugin; permissions do not follow from those names.

### A2 execution, MCP and Plugin preparation

Scope `LH-A2-EXEC-MCP-v1` is **CLOSED for E1–E3 only**. Its authoritative documents are
[requirements](docs/a2-execution/REQUIREMENTS.md),
[architecture](docs/a2-execution/ARCHITECTURE.md) and
[implementation plan](docs/a2-execution/IMPLEMENTATION_PLAN.md).
The previous proposed baseline `9cc628c9679e1530a2be3c7e7efec829d559d438`
is superseded by the [design recheck](docs/a2-execution/DESIGN_RECHECK.md).
That scope's subsequent proposed baseline `bc54edc503a6a88aaca1d98276e403b9d97c6743`
is superseded by the [third design-chain review](docs/a2-execution/DESIGN_CHAIN_REVIEW.md),
which closes input/output discovery, local revocation/startup and blocking storage-I/O design gaps.
The subsequent proposed baseline `231fa26807dca0c411a3972930434750944c0983`
is superseded by the [recovery-contract review](docs/a2-execution/RECOVERY_CONTRACT_REVIEW.md),
which fixes reconciliation request identity/cancellation and separates preflight from business execution intent.
The approved documentation baseline A is `79f73faedcd9cde4164b0d1625782dae27db6c2f`,
under the same R recorded above.
The subsequent [baseline confirmation review](docs/a2-execution/BASELINE_CONFIRMATION_REVIEW.md)
found no further required design changes; the three authoritative documents and A remain unchanged.
That review is evidence only, not an Owner closure decision or implementation verification.
Owner closure decision B: [A2_EXEC_E1_E3_OWNER_DECISION.md](docs/governance/A2_EXEC_E1_E3_OWNER_DECISION.md),
event `LH-A2-EXEC-MCP-E1-E3-CLOSURE-20260922-01`; exact Owner reply and its immediately preceding
baseline/scope request are retained. R remains `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`.
This separate CLOSED registration is C; it contains no implementation and does not change A's three documents.
Their DRAFT/OPEN labels describe the accurate pre-approval baseline. Implementation must descend from C.
The authorized closure is E1–E3 only: isolated job broker, fixed job catalog,
MCP adapter, shared-broker maintenance CLI, Plugin packaging, client evidence assembly and synthetic verification.
E4 actual client/private connection, E5 GX10/S2 deployment and E6 real NAS A2 acceptance
are not included. Earlier design requests did not close this scope; the subsequent retained Owner decision does.
S2 remains OPEN at its separate baseline. E3's real isolated cgroup integration must be proven before
claiming a deployable candidate; unsupported environments do not turn that check into PASS.
Preserve the already CLOSED Ledger A2 body scope; do not require it to be approved again.

### E3 quota and real-harness change

Scope `LH-E3-QUOTA-HARNESS-v1` is **CLOSED for the isolated development scope below**. Its authoritative change documents are
[requirements](docs/a2-execution/e3-quota-harness/REQUIREMENTS.md),
[architecture](docs/a2-execution/e3-quota-harness/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/e3-quota-harness/IMPLEMENTATION_PLAN.md).
R, mandate, Owner authority, accessible source, integrity, exceptions and change rules remain those above.
The approved documentation baseline A is `415327ebdcc251bb055da9931a7a88990f750b7a`.
Its exact document digests and pre-approval scope registration are recorded in
[E3_QUOTA_HARNESS_BASELINE.md](docs/governance/E3_QUOTA_HARNESS_BASELINE.md).
Owner closure decision B is retained in
[E3_QUOTA_HARNESS_OWNER_DECISION.md](docs/governance/E3_QUOTA_HARNESS_OWNER_DECISION.md),
event `LH-E3-QUOTA-HARNESS-CLOSURE-20260923-01`. This separate bookkeeping-only commit is C;
implementation must descend from it. A's three documents remain byte-identical, including their historical OPEN labels.
The authorized implementation scope is an isolated, fixed-object administrative quota observer, its bounded
unprivileged client, internal receipt/budget binding and a test-only real three-unit harness on an
explicitly supplied isolated fixture. Host provisioning, GX10 service installation/cutover and E4–E6
are not authorized by this closure.

The current quota-query permission conflict and missing real harness are confirmed implementation gaps;
the proposal adds a host-privileged trusted component and changes how bootstrap obtains quota facts.
That affected scope was reopened and is now separately closed by the retained Owner decision at the exact R/A.
Follow Q1 feasibility, Q2 binding/budget, Q3 normal chain and Q4 faults/recovery in order;
missing real fixtures remain BLOCKED and cannot be replaced by simulated PASS.
The previous A/B/C remains historical and valid for clearly unaffected E1–E3 work; its three original
documents remain unchanged. This proposal does not reopen S1 or Ledger A2 and does not erase past evidence.
Production `E3_SUPERVISION_UNVERIFIED` remains. Accurate host inputs are currently NOT_PREPARED;
see [received-input audit](docs/a2-execution/GX10_E3_INPUT_CONFIRMATION_VERIFICATION.md).

### Q2 isolated fixture preparation

Scope `LH-Q2-FIXTURE-PREP-v1` is **CLOSED for the bounded isolated preparation below**. Its documents are
[requirements](docs/a2-execution/q2-fixture-preparation/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-fixture-preparation/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-fixture-preparation/IMPLEMENTATION_PLAN.md).
R, readable direct source, integrity, Owner authority, mandate, exceptions and
change rules remain those above. Its approved documentation baseline A is
`2ea59b8d1b262632bae5636938107ef2f002a59b`; exact document digests and scope are
recorded in [Q2_FIXTURE_PREPARATION_BASELINE.md](docs/governance/Q2_FIXTURE_PREPARATION_BASELINE.md).
Owner closure decision B is retained in
[Q2_FIXTURE_PREPARATION_OWNER_DECISION.md](docs/governance/Q2_FIXTURE_PREPARATION_OWNER_DECISION.md),
event `LH-Q2-FIXTURE-PREP-CLOSURE-20260926-01`. This independent bookkeeping-only
C records that decision before new implementation D. A's three authoritative
documents remain byte-identical, including their historical OPEN labels.

This closure addresses the host-provisioning exclusion in the existing
`LH-E3-QUOTA-HARNESS-v1` closure: prepare a new bounded fixture inside the already
supplied isolated Q1 guest, including its ordinary identity/manager, seven
distinct quota roots, protected installation/state and independently supervised
entry. Existing Q1 objects and verdicts remain retained. This is separate from
unaffected repairs to the already CLOSED Q2 development scope. Preparation is
not Q2/Q3 acceptance, production support, GX10 deployment or E4–E6 authority.
It authorizes one new ordinary identity/instance-specific manager, seven new
project roots, bounded installation/state/control objects and one original
supervised test-only handoff within A's ceilings and exclusions. The Owner
explicitly authorized the complete batch without per-item approval. Material
scope changes retain the root change rule. Preserve R → exact A → Owner B →
independent C → D; do not squash this closure with implementation.

### Q2 account-failure recovery

Scope `LH-Q2-PREP-RECOVERY-v1` is **CLOSED for the exact bounded recovery below**. Its approved documentation baseline A is
`72c06ec68d370333f5ffb1079023917828b3e681`, containing
[requirements](docs/a2-execution/q2-preparation-recovery/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-preparation-recovery/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-preparation-recovery/IMPLEMENTATION_PLAN.md).
R, readable direct source and its integrity, Owner-only authority, mandate,
no exceptions and change rules remain those above. Exact document digests,
scope and local/public tree equivalence are in
[Q2_PREPARATION_RECOVERY_BASELINE.md](docs/governance/Q2_PREPARATION_RECOVERY_BASELINE.md).
Owner decision B is retained in
[Q2_PREPARATION_RECOVERY_OWNER_DECISION.md](docs/governance/Q2_PREPARATION_RECOVERY_OWNER_DECISION.md),
event `LH-Q2-PREP-RECOVERY-CLOSURE-20260926-01`. This independent bookkeeping-only
commit records CLOSED C before recovery implementation D. The three documents'
historical OPEN labels and bytes at A remain unchanged.

The original preparation command failed after primary-group creation because
its useradd configuration argument was unsupported. The independently authorized
[account/diagnostic repair](docs/a2-execution/Q2_PREPARATION_ACCOUNT_REPAIR_VERIFICATION.md)
does not authorize replay or a refreshed deadline. The original preparation
window has expired; the Owner now authorizes one at-most-300-second management
window for exact-state attestation, corrected account creation, only the
undelivered original steps and the never-issued first original Q2 run.
Original failure bytes, preparation identity, candidate and cumulative capacity
remain bound; a new recovery ID is evidence identity only. Recovery implementation
must descend from this independent CLOSED C. The Owner explicitly approved the
complete batch without per-item inquiries; material scope changes still follow
the existing change rule.
The existing CLOSED preparation scope and its original three documents remain unchanged.

### Q2 CPU quota startup retry

Scope `LH-Q2-CPUQUOTA-RETRY-v1` is **CLOSED for the bounded batch below**. Its approved documentation baseline A is
`d8e49617efecae199b0874f183530794f8c36e6a`, containing
[requirements](docs/a2-execution/q2-cpuquota-retry/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-cpuquota-retry/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-cpuquota-retry/IMPLEMENTATION_PLAN.md).
R, readable direct source/integrity, Owner authority, mandate, no exceptions and
change rules remain unchanged. Exact document hashes and the proposed boundary
are in [Q2_CPUQUOTA_RETRY_BASELINE.md](docs/governance/Q2_CPUQUOTA_RETRY_BASELINE.md).
Owner decision B is retained in
[Q2_CPUQUOTA_RETRY_OWNER_DECISION.md](docs/governance/Q2_CPUQUOTA_RETRY_OWNER_DECISION.md),
event `LH-Q2-CPUQUOTA-RETRY-CLOSURE-20260927-01`. This separate bookkeeping-only
commit is CLOSED C. It changes neither A's three document bytes nor their
historical OPEN labels, and adds no implementation. Implementation D must descend from C.

Real recovery preparation completed, but its issued owner command failed because
systemd rejected the four-decimal CPUQuota text. The old owner remains INCOMPLETE.
The independently authorized encoding repair, native parser checks and candidate
build are recorded in [Q2_CPU_QUOTA_REPAIR_VERIFICATION.md](docs/a2-execution/Q2_CPU_QUOTA_REPAIR_VERIFICATION.md).
That source repair alone did not authorize changing the frozen guest candidate or
reissuing the consumed recovery/owner attempt. The Owner now explicitly approves one exact
replacement candidate, independently created runtime state, attested reuse of the
seven unconsumed prepared roots, and one new 300-second management window.
Old source, ledger, reservations, deadlines and evidence remain retained.
New retry source/tests/configuration follow R → exact A → Owner B → independent C → D.
The Owner authorizes the complete one-time 300-second batch without per-item
inquiries; retained failure/consumption, fixed candidate and cumulative budgets
remain mandatory. A second attempt or a material scope change is not implied.
The prior preparation and recovery closures and their approved document bytes
remain historical and unchanged; unaffected repairs in their existing CLOSED
development scopes need not be reapproved.

### Q2 supervisor startup failure retry

Scope `LH-Q2-SUPERVISOR-STARTUP-RETRY-v1` is **CLOSED for the one bounded batch below**. Its exact
three-document baseline A is `47b351b2b943bf1d6f1c71cfeb031157a2eb70cc`, containing
[requirements](docs/a2-execution/q2-supervisor-startup-retry/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-supervisor-startup-retry/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-supervisor-startup-retry/IMPLEMENTATION_PLAN.md).
R, readable direct source and integrity, Owner authority, mandate, no exceptions
and change rules remain unchanged. Exact document hashes and the one-batch proposal
are in [Q2_SUPERVISOR_STARTUP_RETRY_BASELINE.md](docs/governance/Q2_SUPERVISOR_STARTUP_RETRY_BASELINE.md).
Owner decision B is retained in
[Q2_SUPERVISOR_STARTUP_RETRY_OWNER_DECISION.md](docs/governance/Q2_SUPERVISOR_STARTUP_RETRY_OWNER_DECISION.md),
event `LH-Q2-SUPERVISOR-STARTUP-RETRY-CLOSURE-20260927-01`. This separate
bookkeeping-only commit is CLOSED C. It retains the exact approval and its
immediately preceding scope request, adds no implementation, and leaves all
three A document bytes and their historical OPEN labels unchanged. D must
descend from C; do not squash the closure with implementation.

The previously approved CPUQuota retry was issued once and remains INCOMPLETE.
Its supervisor actually executed and failed; original streams and exit 3 were
captured, while invocation declaration, independent-stop proof and seal were
not completed. The existing CLOSED source-development authority covers the
[completed source repairs](docs/a2-execution/Q2_SUPERVISOR_STARTUP_REPAIR_VERIFICATION.md),
tests and publication. It does not replay that consumed attempt.

The approved batch pins repaired runtime `b49d3df3d1e76813faf08e59ab4975e25279c2fc`,
binds both historical failures and ledgers, preserves exact historical FAILED
instances, checks all prior identities and cumulative commitments, and authorizes
one new at-most-300-second batch with independent create-only state. Prepared
roots are reused only after joint live attestation. New orchestration, tests,
configuration and execution follow exact A, Owner B and independent C. Owner
approved the complete implementation, verification, delivery and one new run
without per-item inquiries. No second run, refreshed old deadline or material
scope expansion is implied. The prior approved documents
and unaffected CLOSED development scopes remain unchanged.

The independent C is `d4a925c883672fadc7d1b10a8dfe58df18b922cd`; tooling D
`78589e6871cdf5eba72008ee2b27a350a0dfdc03` descends directly from it. See the
[tooling verification and execution blockers](docs/a2-execution/Q2_SUPERVISOR_STARTUP_RETRY_VERIFICATION.md).
The new batch is NOT ISSUED and its one execution authorization is unconsumed.
The no-release lower bound, including retained staging, is now independently
established at 365694976 bytes / 17599 inodes, above 256 MiB / 16384 inodes,
before new staging. The earlier 320 MiB lower bound remains valid but incomplete.
The [new return review](docs/a2-execution/evidence/q2-readonly-return-20260927/README.md)
supersedes the prior missing-raw inventory: all ten reservation inputs are
available across the old and new archives; preflight is verified by its original
historical tree. Twelve historical trees, fifteen old-file digests, 628 overlapping
files and eleven host carriers match. Two second-bootstrap raw inputs lack an
independent historical whole-file pin; their limited prospective adoption is now
approved by the separate decision below. Five disclosed atime changes are retained, not repaired or described
as complete preservation. The accurate second staging tree plus adjacent intent
is the approved 610-entry forward comparison baseline, not historical identity.
Do not ask Owner to find these already retained files again. Complete live
admission remains required. Critical evidence has a repository index with
digest, source relation, retention location and availability; raw machine
evidence remains in its separately versioned private Git archive.

### Installation-reservation reconciliation

Scope `LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1` is **CLOSED for the exact
bounded amendment below**. Its approved
[requirements](docs/a2-execution/q2-installation-reservation-reconciliation/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-installation-reservation-reconciliation/ARCHITECTURE.md) and
[implementation plan](docs/a2-execution/q2-installation-reservation-reconciliation/IMPLEMENTATION_PLAN.md)
jointly authorize limited adoption of two exact current raw inputs, a precise
current second-staging comparison baseline, the five disclosed post-read metadata
values, and append-only termination of only the two installation targets' unused
future obligations. All actual data, other commitments, original ceilings,
frozen runtime and the same single unissued startup batch remain retained.
Full live checks and before/after accounting must fit the original single 300s
window and 140s preparation budget. The additional state record budget is
1 MiB / 16 inodes inside the unchanged state ceiling, not an expansion.
Exact A is `c65ff4e25ea6373aabf8db25d304ee7614b96eb5`; its
[separate baseline registration](docs/governance/Q2_INSTALLATION_RESERVATION_RECONCILIATION_BASELINE.md)
pins the three document hashes. Owner B is retained in
[Q2_INSTALLATION_RESERVATION_RECONCILIATION_OWNER_DECISION.md](docs/governance/Q2_INSTALLATION_RESERVATION_RECONCILIATION_OWNER_DECISION.md),
event `LH-Q2-INSTALLATION-RECONCILIATION-CLOSURE-20260927-01`; exact reply
“按原 R，批准 A c65ff4e2 的对账方案，继续实施” and its preceding request are preserved.
This independent bookkeeping-only commit is C; implementation D must descend
from it. A's three fixed documents remain byte-identical, including historical
OPEN labels. R, direct source/integrity, mandate, Owner authority, no exceptions
and change rules remain unchanged. This authorizes P1–P6 within A, including
implementation, verification, delivery and conditional continuation of the same
single startup batch; it does not authorize an additional run or relaxed ceiling.
Documentation, closure and evidence retention do not consume the run. The new
batch remains NOT ISSUED until actual evidence proves otherwise.

### Host window consumption

Scope `LH-Q2-HOST-WINDOW-CONSUMPTION-v1` is **CLOSED for H1–H6 at exact A
`8402f0cc82d8a0ac0b9a56716bf276f41cafea37`**. Its
[baseline record](docs/governance/Q2_HOST_WINDOW_CONSUMPTION_BASELINE.md) pins the
[requirements](docs/a2-execution/q2-host-window-consumption/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-host-window-consumption/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-host-window-consumption/IMPLEMENTATION_PLAN.md).
Their historical OPEN labels and exact bytes remain unchanged.

Owner B is retained in
[Q2_HOST_WINDOW_CONSUMPTION_OWNER_DECISION.md](docs/governance/Q2_HOST_WINDOW_CONSUMPTION_OWNER_DECISION.md),
event `LH-Q2-HOST-WINDOW-CONSUMPTION-CLOSURE-20260927-01`, with exact reply
“按原 R，批准 A 8402f0cc 的 host 窗口消费方案，继续实施。” and its preceding request.
This independent bookkeeping-only commit is C; new implementation D must descend
from it. Unchanged R is `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`, with the
same direct readable source/integrity, Owner mandate/authority, no exceptions
and change-control rule recorded above.

The prior first-write / cross-process-consumption conflict reopened this exact
host scope; this decision now closes it with A's explicit limited changes.
A permits one bounded host marker inside the original capture ceiling before
joint guest admission, and repeatable local-only read prechecks before exclusive
acquisition. The winner retains its precheck's original clocks; every existing
or partial marker blocks further remote delivery. The location is derived from
the exact carrier parent and original startup C, independent of caller-selected
attempt/output prefixes. The fixed current host-boot adoption, storage assumptions
and existing management audit boundary are part of this exact approval.

H1–H6 includes implementation, isolated validation, exact private delivery and
conditional continuation of the same single startup batch. Full joint admission,
shared host/guest accounting, source preservation, hard deadlines, stop/EOF and
seals remain necessary; no second consumed window, relaxed ceiling, system
configuration change or frozen runtime replacement is authorized. The existing
source containment can be replaced only by verified implementation of this closed
scope. Current code and earlier local tests alone do not establish readiness.

The already closed reconciliation scope and its implementation D
`8fd84521cdd25b455ff148e0c0fed6b5d8e39fe1` remain retained, with old v1 unchanged.
See `docs/a2-execution/Q2_RECONCILIATION_IMPLEMENTATION_REVIEW.md` for the prior
exact evidence and limits. All new results must identify their actual D and field
state; Gate closure, publication and evidence retention do not consume the run
or prove issuance. Material scope/contract/adoption changes retain R's reopen rule.

The subsequent [component implementation review](docs/a2-execution/Q2_HOST_WINDOW_IMPLEMENTATION_REVIEW.md)
records H1/H2/H4 component work and H3 binding primitives. H3's complete field
dispatcher and H5 live delivery remain NOT READY: existing evidence does not
prove the first remote absolute deadline, complete host future/audit costs,
wrapper source admission or actual filesystem qualification. Current production
entries therefore refuse before any field read, window or consumption. This is
a factual readiness block under the closed A, not a request to approve A again.
The private package for that earlier D supports offline verification only. No actual window
was consumed and no owner was issued by that work.

The subsequent [local preflight and deadline review](docs/a2-execution/Q2_LOCAL_PREFLIGHT_AND_DEADLINE_REVIEW.md)
records completion of the already approved read-only LOCAL_PREFLIGHT branch at D
`0a456a909821fd1fc6a4fdec43b9e16bc88679f2`. This does not reopen or close another
scope. The separate local reader verifies exact offline inputs and fixed known
object locators, retains its receiver's earlier dual-clock origin, and returns
only partial observations or BLOCKED. It cannot create the marker, execute the
wrapper, contact the guest, admit a joint bill or dispatch the owner. The existing
consumption and full execution entries remain blocked. The returned host manifest
is used only to locate known objects for current observations; its historical
metadata or fee categories are not newly adopted. Kernel/evidence reads retain
O_NOATIME without a privilege or weaker-read fallback. Lack of that capability
is an explicit local BLOCKED result, not permission to request sudo or modify
the host. Exact RAM delivery and observation results do not consume the original
batch, prove H07, or supply missing historical obligations.

### Fixed kernel fact read amendment

Scope `LH-Q2-KERNEL-FACT-READ-v1` is **CLOSED for K0–K4 at exact A below**.
Its authoritative documents consist of
[requirements](docs/a2-execution/q2-kernel-fact-read/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-kernel-fact-read/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-kernel-fact-read/IMPLEMENTATION_PLAN.md).
Its exact documentation A is `887b640b394f9983f37dfe97c58ba35aaa099359`;
[baseline registration](docs/governance/Q2_KERNEL_FACT_READ_BASELINE.md) pins its three files.
R, direct source/integrity, Owner-only authority and the existing change rule remain unchanged.

The [field screenshot review](docs/a2-execution/Q2_LOCAL_PREFLIGHT_FIELD_REVIEW.md)
records a local preflight permission block at host_boot, empty observations and
no consumption by this invocation. It does not prove the boot value, absence of
the consumption path, full raw output integrity or joint admission. Do not ask
Owner to repeatedly paste the same version or change host privileges.

The approved amendment only permits explicit ordinary reads of the two fixed
kernel views after fd/procfs/mount-identity qualification, with disclosed kernel
metadata semantics. It narrowly supersedes the original host A's universal
O_NOATIME clause for those reads. It is not a generic fallback or a change to R.
Owner B is retained in
[Q2_KERNEL_FACT_READ_OWNER_DECISION.md](docs/governance/Q2_KERNEL_FACT_READ_OWNER_DECISION.md),
event `LH-Q2-KERNEL-FACT-READ-CLOSURE-20260927-01`, including the exact decision
and explicit public disclosure approval for this batch's sanitized documents.
This separate bookkeeping-only C records CLOSED before any new implementation;
A's three documents and historical OPEN labels remain byte-identical. D must
descend from this C. No new implementation or test source is included in C.
All ordinary evidence O_NOATIME protection, old pins and budgets, frozen runtime,
no-consumption/no-remote local branch and the full execution blockers remain.
Unaffected CLOSED work remains authorized; no blanket reopening or new batch.


The subsequent [kernel fact implementation review](docs/a2-execution/Q2_KERNEL_FACT_READ_IMPLEMENTATION_REVIEW.md)
records K1–K3 completion at D `e15c633adbdfbf1e29cb12b2410975fe4911458d`,
with 331 passing / 3 skipped development tests, a separate successful actual
ordinary-identity CI check, and an exact new four-chain RAM delivery. The
workspace PTY's proc submount rejection is a separate expected BLOCKED result.
The general CI retains the same 21 Linux test failures and 6 Windows collection
errors as the prior source run; it is not a full-suite PASS. The review retains
those results separately from the successful scoped and ordinary-identity checks.
K4 still awaits the original host's complete JSON; neither CI nor the private
package establishes original-host facts, H07, joint admission or consumption.

The subsequent [field screenshot result](docs/a2-execution/Q2_KERNEL_FACT_READ_FIELD_RESULT.md)
records OBSERVED_PARTIAL at final_local_recheck on 2026-09-28 +08. This is
evidence that the reported field attempt passed the previous kernel permission
block. K4's complete raw JSON remains unreceived and unverified; retrieve the
existing terminal output without rerunning. Visible allocated bytes are limited
current observations, with cost classification and audit obligations still
unproven. This record changes no code, package, authority or consumption state.

The subsequent [complete local observation receipt review](docs/a2-execution/Q2_KERNEL_FACT_READ_FULL_RETURN_REVIEW.md)
records receipt and scoped verification of the complete Owner-pasted JSON on
2026-09-28 +08. It supersedes only the preceding pending-JSON status: K4's
complete local observation receipt is now received and checked. Exact-D package
tool bytes, retained external sources, all target fields and seven old pins were
checked separately from the independent internal-consistency review. The paste
is retained evidence, not an independently sealed stdout or host attestation.
OBSERVED_PARTIAL remains; unknown bills and qualifications remain unknown, and
the existing general CI failures remain. No new C/D, scope, package, batch,
consumption or full Q2 acceptance follows. Continue offline source-gap accounting
for H07, costs, wrapper binding and filesystem qualification; this receipt review
requires no host rerun or repeated Owner approval.

### Fixed local source evidence

The already closed host scope's subsequent
[v1 record binding repair](docs/a2-execution/Q2_HOST_RECORD_BINDING_REPAIR_REVIEW.md)
is implemented at `14d19f1f52d687afa360353aadecd6ea17725310`, with 942 passing and
5 skipped scoped development tests. This hardens existing root v1 record and
billing consistency; ordinary-identity support was not implemented at that D,
and field readiness remains unproven. It creates no new execution authority or consumed batch.

Scope `LH-Q2-LOCAL-SOURCE-EVIDENCE-v1` is **CLOSED for L0–L6** at
exact documentation A `b8b9ec3da3de43b72e4e17416ea6633494d50c1d`. Its
[baseline registration](docs/governance/Q2_LOCAL_SOURCE_EVIDENCE_BASELINE.md) pins
the three approved documents and explains the material change from the old K
scope. Their exact bytes and historical OPEN labels remain unchanged. Owner B is
retained in [Q2_LOCAL_SOURCE_EVIDENCE_OWNER_DECISION.md](docs/governance/Q2_LOCAL_SOURCE_EVIDENCE_OWNER_DECISION.md),
event `LH-Q2-LOCAL-SOURCE-EVIDENCE-CLOSURE-20260928-01`, with exact reply
“按原 R，批准 A b8b9ec3d 的固定本地来源补证方案，关闭该范围 Gate，继续实施。”
and the preceding request. The independent bookkeeping-only C is
`8e7545199bde66583e1d643656dece867ab1dbda`; new D must descend from it.
R, its direct readable source/integrity, Owner mandate and
authority, no exceptions and change rules remain unchanged.

This closure authorizes only seven fixed adjacent metadata/hash observations, four
fixed control-file matching raw inputs, two parents' existing filesystem facts
and narrowly reused fixed kernel views in a new local-only branch, with L1–L6
implementation, isolated verification, exact RAM delivery, one initial bounded
original-host invocation and receipt/static-source review. No automatic retry,
wrapper execution, remote, marker or Q2 consumption is authorized. This does not
admit ordinary writer support, H07, full billing, filesystem allocation/durability
or Q2/Q3. The old K4 receipt is already complete and need not be resubmitted or
rerun. Unaffected CLOSED work remains authorized. Material scope, source adoption
or contract changes retain R's reopen rule.

L1–L4 are implemented at final D `411a9f054d0ee85c3e82296a1fdd3a9ed4ae6239`, tree
`21773876ef321eb70fdfd9dc24cbeed881efd2ef`, descending from C through the first
implementation and isolated CI fixture repairs. The source change,
211 PASS / 3 SKIP affected regression, exact private RAM delivery, independent
review and accurate CI outcomes are registered in
[the implementation review](docs/a2-execution/Q2_LOCAL_SOURCE_EVIDENCE_IMPLEMENTATION_REVIEW.md).
Development/CI identity evidence does not attest the original host. The subsequent
[first field receipt review](docs/a2-execution/Q2_LOCAL_SOURCE_EVIDENCE_FIELD_REVIEW.md)
records the returned L5 invocation and completed L6 receipt/block review: BLOCKED
at protected_parents, all eleven targets unattempted. Four raw sources were then
unavailable; static wrapper review and full Q2 were incomplete. A bounded
diagnostic repair may retain metadata already obtained by the same checks; it
must not add reads, weaken protection or retry the host automatically.
This diagnostic repair is implemented at `89c725efd61dad11b0cc9ae11c3c08a941e3111a`,
with 236 PASS / 3 SKIP scoped regression and an exact offline-verified private
package. The initial diagnostic and separately initiated rerun1/rerun2 have returned;
the [field review](docs/a2-execution/Q2_LOCAL_SOURCE_EVIDENCE_FIELD_REVIEW.md)
retains those three exact diagnostic receipts at the same D. The retained rerun2
passed the initial parent-chain checks and reached fixed_objects, then blocked
at M01: retained mode 0664 intersects 06022 only at group-write. One target was
attempted, ten were unattempted; observed/matched/raw and ordinary bytes were zero.
M01 metadata is from the parent-relative no-follow stat before file open, not
an opened-file fstat or a completed file stability/ACL check. Final parent/marker/
boot rechecks were not reached; initial parent success is not permanent admission.
The [maintenance receipt review](docs/a2-execution/Q2_FIXED_OBJECT_MAINTENANCE_REVIEW.md)
now records receipt of the eleven-file/eight-directory inventory and the six-file
permission-maintenance report. Cross-report identities and the exact 0664-to-0644
delta match. The local executor reports maintenance after Owner's six-file instruction;
this cloud review did not perform host operations. Shared-write dependency remains
UNKNOWN, with no retained explicit acceptance of that unknown. Do not silently mark
it resolved, repeat the maintenance, or undo the completed change. ctime changes and
the limits of report-only evidence remain recorded.

The subsequent [rerun3 completion review](docs/a2-execution/Q2_LOCAL_SOURCE_EVIDENCE_COMPLETION_REVIEW.md)
records Owner's explicit single-call instruction under the 172bb13 handoff and
receipt of the complete 32,439-byte JSON. Exact D is still 89c725ef. All eleven
targets matched, four raw controls returned, and the result is OBSERVED_PARTIAL
at final_local_recheck. L5 receipt/source verification and L6 static dependency
review are complete; L1–L6's limited local-evidence task is complete. Per-file
read stability is not a simultaneous global snapshot or independent host attestation.
The [remaining admission plan](docs/a2-execution/Q2_POST_SOURCE_ADMISSION_PLAN.md)
records the wrapper compatibility boundary and the current
indexed 12-KiB parent exceeding the writer's narrow filesystem profile. Raw text
availability does not authorize execution; H07, billing, ordinary-identity field
qualification/entry assembly, filesystem peak/durability and full Q2 remain unproved. Do not rerun the same collection or
repeat maintenance. Further observation, new source adoption or supervision changes
retain their existing authority/change rules; there is no automatic retry or new batch.

The subsequent [wrapper profile review](docs/a2-execution/Q2_WRAPPER_PROFILE_IMPLEMENTATION_REVIEW.md)
records D `22efa42ab362ab3ea4b811fc1c1519ddc2ef2bb3`: an explicit finite
env-Bash/literal-SSH profile and synthetic isolated tests within existing CLOSED
H1/H4. The old default remains unchanged. There are 143 distinct targeted local
test passes; independent reruns are a subset. The real source only matched
statically and was not executed or adopted for execution. Source admission,
actual tool/environment binding, H07 and all field readiness gates remain required.
This implementation does not update old exact delivery packages or the frozen runtime.

The subsequent [ordinary writer component review](docs/a2-execution/Q2_ORDINARY_WRITER_IMPLEMENTATION_REVIEW.md)
records D `c2373313eb78aa55373cb0318d08d5f60424dafd` within existing CLOSED H1/H2/H4.
Explicit ordinary precheck/intent/evidence v2 binds live process credentials,
parent and actual created ownership, full protected name/fd chains and exact bills.
Old root v1 and the existing production loader remain strict. Pure input consistency
never grants execution or source adoption. Kernel/FS qualifiers and field refusal
are unchanged; the local-only kernel read exception is not wired into consumption.
Ordinary component testing does not establish original-host qualification, H07,
complete common billing or Q2. Exact local/native results belong to that review;
old runtime and private packages are not rebuilt, and the startup batch remains unissued.

The subsequent [parent-allocation component review](docs/a2-execution/Q2_PARENT_ALLOCATION_IMPLEMENTATION_REVIEW.md)
records D `530a2a45bc6e96270771ccf266793e471d8408ee` within existing CLOSED H2/H3/H4.
The ordinary writer retains the first already-read parent metadata and marker
snapshot binding in RAM; the explicit bill/v2 moves only that observed net
growth from the same marker pool's future to actual. Total reservation is
unchanged. This is neither causal attribution nor peak/durability proof.
The narrow profile rejects old parent/ancestor scan or obligation coverage and
physical aliases; baseline parent cost remains UNPROVEN, never zero or capture.
Old bill/run APIs and field refusal stay strict. New arithmetic/consistency
outputs do not establish full billing, filesystem qualification or execution.
The [next qualification review](docs/a2-execution/Q2_FIELD_QUALIFICATION_NEXT_REVIEW.md)
fixes the H07 domain/state and FS source-proof work; it is not a new A/closure
or host instruction. No original-host action, new source adoption or startup
consumption follows from this component. Frozen runtime and old packages remain.

The subsequent [H07 consistency component review](docs/a2-execution/Q2_H07_MODEL_IMPLEMENTATION_REVIEW.md)
records a bounded, explicit offline API within CLOSED H1/H3/H4. It rechecks
supplied source bytes, derives fixed planned domains, and models the two internal
manager-request edges independently. Unknown dynamic domains remain missing.
Submission stays unresolved after absent Job, cancellation, empty tree or EOF;
no model event grants a fence, actual closure, source adoption or execution.
An input window's syntax/hash consistency does not prove its actual origin.
The old source-closure list and live entries remain unchanged. A separate H2/H4
fail-closed fix rejects ext4 EA_INODE from already-read superblock bytes; this
does not qualify the current indexed parent, all allocation costs or durability.
Exact D, test and native CI evidence belong to the linked component review.
No original-host action or new operational authority follows from these repairs.

The subsequent [cost-source claims component review](docs/a2-execution/Q2_COST_SOURCE_IMPLEMENTATION_REVIEW.md)
records a bounded stdlib-only, pure-bytes API within CLOSED H1/H3/H4. Final D
`24b5536ccf98c081212c7a05a6a883863d6f96fc` retains the initial module bytes and
repairs only two oversized pytest parameter IDs; its native CI is 3/3 successful,
with 78 new passing cases on each platform. The initial Windows failure is retained. It checks
source pins, exact field references and coverage/credit claim conflicts. A source
digest groups a container, not an observation epoch; selected-field arithmetic is
not actual inventory or a current lower bound. It does not release obligations,
apply credits, derive G/future, adopt sources or qualify the field. Existing bills,
writer, entry and frozen runtime stay unchanged. The [H07 route review](docs/a2-execution/Q2_H07_MECHANISM_ROUTE_REVIEW.md)
records why a side broker cannot cover the frozen direct manager calls; no complete
actual route is currently established. The [FS/billing source contract](docs/a2-execution/Q2_FS_BILLING_SOURCE_CONTRACT.md)
retains precise missing sources and proof duties. These records authorize no host
action, retry, new facility or new startup batch.

The subsequent [pending-request source review](docs/a2-execution/Q2_H07_PENDING_REQUEST_SOURCE_REVIEW.md)
traces pinned upstream systemd control flow: client timeout/disconnect, AddRef
release and a generic error reply are not an atomic start cancellation. Failures
can occur after job insertion. The project's wait/pipe calls select the system
bus in that upstream version; bypassing this repository's broker must not be
misdescribed as necessarily using the manager's private socket. This is static
research, not original-host version qualification or new execution authority.

The subsequent [CI repair review](docs/a2-execution/CI_REPAIR_20260928.md)
records test-fixture and platform-collection repairs at
`3d9b9ff306bc6c4cfc48bafbeaaad4f114a5dafe`. These remain inside existing CLOSED
isolated-verification scopes. Production modules and authoritative A documents
are unchanged; real root-only collector coverage is mandatory alongside the
ordinary-user suite. Exact native CI outcomes are distinct from cloud skips
and do not establish original-host readiness or Q2 acceptance.

### H07 cgroup fence qualification spike

Scope `LH-Q2-H07-CGROUP-FENCE-SPIKE-v1` is **CLOSED for F1–F4** at exact approved A
`71c7e842c724650a0e949a63bb898699b41107be`. Its
[baseline record](docs/governance/Q2_H07_CGROUP_FENCE_SPIKE_BASELINE.md) pins the
[requirements](docs/a2-execution/q2-h07-cgroup-fence-spike/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-h07-cgroup-fence-spike/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-h07-cgroup-fence-spike/IMPLEMENTATION_PLAN.md).
Unchanged R/source/integrity, Owner mandate/authority, no exceptions and change
rules remain those above. Owner B is retained in
[Q2_H07_CGROUP_FENCE_SPIKE_OWNER_DECISION.md](docs/governance/Q2_H07_CGROUP_FENCE_SPIKE_OWNER_DECISION.md),
event `LH-Q2-H07-CGROUP-FENCE-SPIKE-CLOSURE-20260929-01`, with the exact reply
and preceding request. This independent bookkeeping-only commit is CLOSED C;
implementation D must descend from it. The three approved document bytes and
historical OPEN labels remain unchanged.

The approved F1–F4 experiment uses atomic clone3 placement and a separately
observed guardian to close a subtree containing every synthetic workload producer.
It includes a bounded temporary hosted-Linux fixture, manual-only GitHub workflow,
and at most three dispatched rounds (initial plus two justified source-repair
verifications), each with six fixed cases. It is not existing H4 guest authority,
a production backend, original-host provisioning, frozen runtime replacement or
permission to issue/consume the original Q2 batch. Successful local fencing would
not qualify first remote dispatch, cross-clock mapping, FS or full billing.
The Owner expressly permits executor-triggered GitHub-page manual dispatch within
that quota, and in-scope repairs without repeated approval. Exact A stopping and
change-control conditions apply. No laboratory round is consumed by this closure.

The subsequent [round 1 review](docs/a2-execution/Q2_H07_CGROUP_FENCE_SPIKE_IMPLEMENTATION_REVIEW.md#round-1-2026-09-29)
records run `36577764454`, attempt 1, at `6b085d9ceb536b9785ea683cd108e92cd8a4eec4`.
Quota consumed is **1/3**. Account setup failed before the capability probe and
all six cases; the retained result is **UNKNOWN_RETAINED**, cleanup unverified.
Exact A therefore blocks further laboratory dispatches, including on a fresh
runner. The in-scope account-argument repair and offline tests do not clear
this stop condition or alter the original run's evidence.

### H07 round 1 bounded continuation proposal

Scope `LH-Q2-H07-R1-CONTINUATION-v1` is **CLOSED for U1–U4**.
The [requirements](docs/a2-execution/q2-h07-r1-continuation/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-h07-r1-continuation/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-h07-r1-continuation/IMPLEMENTATION_PLAN.md)
authorize accepting only run `36577764454`'s historical cleanup unknown as no longer
independently blocking the remaining two rounds. Its original failure, cleanup
unknown and consumed round remain unchanged; all later stopping conditions stay.
The proposal also separates observed account identity from admitted cleanup
identity and specifies bounded account evidence and explicit report versioning.
Rule R/source/integrity, Owner-only Authority, adoption mandate and no exceptions
remain as above. The exact new documentation baseline is
`a08a5055c35009a896ad6c6059d709758cc78436`; its
[baseline record](docs/governance/Q2_H07_R1_CONTINUATION_BASELINE.md) pins all three
document digests and the precise historical acceptance. Owner B at 2026-09-29
22:38:51 +08, event `LH-Q2-H07-R1-CONTINUATION-CLOSURE-20260929-01`, is retained in
[the accurate decision record](docs/governance/Q2_H07_R1_CONTINUATION_OWNER_DECISION.md).
This independent bookkeeping-only commit is new C; affected implementation D
must descend from it. New A's three original documents and historical OPEN
labels are unchanged. Its requirements' unique supersede table controls both
old cross-round stop clauses only for the named round 1 historical event.
All later stopping conditions, original consumed 1/3, exact new-source and
environment admission, and the requirement for justified remaining rounds stay.
Unaffected original CLOSED scopes remain valid. This closure consumes no round.

### H07 round 2 repair and final-round continuation

Scope `LH-Q2-H07-R2-CONTINUATION-v1` is **CLOSED for V1–V4** at exact A
`eac5e65449e3a4b7083bc91b9123a253e0cb8320`. Its
[requirements](docs/a2-execution/q2-h07-r2-continuation/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-h07-r2-continuation/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-h07-r2-continuation/IMPLEMENTATION_PLAN.md)
retain their approved original bytes and historical OPEN labels; the
[baseline record](docs/governance/Q2_H07_R2_CONTINUATION_BASELINE.md) fixes their
hashes and the exact historical event. Owner B at 2026-09-30 12:35:14 +08,
event `LH-Q2-H07-R2-CONTINUATION-CLOSURE-20260930-01`, is retained in the
[accurate decision record](docs/governance/Q2_H07_R2_CONTINUATION_OWNER_DECISION.md).
This independent bookkeeping-only commit is new CLOSED C; affected implementation
D must descend from it. It contains no new implementation and changes no A document.
Rule R/source/integrity, Owner-only Authority, mandate, no exceptions and change
control remain unchanged.

The requirements' precise supersede table accepts only round 2 run `36662298613`
as a historical UNKNOWN no longer independently blocking the sole final round.
Its original UNKNOWN_RETAINED, C1 failure, C2–C6 NOT_RUN, recorded-object cleanup
verified and whole-report REJECTED with validation errors remain distinct facts.
Round 1 UNKNOWN/cleanup=false and its accurate historical acceptance remain.
Both previous A sets and verification indexes retain their original bytes.

V1–V4 authorizes the bounded fixed cgroup generations, diagnostics, explicit
native v2/report v3/continuation v2, offline validation and conditional final
hosted experiment in exact A. Quota remains 2/3 used; round 3 is NOT_DISPATCHED
and requires accurate D, ordinary CI and every documented admission predicate.
No rerun, quota reset or fourth round; later unknowns and stopping rules remain.
The Owner permits in-scope implementation and qualified remaining dispatch without
per-item reconfirmation. PRO6000/GX10/guest, deployment, frozen runtime changes
and original Q2 startup remain outside this closure. Unaffected CLOSED work and
the prior U2 test repair `824f4be40fc02a68fe64df4934966471e146b222` remain valid.

The subsequent [partial implementation review](docs/a2-execution/Q2_H07_R2_PARTIAL_IMPLEMENTATION_REVIEW.md)
records pure-data receipt/history checking after C. The execution environment
rejected the native-helper implementation subtask; it was not retried through
another agent or execution path. No native producer, generation fixture or
workflow change was implemented. Pure input-consistency results do not establish
live eligibility; V1–V4 remains PARTIAL and round 3 remains NOT_DISPATCHED.
The accurate Owner closure remains valid; this is an implementation-environment
block, not missing approval or a new consumed laboratory round.

### Native spike retirement and existing executor repairs

The later Owner direction on 2026-09-30 is retained in
[SYSTEMD_CANCELLATION_REPAIR.md](docs/a2-execution/SYSTEMD_CANCELLATION_REPAIR.md).
It permits replacing or removing unnecessary implementation while preserving
the product's functionality and requirements. The independent native cgroup
spike is now **RETIRED_UNQUALIFIED**; stop extending its native helper, generation
fixture, report producer and final-round admission. Its laboratory workflow job
is disabled. Round 3 is not to be dispatched. The two consumed rounds, all
historical failures and approved document bytes remain unchanged; no quota is
reset and no experiment is recorded as passed.

This supersedes the preceding forward plan to finish V1–V4, not its historical
R/A/B/C or evidence. The spike was never imported by the production backend or
packaged in the wheel. Repairs now use the already CLOSED E1–E3 and E3 quota
architecture: the existing Broker/Runner/systemd lifecycle, original identities,
bounded observation and UNKNOWN with retained resource barriers. A cancellation
implementation repair within those unchanged contracts is not a new architecture
or permission to activate the production backend. E3 real qualification,
the original Q2 first-remote contract, E4–E6 and NAS remain separately unverified.
Do not resume the retired candidate as a dependency of those functions.

The subsequent [Q2 management timeout repair](docs/a2-execution/Q2_MANAGEMENT_TIMEOUT_REPAIR.md)
records an original listener runtime timeout after the broker-session repair.
It retains the original per-stage bounds and all identity checks, redistributes
the next protected case's finite time budgets, and adds bounded failure metadata.
Its offline checks do not establish Q2 acceptance; old evidence and obligations
remain retained, and the next guest normal chain is a single explicit attempt.

### Q2 system-manager startup repair

Scope `LH-Q2-SYSTEM-MANAGER-REPAIR-v1` is **CLOSED for M1–M4** at documentation A
`ae50aea2639c32021794ecb70730f4b9e781c8d6`. Its
[baseline registration](docs/governance/Q2_SYSTEM_MANAGER_REPAIR_BASELINE.md) pins
the [requirements](docs/a2-execution/q2-system-manager-repair/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-system-manager-repair/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-system-manager-repair/IMPLEMENTATION_PLAN.md).
Unchanged R/source/integrity, Owner-only decision authority, mandate and change
control remain as declared above. Owner B at 2026-10-01 21:01:22 +08:00,
event `LH-Q2-SYSTEM-MANAGER-REPAIR-CLOSURE-20261001-01`, is retained verbatim in
[the Owner decision](docs/governance/Q2_SYSTEM_MANAGER_REPAIR_OWNER_DECISION.md).
This independent bookkeeping-only commit is CLOSED C. A's three documents and
historical OPEN labels remain byte-identical; implementation D must descend from C.

The [complete failure review](docs/a2-execution/Q2_APPARMOR_FAILURE_REVIEW.md)
establishes an AppArmor capability-setup failure before the earlier listener
timeout; the later empty-ledger attempt stopped at retained user-manager inventory.
Do not call the timeout budget change a verified fix for this root cause.
The proposed repair uses a fixed privileged launcher inside the existing controller
and PID 1 to start ordinary workers with all original identity and isolation checks.
It changes the approved user-manager geometry and adds a trusted launch responsibility;
it is not a one-property repair or an extension of the quota observer's read-only API.

M1–M4 covers explicit manager/handle/evidence versions, nested bounded ordinary
slice, complete old-producer admission, source-pinned new payload using the old
interpreter, targeted validation and one guarded original-guest package execution.
Old objects, unknown outcomes and resource obligations remain retained. No global
AppArmor change, reinstallation, old-manager restart, cleanup, automatic retry or
production activation is authorized. At this closure, implementation remains at
`7780364`; this C contains no new program, test or runtime configuration and consumes
no field run. The complete M1–M4 batch is authorized without repeated per-item
approval; material changes retain R's change rule. Unaffected CLOSED work remains
valid. Do not ask for a cyber access qualification.

### Q2 old-producer admission retry

Scope `LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1` is **CLOSED for P1–P3 implementation
and P4 contract/qualification verification** at
documentation A `68424df2ddbf812b9479ffa7a64dcaa59a2a9f76`. Its
[baseline registration](docs/governance/Q2_OLD_PRODUCER_ADMISSION_RETRY_BASELINE.md)
pins the [requirements](docs/a2-execution/q2-old-producer-admission-retry/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-old-producer-admission-retry/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-old-producer-admission-retry/IMPLEMENTATION_PLAN.md).
R, source/integrity, Owner-only authority, mandate and change control remain those
declared above. The current executor directly read the private pinned rule at R and
verified its recorded SHA-256. Owner B at 2026-10-02 12:59:30 +08:00, event
`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-CLOSURE-20261002-01`, is retained verbatim in
[the Owner decision](docs/governance/Q2_OLD_PRODUCER_ADMISSION_RETRY_OWNER_DECISION.md).
Owner explicitly accepted A's disclosed trusted-storage/no-same-UID-tamper governance
premise; this does not make it a technical anti-rollback proof.

The consumed `20261001e` M4 remains `FAILED_RETAINED`: its private admission helper
raised `KeyError: ExecStartPre` before provision and before any normal-chain execution.
The approved plan retains that batch and defines a separate create-only `20261002a`
contract for the four omitted empty Exec-array fields. It also authorizes the bounded
integration of the CLOSED K reader into this new consumer for boot_id and its own
mountinfo only, after exact ordinary-identity verification. The old K authorization
covered local preflight only and grants no consumer, package, batch or field authority.

This commit is the independent bookkeeping-only C. A's three documents, their historical
OPEN labels and the OPEN baseline registration remain byte-identical. C contains no new
program, test, executable prototype, dependency, runtime configuration or field action;
implementation D must descend from C. Product implementation
`1a900e4a38e9567655f21cbf3c3f17941de1a8d5` is not this scope's D.

Implementation D is `4b71824a4660723d064969cbf0c39cd4325dd62a`, tree
`1fe7a678ce857611b617ba2429a8298da2cc6141`, with C as its direct parent.  Its
[implementation review](docs/a2-execution/Q2_OLD_PRODUCER_ADMISSION_RETRY_IMPLEMENTATION_REVIEW.md)
records the four-field parser adoption proof, the two-view consumer integration and
the bounded validation results.  The generated archive is explicitly a partial,
non-executable contract prototype: it has no `TASK.txt`, reports both future-package
contract completion and P4 qualification false, and grants no field authority.

P4 remains independently **BLOCKED**. H07 and both parent filesystems' qualification,
evidence peak and persistence proofs are open; current materials must remain
`field_ready=false`, `allow_run=false` and without executable `TASK.txt`. No live ZIP,
host consumption object or guest connection is authorized. Original-host terminal and
proc/PID namespace alignment remains `EXTERNAL_ASSUMPTION_NOT_PROVEN`; it is not supplied
by the fixed reader or the governance premise. Even after accurate package and
qualification work, Owner must issue a separate stable P4 event binding exact
scope/batch/A/C/D/package/evidence limits and once/no-retry terms. Bare
“continue/authorized continue”, B/C/D, CI/READY, a ZIP or TASK cannot replace it.

### Q2 namespace proposal history

Scope `LH-Q2-NAMESPACE-REFERENCE-v1` is
**SUPERSEDED_PROPOSAL_NOT_APPROVED**. Its historical proposed documentation A is
`dfdd653dd48388d8ab1a2554d16bf5b610edba10`; the
[baseline registration](docs/governance/Q2_NAMESPACE_REFERENCE_BASELINE.md) pins the
[requirements](docs/a2-execution/q2-namespace-reference/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-namespace-reference/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-namespace-reference/IMPLEMENTATION_PLAN.md).
R, readable direct source and integrity, Owner-only authority, mandate, no exceptions
and change control remain those above. That registration was a proposal, not Owner B
or CLOSED C; the three documents retain their accurate pre-approval OPEN labels and
were never approved for implementation.

The proposed closure is NS1–NS2 only: a bounded standalone G/R/O collector contract
and isolated synthetic/native fixture qualification. It introduces fixed status and
pid/mnt namespace-FD sources, narrow proc-to-nsfs leaf exceptions, direct-child pidfd
binding and anonymous IPC. Its original-terminal provenance and endpoint execution
integrity premises are explicit candidate design inputs, not accepted facts or
extensions of the previous storage premise. Existing qualified ordinary supervision
and fixture audit/resource/stop/EOF evidence are required; absence stays BLOCKED.
No fixture provisioning, privilege/system change or retired H07 facility restart is
proposed. NS3 original-host collection, NS4 actual consumer integration and P4 issuance
are excluded. No new collector source/test/prototype or field collection is authorized
until exact Owner B and independent bookkeeping-only C precede D. Unaffected existing
CLOSED repairs remain valid. Proposed A and publication do not prove namespace
alignment or alter `field_ready=false`, `allow_run=false` or the zero normal-run count.

The subsequent [NS2 fixture readiness review](docs/a2-execution/Q2_NAMESPACE_FIXTURE_READINESS_REVIEW_20261002.md)
finds the admission inputs NOT_PREPARED and an existing environment's fitness for
this exact NS2 contract NOT_PROVEN; native qualification remains BLOCKED / NOT_RUN.
Historical Q1/Q2 guest evidence remains valid in its own scope. This read-only finding
does not assert that no physical fixture exists, change A, adopt a root supervisor or
authorize provisioning, probes or the retired H07 laboratory. No Owner B/C is recorded.

The successor scope `LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1` is **CLOSED for F0–F4 only**
at exact documentation A `ad5abaee642cba02d997149badf75a08c219a35c`;
the [baseline registration](docs/governance/Q2_NAMESPACE_FIXTURE_DELIVERY_BASELINE.md)
pins the [requirements](docs/a2-execution/q2-namespace-fixture-delivery/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-namespace-fixture-delivery/ARCHITECTURE.md),
[implementation plan](docs/a2-execution/q2-namespace-fixture-delivery/IMPLEMENTATION_PLAN.md)
and [design review](docs/a2-execution/Q2_NAMESPACE_FIXTURE_DELIVERY_DESIGN_20261002.md).
R, direct readable source/integrity, Owner-only authority, mandate, no exceptions and
change control remain unchanged. Owner B at 2026-10-03 09:32:57 +08:00, event
`LH-Q2-NAMESPACE-FIXTURE-DELIVERY-CLOSURE-20261003-01`, is retained verbatim in
[the Owner decision](docs/governance/Q2_NAMESPACE_FIXTURE_DELIVERY_OWNER_DECISION.md).
This independent bookkeeping-only commit is CLOSED C. It contains no implementation,
test source, executable prototype, dependency, runtime configuration, bundle or field action;
implementation D must descend from it. A's four files, historical OPEN labels and proposal
registration remain byte-identical.

The approved scope jointly authorizes offline binding, implementation and synthetic
verification after this C, one conditional isolated-guest delivery, at most one
`BATCH_RELEASE`, no more than twelve unique native cases and final receipt/accounting.
It requires an already installed and exactly qualified sealed native watchdog W; it
does not authorize installing, uploading, compiling or replacing W, provisioning an
account/manager/unit/mount, changing system configuration or contacting the guest
before this exact Owner B and independent bookkeeping-only C. Owner expressly accepts A's
sole new `fixture endpoint execution integrity` premise, exact objects, budgets, one carrier
request, at most one `BATCH_RELEASE` and at most twelve native cases. Missing static inputs
remain `NOT_ISSUED`; later incomplete identity/status/EOF/accounting remains BLOCKED or
UNKNOWN under A's exact rules. Closure does not establish implementation D, field readiness,
guest readiness or a consumed request. Preserve R → exact A → exact Owner B → independent
C → D, without squashing C into implementation.
The old proposal and its readiness review remain historical evidence only.

The subsequent partial implementation D is
`5926dbe369e221775e32ae8164a571d1128e211f`, tree
`1fd06ecfa7486a597844acce08e4b4b50b5c7453`, with C as its direct parent. Its
[implementation review](docs/a2-execution/Q2_NAMESPACE_FIXTURE_DELIVERY_IMPLEMENTATION_REVIEW.md)
records the exact source/test hashes, targeted validation and retained full-suite failure.
D supplies fail-closed offline plan/manifest and envelope validation, a pure fixture model,
a standalone anonymous synthetic reference protocol and low-level native bridge primitives;
it is not the complete F0–F4 execution body, bundle or a field-ready candidate.

F0 currently remains `NOT_ISSUED` because no real private plan, sealed manifest, qualified
installed W, target and budget inputs were available. F1/F2 are partial; the RAM bootstrap,
guardian/root supervisor, owner durable capture, complete cgroup/stop/EOF/cleanup orchestration,
frozen real bundle and live harness qualification remain absent. F3/F4 remain `NOT_RUN`:
carrier requests, `BATCH_RELEASE`, native batches and native cases are all zero, and no field
receipt/seal was accepted. Targeted model/source tests and local native-tail checks do not prove
real namespace/cgroup execution or `FIXTURE_LIVE_REFERENCE_MATCHED`. The one-request,
one-release and twelve-case ceilings remain wholly unconsumed. Do not describe this D as
complete implementation, conditional delivery, artifact/field readiness or native/live PASS.

### Continuing constraints

- Repository formation also follows Owner-mandated Provisional [RFS-1.0 at the same fixed source commit](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/principles/repository-formation-standard-v1.0.md) and its Established module-boundary principle. The current formation assessment is in FORMATION_AND_MIGRATION.md; a Public shell does not close formation, publication or Authority admission.
- Preserve source provenance and historical evidence; do not copy private history or raw machine evidence into the Public repository.
- Existing Task v1 remains limited to the eight documented actions. The separately CLOSED E1–E3 scope above authorizes isolated implementation of the new job protocol; it does not extend Task v1 or authorize live deployment. A model, adapter, task, tool capability or test PASS grants no extra authority.
- Keep user/node identity, repositories, mailbox, executable paths and credentials out of source defaults. Configuration admission must retain allowlists and fail-closed checks.
- Preserve existing environments and the active deployment. S1 uses new isolated directories and synthetic fixtures; it does not submit live tasks or switch a service.
- Record real command outcomes, versions, commit and artifact digests. Never convert SKIP, unsupported, timeout or incomplete evidence into PASS.
- Source facts that contradict the plan trigger review and an explicit update; they do not silently expand the approved scope.

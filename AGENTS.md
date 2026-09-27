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

Scope `LH-Q2-KERNEL-FACT-READ-v1` is **PROPOSED / OPEN**, not covered by a new
Owner B or CLOSED C. The authoritative proposal consists of
[requirements](docs/a2-execution/q2-kernel-fact-read/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-kernel-fact-read/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-kernel-fact-read/IMPLEMENTATION_PLAN.md).
Its exact documentation A is to be pinned by a subsequent baseline record.
R, direct source/integrity, Owner-only authority and the existing change rule remain unchanged.

The [field screenshot review](docs/a2-execution/Q2_LOCAL_PREFLIGHT_FIELD_REVIEW.md)
records a local preflight permission block at host_boot, empty observations and
no consumption by this invocation. It does not prove the boot value, absence of
the consumption path, full raw output integrity or joint admission. Do not ask
Owner to repeatedly paste the same version or change host privileges.

The proposed amendment only permits explicit ordinary reads of the two fixed
kernel views after fd/procfs/mount-identity qualification, with disclosed kernel
metadata semantics. It would narrowly supersede the original host A's universal
O_NOATIME clause for those reads. It is not a generic fallback or a change to R.
Before exact B and independent C, do not implement or field-run that amendment.
All ordinary evidence O_NOATIME protection, old pins and budgets, frozen runtime,
no-consumption/no-remote local branch and the full execution blockers remain.
Unaffected CLOSED work remains authorized; no blanket reopening or new batch.

### Continuing constraints

- Repository formation also follows Owner-mandated Provisional [RFS-1.0 at the same fixed source commit](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/principles/repository-formation-standard-v1.0.md) and its Established module-boundary principle. The current formation assessment is in FORMATION_AND_MIGRATION.md; a Public shell does not close formation, publication or Authority admission.
- Preserve source provenance and historical evidence; do not copy private history or raw machine evidence into the Public repository.
- Existing Task v1 remains limited to the eight documented actions. The separately CLOSED E1–E3 scope above authorizes isolated implementation of the new job protocol; it does not extend Task v1 or authorize live deployment. A model, adapter, task, tool capability or test PASS grants no extra authority.
- Keep user/node identity, repositories, mailbox, executable paths and credentials out of source defaults. Configuration admission must retain allowlists and fail-closed checks.
- Preserve existing environments and the active deployment. S1 uses new isolated directories and synthetic fixtures; it does not submit live tasks or switch a service.
- Record real command outcomes, versions, commit and artifact digests. Never convert SKIP, unsupported, timeout or incomplete evidence into PASS.
- Source facts that contradict the plan trigger review and an explicit update; they do not silently expand the approved scope.

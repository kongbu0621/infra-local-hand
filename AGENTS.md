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
Public CI run `37093976157` at review head `d45b60062023e39ffc9fe76a45bd822b2639198a`
completed successfully on Windows and Ubuntu; this repository result does not change any of
the `NOT_ISSUED` / `NOT_RUN` field states or supply the missing live evidence.

### Local Hand core acceptance delivery

Scope `LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1` is **CLOSED** at exact documentation A
`74366b3fe41e675b1aa2d677228714a5606c275c`. Its independent
[baseline registration](docs/governance/Q2_CORE_ACCEPTANCE_DELIVERY_BASELINE.md) pins the
[requirements](docs/a2-execution/q2-core-acceptance-delivery/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-acceptance-delivery/ARCHITECTURE.md),
[implementation plan](docs/a2-execution/q2-core-acceptance-delivery/IMPLEMENTATION_PLAN.md),
[live-input review](docs/a2-execution/Q2_CORE_LIVE_INPUT_REVIEW_20261003.md) and two bounded
artifact records. R, direct readable source/integrity, Owner-only authority, mandate, no
exceptions and change control remain unchanged.

Owner B at 2026-10-03 21:16:05 +08:00, event
`LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01`, is retained verbatim together with its
immediately preceding request in
[the Owner decision](docs/governance/Q2_CORE_ACCEPTANCE_DELIVERY_OWNER_DECISION.md). Owner
explicitly accepted A's sole new broad-sudo governance premise, fixed candidate/artifacts/objects,
physical/admission/CPU/peak/input/output/capture budgets, outer deadlines, one create-only marker,
one carrier request and no-reconnect/no-retry rule. The existing fixture policy is not technical
exact-command or one-shot containment; the approval does not grant generic sudo or system changes.

This commit is the independent bookkeeping-only CLOSED C. A's six files, their historical
OPEN labels and proposal registration remain byte-identical. C contains no source, executable
prototype, dependency, runtime configuration, package or field action; implementation D must
descend directly from C. D may implement, verify and freeze the package, then conditionally execute
only H01 semantic PASS → Q4 semantic PASS → H11. H01 retains the empty-ledger gate. H11 uses the
original ledger and request/execution/unit identity without restarting business, reading or
packaging original business result bytes, creating a new grant/unit or refreshing deadlines.

At C, marker/request/task/result/evidence counts remain zero. The old `20261001e` and other
expired/consumed batches cannot be replayed; marker creation consumes the sole delivery and no
failure yields reconnect, retry, a second marker/request or a renamed attempt. namespace/watchdog
remains paused and excluded. Production `E3_SUPERVISION_UNVERIFIED` remains; this closure grants
no production activation, cutover, E4–E6, system configuration change or success inference from
UNKNOWN/missing evidence. Material premise, artifact, object, budget, deadline, management-entry
or execution-rule changes retain R's reopen rule.

The subsequent partial implementation D is
`520f77f578b90d31870517e33e29bee42918f3c0`, tree
`bcffbf66209008ff8dd5db312f53af8ced824cff`, with C as its direct parent. Its
[implementation review](docs/a2-execution/Q2_CORE_ACCEPTANCE_DELIVERY_IMPLEMENTATION_REVIEW.md)
records exact source hashes, targeted validation, the non-passing full-suite attempt, static-member
freeze and all retained blockers. D is fail-closed and **not releasable**: the local entry checks an
exact dispatcher-digest release gate before management reads, object-absence checks, clocks, marker
or request; its allowlist is empty and dispatcher readiness is false.

Only the 859-member static closure is frozen. No `.lhfp` was serialized; package remains `null`,
issuance `NOT_ISSUED`, and six remote management identities plus three approved-input relations are
missing. Eight high-level field effects, deep raw-evidence cross-binding and finalizer deadline
closure remain incomplete. Marker/request/H01/Q4/H11/task/result/evidence counts remain zero.
Tests using fake effects/pipes are code tests only and must never be cited as live PASS. Before any
release digest is added, all blockers in the review must close and a complete package must pass
independent build/parse verification. namespace/watchdog remains paused and production
`E3_SUPERVISION_UNVERIFIED` remains unchanged.

### Core binding and finalization amendment

Scope `LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-v1` is **CLOSED for D1–D4 and conditional single F1** at documentation A
`0bdb49cae5586be60a7ba31d4a8e8367854d1e8c`, superseding unapproved
`4009e1b560dd873bc3d9b937be539f329b93371a` and `0a843218a1614b62c62e7dad8578748f911dad27`.
The [baseline registration](docs/governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_BASELINE.md)
pins the [requirements](docs/a2-execution/q2-core-binding-finalization-amendment/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-binding-finalization-amendment/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-core-binding-finalization-amendment/IMPLEMENTATION_PLAN.md).
R, readable direct source/integrity, Owner authority, mandate, no exceptions and change control remain unchanged.
The baseline registration retains its historical OPEN state and bytes. Owner B is retained in
[Q2_CORE_BINDING_FINALIZATION_AMENDMENT_OWNER_DECISION.md](docs/governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_OWNER_DECISION.md),
event `LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-CLOSURE-20261004-01`.
This independent bookkeeping-only commit is C; it changes no authoritative A document and adds no
implementation, test, package or field action. The first D must descend directly from this C.

The retained-material return at `c83dad17040e9f8cec148303083c47311f8b7fb9` is complete. It identifies
the historical 4 KiB control parent as the correct anchor; a different 12 KiB parent is not that anchor.
Existing VM images share the host filesystem and no dedicated hard-limit mechanism is established by the records.
Do not request the same R3/K4 collection again, read VM payloads, build dedicated storage or start a kernel proof project.

This proposal returns to six fixed capture files and the original v1 receipt/capture manifest, with COMPLETE
accepted only by the original live caller after final fsync, same-inode reread, actual allocation and deadline checks.
It withdraws the seventh attestation, local restart acceptance, loaded-ext4/IKCONFIG measurement, raw-device and
superblock qualification, kernel Git proofs and complete filesystem allocator model. It retains the exact
approved-input source relation, corrected sudo semantics, source horizon, package/HELLO JIT and current admission.

Owner explicitly accepts the material host capture guarantee change: application-enforced logical limits
and observed scope-owned file allocation, not a full-host-filesystem instantaneous physical peak guarantee.
Streams total at most 52 MiB; all six role limits total at most 55132160 logical bytes. The 64 MiB/16 ceiling
applies to application accounting and observed owned-file allocation; at most six files are created.
Checks after create/write/fsync must stop on unknown identity or observed excess, but cannot claim an excess
never occurred or that unobserved filesystem metadata/peaks were bounded. Live reporting explicitly sets
`full_filesystem_peak_proven=false`. Guest resource ceilings and all identity/security checks remain unchanged.

The retained exact B also accepts JIT self-observation limitations, governed source-horizon completeness and
the local trusted single-writer premise defined in A. This acceptance is a governance decision, not a technical
proof or a CI result. D1–D4 and conditional single F1 are authorized after this independent C. All original
input, identity, resource, deadline, release and live admission gates remain required before any execution.
The previous core A/B/C remains historically accurate and partial D remains non-releasable.

After closure, directly complete approved inputs/JIT, all eight groups of real dispatcher effects, six-file
finalization and necessary release validation. Cloud work covers repository implementation and testing;
local Codex handles private source/host binding, independent package verification and the single conditional
H01→Q4→H11 run. H11 recovers its own origin ledger, never Q4's. Reuse the existing SSH and host preparation;
only the original A's new-batch create-only candidate placement is allowed, with no historical reinstall or overwrite.

Package is still null/NOT_ISSUED; this core batch has no marker/request/H01/Q4/H11/task/exit/result execution.
No old batch replay, reconnect, automatic retry, cleanup, host sudo/configuration change or UNKNOWN promotion is allowed.
namespace/watchdog and other side work remain paused; production `E3_SUPERVISION_UNVERIFIED`, E4–E6 and NAS remain excluded.

The subsequent [input/capture review](docs/a2-execution/Q2_CORE_AMENDMENT_INPUT_CAPTURE_REVIEW_20261004.md)
records first D `a7e2a6ffb97b7515ec3f8ceab00ff5e0789f65c9`, directly descending from independent C
`7598886e15ed6911fe0e09e2f8d66203455f9057`, and follow-up source baseline
`1caf26facbccfc9e8783d94504e599914bde7365`, followed by capture/finalizer D
`5e129f76a4a716053a769a3fbfd15bd19da737b4`. Fixed horizon transforms, exact legacy-input reconstruction
and static policy-basis components are implemented and narrowly verified against retained inputs.
Six-file persistence, allocation observations and original dual-clock checks are integrated in the local finalizer.
This is partial D1/D3, not complete approved-input/package/JIT/live admission integration or D2–D4 completion.
All eight real effect groups, v2 local binding integration and complete release verification remain required.
F1 is still NOT_ISSUED; no new management observation, marker, carrier or real task was performed.
The already CLOSED D1–D4 authority remains available; do not seek the same approval again or resume side work.

The subsequent [local v2 review](docs/a2-execution/Q2_CORE_LOCAL_V2_REVIEW_20261004.md)
records cloud integration `bd4a106`, local repair D `33de2ccd5575f73f7644905008b92011c2f8e7e0`,
its exact source/validation limits and retained-input verification. Installer child wait4/EOF/stop accounting
is implemented as a component only; complete guest usage, admission and H01/Q4/H11 effects remain incomplete.
No marker, carrier or real core task was issued. Do not promote those source tests into field acceptance.

### Core host writer transport

Scope `LH-Q2-CORE-WRITER-TRANSPORT-v1` is **CLOSED** for T1–T3 at documentation A
`60756caedf6a2d978627272e44784d11009ac309`. Its [baseline registration](docs/governance/Q2_CORE_WRITER_TRANSPORT_BASELINE.md)
pins the [requirements](docs/a2-execution/q2-core-writer-transport/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-writer-transport/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-core-writer-transport/IMPLEMENTATION_PLAN.md).
R, direct source/integrity, Owner-only authority and change rules remain unchanged.
Owner B is retained verbatim in [Q2_CORE_WRITER_TRANSPORT_OWNER_DECISION.md](docs/governance/Q2_CORE_WRITER_TRANSPORT_OWNER_DECISION.md),
event `LH-Q2-CORE-WRITER-TRANSPORT-CLOSURE-20261004-01`, with the immediately preceding exact request.
This independent bookkeeping-only commit is C; it adds no implementation and preserves the three A document
bytes and their historical OPEN labels. New T1–T3 implementation D must descend from this C.

The prior A requires host writer in marker v2 but does not transport its preimage to the guest.
The approved amendment only adds entry.writer in a strict package v3, binding the original held writer and exact marker;
it does not replace the host with guest identity or weaken the marker digest check. Original A/B/C and
unaffected CLOSED D1–D4 work remain valid. This is not another fixture project or an extra field authorization:
all original budgets, deadlines, single marker/request and conditional H01→Q4→H11 rules remain.
No additional F1, replay, reconnect, retry, cleanup, system change or production activation is authorized.
Original budgets and deadlines remain unchanged. This closure does not complete other D1–D4 gaps or authorize
release before every original gate and this amendment's source-lineage/package verification pass.
At C, marker/request/H01/Q4/H11 remain unissued; production E3 and paused side scopes remain unchanged.

The subsequent [writer transport implementation review](docs/a2-execution/Q2_CORE_WRITER_TRANSPORT_REVIEW_20261004.md)
records exact D `0e72ffae85f247e9423ef2cfa9bda26cf8ba6077`, a direct child of independent C
`8e891e11fb6e563353013ac94c201f30a1df66c9`. Strict v3 writer transport, marker reconstruction,
host return cross-binding and dual-C offline lineage are implemented. This resolves only the writer protocol gap;
real D2 effects, full release verification and independent review remain required. Package remains null/NOT_ISSUED,
the release allowlist remains empty, and no field marker/request/case was issued. A's exact document bytes remain unchanged.

The subsequent [core preparation followup](docs/a2-execution/q2-core-acceptance-delivery/CORE_EXECUTION_PROGRESS.md)
records D `0c786ac2389291f488c60ccc32e7eb468d5e30d0`, following the core execution/evidence checkpoint
`ca4199e2ede7821af1ebe30d1f77f719743414c0`. The fixed existing-account preparation adapter and guarded
create-only effects are implemented and source-tested, not field-accepted. Current guest admission and
preparation capacity collectors, complete shared-pool/usage accounting, installation internal deadlines and
executable binding remain blocked. The dispatcher stays within 262144 bytes; do not restore the oversized
development checkpoint or add an unapproved field module. Runtime candidate/wheel, original F1 and all
budgets/deadlines remain unchanged. No field marker/request/task or production activation was performed.

The subsequent [frozen installer deadline followup](docs/a2-execution/q2-core-acceptance-delivery/CORE_EXECUTION_PROGRESS.md)
records D `247d3ab7de8c323db883a5ed877ab06311ab1cc3`, following `0d2b7c7`'s cancellation and
executable-identity repair. Private guarded I/O bindings now apply the original clocks inside the
unchanged frozen installer; late returns stop subsequent effects and retain partial objects.
Full source and isolated installed checks pass, but this is not guest acceptance. Current admission/capacity collectors,
complete shared-pool peak accounting and aggregate usage evidence remain blocked. The field allowlist
stays empty; runtime candidate/wheel, budgets, deadlines and conditional single F1 are unchanged.
No field connection, marker, request or core task was issued by this followup.

The subsequent [preparation capacity collector followup](docs/a2-execution/q2-core-acceptance-delivery/CORE_EXECUTION_PROGRESS.md)
records D `3f1c4745d8ee888f0c0057794532aa78cfcddbbe`. The three preparation collectors
now perform bounded retained-root snapshots, read-only project-quota inventory and enforcement
observations under the original preparation clocks. Late EOF/errors and identity drift fail closed;
no-atime reads have no fallback. Local retained-file tests use real temporary files, while native
quota observations are explicit doubles, not guest evidence. Full source testing passes.
The exact-D isolated build/install verifier also passes 94 checks / 292 commands;
that test wheel does not replace the approved field wheel.
Current guest admission and its input bindings, shared installation-pool peak accounting and aggregate
usage evidence remain incomplete. The dispatcher is 262044/262144 bytes; no extra field module,
candidate/wheel change, budget increase or refreshed deadline is authorized. The release allowlist
remains empty; this followup issued no marker, carrier or guest task and collected no guest result.

### Core completion adjustment

Scope `LH-Q2-CORE-COMPLETION-ADJUSTMENT-v1` is **CLOSED for C1–C3** at
documentation A `851a1afe4e55196212aa6913e81e0722deed1032`, tree
`5b6c8d3a55d8d0678f2b4543f13df32016630fdd`.
The [baseline registration](docs/governance/Q2_CORE_COMPLETION_ADJUSTMENT_BASELINE.md) pins its
[requirements](docs/a2-execution/q2-core-completion-adjustment/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-completion-adjustment/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-core-completion-adjustment/IMPLEMENTATION_PLAN.md).
R, direct source/integrity, Owner mandate and Authority, no exceptions, and change control remain unchanged.
Owner B is retained verbatim in
[Q2_CORE_COMPLETION_ADJUSTMENT_OWNER_DECISION.md](docs/governance/Q2_CORE_COMPLETION_ADJUSTMENT_OWNER_DECISION.md),
event `LH-Q2-CORE-COMPLETION-ADJUSTMENT-CLOSURE-20261004-01`, with the immediately preceding exact request.
This independent bookkeeping-only commit is CLOSED C. It changes no approved A document or historical
OPEN baseline registration and adds no implementation, test, configuration or field action. New D must
descend from C; do not squash C with implementation.

The approved adjustment changes only the dispatcher source cap to 524288 bytes and replaces unproved instantaneous
physical-peak guarantees for the eleven non-quota pools with application accounting and complete boundary
observations. It preserves the 21 existing project-quota roots, credential/identity checks, numerical runtime
limits, frozen candidate/wheel, original clocks and the conditional single F1. Its remote-result/v2 explicitly
reports the limited guarantee; original package/session/marker versions and fixed file/member sets remain.
Cross-device conservative reservations are not consumable budgets. H11 business-result reads remain forbidden.

At C these changes are not yet implemented: current source cap remains 262144 and current release blockers remain.
The Owner accepts the disclosed source-cap, storage-guarantee and conservative per-device reservation changes;
other budgets, deadlines and the original conditional single F1 remain unchanged. This acceptance is a
governance decision, not proof of an unobserved physical peak or successful guest acceptance.
Existing unaffected CLOSED D1–D4 work remains authorized. C1–C3 must preserve the exact scope and
all release gates; no second execution, reconnect, retry, historical reinstall, cleanup or system change is implied.
The original-scope fix `631677039af3b17392f3269e39a4b1f409fc4f08` is already published and its CI is 3/3 success;
it stops executable binding after late I/O and does not implement this proposal.
Current admission, usage and complete release review remain incomplete. There is no new field package,
marker, carrier or case execution from this followup; no observed old guest state is inferred.

The subsequent [admission implementation checkpoint](docs/a2-execution/Q2_CORE_COMPLETION_ADMISSION_REVIEW_20261004.md)
records D `53533accbf834d489c773d2a037c008059c90c4f`, a direct child of independent C
`c32799c03a32d81deec02f7492c1b71eb47b2b6d`. Current-guest admission and conservative
per-device reservations are connected, and a bound carrier-counter component is implemented.
This is partial C1–C3 work, not complete C2 resource accounting, package release or guest acceptance.
The dispatcher is 331928/524288 bytes. Exact A documents and fixed runtime candidate/wheel remain unchanged.
The release allowlist remains empty; complete 32-pool observations, remote-result/v2, aggregate usage,
independent review and original private package checks still precede the single conditional F1.
This checkpoint made no guest connection, marker/request, real core task or result collection.

### Core fixed cloud init grant binding review

The local private-package review at source D `e2a40bd4b0e0b17ebe2a2ad3f533bdace318cc05`
found a conflict between the pinned cloud-init bytes and the full sudoers literal required by
binding amendment A `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c`. See
[the exact review](docs/a2-execution/Q2_CORE_PRIVATE_PACKAGE_REVIEW_20261005.md).
Scope `LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-v1` is **CLOSED for G1–G3**, only for the fixed-source
normalization in [requirements](docs/a2-execution/q2-core-cloud-init-grant-binding/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-cloud-init-grant-binding/ARCHITECTURE.md) and
[G1–G3 plan](docs/a2-execution/q2-core-cloud-init-grant-binding/IMPLEMENTATION_PLAN.md).
Exact approved A is
`018bdd7f09998290f536ab5a3726ccb4123dffa3`; its three document hashes and decision request are in
[the OPEN baseline record](docs/governance/Q2_CORE_CLOUD_INIT_GRANT_BINDING_BASELINE.md).
Owner B is retained verbatim in
[the Owner decision](docs/governance/Q2_CORE_CLOUD_INIT_GRANT_BINDING_OWNER_DECISION.md), event
`LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-CLOSURE-20261005-01`. This independent bookkeeping-only
commit is CLOSED C; it preserves A's exact three documents and historical OPEN baseline bytes and
adds no implementation. New D must descend from C; do not squash C with implementation.
Unchanged R, readable direct source/integrity, mandate, Owner authority and no-exception change rules apply.
The original source hash, account and sudo privilege must not be replaced. Only A's bounded same-mapping
normalization and explicit source interpretation change are approved; current guest grant/identity checks
remain. Existing unaffected closures remain valid; original conditional single F1, budgets, deadlines,
production E3 restriction and paused side work remain. Complete original/new release predicates still precede
any field action. This C issues no package or field action; historical nonissuance is not current marker-absence evidence.

The subsequent [single F1 result](docs/a2-execution/Q2_CORE_SINGLE_F1_RESULT_20261005.md)
supersedes earlier unconsumed-status checkpoints. Exact delivery D
`605a2a38d1db5ef85c961b4d357cafa157bdd7d5` consumed the original marker and issued
one carrier; a valid real HELLO was received, then the host rejected its v3 package
entry before BIND because the writer field was omitted from the old constructor keyset.
Zero input bytes were sent. The retained receipt is STOP_AND_RETAIN with both business
truths UNKNOWN; remote exit closure is not proven. The original batch is consumed:
no second request, reconnect, renamed marker, refreshed deadline or cleanup is authorized.
The existing CLOSED development scope permits the compatibility repair, not another run.
Release remains hard-closed after this failure; source/CI PASS cannot reset consumption.
Repair D `a6638424c5de2ea59f39cf6e24f07b06040d0884` validates the unchanged v3 writer
in BIND and has passed 4905 source tests (126 skipped) plus the independent installed
verifier (94 checks / 292 commands). Exact reports and retained failures are in the
same single-F1 record. This repaired D was not field-issued; no further marker or request
is authorized by these verification results.

### Core next single acceptance

The existing-scope compatibility repair `40f0f989cc1d76f35a17bb1551ea6a1c68da0441` rejects
package names incompatible with the unchanged guest contract before creating a marker or issuing a request.
Its six relevant test groups passed 232 tests; exact CI 37221463294 is 3/3 success,
including 4963 Linux source tests and an independent installed verifier with 94 checks / 292 commands. See the
[repair review](docs/a2-execution/Q2_CORE_BIND_PREFLIGHT_REVIEW_20261005.md).
This repair does not reset the original consumed F1 or issue another package/request.

Scope `LH-Q2-CORE-NEXT-ACCEPTANCE-v1` is **CLOSED for N1–N3 only**.
Exact approved A is `0b0f445a36232f6bcd32c395b642f9a6b259d2db`, tree `c2ee02917768f4f8b6ef905b7fec0159dffd224f`;
its three authoritative document hashes are in
[the baseline registration](docs/governance/Q2_CORE_NEXT_ACCEPTANCE_BASELINE.md).
The authoritative [requirements](docs/a2-execution/q2-core-next-acceptance/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-next-acceptance/ARCHITECTURE.md) and
[plan](docs/a2-execution/q2-core-next-acceptance/IMPLEMENTATION_PLAN.md) remain byte-identical to A,
including their historical OPEN labels. Owner B is retained verbatim in
[the Owner decision](docs/governance/Q2_CORE_NEXT_ACCEPTANCE_OWNER_DECISION.md), event
`LH-Q2-CORE-NEXT-ACCEPTANCE-CLOSURE-20261005-01`.
This independent bookkeeping-only commit is CLOSED C; it contains no implementation, tests,
runtime configuration, package or field action. New D must descend from C; do not squash C with D.

Owner accepts only the fixed old batch's historical exit/usage remaining UNKNOWN, conditional on
current old-scope quiescence within the single new carrier before installation/cases and full retention
of all old commitments. This is not historical PASS, a refund or a reset of the original consumed F1.
N1–N3 authorizes necessary implementation, exact verification/package freeze and at most one new
fixed `lhqcore-20261005a` marker/request, only after all original and new release/admission gates pass.
Old five raw files and earlier evidence/objects remain unchanged. Old/new identity isolation,
conservative per-device admission and no refund are specified in A. Failure, disconnection or UNKNOWN
stops the new batch: no retry, reconnect, renamed attempt, cleanup or third batch is authorized.
Existing approvals remain valid only for their unchanged scopes. At C, this new batch is NOT_ISSUED;
current old-scope state and new-object absence have not been observed.
R, direct source/integrity, mandate, Owner authority, no exceptions and A→B→independent C→D remain unchanged.
Paused side work and production `E3_SUPERVISION_UNVERIFIED` remain. Governance closure does not establish
field readiness or authorize production activation. Material changes retain R's reopen rule.

The next-core N1 implementation at `27928b35e4406f7cfbbd360bccf0e0a8c4d7ea03`
descends directly from its independent C. Its [implementation and package review](docs/a2-execution/Q2_CORE_NEXT_ACCEPTANCE_IMPLEMENTATION_REVIEW.md)
records fixed prior-source binding, quiescence checks and conservative guest reservations.
Complete earlier-host obligation accounting is not yet bound; the two-core host floor is not admission.
Release remains empty and the new `lhqcore-20261005a` marker/request remains NOT_ISSUED.
Do not reuse the completed read-only package-check caller's writer/window or replay the old consumed batch.

The subsequent local saved-source search in the same review found and byte-verified all 44
historical host originals against the fixed collection/archive chain (zero missing or changed),
and revalidated all six guest horizon archives. The remaining gap is not their file locations:
it is complete earlier-host obligation coverage, unreleased byte/inode amounts and shared-pool
relations, followed by current held-parent device mapping. The approved guest-only source-horizon
premise must not be silently extended to host. Two null cost-source claims are not two lost files.
See [the sanitized source-check index](docs/a2-execution/evidence/q2-core-next-host-source-20261005.json).
No code, approval, release or field-consumption status changed in this documentation followup.

### Core host capacity boundary

Scope `LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-v1` is **CLOSED for B1–B3 only**.
Exact approved A is `f491b15514ed0e05f7e1924785a3f7d162dae90f`, tree `318a7ddb656c9256ab4348379dcb12848ef82351`;
its three document digests and the precise requested decision are in
[the boundary baseline](docs/governance/Q2_CORE_HOST_CAPACITY_BOUNDARY_BASELINE.md).
The 44 saved originals do not establish complete earlier-host obligations. Owner explicitly accepts
the narrower capacity guarantee for the already authorized, unconsumed `lhqcore-20261005a`:
current availability must satisfy both fixed core commitments (128 MiB / 32 inodes), while earlier-host
coverage/amounts/shared pools remain UNKNOWN and do not alone block this one capture. There is no refund,
history-completeness claim or exclusive space reservation. Space contention may cause task or evidence failure.
Original guest accounting, credentials/identity, observed/application limits, prior quiescence and all stop
conditions remain. No new request count, batch, namespace, quota mechanism or production activation is proposed.

Owner B is retained verbatim in
[the boundary Owner decision](docs/governance/Q2_CORE_HOST_CAPACITY_BOUNDARY_OWNER_DECISION.md),
event `LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-CLOSURE-20261005-01`.
This independent bookkeeping-only C records that exact decision before implementation D; no source,
tests, runtime configuration, package, release digest or field action is included. The three A documents
and historical OPEN baseline remain byte-identical. D must descend from this C; do not squash C with D.
Existing next-acceptance N1–N3 remains CLOSED, with only A's precisely identified host historical-capacity
condition superseded for this original single unconsumed batch. Its earlier B alone did not approve this change.
This closure does not consume or add a request; current checks and exact B2 verification remain required.
Do not open the allowlist without the approved implementation and explicit host-condition return binding.
R/source integrity, Owner authority, mandate, no exceptions and A→B→independent C→D remain unchanged.
Paused side work remains paused; true H01/Q4/H11 acceptance is still unobserved.

The subsequent [B1–B3 implementation and field result](docs/a2-execution/Q2_CORE_HOST_CAPACITY_BOUNDARY_REVIEW_20261005.md)
supersedes earlier unconsumed checkpoints for `lhqcore-20261005a`. Independent C is
`434c6a07f7a84f26d7bd01de138125debc467dd4`; implementation starts at its direct child
`61e232e1a4b57c9b7fbd523cbd7d4f8f747d756e`. Exact issued D is
`59d7c32bbe10d580603b8e5e62dd49ad6a538e56`, verified before issuance by full source tests,
independent installation, 3/3 CI and actual private double-build. The one marker and one request
were consumed: valid HELLO, BIND and package sent, then `CORE_ADMIT_SUDO_OUTPUT`, carrier wait 3,
both stream EOFs and host deadline met. The fixed 128 MiB / 32 inode capacity condition passed,
without historical-completeness or exclusive-reservation claims. No output package or case verdict
returned; the original receipt's business execution and evidence collection remain UNKNOWN.
Static ordering places this rejection before old-scope quiescence, installation and H01; it does not
prove remote supervisor closure or guest usage. Five capture files and both batches' obligations
remain retained, with no refunds. Both core opportunities are now consumed; release is closed again.
Do not retry, reconnect, clean up, rename a batch or promote UNKNOWN. This result is not an approval
for another attempt or production E3. Any future field request requires its own exact approval chain.

### Post-sudo single core acceptance

The existing-scope sudo listing repair `432f3f4c5a36735d38869261968fc44583f14023`
has completed CI 37270712716 with all three jobs successful, including Linux 5157 source
tests and the independent installed verifier (94 checks / 292 commands). This does not reset
either consumed attempt or establish real H01/Q4/H11 acceptance.

Scope `LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1` is **CLOSED for S1–S3 only** at
exact three-document A `f9ba6fbc2fa983c46322a00f3385af172fed7cb4`, tree `45b9d9dff11e87a8c83453bdab5d93c0b1ab5734`.
The [baseline and requested decision](docs/governance/Q2_CORE_POST_SUDO_ACCEPTANCE_BASELINE.md)
pin its [requirements](docs/a2-execution/q2-core-post-sudo-acceptance/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-post-sudo-acceptance/ARCHITECTURE.md) and
[plan](docs/a2-execution/q2-core-post-sudo-acceptance/IMPLEMENTATION_PLAN.md).
It authorizes only one fixed `lhqcore-20261005b` request with both consumed priors retained,
current quiescence of both scopes, full non-refunded commitments, a fixed 192 MiB / 48 inode
host availability condition with earlier-host UNKNOWN disclosed, and explicit three-carrier
pre-admission bounds. It does not inherit the consumed 05a request or host-boundary authority.
Owner B is retained verbatim in
[the post-sudo Owner decision](docs/governance/Q2_CORE_POST_SUDO_ACCEPTANCE_OWNER_DECISION.md),
event `LH-Q2-CORE-POST-SUDO-ACCEPTANCE-CLOSURE-20261005-01`.
This independent bookkeeping-only C records that exact decision and contains no implementation,
tests, configuration, package, release digest or field action. The three A documents and their
historical OPEN labels remain byte-identical. New D must descend from C; do not squash C with D.
At this closure the fixed 05b marker/request is NOT_ISSUED. Accurate source/installed/CI and
private double-build checks must precede release; current same-window conditions must still pass
before the one request. This closure does not authorize reusing 03a/05a, another probe, retry,
reconnect, cleanup, refund or fourth batch. A failure ends this scope with retained evidence.
Unaffected CLOSED development remains valid. R/source integrity, Owner mandate/authority,
no exceptions and independent A→B→C→D order remain unchanged. Side work and production E3 stay paused.

The [post-sudo implementation review](docs/a2-execution/Q2_CORE_POST_SUDO_ACCEPTANCE_REVIEW_20261005.md)
records S1 dual-prior/new-identity implementation and local verification after independent C
`0c63e733b166f8f9539fd821db621b331a3ede61`. Implementation D
`c6afff10656624cccbf554688e730f6bde6d82b7` passed full source (5183/127), independent
installed verification (94/292), exact CI 37277874571 (3/3), and real private double-build.
The separate digest registration left field code unchanged. Final issued D
`8704a24b6c3c79ce4a36028ae2182dec2a35843e`, tree `89a5f221883c11838a10a452be2dcb756abb5a17`,
passed its own full source (5184 passed / 126 skipped), independent installed verifier (94/292),
exact CI 37279434388 (3/3 success) and real private double-build before issuance.
The final same-window caller then consumed the single 05b marker and request: valid HELLO,
BIND/package sent, wait status 3, both stream EOFs and host deadline met, with
`CORE_ADMIT_SSHD_GRAMMAR`. The original finalizer returned STOP_AND_RETAIN, no output package,
no remote-result and no H01/Q4/H11 verdict. Five private capture files (9073 B total) remain retained;
original business-execution and result-collection truth stays UNKNOWN. The fixed 192 MiB / 48 inode
current host capacity condition passed without complete historical admission or exclusive reservation.
Exact issued source ordering places rejection at sshd source grammar, after sudo checks and before
sshd helper, old-scope quiescence, guest capacity, installation and H01; this is not proof of remote
supervisor closure or guest usage. The failing sshd source line was not returned; do not guess it.
All three core requests are now consumed. Release is closed again, no refund/retry/reconnect/cleanup
occurred, and this scope ends with retained failure. Another field request requires separate exact
approval, never a replay or a renamed continuation. Production E3 and all paused side work remain.

The subsequent [sshd source diagnostic review](docs/a2-execution/Q2_CORE_SSHD_DIAGNOSTIC_REVIEW_20261005.md)
records an offline repair within unchanged CLOSED core development. Bounded searches of the
retained local material, two historical tar indexes and six pinned guest ZIPs found no sshd
configuration original. A synthetic AcceptEnv glob reproduces rejection but is not evidence of
the actual 05b line. Accepted grammar and effective-policy predicates remain unchanged; only
fixed rejection stages, file/line indexes, counts and digests are added to the existing stderr
channel. No raw configuration/path is disclosed, and no field request, marker or new batch is
issued. Scoped tests are 395 passed / 10 skipped; full local source/installed verification was not
repeated. The exact field trigger remains unproven; release stays empty and all consumption,
UNKNOWN, no-retry/reconnect/cleanup and production E3 boundaries remain.

### Single read-only sshd source capture

Scope `LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1` is **CLOSED for P1–P3 only**.
Exact three-document A is `f2eb31deb3c52d69ccd2079fb7d88608d1a25a62`, tree
`dec4cf6e6cd32010d203e8bde2dfde4d53a02104`; the
[baseline and requested decision](docs/governance/Q2_CORE_SSHD_SOURCE_CAPTURE_BASELINE.md)
pin its [requirements](docs/a2-execution/q2-core-sshd-source-capture/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-sshd-source-capture/ARCHITECTURE.md) and
[plan](docs/a2-execution/q2-core-sshd-source-capture/IMPLEMENTATION_PLAN.md).
The earlier screenshot requested preparation only. The subsequent exact Owner B is retained in
[the capture Owner decision](docs/governance/Q2_CORE_SSHD_SOURCE_CAPTURE_OWNER_DECISION.md), event
`LH-Q2-CORE-SSHD-SOURCE-CAPTURE-CLOSURE-20261005-01`. This independent bookkeeping-only C
records that decision before implementation D. It contains no source, tests, scaffold, configuration,
release digest or field action. A's three documents and historical OPEN labels remain byte-identical.
New implementation must descend from C; do not squash the closure with implementation.

The approval permits only one fixed `lhqsshd-20261005a` diagnostic request after exact B/C and
verified D, reading the fixed sshd source closure into private local capture. It is not a fourth core
acceptance. It discloses diagnostic-only endpoint/runtime trust, login/audit/atime effects, nonexclusive
capacity and possible UNKNOWN remote exit rather than claiming full core supervision. Limits include
65 files / 1 MiB input, a 60s local window, initialized-reader 20s alarm / 5 CPU-s / 128 MiB address-space,
2 MiB stdout / 64 KiB stderr, and additive 4 MiB / 8-inode capture with a 196 MiB / 56 current host check.
All three consumed core requests, old UNKNOWN states and full commitments remain retained.
Raw configuration stays private; no retry, reconnect, cleanup, SSH configuration change, business
execution or production E3 enablement follows from this closure. The new request is NOT_ISSUED
at C; accurate offline validation and same-window local admission must precede issuance.
Paused side work remains paused.
Unchanged R/source integrity, Owner mandate/authority, no exceptions and independent R→A→B→C→D
order apply. The earlier CLOSED development and exact source-diagnostic repair remain unaffected.

The [single-capture implementation and field review](docs/a2-execution/Q2_CORE_SSHD_SOURCE_CAPTURE_REVIEW_20261005.md)
records independent C `b346cbd44dd4f376d4386f72d7029b1311788229` and its direct implementation child,
actual issued D `bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891`. Scoped sandbox checks passed 225/3 skipped;
the new offline tests in the real host view passed 84/0 skipped. Exact D CI 37297107615 completed
successfully (3/3) and local-only preflight passed before the one conditional capture.
The fixed diagnostic opportunity is now **CONSUMED / COMPLETE**: one marker, one SSH request,
exit 0, both EOFs and original host deadline met; three current configuration files totaling 3569 B
were recovered and verified privately. Four original capture files (8782 logical B / 16384 currently
allocated B) and their digests are indexed in the review; the full 4 MiB / 8-inode commitment remains.
Remote completion is reader-reported, not independent supervision proof. The one offline parser pair
reproduced current rejection, with the diagnostic baseline locating `GLOB` at file 1 / line 121.
This does not identify the historical 05b trigger or establish effective SSH policy or core acceptance.
No configuration or grammar was changed; no H01/Q4/H11, business result collection, retry, reconnect,
supplemental capture or cleanup occurred. Do not reuse this consumed diagnostic or any old core batch.
Three old UNKNOWN states and full commitments remain; future grammar/contract changes and field
acceptance retain their own scope/approval rules. Raw configuration remains private, side work stays
paused, and production `E3_SUPERVISION_UNVERIFIED` remains unchanged.

### Fixed sshd locale grammar amendment

Scope `LH-Q2-CORE-SSHD-LOCALE-GRAMMAR-v1` is **CLOSED for offline G1–G3 only**.
Approved exact A is `25e8d6cb015b619d8a55b6157a9454501b1c5f2e`, tree
`3fe2510fd8ba012fe7a733300e1c3d8afdfca9bd`. The [baseline and requested decision](docs/governance/Q2_CORE_SSHD_LOCALE_GRAMMAR_BASELINE.md)
pin its [requirements](docs/a2-execution/q2-core-sshd-locale-grammar/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-sshd-locale-grammar/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-core-sshd-locale-grammar/IMPLEMENTATION_PLAN.md).
Local read-only classification of the saved, digest-verified three-file snapshot confirmed that
file 1 / line 121 is an AcceptEnv locale declaration whose parameter contains the rejected asterisk.
Except for the already allowed Include, no other active wildcard line was found. This is current
saved-input evidence, not proof of the historical 05b trigger or complete modified-parser acceptance.
The original approved grammar rejects that case; changing it requires this narrow amendment,
not an inference from legal OpenSSH syntax or the completed diagnostic capture.

The approved amendment only allows the main file's single exact ordered locale pair under the specified
whitespace and token rules, with all other grammar and effective-policy checks retained.
Owner B is retained verbatim in [the locale grammar decision](docs/governance/Q2_CORE_SSHD_LOCALE_GRAMMAR_OWNER_DECISION.md),
event `LH-Q2-CORE-SSHD-LOCALE-GRAMMAR-CLOSURE-20261005-01`. This independent bookkeeping-only C
contains only the exact decision and closure registration, no source, test, prototype, configuration,
release digest or field action. The three A documents and historical OPEN registration remain unchanged.
New D must descend from C; do not squash closure with implementation. G1–G3 implement the exception,
run targeted synthetic tests, freeze D and perform one new-version local parse of the saved complete
three-file snapshot, at most 5s. At C that new-version private parse is NOT_RUN; failure does not permit
automatic replay or altered input. Unaffected CLOSED scopes and their historical bytes remain unchanged.
The three old core requests and diagnostic request remain consumed, with full commitments and
UNKNOWN states retained; this scope authorizes no new marker, SSH/carrier, collection, batch,
configuration change, cleanup or H01/Q4/H11. R, Owner-only authority, no exceptions, side-work pause
and production E3 restriction remain unchanged.

The subsequent [locale implementation and offline review](docs/a2-execution/Q2_CORE_SSHD_LOCALE_GRAMMAR_REVIEW_20261005.md)
records D `d0c8749e47647264c14c406cd85c8c68006689a0`, directly descending from independent C
`86c5779f306d24756a8be383846e55afc0708b8b`. Targeted tests returned 359 passed / 2 skipped;
exact D CI completed with 3/3 successful jobs. After identity and input-digest checks, the single
authorized new-version parse of the complete saved three-file snapshot returned
`SOURCE_GRAMMAR_ACCEPTED` in 139.679 ms, within 5s. Offline G1–G3 are complete; do not replay that
private parse or the consumed capture. This proves only saved-snapshot source grammar compatibility,
not current effective policy, environmental safety, historical business execution or H01/Q4/H11.
No new marker, SSH request, field helper, package release or business task was issued. Future field
acceptance still requires a separate accurate Owner decision; historical UNKNOWN, full commitments,
paused side work and production `E3_SUPERVISION_UNVERIFIED` remain unchanged.

### Post-locale single core acceptance

Scope `LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1` is **CLOSED for L1–L3 only**.
Exact three-document A is `a243362d473891469b012a0ab8c3bd221794aa50`, tree
`179045d0c3bcf9bf6c154c191068c96c379fe13e`; the [baseline and requested decision](docs/governance/Q2_CORE_POST_LOCALE_ACCEPTANCE_BASELINE.md)
pin its [requirements](docs/a2-execution/q2-core-post-locale-acceptance/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-post-locale-acceptance/ARCHITECTURE.md) and
[implementation plan](docs/a2-execution/q2-core-post-locale-acceptance/IMPLEMENTATION_PLAN.md).
The earlier screenshot requested preparation only. Subsequent exact Owner B is retained verbatim in
[the Owner decision](docs/governance/Q2_CORE_POST_LOCALE_ACCEPTANCE_OWNER_DECISION.md), event
`LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-CLOSURE-20261005-01`. This independent bookkeeping-only C
records that decision before implementation D. A's three documents and historical OPEN baseline
remain byte-identical. C contains no implementation, tests, configuration, release digest or field action.
New D must descend from C; do not squash C with D.
The completed locale repair and its single saved-snapshot parse remain complete; do not repeat them.

The approval pins repair baseline `d0c8749e47647264c14c406cd85c8c68006689a0`, retains its grammar
and original runtime/wheel/harness, and authorizes one fixed `lhqcore-20261005c` only after independent
C, necessary triple-prior/diagnostic bindings, exact D validation and all original live gates.
All three consumed core UNKNOWNs and commitments remain. The consumed diagnostic's 4 MiB/8-inode
commitment and unproven independent remote/ancestor closure are explicit retained boundaries,
not core admission evidence. Required host availability is 260 MiB/72 inodes, not an exclusive reservation;
the four-core-carrier pre-quiescence bound is 4096 MiB/512 pids, excluding diagnostic/management ancestors
and unrelated host load. Six fixed SHOWs stay inside the new original per-batch budget and clocks.
At C the new marker/request is NOT_ISSUED. Accurate source/installed/CI, private double-build and
all original live gates remain necessary. Failure ends this scope: no retry, reconnect, supplemental
capture, cleanup, refund or automatic next batch. Existing code still binds two priors and the consumed
05b identity; it cannot be used as the new implementation. R/source integrity, Owner authority, no exceptions,
independent R→A→B→C→D, paused side work and production E3 remain unchanged.

The [post-locale implementation review](docs/a2-execution/Q2_CORE_POST_LOCALE_ACCEPTANCE_REVIEW_20261005.md)
records L1 D `29e2c6cfb3897a07edae8c0464d5b794fed3473c`, directly descending from independent C
`fe635c4885b8f31dd13901bef47e619480b2eda3`. Its triple-prior/diagnostic binding, 05c identities,
six SHOW slots and five-row capacity condition are implemented. Exact source, installed, CI and
private double-build passed before the separate digest-only release registration. Final release D
still requires all L2 checks again before conditional L3. No 05c marker/request has been issued at
this checkpoint; old UNKNOWNs, full commitments, no retries and production E3 remain unchanged.

The same review now records final release D `657b1bcd749cb4281b0193b2bc9430b0662faf98` and its
completed exact source, installed, private double-build and 3/3 CI checks. Only after all passed,
the single 05c marker/request was consumed. Valid HELLO/BIND and complete package transport returned
wait 3 and `CORE_CAP_INSUFFICIENT`; the live finalizer retained five capture files and
`STOP_AND_RETAIN` / `CORE_OUTPUT_MISSING`. No H01/Q4/H11 verdict or remote result exists; task and
business-result truth remain UNKNOWN. Issued-source order places this rejection at guest capacity
admission before installation/cases, without proving full old A/B quiescence or remote supervision.
The release allowlist is closed again. This scope has ended with retained failure: no retry,
reconnect, supplemental capture, cleanup, refund or next batch. Further field work needs separate
exact authority. The current host capacity check is not proof of guest capacity; the failing device
and shortfall were not returned. Preserve all old and new commitments, paused side work and production E3.

The subsequent [offline capacity accounting and diagnostic repair](docs/a2-execution/Q2_CORE_CAPACITY_DIAGNOSTIC_REVIEW_20261005.md)
revalidates the pinned capacity components and all 15 role-device grouping possibilities without observing
current guest capacity. The existing CLOSED development repair preserves the original admission predicate,
full commitments, first-failure stop and empty release allowlist. It adds bounded role/identity-digest,
available, historical, new, required and deficit details to the existing stderr rejection, without raw
paths/UUIDs, new I/O or schema changes. Scoped checks passed 788/2 skipped; 141 offline comparisons with
the issued 05c adder retained all acceptance/rejection results. The historical sandbox home-fixture failure
is retained. This repair neither resolves the guest shortfall nor recovers 05c's missing values. No new
marker/request, field collection, cleanup, refund or batch is authorized; production E3 and paused side work remain.

### Single core capacity observation

Scope `LH-Q2-CORE-CAPACITY-OBSERVATION-v1` is **CLOSED for O1–O3 only**.
Exact documentation A is `1ba20d196facc82cf74aea88e7df3d4fe31e0584`, tree
`2da72e01961f7ac1bf32edd521090dafe34b780a`. The [baseline and pending decision](docs/governance/Q2_CORE_CAPACITY_OBSERVATION_BASELINE.md)
pin the [requirements](docs/a2-execution/q2-core-capacity-observation/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-capacity-observation/ARCHITECTURE.md) and
[plan](docs/a2-execution/q2-core-capacity-observation/IMPLEMENTATION_PLAN.md).
This authorizes one fixed `lhqcap-20261006a` read-only observation of five original-plan parent devices
and available bytes/inodes, followed by a conditional comparison with the frozen 05c commitments.
It is not a fifth core attempt or complete admission. Original-plan bytes and issued mappings bind
the intended paths without reconstructing the full consumed package. Current historical placement,
quota enforcement and old-process closure remain UNVERIFIED.

The approval retains all four consumed core requests and the consumed sshd diagnostic, full commitments,
UNKNOWNs, existing installation and empty release allowlist. New capture is 4 MiB/8 inodes; the approved
current host floor is additive 264 MiB/80. It preserves diagnostic trust and remote-closure limits,
one marker/request, original clocks and no retry/reconnect/cleanup/refund. No H01/Q4/H11, runtime/configuration
change, next batch or production E3 is authorized; side work remains paused.
Exact Owner B is retained in [the Owner decision](docs/governance/Q2_CORE_CAPACITY_OBSERVATION_OWNER_DECISION.md),
event `LH-Q2-CORE-CAPACITY-OBSERVATION-CLOSURE-20261006-01`. This independent bookkeeping-only C
records CLOSED before new implementation D, without changing A's three documents or historical OPEN
baseline. C contains no source, tests, configuration, release digest or field action; D must descend
from C and must not be squashed with it. At C, the new marker/request is NOT_ISSUED. O1 implementation
and O2 exact verification must precede conditional O3. Unaffected CLOSED development remains.
R/source integrity, Owner mandate/authority, no exceptions and independent R→A→B→C→D order are unchanged.

The [capacity observation review](docs/a2-execution/Q2_CORE_CAPACITY_OBSERVATION_REVIEW_20261006.md)
records independent C `cd4dc50df1d62591548c54afa3e5405608aba20b` and implementation D
`dafa4360c1b62c59677236ab93da5af203fac240`. Exact local targeted verification passed 290 tests;
CI 37398006101 passed all three jobs before the single conditional O3. The one
`lhqcap-20261006a` marker and SSH request are now CONSUMED. Wait 0, both EOFs, validated five-role
output and four sealed local files establish CURRENT_CAPACITY_OBSERVATION, not core admission.
One local conditional comparison found journal available 229134336 B against the frozen 05c
threshold 299892736 B: a current 70758400 B shortfall. All sampled inode thresholds and other
sampled byte thresholds were sufficient for that conditional comparison. This does not reconstruct
05c's historical free values or verify historical placement/current quota/independent remote exit.
All UNKNOWNs and full commitments remain. O1–O3 are complete; no further marker, SSH, supplemental
collection, cleanup, refund or business attempt is authorized. H01/Q4/H11 were not executed.
Any capacity change or future business acceptance needs separate exact authority. Side work and
production `E3_SUPERVISION_UNVERIFIED` remain unchanged.

### Journal capacity growth

Scope `LH-Q2-CORE-JOURNAL-GROWTH-v1` is **CLOSED for J1–J3 only**.
Exact documentation A is `59948ec4fedb807a31cdbff77acc134e84414160`; the
[baseline and pending decision](docs/governance/Q2_CORE_JOURNAL_GROWTH_BASELINE.md) pin its
[requirements](docs/a2-execution/q2-core-journal-growth/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-journal-growth/ARCHITECTURE.md) and
[implementation plan](docs/a2-execution/q2-core-journal-growth/IMPLEMENTATION_PLAN.md).
Saved capacity evidence and local fixed configuration/header inspection identify a 256 MiB qcow2
journal disk with whole-device ext4. The fixed launcher has no QMP and disables its monitor;
current process/quiescence and full image integrity are not yet proven.
The proposal is one controlled guest power cycle with a verified offline backup, journal growth to
512 MiB, and at least 400 MiB ordinary available capacity. It proposes one marker and two fixed
maintenance SSH phases, not a retry of any consumed request.
It explicitly discloses guest interruption, volatile-state/boot changes, a new pidfile/serial-null
launch difference, non-exclusive capacity, full retained UNKNOWN obligations and non-atomic recovery.
Mutators are not forcibly killed to manufacture a hard deadline guarantee; incomplete exit is retained.
Exact Owner B is retained in [the Owner decision](docs/governance/Q2_CORE_JOURNAL_GROWTH_OWNER_DECISION.md),
event `LH-Q2-CORE-JOURNAL-GROWTH-CLOSURE-20261006-01`. This independent bookkeeping-only C
records closure before implementation D; it changes none of A's three document bytes or historical
OPEN labels and contains no source, tests, configuration or release digest. D must descend from C.
Only after J1 and all necessary J2 checks pass may the single conditional J3 perform maintenance.
At C, no new marker/request, shutdown, backup, image growth or restart has been issued.
The old boot equality check remains: a future core batch needs separate exact authority for the new
maintenance generation and management bindings. This scope does not authorize H01/Q4/H11 or production.
R, source integrity, Owner mandate/authority, no exceptions and independent R→A→B→C→D remain unchanged.
All old consumptions and paused side work remain. Do not squash C with implementation.

### Journal host read amendment

The original journal maintenance closure remains historical and valid for unaffected work.
Its first local J3 preflight at `50ec8f2dcb4bbee97934b22cb5f24d372ce19613` stopped at host boot
`O_NOATIME` open with EPERM before input/VM/writer admission, marker or SSH. See the
[local preflight record](docs/a2-execution/Q2_CORE_JOURNAL_GROWTH_LOCAL_PREFLIGHT_20261006.md).
Do not discard its partial window binding or automatically start a fresh window merely because
no marker was created. No maintenance shutdown, backup, growth or restart was issued.

Scope `LH-Q2-CORE-JOURNAL-HOST-READ-v1` is **CLOSED for R1–R3 only**.
Exact approved A is `2b4448c7b89d1910840f7aee2ae2b781f970e179`; its
[registration and exact decision request](docs/governance/Q2_CORE_JOURNAL_HOST_READ_BASELINE.md) bind the
[requirements](docs/a2-execution/q2-core-journal-host-read/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-journal-host-read/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-core-journal-host-read/IMPLEMENTATION_PLAN.md).
It authorizes qualified fixed host kernel reads, a bounded read-only root writer observer through
existing noninteractive administration, and one explicitly substituted preflight window.
Exact Owner B is retained in [the Owner decision](docs/governance/Q2_CORE_JOURNAL_HOST_READ_OWNER_DECISION.md),
event `LH-Q2-CORE-JOURNAL-HOST-READ-CLOSURE-20261006-01`. This separate bookkeeping-only
commit is C, contains no implementation and leaves all three A document bytes unchanged.
Implementation must descend from C. The one replacement window is conditional on complete R1/R2,
not authority to replay any consumed batch or refresh another failed window. At C it has not started.
Original maintenance limits, all historical UNKNOWN commitments, paused side work and production E3 remain.

The [host-read implementation and R2 record](docs/a2-execution/Q2_CORE_JOURNAL_HOST_READ_IMPLEMENTATION_20261006.md)
records independent C `b5414d0cfd505b220ba4b68a454202f245c77f6c` and implementation D
`8ce15f5786877e36c5983282b19a75d1439f6c47`, with 395 targeted tests passing on the ordinary host.
Its original saved-frame and publication blockers were subsequently resolved without changing
source: the one frame was explicitly tightened from 0664 to 0600 with the same device, inode, size
and expected digest; all eight static inputs then froze successfully. Exact published candidate
`c62319400c58e8ce067f0df150f8eb9ad0046719` has successful CI and a repeated 395-test host result.

The [follow-up field record](docs/a2-execution/Q2_CORE_JOURNAL_HOST_READ_FIELD_20261006.md) supersedes
the earlier readiness statement, not its retained failures. The single authorized replacement
preflight window was started once and stopped at its first root-writer checkpoint:
`sudo -n` reported that a password is required, so no root payload/report existed. Marker, SSH,
shutdown, backup, resize, restart and H01/Q4/H11 all remain zero. That replacement window may not
be reopened under the current A. The actual host has no proven NOPASSWD admission for the approved
fixed observer argv; guest cloud-init grants do not establish host authority. Any new privileged
host carrier, sudo policy/configuration change, observer invocation change or further window is a
material change requiring a new exact review and Owner closure. Do not probe sudo, retry the
observer, change host configuration or start maintenance under this closure.

### Journal terminal authentication amendment

Scope `LH-Q2-CORE-JOURNAL-TERMINAL-AUTH-v1` is **CLOSED for T1–T3 only** at exact A
`2b236865dc0a89e475c4021cac44d7193f252f67`. Its
[baseline registration](docs/governance/Q2_CORE_JOURNAL_TERMINAL_AUTH_BASELINE.md) pins the
[requirements](docs/a2-execution/q2-core-journal-terminal-auth/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-journal-terminal-auth/ARCHITECTURE.md), and
[implementation plan](docs/a2-execution/q2-core-journal-terminal-auth/IMPLEMENTATION_PLAN.md).
Their historical OPEN labels and exact bytes remain unchanged. R, direct source/integrity,
Owner-only authority, mandate, no exceptions and the material-change rule remain unchanged.

Exact Owner B is retained in
[the Owner decision](docs/governance/Q2_CORE_JOURNAL_TERMINAL_AUTH_OWNER_DECISION.md), event
`LH-Q2-CORE-JOURNAL-TERMINAL-AUTH-CLOSURE-20261006-01`. This independent bookkeeping-only C
records CLOSED before implementation D and contains no source, tests, executable prototype,
dependency, configuration, release digest or field action. A and the retained failed-window record
were joined without rewriting either history; D must descend from C and must not be squashed with it.

The amendment allows only the Owner in an existing real local foreground terminal to authenticate
the fixed read-only writer sudo call, without `-n`, and one new replacement preflight window.
It does not grant or install host privilege: sudoers, accounts, capabilities, services and helpers
must not change. Passwords must remain solely between the Owner and sudo's controlling terminal;
Codex, program inputs, environment, files, logs, pipes and askpass must not receive them. No `-S`,
`-A`, sudo-v, separate sudo probe, authentication warming or noninteractive-to-interactive fallback
is allowed. Missing TTY, permission, timely authentication or any original check remains BLOCKED.

T1 implementation and T2 exact verification/CI must complete before T3. T3 is at most one new
900s/780s dual-clock window under the original session and inputs. Every writer checkpoint remains
one call within 15s and the original maximum of eight; authentication time is included. Original
budgets and cumulative maxima remain one marker, two maintenance SSH requests, one normal shutdown,
backup, image growth, VM start and ext4 growth. Failure stops without retry, reconnect, supplemental
capture, forced shutdown, rollback or cleanup. H01/Q4/H11, namespace/watchdog and production
`E3_SUPERVISION_UNVERIFIED` remain outside this closure.

The [terminal-auth field record](docs/a2-execution/Q2_CORE_JOURNAL_TERMINAL_AUTH_FIELD_20261006.md)
now records the one authorized replacement preflight. Exact candidate
`202c70a15c0e52940d8544c3ae3c41e0b57ebaec` reached writer checkpoint 1 and returned exit 3 with
`GROWTH_WRITER_FAILED`; marker creation was false and SSH/transport, maintenance mutators and
H01/Q4/H11 all remained zero. The window is consumed and closed. The candidate's parent observer
collapsed every nonzero sudo/writer child exit without retaining whether a valid bounded child failure
report was present, so the exact lower-layer reason and root-payload execution remain UNKNOWN and must
not be inferred from the password prompt or possible source failure set. A later local-only parse of
the already retained diagnostic added stdout 648 bytes with SHA-256
`a56d810d1be3a13e21fe33892f43f407b0530da561836609780a258008944e74` and empty stderr; it did not
make another call. Because no stdout body was retained, these stream facts do not establish its schema,
request, reason or root-payload execution. Follow-up source repair
`ac08b519f741b301f37959808749cb9755359123` preserves a valid future child's exact bounded failure
reason and rejects absent/malformed failure reports; it passed 401 targeted host tests, but neither
changes this result nor refunds or authorizes another field action. Exact `ac08b51` CI run
`37445246001` completed successfully on Linux and Windows. No sudo/writer probe, retry,
reconnect, supplemental capture, cleanup, marker, SSH or maintenance is permitted under this closure.
A new exact A, Owner decision and independent C are required before any further affected host window.

### Journal diagnostic resume amendment

Scope `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v1` is **CLOSED for DR1–DR2 only** at exact A
`ef46ac169fd9084875cb5c5148a9c4985ace680c`. The
[baseline registration](docs/governance/Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_BASELINE.md) links the
[requirements](docs/a2-execution/q2-core-journal-diagnostic-resume/REQUIREMENTS.md),
[architecture](docs/a2-execution/q2-core-journal-diagnostic-resume/ARCHITECTURE.md), and
[plan](docs/a2-execution/q2-core-journal-diagnostic-resume/IMPLEMENTATION_PLAN.md).
Their historical OPEN labels and exact bytes remain unchanged. R, direct source/integrity,
Owner-only authority, mandate, no exceptions and the material-change rule remain unchanged.

Exact Owner B is retained in
[the Owner decision](docs/governance/Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_OWNER_DECISION.md), event
`LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-CLOSURE-20261006-01`. This independent bookkeeping-only C
records CLOSED before new implementation and contains no source, tests, executable prototype,
dependency, configuration, release digest or field action. D must descend from C and must not be
squashed with it.

The closure permits only one further replacement preflight window after the diagnostic repair is
verified, published and bound to an exact execution candidate descending from C. All prior windows
remain consumed; the prior writer cause and root-payload execution remain UNKNOWN.
The [diagnostic repair review](docs/a2-execution/Q2_CORE_JOURNAL_WRITER_DIAGNOSTICS_REVIEW_20261006.md)
records source repair `aba18e33f79295f3df1964606e389297d1a8a26a`, 428 local tests passed and 3 skipped,
and exact CI `37450280680` completed successfully on all three jobs. This is not field admission.
DR1 must now bind exact A/B/C, the existing repair, original inputs, payload and argv, run affected
verification and freeze the final candidate. Only after every DR1 gate passes may the Owner use the
existing real local foreground terminal for the one DR2 preflight. The original authentication,
checks, 15s/900s/780s, budgets and cumulative maintenance limits remain unchanged. No privilege,
helper, probe, retry, reconnect, supplemental capture, cleanup or automatic rollback is added.
Only a fully passing preflight may continue the already authorized journal maintenance in the same
window. H01/Q4/H11, new-boot core adoption, namespace/watchdog, production E3 and side work remain
outside this closure. Do not change prior approval records.

The [DR1 candidate review](docs/a2-execution/Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_REVIEW_20261006.md)
records implementation D `deab8acdabf0d35294f55fa87f2bc86d542fdf2e`, the direct child of independent
C `65026c8c7722bc487c317d392b50b017a7350dee`. It adds exact resume A/C ancestry/document checks
and manifest binding while retaining original approvals and all execution contracts. Native scoped
verification passed 325 tests with no skips; the static symlink refusal remains recorded separately.
Exact D CI run `37458930058` completed successfully on classify-change, Linux and Windows, including
independent installed verification, without a rerun. Eight original static inputs match the earlier
aggregate binding. These checks created no window and invoked no field writer, sudo or SSH. An isolated
source worktree retains exact D for the Owner's real-terminal handoff; later evidence commits do not
change its candidate identity. DR1 is complete; this is not original-host admission or maintenance acceptance.
DR2 remains NOT_STARTED until an actual original-terminal invocation proves otherwise. Current VM,
writer, tool and budget admission must still pass inside the sole authorized window. Do not infer
maintenance success, prior-writer root cause or permission to repeat any failure from DR1 results.

### Continuing constraints

- Repository formation also follows Owner-mandated Provisional [RFS-1.0 at the same fixed source commit](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/principles/repository-formation-standard-v1.0.md) and its Established module-boundary principle. The current formation assessment is in FORMATION_AND_MIGRATION.md; a Public shell does not close formation, publication or Authority admission.
- Preserve source provenance and historical evidence; do not copy private history or raw machine evidence into the Public repository.
- Existing Task v1 remains limited to the eight documented actions. The separately CLOSED E1–E3 scope above authorizes isolated implementation of the new job protocol; it does not extend Task v1 or authorize live deployment. A model, adapter, task, tool capability or test PASS grants no extra authority.
- Keep user/node identity, repositories, mailbox, executable paths and credentials out of source defaults. Configuration admission must retain allowlists and fail-closed checks.
- Preserve existing environments and the active deployment. S1 uses new isolated directories and synthetic fixtures; it does not submit live tasks or switch a service.
- Record real command outcomes, versions, commit and artifact digests. Never convert SKIP, unsupported, timeout or incomplete evidence into PASS.
- Source facts that contradict the plan trigger review and an explicit update; they do not silently expand the approved scope.

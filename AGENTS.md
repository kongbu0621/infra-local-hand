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

### Continuing constraints

- Repository formation also follows Owner-mandated Provisional [RFS-1.0 at the same fixed source commit](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/principles/repository-formation-standard-v1.0.md) and its Established module-boundary principle. The current formation assessment is in FORMATION_AND_MIGRATION.md; a Public shell does not close formation, publication or Authority admission.
- Preserve source provenance and historical evidence; do not copy private history or raw machine evidence into the Public repository.
- Existing Task v1 remains limited to the eight documented actions. The separately CLOSED E1–E3 scope above authorizes isolated implementation of the new job protocol; it does not extend Task v1 or authorize live deployment. A model, adapter, task, tool capability or test PASS grants no extra authority.
- Keep user/node identity, repositories, mailbox, executable paths and credentials out of source defaults. Configuration admission must retain allowlists and fail-closed checks.
- Preserve existing environments and the active deployment. S1 uses new isolated directories and synthetic fixtures; it does not submit live tasks or switch a service.
- Record real command outcomes, versions, commit and artifact digests. Never convert SKIP, unsupported, timeout or incomplete evidence into PASS.
- Source facts that contradict the plan trigger review and an explicit update; they do not silently expand the approved scope.

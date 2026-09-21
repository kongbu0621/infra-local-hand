# Execution guidance

## Publication and GX10 handoff

Owner approved public disclosure of exact original candidate `b763bd6714721d22278086db559fa3f6684aad7b` and its governance excerpt, with no license added and no SOP history or raw machine evidence. See [PUBLICATION_OWNER_DECISION.md](docs/governance/PUBLICATION_OWNER_DECISION.md). After the authorized GX10 S1 verification found and repaired defects, Owner separately directed repaired candidate `1e2f9dce87e57c34a35fe3a6a75a8c784181ba83` to be committed and pushed directly to `main`; see [Q6_MAIN_PUBLICATION_OWNER_DECISION.md](docs/governance/Q6_MAIN_PUBLICATION_OWNER_DECISION.md). These are disclosure decisions, not replacements for the S1 closure below. Equivalence/adoption of the public governance excerpt remains pending. Windows is deferred. Owner subsequently directed “全部提交推送。 你直接继续修复”; the follow-up S1 repair/publication record and exact verified candidate are in [S1_FOLLOWUP_REVIEW.md](docs/S1_FOLLOWUP_REVIEW.md). This does not expand S1 closure or authorize live cutover. The subsequent Owner-directed chain-only review is recorded in [S1_CONFLICT_CHAIN_REVIEW.md](docs/S1_CONFLICT_CHAIN_REVIEW.md); its exact candidate and scoped validation are separate from earlier full-suite results. The earlier delivery/receipt recovery repair and chain-only evidence are recorded in [S1_DELIVERY_RECOVERY_REVIEW.md](docs/S1_DELIVERY_RECOVERY_REVIEW.md). The subsequent process-lifetime and bounded-capture repair is recorded in [S1_PROCESS_LIFETIME_REVIEW.md](docs/S1_PROCESS_LIFETIME_REVIEW.md), with targeted source and installed-chain evidence. The subsequent Result size and durable recovery repair is recorded in [S1_RESULT_BUDGET_REVIEW.md](docs/S1_RESULT_BUDGET_REVIEW.md), with exact source and installed-chain evidence.

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
- Gate state: **CLOSED for S1 only**.
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

- Repository formation also follows Owner-mandated Provisional [RFS-1.0 at the same fixed source commit](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/principles/repository-formation-standard-v1.0.md) and its Established module-boundary principle. The current formation assessment is in FORMATION_AND_MIGRATION.md; a Public shell does not close formation, publication or Authority admission.
- Preserve source provenance and historical evidence; do not copy private history or raw machine evidence into the Public repository.
- Implement only the eight documented actions. A model, adapter, task, tool capability or test PASS grants no extra authority.
- Keep user/node identity, repositories, mailbox, executable paths and credentials out of source defaults. Configuration admission must retain allowlists and fail-closed checks.
- Preserve existing environments and the active deployment. S1 uses new isolated directories and synthetic fixtures; it does not submit live tasks or switch a service.
- Record real command outcomes, versions, commit and artifact digests. Never convert SKIP, unsupported, timeout or incomplete evidence into PASS.
- Source facts that contradict the plan trigger review and an explicit update; they do not silently expand the approved scope.

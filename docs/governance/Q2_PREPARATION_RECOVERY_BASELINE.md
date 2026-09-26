# Q2 preparation recovery — proposed baseline

2026-09-26. Authority: Owner. Status: **PROPOSED / OPEN**.

- Scope: `LH-Q2-PREP-RECOVERY-v1`.
- Gate rule R: `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`, with the same readable direct source, integrity and adoption recorded in root `AGENTS.md`.
- Public documentation baseline A: `72c06ec68d370333f5ffb1079023917828b3e681`.
- A tree: `2b38a8db7716335a9eec507add3bb8f6705e59de`.
- Local reviewed byte-equivalent commit: `bd158887624f661045caed420da573810737e89f`.
- No Owner closure B or CLOSED C exists for this scope. This registration is documentation only.

| Authoritative document at A | SHA-256 |
| --- | --- |
| [REQUIREMENTS](../a2-execution/q2-preparation-recovery/REQUIREMENTS.md) | `01ebc3b7e451e9281c7aa102f1c615d2f8ce6dda8dec01aa82e8a0f6b2a24488` |
| [ARCHITECTURE](../a2-execution/q2-preparation-recovery/ARCHITECTURE.md) | `4a264b857d7bf008c9f8232980c589a56a9707849cf1da65726f8b5017919edb` |
| [IMPLEMENTATION_PLAN](../a2-execution/q2-preparation-recovery/IMPLEMENTATION_PLAN.md) | `2966684e611568d0271c82a34a5dbd7d58fed811dd766b8a98daa8b9668f2b4e` |

## One concrete change

The already approved preparation failed after its primary group was created.
The useradd failure had a real exit 3 and both EOFs; its error was an unsupported
configuration argument. The old time window has ended. The original architecture
allows recovery only with original intent, objects, undelivered-step proof and
no extra budget; the original implementation plan prohibits extending the total
deadline. A new bounded recovery window therefore needs an explicit decision.

The proposal permits one management/capture window of at most **300 seconds**,
containing a guest service of at most 270 seconds, stop at most 3 seconds,
attestation/preparation/assembly at most 140 seconds from guest entry, and the
never-issued original Q2 owner at its unchanged 120-second limit. Exact remaining
deadlines, stop and EOF margins must admit the first run before it is issued.

Only the exact known partial state is accepted: the original group succeeded,
the account is absent after the precise configuration parsing failure, and all
later planned steps and original runtime issuance are proven undelivered.
The batch then performs the corrected account command, the original missing
preparation and assembly, and the original first supervised run. No group
recreation, previously consumed step replay, second recovery, changed installation
candidate, quota increase, package/mount change or Q1 cleanup is included.

The same preparation ID, old failure bytes and plan remain. Recovery has separate
append-only evidence. Existing and new files share the original capacity ceilings.
Approval covers the complete bounded batch without per-item approvals; it does
not assert Q2/Q3 acceptance or production support.

## Completed repair and review

The independent account/diagnostic repair is public commit
`56b6ca430e65acffba927aae89d50b42a2903b0f`, local byte-equivalent
`11dc4d3c3cd191bf7d7ba0397678bee85984e0e5`, tree
`8631223c9e37b2e162b6a88e43b4edda9a7a43cb`.
Its [verification report](../a2-execution/Q2_PREPARATION_ACCOUNT_REPAIR_VERIFICATION.md)
records 72 passed and 1 environment skip, plus the real-host verification limit.
The exact original approved preparation documents were checked against their
baseline bytes and SHA-256 digests and remain unchanged.

Independent documentation review found the nested limits and no-replay boundaries
consistent. The review's timing clarification is included at A: the 140 seconds
starts before the first attestation read, so attestation does not escape its budget.
There is no newly implemented recovery source, test, executable prototype or runtime configuration.

After Owner explicitly approves R/A and this scope, record a separate CLOSED
commit C containing the exact decision before implementing recovery D.

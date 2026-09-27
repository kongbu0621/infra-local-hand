# Q2 CPU quota startup retry — proposed baseline

2026-09-27. Authority: Owner. Status: **PROPOSED / OPEN**.

- Scope: `LH-Q2-CPUQUOTA-RETRY-v1`.
- Gate rule R: `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`, with the same readable direct source, integrity, mandate and change rules recorded in root `AGENTS.md`.
- Public documentation baseline A: `d8e49617efecae199b0874f183530794f8c36e6a`.
- A tree: `341be3060bbba88c82744a19805d9d53ed65a1a9`.
- Local byte-equivalent documentation commit: `4464871390c4bebeda9e7e5d3c7673f7f10414b2`.
- No Owner closure B or independent CLOSED C exists. This registration introduces no retry implementation.

| Authoritative document at A | SHA-256 |
| --- | --- |
| [REQUIREMENTS](../a2-execution/q2-cpuquota-retry/REQUIREMENTS.md) | `05df680a26c8c0f23898b89ba3a4b0031491e4ba7ec2d82579a9680240db2c3b` |
| [ARCHITECTURE](../a2-execution/q2-cpuquota-retry/ARCHITECTURE.md) | `3eff3e61fcf0d75beb705799dcbce54f1598bc7e2e7f88994cea7877ab9cc55d` |
| [IMPLEMENTATION_PLAN](../a2-execution/q2-cpuquota-retry/IMPLEMENTATION_PLAN.md) | `cd780d21c3a86a69586191c2c222ccc10d818a22712f3cf588dea7bf03d81c55` |

## Concrete change requiring a decision

The approved recovery at A `72c06ec68d370333f5ffb1079023917828b3e681`
completed fixture preparation and issued its original owner handoff. The inner
systemd-run client then exited 1 because `CPUQuota=100.0000%` was rejected.
Both inner output EOFs were captured; no child service InvocationID was created.
The retained owner remains INCOMPLETE. A failed parser does not undo issuance.

The original recovery requirements R05/R06/R07 freeze the candidate, permit only
the never-issued first run and forbid automatic retries or replacement IDs.
Its architecture also prohibits deleting/recreating an issued owner/handoff.
The recovery window has expired. A repaired candidate and another real execution
therefore require this explicit new scope; the prior batch approval is not being
asked again for unaffected source repairs or individual preparation steps.

## Exact proposed batch

One new at-most-300-second management/capture window, guest service at most 270
seconds plus its bounded stop, attestation/installation/assembly at most 140
seconds from guest entry, and owner at most 120 seconds. Actual nested deadlines
must reserve stop, EOF, fsync and seal time before issuing anything.

Install candidate `9a556322183f0fa80d4edeada4b03c74a26524a5` into an independent
protected location; create new runtime policy/ledger, journal, declarations,
control/session and evidence. Record fresh identities and explicit links to the
old failed attempt. Reuse the exact ordinary account/configuration and seven
prepared quota roots only after attesting that no operation, grant or payload
consumed them. Actual SQLite and root-member checks remain guest admission work;
the received diagnostic package does not contain those complete snapshots.

Accurately configured normal inactive manager/slice instances may each be started
once, with current identities recorded. Existing active instances are not
restarted, old configuration is not overwritten, quota limits are not reset,
and no new account/project is created. Unknown delivery, consumption, unrelated
work or drift blocks the batch. All old candidates, reservations, ledgers,
deadlines, payloads and verdicts remain intact.

Installation/state/journal/capture retain their original **combined old-and-new**
space ceilings of 256/32/64/64 MiB. No cleanup, refund or storage expansion is
included. The new management CPU ceiling is 300 seconds, plus at most 400 seconds
for the independent runtime domains; this is an explicit additional authorization,
not a refresh of historical CPU or time budgets. Memory/PID peaks and per-role
limits remain separately admitted. The fixed host.inspect three-stage attempt
and complete exit/EOF collection run once; any failure is retained without retry.

## Completed source repair and review

The independent repair is public commit
`9a556322183f0fa80d4edeada4b03c74a26524a5`, local same-tree commit
`5c4c07a3cea58db2660be9f1f9322ddbafdfefbe`, tree
`0687d7cd8eaf6a901d565a60b99042827437354c`.
Its [verification record](../a2-execution/Q2_CPU_QUOTA_REPAIR_VERIFICATION.md)
documents 297 passing tests, one unavailable real-systemd integration skip,
the actual systemd 255 percentage parser, legacy/new sealed evidence negatives,
and an exact public-commit wheel build with 53 verified payload files.
Wheel SHA-256 is `0924ac531f3f710cd39838318e8d72b09a4261589df70cf3f650be62a8c8ebcb`.

An independent review found no blocking conflict among the three proposal
documents. SQLite system objects and store-parent/root distinctions are explicit
to avoid mistaking initialized state for consumption. The old approved documents
remain unchanged. No retry tool, test, executable prototype or runtime configuration
has been added before closure.

Owner may approve this exact R/A and the complete scope once, without per-item
inquiries. Record that accurate B in a separate CLOSED C before implementing D.
This decision would not accept Q3, production, GX10 or E4–E6, or change old results.

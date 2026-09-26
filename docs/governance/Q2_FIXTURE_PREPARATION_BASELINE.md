# Q2 fixture preparation — proposed baseline

2026-09-26. Authority: Owner. Status: **PROPOSED / OPEN**.

- Scope: `LH-Q2-FIXTURE-PREP-v1`.
- Gate rule R: `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`.
- Public documentation baseline A: `2ea59b8d1b262632bae5636938107ef2f002a59b`.
- A tree: `dcb3b7163afc4187b9eb5b04d8d73d14a2a1f5e5`.
- Local reviewed byte-equivalent commit: `e912b3eaa7bce19e27aa167c281ccc8126d6c6f8`.
- Root AGENTS retains the direct pinned rule, integrity, mandate, Owner authority and no exceptions.
- No Owner closure B exists for this new scope. This is a proposal record, not CLOSED C or implementation D.

| Authoritative document at A | SHA-256 |
| --- | --- |
| [REQUIREMENTS](../a2-execution/q2-fixture-preparation/REQUIREMENTS.md) | `1066c9cf35995bd7da7a568769ad78a40f1fe9304bfc1c614448a0c73ff8644e` |
| [ARCHITECTURE](../a2-execution/q2-fixture-preparation/ARCHITECTURE.md) | `4290aafd1fc54ccf581dd9f6890f1c9d82dccfd455172b6370eb7213f8cdd684` |
| [IMPLEMENTATION_PLAN](../a2-execution/q2-fixture-preparation/IMPLEMENTATION_PLAN.md) | `9e09666bd9de93b8ef26dac1ac7d8235030e2c9804d9de3ba1608003751b63e6` |

The concrete proposal is limited to the already supplied isolated Q1 guest:
one new ordinary account/group and instance-specific user manager delegation,
two new three-root slots plus one independent evidence store (seven new project
domains), bounded new installation/state/journal/capture directories, and one
original independently supervised test-only Q2 handoff with same-MainPID binding.
Per-domain limits are at most 64 MiB/4096 inodes; all seven total at most
448 MiB/28672 inodes. Installation/staging is bounded by 256 MiB, ordinary state
and preparation logs by 32 MiB, management journal by 64 MiB, and management
capture/declarations by 64 MiB. These are ceilings, not manufactured host inputs
or a finding of available capacity. Actual values must be pinned and admitted.

No formatting, mount changes, package upgrades, Q1 replay/reuse or GX10 changes
are included. Preparation is not Q2/Q3 acceptance or production support.
Existing closed-scope code repairs were completed independently of this proposal.

A single Owner decision may approve the three exact document versions at R/A,
close only this scope, and authorize its bounded preparation and one original
handoff. After that decision, record an independent bookkeeping-only CLOSED
commit C before creating new preparation source/tests/configuration D. No
per-directory approval is proposed within the approved object/count/ceiling
boundaries; material scope changes still follow the root change rule.

# Q2 CPUQuota retry implementation verification

This records implementation and offline verification after the Owner closed
`LH-Q2-CPUQUOTA-RETRY-v1`. It does not record a successful guest retry or Q2
acceptance.

## Authority and immutable inputs

- Approved A: `d8e49617efecae199b0874f183530794f8c36e6a`.
- Independent CLOSED C: `b0964e7adb50a49064f522fedbb1d46c3af08911`.
- C tree: `b435ba1d366d473ef5e1928e2a3f0acdc81a0001`.
- Runtime candidate: `9a556322183f0fa80d4edeada4b03c74a26524a5`.
- Runtime tree: `0687d7cd8eaf6a901d565a60b99042827437354c`.
- Wheel SHA256: `0924ac531f3f710cd39838318e8d72b09a4261589df70cf3f650be62a8c8ebcb`.

The three approved baseline documents retain their original bytes. New
orchestration descends from C and is pinned separately from the frozen runtime.
Private plans, host paths and raw machine evidence are excluded from this repository.

## Implementation

The six `tests/e3_host/q2_retry*.py` modules provide strict plan binding,
historical-failure attestation, create-only installation/state, fixed-window
transport, orchestration and read-only evidence collection. The in-memory
loader validates the complete orchestration bundle before executing unchanged
helper bytes; after staging, a fresh interpreter runs the pinned disk entry.
It does not modify the runtime candidate.

The new attempt preserves the issued historical failure and all previous
reservations, ledgers, payloads and verdicts. Seven prepared quota roots are
reused only after their original identity, empty membership and unused ledger
are established together. Matching inactive instances may start once; failed,
changed or working instances are rejected. No quota reset or cleanup is added.

One host deadline starts before the first probe. Guest preparation, owner,
stop, collection and final writes consume that same 300-second window.
Both clocks are checked, all external captures share a 2 MiB budget, and old
and new storage commitments remain cumulative. Complete EOF with nonzero
exit records a captured failure; it is not mislabeled as lost capture.
Read-only collection cannot replace missing original EOF or an absent seal.

## Verification performed

| Check | Actual result |
| --- | --- |
| Q2 source and CPUQuota regression (`test_e3_quota_q2_*.py`, `test_e3_cpu_quota_serialization.py`) | 471 passed, 2 environment skips |
| Private delivery integration | 7 passed; exact source/wheel archive, committed helper bytes, corruption rejection, inert default, failure preservation, single delivery, bounded collector and replay rejection |
| Final bounded failure-diagnostic change | 10 driver tests passed; stage and bounded errno/path retained without reading file contents |
| Frozen candidate Linux CI | 1640 passed, 12 skipped; installed-wheel verification PASS, 94 checks and 292 commands |
| Strict local installer with the frozen candidate | 120 successful commands through source verification, copied venv, wheel installation, native compilation and ABI checks; ordinary-UID probe blocked by the executor mapping only UID/GID 0 |
| Historical uploaded evidence | Exact startup error/argv and retained seven-root pins checked; live ledger emptiness and root membership remain guest preconditions |

Candidate CI run [36288350559](https://github.com/kongbu0621/infra-local-hand/actions/runs/36288350559)
failed only Windows test collection: the new CPUQuota test imported Linux
`fcntl` before a platform guard. This implementation adds a test-only Linux
guard and guards Linux-specific retry tests. Simulated Windows entry verifies
the guards; an actual Windows CI result is not claimed here. The approved
runtime candidate is unchanged.

The actual private identity/path recipe also passed a modeled contract bind
with archived original identities and limits. Because the original plan file
is only on the guest, that check substituted its digest in the model; live
admission still requires the exact original plan bytes and pinned digest.

The private entry verifies its committed helper tree and cached candidate
before packaging. It creates one result archive containing original streams,
transport records, read-only diagnostics and a completion record for the
fsynced core evidence. The final upload archive's completion time is checked
after its durable write and reported by the process exit and terminal output;
it is not retrospectively substituted for guest execution evidence.

## Remaining live step

The cloud executor has no connection to the original host's SSH wrapper.
The delivered private entry must run once on that host. Its preflight checks
the actual ordinary account, service configuration, preserved inputs,
unconsumed roots and available capacity. Code verification alone does not
establish those facts. Guest failure retains the attempt and produces a
structured result; the entry does not replay automatically.

Status: **implementation verified / guest execution pending**.
`q2_accepted=false`, `q3_accepted=false`, `production_supported=false`.

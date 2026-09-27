# Q2 startup retry: verified tooling, unissued batch

2026-09-27. The Owner-approved new batch is **NOT ISSUED**. No connection to
the original guest, new installation, owner request or management window was
started during this work. Its one execution authorization remains unconsumed.
The new tooling is published; complete historical admission and execution remain
blocked. The two previous issued attempts retain their original INCOMPLETE results.

## Exact authority and source

| Identity | Retained value |
| --- | --- |
| Scope | `LH-Q2-SUPERVISOR-STARTUP-RETRY-v1` |
| Rule R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| Approved three-document A | `47b351b2b943bf1d6f1c71cfeb031157a2eb70cc` |
| Owner B | Exact reply “批准新批次”, retained with the preceding exact scope request in [the decision record](../governance/Q2_SUPERVISOR_STARTUP_RETRY_OWNER_DECISION.md) |
| Independent closure C | `d4a925c883672fadc7d1b10a8dfe58df18b922cd` |
| Tooling implementation D | `78589e6871cdf5eba72008ee2b27a350a0dfdc03` |
| D tree | `a894d0679cd23995a5b3cfd93168d4c05355fc68` |
| Frozen runtime | `b49d3df3d1e76813faf08e59ab4975e25279c2fc` |
| Frozen runtime tree | `2d957ccf1d9cbdf5e538189c6b68d56f34590a42` |
| Frozen wheel SHA-256 | `c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b` |

C contains only closure bookkeeping. D is its direct child and adds seven
test-only orchestration modules and seven test modules. No old helper or frozen
runtime module is changed. The public Git commit object was reconstructed and
hash-checked locally, and the local index tree equals the public tree above.
A's requirements, architecture and implementation-plan SHA-256 values remain
respectively `fc6dd6b0c7b7081da61c0c200ea4ebbaf1e6baac4364b70e4f8927e6614c2139`,
`fc4ea078aab64f64ba59dc9f5247e4a91e4d1237ed56488014cb516ae7313773` and
`b3eff564624fae0c4d98bb10d5cd47a1372b0a445f3f4c3bae1f0e863e3b9f6b`.

## Implemented behavior

The new strict contract binds both historical failures, both unchanged ledgers,
the seven roots, ten historical reservation records, exact failed service
instances, fixed runtime and independently pinned orchestration. Missing raw
bytes, source pins, original instance identity or capacity causes refusal. It
does not infer an old instance from its current failed status.

Historical reads use protected noatime descriptors, including the existing
in-memory SQLite validator. The driver assembles independent create-only state
and repeats preservation checks before fresh execution of the frozen candidate.
Collection has a separate preservation path and does not reserve, install or
reissue. Complete raw collection cannot itself establish Q2 acceptance.

Host entry, preparation, subprocess capture, transport reporting and finalization
retain the original MONOTONIC and BOOTTIME bounds. Suspension cannot silently
extend the original window. The original 300-second management, 270-second guest,
140-second preparation, 120-second owner and 3-second stop ceilings remain.
The archive and every bounded metadata file are charged before staging effects;
partial staging is retained and cannot be replayed under the same identity.

Management output is one shared commitment across capture, declarations and
journal. Actual coverage is credited once. Each category checks its conditional
worst case against its original ceiling; those category bounds are not summed
as independent commitments. Physical capacity deduplicates the pool per device,
covers every possible destination device, and uses the minimum available space
among sequential samples of aliases for the same device.

## Verification and limits

| Check | Result |
| --- | --- |
| Seven new test modules together, Python 3.12.14 | **94 passed, zero skipped or failed**, 34.36 seconds reported by pytest |
| AST compilation, whitespace, approved-document hashes and publication tree | PASS |
| Independent reviews | Contract, backend, driver, bootstrap, host delivery, collector and draft reconciliation boundary reviewed |
| Historical private failure-record compatibility | Both retained failure groups pass their pure failure parsers; this is not complete backend admission |
| Native Linux CI | **PASS: 1845 passed, 13 explicit environment skips**; isolated installed acceptance 94 checks/292 commands; Plugin packaging and Linux bootstrap checks passed |
| Native Windows CI | **PASS: 386 passed, 739 explicit platform skips**; isolated installed acceptance 10 checks/10 commands; bootstrap, ACL, Local Service, exit propagation and junction checks passed |
| Exact-D workflow | [36298482316](https://github.com/kongbu0621/infra-local-hand/actions/runs/36298482316) |
| Full historical admission / actual guest execution | **Not performed; BLOCKED / NOT ISSUED** |

The joint suite includes actual temporary filesystem effects, a temporary SQLite
ledger and complete driver assembly under a strict synthetic contract. It also
checks incomplete captures, expiry after suspension, repeated entry, missing
provenance, changed identities, shared-pool/device accounting and the actual
320 MiB reservation rejection before state-creation calls. These controlled tests
do not establish live systemd, quota, original-guest preservation or Q2 acceptance.

The complete focused-test log SHA-256 is
`38ebd6d11b2bb9b06abafb10ef8137729c0664b264c5b0ebef5e5e6e8728b59b`.
Native CI builds its own D-stamped verification wheel. It does not replace the
separately frozen b49d runtime wheel, whose prior full source and isolated installed
verification are retained in [the runtime repair report](Q2_SUPERVISOR_STARTUP_REPAIR_VERIFICATION.md).

## Two independent execution blockers

The earlier proposal missed a retained installation obligation. Under approved
S02/S06, elapsed time, service termination or successful installation does not
release unused storage commitments.

| Retained installation obligation | Minimum committed capacity |
| --- | --- |
| Original installation, including its nested recovery reservation | 192 MiB, counted once |
| Subsequent independent CPUQuota retry installation | 64 MiB |
| Approved new startup installation/build peak | 64 MiB |
| Lower bound before additional staging and metadata | **320 MiB** |
| Unchanged installation ceiling | **256 MiB** |

This is commitment accounting, not a claim of 320 MiB actual disk use. Actual
bytes/inodes remain separately charged. The old obligations already fill the
entire ceiling. The new tooling correctly refuses this lower bound before
persistent mutation. The historical 8192/4096 installation inode reservations
were independently traced to pinned pre-installation code; 16384 is the original
total inode ceiling, not an extra reservation.

Separately, seven historical raw reservation files are absent from returned
local evidence, with six lacking independently anchored single-file digests.
Some may be recoverable by fully expanding and reproducing an already anchored
historical tree hash. The second staging tree has no usable historical anchor;
newly hashing current content cannot manufacture historical provenance. Original
preparation/recovery service instance identities also need their original retained
evidence. Private file paths and machine identities are in the delivered private
missing-input list, not this public repository.

No runnable READY private entry was generated. No old reservation was released,
no ceiling or capability was raised, and no old verdict was revised. Q2, Q3 and
production acceptance remain false; independent-stop and tree-seal proof for a
new actual run remain absent.

## Reviewable next work

The [reservation reconciliation proposal](q2-installation-reservation-reconciliation/REQUIREMENTS.md)
is **PROPOSED / Gate OPEN / BLOCKED ON HISTORICAL INPUTS**. It only considers
terminating unused future installation obligations of the two terminated attempts
through a new append-only record while retaining all actual data, all other
commitments, original ceilings, frozen runtime and this same single unissued batch.
No reconciliation algorithm, executable prototype or release configuration is
implemented or authorized.

First obtain the missing existing raw records and original instance evidence, or
valid historical tree-expansion proofs, and close the exact provenance and amount
inventory. Only then can a complete three-document amendment A, exact Owner B
and independent C authorize that changed accounting. This report does not ask
for immediate approval of an incomplete release proposal. Tooling P1 and the
reported P2 checks are delivered; private READY handoff and actual execution
remain blocked.

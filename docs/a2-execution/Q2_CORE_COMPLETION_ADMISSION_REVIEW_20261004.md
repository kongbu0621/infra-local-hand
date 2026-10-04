# Core completion adjustment: admission implementation checkpoint

This is a partial C1–C3 implementation record, not completed core acceptance or a
new execution authorization. The source was frozen after the independent CLOSED
record; the original single conditional F1 remains unissued by this work.

## Exact authority and source

- R: `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`; its direct pinned source was read again.
- Approved A: `851a1afe4e55196212aa6913e81e0722deed1032`, scope
  `LH-Q2-CORE-COMPLETION-ADJUSTMENT-v1`.
- Owner B: [retained exact decision](../governance/Q2_CORE_COMPLETION_ADJUSTMENT_OWNER_DECISION.md),
  event `LH-Q2-CORE-COMPLETION-ADJUSTMENT-CLOSURE-20261004-01`.
- Independent bookkeeping-only C: `c32799c03a32d81deec02f7492c1b71eb47b2b6d`, tree
  `1ccf7b10f65e43f5099c17c7c7fb7e9f5e5da77b`.
- First D: `53533accbf834d489c773d2a037c008059c90c4f`, tree
  `4207e1e5317f7b7f69818f3aba476dc85dc9cc44`; its direct parent is C.

C contains only the Owner record and AGENTS registration. D contains source and
tests separately. The three approved A documents, including their historical
OPEN labels, remain byte-identical. The new offline verifier checks this third
amendment's exact A/B/C pins and C→D ancestry in addition to the prior chains;
it passed against the actual D Git blobs. No source-lineage proof grants field release.

## Delivered code

The dispatcher now connects the current-guest admission collector to the existing
installation/preparation path. The retained development ancestor was used only
for selected admission/capacity definitions and tests, not restored wholesale.
Current installation guards, executable binding, quota readers and preparation
repairs remain in place.

Admission collects and checks policy/source predicates, resolved programs,
guest/boot/ordinary-account identity, existing managers/cgroups, filesystem and
quota identity, historical obligations, retained objects and new-object absence.
The approved static inputs cannot stand in for these observations. Collection is
at most once in an effects instance; failure does not set an admitted baseline.
Installation still requires that baseline before its first mutation.

Migration fixes include the current HELLO guest-boot key, the current quota-reader
interfaces, held executable execution for semantic helpers, cached held policy
ancestors, late-open closure, per-operation guards and bounded kernel reads with
actual procfs/sysfs/cgroup2 qualification. The original dual clocks are retained.
Repeated list-valued sshd output does not invalidate the five exact required
predicates; duplicate required predicates still fail. None of these checks was
run on a guest during this checkpoint.

The fixed 32-pool mapping now drives conservative per-device admission. Each
pool is reserved in full on every distinct output device, including SESSION and
case metadata ancestors on quota/journal/evidence devices. Same-device aliases
are deduplicated. The all-same-device logical admission remains 276 MiB / 16512;
the explicit four-device test requires 372 MiB / 31872. This duplication is
unspendable admission headroom, not a budget increase. Historical charges and
no-refund obligations remain separate and retained. The consumer rejects wrong
device mappings, wrong reserves and omitted required absence rows.

For C2, `_carrier_usage()` is a component collector for the original bound
carrier's `cpu.stat`, `memory.peak` and actual `pids.peak`, with identity,
membership and deadline checks. Missing `pids.peak` fails; neither current PID
count nor a configured limit replaces it. Its fixtures explicitly double kernel
views and do not prove guest support. This component is **not yet wired into
complete usage** and does not account for independently managed business units.

Only the dispatcher length cap changed. Actual field blobs at D are:

| Blob | Bytes / cap | SHA-256 |
| --- | ---: | --- |
| loader | 2160 / 8192 | `6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61` |
| bootstrap | 49102 / 49152 | `039fe87cc91a64c0327dc404e0ccf9728c32a1cc07e3e6fb11ed74c979f904f3` |
| dispatcher | 331928 / 524288 | `bc491ab9523cef7d1a247eac80d1c921451470fa8622bd9027be71eea7df4892` |

There is no fourth field module or compressed executable payload. The fixed
field runtime `4b6e4a7c403362358192086b88679e1326dcb2e1`, its wheel and projection
are unchanged. D is the delivery-source checkpoint, not a replacement runtime.

## Verification and retained limits

Core regressions passed **745 / 34 skipped**. After the final sshd parser repair,
admission/capacity/carrier-usage/freezer tests passed **129 / 2 skipped**.
The initial migration core run retained **9 failed / 702 passed / 34 skipped**:
one stale stub expectation and eight local-consumer context failures. The
consumer now binds to its original HELLO without requiring a dispatcher-private
context field; no identity or deadline check was disabled.

Exact-D complete source verification: **4656 passed / 125 skipped in 439.71 s**.
No test was deselected and skips were not promoted to acceptance.
The preceding unfrozen full run passed 4656 / 125 skipped but began before the
final parser edit; it is not substituted for exact-D verification.

An independent clean clone of exact D built and installed a test-only wheel,
then ran the existing installed verifier from outside that checkout:
**PASS, 94 checks / 292 commands**. Test wheel is 288725 bytes, SHA-256:
`9c285119777fa8ad07bb5943d524ce8c38d49c9647a538a4f5fe16007a032c44`.
This wheel does not replace the approved field wheel. The installed tests use
isolated local fixtures, not H01/Q4/H11 guest execution. Raw local test reports
and command logs are retained outside the repository; no raw machine evidence
was published. The source D is pushed to main;
[CI 37207259463](https://github.com/kongbu0621/infra-local-hand/actions/runs/37207259463)
was in progress when this record was prepared, not yet reported as PASS.

Retained local verification artifacts (not field evidence):

| Artifact locator under `/mnt/data1/tmp` | SHA-256 |
| --- | --- |
| `lh-core-completion-exact-source.6STeAW/source.xml` | `ee77e8d6660e01f4cf7a7be22936d96a4eecc483bfcea57c51d07fba505359d0` |
| `lh-core-completion-installed.3ro3NZ/acceptance/report.json` | `eb7d2b1ae218714ba5a7f5f0db5782c0f3a9dec59c253aed981a40761f4d4593` |
| `lh-core-completion-source.5kAFsc/source.xml` (unfrozen first run) | `663b62da6841034b60c147c579330be73623a5f37f2a63b33badd5a7b26cbe11` |

The installed report also indexes the 292 retained command logs in its sibling
`commands` directory. All these artifacts were locally readable at verification;
the repository retains their digests and exact source relation, not raw logs.

## Direct remaining work under the existing approval

1. Complete C2's 32-pool controlled-I/O ledger and metadata-only allocation
   observations at the exact approved boundaries. Wire existing create/write/
   fsync, installer and preparation adapters; keep quota setup ordering and
   reject incomplete observations. Do not scan quota business payloads or read
   H11 business results/ledger content for accounting.
2. Implement and consume the exact remote-result/v2 `resource_accounting`, all
   identity/digest/time/maxima checks, true execution counts and complete usage.
   Preserve `full_guest_filesystem_peak_proven=false`. `_carrier_usage()` alone
   does not satisfy this step; `usage()` still fails closed, and the current v1
   code is not releasable as the newly approved guarantee.
3. Finish C3 against the resulting new exact D: source/installed regressions,
   independent complete-chain review and both original private package
   build/parse checks. The offline source check in this record is not a complete
   package freeze or independent field-readiness approval.
4. Only after every original and new gate passes may the original single F1
   execute H01 semantic PASS → Q4 semantic PASS → H11 same-ledger recovery.
   No fresh approval for unchanged C1–C3 is being requested here.

The release allowlist remains empty and the field package remains null /
NOT_ISSUED. This work made no guest connection, marker, carrier request, H01, Q4
or H11 attempt. **No real core task ran and no business result/evidence returned.**
Existing guest state was not newly observed, so marker absence is not inferred.
No reconnect, replay, historical reinstall, cleanup or system change was made.
namespace/watchdog remain paused; production `E3_SUPERVISION_UNVERIFIED` remains.

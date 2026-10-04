# Core execution progress and local Codex handoff — 2026-10-04

## Current cancellation and installation followup

This core-only D followup descends from `5208e43d785f1c3eaacedf632029ed144b37833c`.
It continues the existing CLOSED scopes; candidate, wheel, projection, budgets,
deadlines, field allowlist and conditional single F1 are unchanged. The preceding
implementation `0c786ac` has now completed [CI 37191629497](https://github.com/kongbu0621/infra-local-hand/actions/runs/37191629497)
successfully in all three jobs.

### Corrected original Q4 cancellation

The frozen candidate's runner deliberately does not start a result-reader after
successful helper-running cancellation. The previous adapter indexed that absent
receipt and required an InvocationID for it. Q4 now requires the actual bootstrap
and helper receipts, matching helper boot/unit/InvocationID to the original
trigger and final report. It also binds durable delivery events to the original
report and rejects any reader or delivery after cancel. H01/H11 retain their
three-stage requirements. All three static authorized names remain in the plan.

This follows the original A requirements: static names at lines 176–182, launch
upper bounds at 200–203, actual identity array at 803–804, and Q4 PASS at
1132–1140. It changes no authority or acceptance contract. Regression evidence
uses the original Broker, SQLite ledger and cancellation report code; manager
and OS observations in that test are explicit doubles, not field evidence.

### Installation execution and internal I/O

Each installation/owner child now executes an already-opened, verified ELF
descriptor. The six admitted program identities remain checked. New runtime and
ABI programs are permitted only during the active original installation; their
held execution identities are retained and checked against its returned receipt.
The installed runtime also binds the receipt's device/inode. Equal-content inode
replacement, file capabilities and identity drift are rejected.

The original setpriv flags and credential checks remain. Its second Python hop
uses the held interpreter descriptor and a fixed `__PYVENV_LAUNCHER__` value to
preserve the original venv path. No wrapper executable, shell, extra runtime
module, new privilege, refreshed deadline or retry was added. Actual child exit,
wait4 usage and both EOFs remain mandatory; descriptors close on failures.

Dispatcher-owned extraction, scans, reads, creates, mkdir, metadata and fsync
now check the original paired clocks around each operation. Late opens and
iterators are closed; late writes leave partial objects without further writes.
Even a late ENOENT is checked before a caller can treat it as an absent object.
This cannot interrupt a blocked kernel call. Frozen `q2_prepare_build` internal
multi-step I/O still needs integration, so `installation.deadline_guarding`
remains a blocker. Directory samples remain observations, not a complete peak.

### Exact validation and remaining work

Dispatcher: **261898 / 262144 bytes**, SHA-256
`ba990dbac0c1fb9f63f25a353686124aa4f8035535f9b2055e6931fa99041653`.
Readable shared checks and data construction recovered space without dropping
predicates or changing diagnostic codes. Independent reverse expansion verified
the unchanged AST of 40 pure functions and the effect methods before the final
late-exception fix; ordered source lists, budgets, intents and session values
were also checked for equality. No compressed executable payload was added.

Local final core result: **608 passed, 1 skipped, 1 deselected (12.98 s)**.
The deselected unchanged writer test encounters the already-recorded cloud
`os.getpid()` versus `/proc/self/stat` discrepancy; it remains enabled in CI.
Installation binding/deadline regression files together: **28 passed**. Real
held Python created and ran a real temporary venv; the second Python hop retained
the venv identity. This executor has `CapEff=0`, so full setpriv credential
transition was not validated here. Root-owned ELF tests explicitly skip on an
ordinary CI account; two permission-independent rejection tests still run there.
The exact published commit must additionally complete the ordinary full source
and installed CI gates. These component results do not establish field PASS.

`installation.program_execution_binding` is implemented. Remaining code gaps are
current-guest admission, preparation's current-capacity collectors, complete
shared-pool peak accounting, frozen installer internal deadlines and aggregate
usage/peak evidence. Continue those core items before D4 release review. The
oversized development ancestor is a reference, not a deployable replacement.

The release allowlist stays empty. This followup issued no field package, marker,
request, SSH command or H01/Q4/H11 run. Existing guest state was not re-observed.
No reinstall, cleanup or automatic retry was performed. Namespace/watchdog and
other side features remain paused; production E3 remains restricted.

## Current preparation adapter followup

The current implementation D is `0c786ac2389291f488c60ccc32e7eb468d5e30d0`, tree
`5579ae72c83cd928e3e21e13944ad65924a6b82f`, directly following `ca4199e2` below.
This is continued D2 work under the existing core amendment, not a new Gate,
completed D1–D4, or field acceptance. The original R was read directly again.
The exact Git-blob verifier passed both independent C ancestry chains and the
unchanged A document/B decision digests. The approved runtime candidate, wheel,
projection, budgets, deadlines and conditional single F1 remain unchanged.

The selected dispatcher now contains the existing-account preparation adapter:

- Verify installation, current-capacity dependencies, persisted intent, retained
  objects, unused project IDs and parent identities before creating case resources.
- Create only the case/reservation ancestry, persist the preparation preimage,
  then create the fixed directories and seven quota roots. Limit mutation accepts
  only the original 21 IDs and their original 1 MiB/128-inode limits.
- Recheck retained inputs and quota inventory, invoke the original candidate
  constructors, save policy/authority, and initialize one empty ledger through
  the bounded ordinary child. Existing or partial objects are retained, not
  overwritten, cleared or retried. H11 recovery still uses its own origin ledger;
  this preparation entry is not called again during recovery.
- Guard individual directory/file/quota effect calls against the original paired
  clocks. Late-opened descriptors are retained for closure; a late return stops
  subsequent writes. This does not prove the still-incomplete installer/collector
  internals or that blocking kernel calls always return on time.

The dispatcher is **261960 / 262144 bytes**, SHA-256
`ca0efe77e6651a95afaa7a4853caf5f085b50e584fa96dbfc6050b257d02b4c9`.
The unchanged loader is 2160/8192 bytes and bootstrap is 49102/49152 bytes.
Common preparation error prefixes and concise comments keep the code within the
existing limit. No existing predicate was dropped, no extra field module was
introduced, and no byte ceiling was raised.
Only 184 dispatcher bytes remain. Remaining integration needs a reviewable
refactor within the same boundary, not restoration of the oversized checkpoint.

Validation of this D's source/test bytes: preparation **70 passed**; core
**567 passed / 9 skipped**; full source **4478 passed / 100 skipped, 434.30 s**.
The full report is retained locally at
`lh-core-preparation-source.GgTh1C/results.xml`, SHA-256
`9ba029170912963c5006896fac7c1142f983d8b2d63c22032b18c33278fb82aa`.
The new tests exercise actual temporary-file effects and one actual SQLite child
under the existing ordinary test account. Quota/service observations and
orchestration OS facts are explicit test doubles; they are not a guest measurement.
Initial failures retained in the execution transcript concerned an unnecessary
O_NOATIME requirement on directory traversal, then fixture file protection and
synthetic inode aliasing. Regular preparation-file O_NOATIME and the production
ownership/alias checks remain; no privilege fallback was introduced.

An isolated clone of the exact D built and installed a test wheel, then the
existing installed verifier returned **PASS, 94 checks / 292 commands**. The
local report `lh-core-preparation-installed.IouVnM/acceptance/report.json` has
SHA-256 `56a9d8bc94bc2e0cb3f54554d01f957daabed8f2c86b03b342a9c3852f8cc684`;
the test wheel SHA-256 is
`dd51d4c7ce98c30fcb527a88504cc9700290a84a474785d920a0a5c1fd37e7e6`.
This disposable installation does not replace the frozen field wheel or prove
an E3 business chain. At record time, the exact D's [CI run](https://github.com/kongbu0621/infra-local-hand/actions/runs/37191629497)
had passed classification; Linux and Windows semantic jobs were still running.
Skipped, pending and modeled checks are not field PASS or independent review.

### Direct remaining blockers

`admit()` still refuses: current guest, policy entities and historical obligations
must be independently collected and charged per live pool. Preparation refuses
before clock/file effects if its three current-capacity collectors are missing;
these are now named `preparation.current_capacity_collectors` in readiness.
Shared installation peak/usage accounting, installer internal deadlines and
executable binding also remain unproved. Neither the new adapter nor tests
remove these release predicates. Independent review and the complete original D4
checks still precede final private package construction and field admission.

The release allowlist is empty, the field package is null/NOT_ISSUED, and this
followup issued no marker, carrier request, H01, Q4 or H11. No real field task was
executed and no business result/evidence was collected. Existing physical guest
state was not newly observed; absence of a marker cannot be inferred from this
record. namespace/watchdog remain paused and production E3 remains restricted.

## Retained ca4199e2 checkpoint

This commit advances the approved core only. It does not declare Q2 accepted,
production support, or permission to ignore any existing field check. The runtime
candidate, wheel/projection identities, field protocol and resource limits remain
unchanged. The field allowlist remains empty.

Main now contains executable adapters for:

- H01 original normal handoff, Q4 running cancellation, and H11 same-ledger recovery;
- protected candidate module loading, including delayed imports;
- empty-ledger admission before submit and H01/Q4 closed-ledger logical export;
- original request, quota, phase, stage and controller fact extraction;
- preparation contract construction and original candidate handoff decoding.

The adapters retain single-attempt execution, original dual-clock deadlines,
wait4 and both pipe EOFs, original ledger identity, exact source sets and strict
result/stop/seal checks. H11 does not read a business result or export the ledger.
Prepared source objects are reread around the original owner execution.

Two concrete implementation defects were corrected: the root-owned session
container permits ordinary traversal while carrier/intents remain private; the
controller's original deadline is bounded by, rather than incorrectly equated to,
the longer owner deadline. The original controller envelope is still validated.
Independent review also reproduced SQLite creating WAL/SHM sidecars during an H11
`mode=ro` read. The selected-main reader now uses the already-quiescent immutable
held-fd view and rechecks both sidecars and file identity afterward. A real WAL
fixture and a pathname replacement regression cover that repair.

### Boundary at ca4199e2

Current-guest `admit()` and actual `prepare_case()` remain fail-closed in main.
Their full development implementation is retained in commit
`f342f325e5fc4ac2fc27795045813735fc1a2302`, a non-releasable ancestor, with admission
and capacity tests. Do not restore that whole dispatcher as a field artifact:
its 326139 bytes exceed the unchanged 262144-byte maximum.

Main selects the complete core execution/evidence dependency closure within that
maximum. Removing the oversized integration from the field artifact does not
authorize an alternate runtime module, compressed executable payload, larger
limit, fake admission result, or skipped predicate. The historical development
checkpoint is preserved to avoid repeating the work.

Guest shared installation physical allocation peak and complete usage accounting
remain unproven. Directory sampling is not a complete peak measurement. Existing
installation deadline/executable-binding blockers remain. Q4 must retain real
original stage InvocationIDs; do not invent a result-reader identity when running
cancellation precedes its startup.

### Validation and handoff at ca4199e2

The first selected-main core run produced **532 passed, 1 failed**. The unchanged
writer process-identity test fails because this cloud execution surface exposes
different `/proc/self/stat` and `os.getpid()` identities. The original assertion is
retained for ordinary-host CI. All field-size assertions passed. Further CI results
must identify the exact published commit; these local results are not field PASS.

The new SQLite/persistence fixtures use the actual test account. The production
writer continues to require its original owner. The root-owned carrier directory
test explicitly requires root. A local ordinary-user test launch was unavailable
(`runuser` could not set supplementary groups); ordinary-account validation remains
the GitHub runner's responsibility.

Local Codex should continue these core steps, in order:

1. Fetch main and preserve these fixes. Compare the development ancestor for the
   `_admit_*`, `_capacity_*`, actual preparation and associated tests; integrate
   them only with a reviewable implementation that remains within the existing
   field boundary. Do not replace the selected dispatcher wholesale.
2. Close real shared-pool/usage evidence and the remaining installation guards.
   Keep observed values and enforced limits distinct; never fill unknown peaks,
   PID counts or unit counts with zeros or inferred success.
3. Re-run core and installed checks on the exact resulting commit, then review
   field readiness and the original source/identity/deadline bindings.
4. Only after every release condition is satisfied, use the existing authorized
   single F1 sequence on the original fixture. Preserve original evidence and
   identifiers. No reinstall, cleanup, replacement identity or automatic retry
   is authorized by this progress note.

No side-feature development, SSH connection or actual original-chain execution
was performed in this turn.

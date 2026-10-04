# Core execution progress and local Codex handoff — 2026-10-04

## Current deliverable

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

## Explicit remaining boundary

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

## Validation and next work

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

# Retire the native experiment; repair the existing executor

2026-09-30. This is an implementation repair and a record of stopping an
independent candidate experiment, not a new product architecture or deployment.

## Owner direction and scope

Owner's exact direction in the current task:

> 换实现，或不要那个部分实现，又不影响我的功能和需求，就砍掉或绕过。

Local event: `LH-EXPERIMENT-RETIREMENT-20260930-01`. This record retains the
decision text for Owner verification. No new Gate closure is inferred from it.

The cgroup primitive spike is **RETIRED_UNQUALIFIED**. Its own requirements
allow the candidate to be disproved; its architecture explicitly excludes the
source from the wheel, Plugin and production loader. The product requirements
do not mandate C, clone3, the G/B/S/W layout, seven generations or a third lab
round. Those unfinished parts will not be built. The manual laboratory job is
disabled without executing it. Existing source and historical evidence remain
available for interpreting the two previous runs.

The user-visible execution, cancellation, quota, deduplication, recovery and
evidence requirements stay in force. The existing AX-A05 architecture already
uses systemd/cgroup v2 and permits UNKNOWN with retained capacity when stopping
or future activation cannot be proved. This repair uses that existing path;
it adds neither a custom native supervisor nor prestarted execution slots.

This is not a diagnosis of the platform rejection. The original platform
response/request identifier is unavailable, and filename causation is not
established. No platform trigger tests or refused native subtask retries were
performed as part of this repair.

## Concrete defect and change

All quota-backed stages use `systemd-run --pipe` with `quota_transport`.
The helper lacks `quota_pipe`, which is the bootstrap receipt decoder. However,
`_stop_unit()` recognized only `quota_pipe` and `result_reader` as long-lived
pipe clients. A running helper client was therefore treated as an unacknowledged
start. Cancellation returned without asking the manager to stop it.
`quota_lifecycle.observe()` also ignored the cancellation event and stop request,
so the helper could continue until its normal deadline.

The repair retains a single original-instance observation and stopping path:

- `_stop_unit()` records a quota-backed stage's stop request and delegates it to
  the existing lifecycle observer. It does not wait for the pipe client to exit
  or stop the unit before its original facts can be captured.
- The observer honors `stop_requested` and the shared cancellation event before
  the deadline. It validates the original boot/unit/InvocationID/cgroup and unit
  configuration, then rechecks InvocationID immediately before StopUnit.
- A lost or unsuccessful stop acknowledgement permits another bounded stop
  only after observing the same original instance. It never permits a new start.
- Only a genuinely terminal observation is saved as terminal evidence. A
  running pre-stop snapshot cannot justify closure after transient-unit GC.
  Missing terminal facts, original exit, either EOF or parent identity continue
  to produce UNKNOWN. Stop acknowledgement alone never releases resources.

Existing broker/ledger ownership, fixed job mappings, authorization, namespaces,
resource ceilings, original deadlines, exit-code rules and evidence protocols
are unchanged. The production `E3_SUPERVISION_UNVERIFIED` qualification remains.

## Authority and retained history

The unchanged authorized implementation scopes are E1–E3 at A
`79f73faedcd9cde4164b0d1625782dae27db6c2f` and the E3 quota harness at A
`415327ebdcc251bb055da9931a7a88990f750b7a`, under R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`. Their existing Owner decisions and
independent CLOSED records are referenced by root `AGENTS.md`. Independent
reviews confirmed this fixes the existing AX-A05 cancellation contract without
changing its requirements or architecture.

The native experiment's original approved A and continuation A documents remain
historical. Run `36577764454` remains UNKNOWN with cleanup unverified; run
`36662298613` remains UNKNOWN with its separately recorded cleanup and rejected
report. Consumption remains 2/3. Round 3 remains NOT_DISPATCHED and is no longer
planned. Stopping this candidate does not pass either the host-window H07 or
the E3 cancellation/late-activation H07, which are different acceptance items.

## Verification

The new cancellation cases were first run against the old implementation and
failed: no stop was delivered for a running stage. They cover both cancellation
inputs, original-instance mismatch, a lost stop acknowledgement, terminal facts
arriving after stopping, and immediate GC without terminal evidence. Runner
tests cover the actual stop-to-inspect handoff into the lifecycle observer and
avoid an early independent StopUnit path.

The four affected regression files completed with **114 passed, 1 skipped**:
`test_local_hand_jobs_quota_lifecycle.py`, `test_local_hand_jobs_runner.py`,
`test_local_hand_jobs_result_reader_runner.py` and `test_local_hand_jobs_broker.py`.
The skip is the real systemd/cgroup integration test in an unsupported execution
environment; it is not a pass. Independent review found no blocking issue and
confirmed cancellation still prevents a new result-reader launch and retains
the existing resource-release proof requirements. `git diff --check` passed.

Manager/cgroup facts in these tests are modeled; anonymous pipes and child exit
observations are real where stated by the existing test fixtures. This is not
real systemd/cgroup qualification, a host deployment, NAS acceptance or a claim
that the whole product is now deployable.

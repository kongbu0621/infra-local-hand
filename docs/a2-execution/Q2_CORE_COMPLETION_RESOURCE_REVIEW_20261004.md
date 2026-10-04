# Core resource/result integration and local Codex handoff — 2026-10-04

## Scope and outcome

This implementation continues the already approved C1–C3 scope at A
`851a1afe4e55196212aa6913e81e0722deed1032`, following independent CLOSED C
`c32799c03a32d81deec02f7492c1b71eb47b2b6d`. Its publication parent is
`44b801365d68157a675422ff5ad612d1b3175249`. No new approval or field attempt is implied.

The remaining source effects are connected: 32 fixed resource pools, controlled
I/O accounting, child/case/final observations, actual invocation/native counts,
carrier counters, and remote-result/v2 generation and independent consumption.
Source readiness now has no unimplemented effects. The host dispatcher digest
allowlist remains empty pending exact private release review; no package is issued.

## Concrete changes

- Non-quota allocation uses protected metadata-only observations. Other pool roots
  are excluded before traversal, so roots are not counted twice. The 21 project
  quota roots use original setup identities and quota observations; H11 business
  payloads are not reread, hashed or traversed for accounting.
- Successful short writes and creates are charged before the post-syscall deadline
  check. Late returns retain partial objects and actual amounts. Touched parent
  pools are observed too. Failed or missed boundaries remain INCOMPLETE; a later
  successful observation cannot erase the failure.
- The frozen installer receives private guarded bindings, including fd-to-path
  bookkeeping. Existing child wait/reap/EOF and alias checks remain. Child failure
  is observed within the original window or explicitly marked missing.
- Persistence uses the original preparation/owner clocks; final session/resource
  operations use the original outer reserve. No window is refreshed or extended.
- Actual unit identities and native reports come from original control evidence.
  A successful synthetic full chain counts 14 job units (9/2/3), not the budget 15.
  Unknown groups stay null with exact missing roles while known groups survive.
- v2 contains all 32 rows, independent maxima, source and snapshot digests, and the
  approved completion descriptor. Sender and host independently validate paths,
  original preparation identities, clocks, totals and missing evidence. Final
  accounting is frozen once before the output-frame length fixed point.
- Existing admission consumers now bind controller identities and the complete
  planned-unit absence set to the original locators.

Frozen producer compatibility was checked against candidate `4b6e4a7c` (12 source
files compared byte-for-byte). Q4's durable handle uses a physical cgroup path;
the new count collector now verifies that path before deriving its logical key.
H11 may retain a terminal unit's empty ControlGroup. Only after the original
manager/parent, unit/InvocationID, stop and terminal evidence bind is a counting
key derived; the original observation remains unchanged. Running or conflicting
identities are rejected.

## Verification and limits

Initial integrated core tests: **968 passed, 1 skipped, 2 deselected**. The two exclusions
are the existing cloud PID-versus-proc identity tests, whose assertions remain
unchanged and run in ordinary CI. Earlier integration failures were retained and
fixed: synthetic admission/extraction fixtures and the old source-readiness
assertion. No failing real observation was converted into a pass.

Tests include actual temporary filesystem I/O, late/partial writes, metadata drift,
unknown and over-limit observations, producer-to-two-consumer checks, exact frozen
control schemas and partial v2 framing. Quota/manager doubles establish code
conditions only. Full source and independent installed verification remain CI
checks on the published commit, not evidence of guest acceptance.

The first published implementation is `2f126dcabbe536f16da20ec3ab9e23ddba6ed8b6`,
tree `52fd8c67ce3e16eaeab545c162665d259556ae8d`. Its CI run `37211389457` exposed a
Windows collection error in the new guest-validator tests: importing the
Linux-only dispatcher attempted to import `resource`. The follow-up marks that
test module Linux-only before importing it, consistent with existing guest tests.
The independent portable resource-contract tests still run on Windows. Runtime
code and field-source digest are unchanged by this test-scope correction.

The Windows collection follow-up is `fd404b8cbc47e55af892f29f4f780974f645b85a`.
Its CI run `37211608455` passed Windows (1747 passed / 1269 skipped; independent
installed verifier 10 checks / 10 commands). Linux reported 4884 passed / 88
skipped and one test fixture failure: an ordinary runner correctly received
`CORE_EFFECT_MKDIR_OWNER`. The follow-up preserves that production root-owner
check and verifies both outcomes: root success or ordinary-user rejection, with
the actual completed create charged in either case. No permission check is relaxed.

A concrete full-scan cost was also found before private release. The second pass
now groups objects by parent within one observation, retaining each object's
name/O_PATH/fstat/name checks and full no-follow parent walks before and after
each group. No allocation sum or object identity is reused across observations.
The boot clock retains six bounded, pinned descriptors while still reading fresh
boot bytes and EOF, validating file/parent/ancestor identities and reading both
clocks on every call. All controlled I/O boundaries still trigger full scans.

In the same isolated 500-file/10-directory fixture, with real boot reads and clock
guards, three final scans took 0.261011 / 0.259899 / 0.238914 seconds, versus
0.616289 / 0.574619 / 0.548356 before. Mean time fell about 56%; open calls fell
from 158688 to 1205. This is a local overhead measurement, not a guest runtime
qualification or proof that the real chain fits its original 750-second cap and
705-second normal window. Neither deadline is changed. The frozen installer's
435 internal verification commands are not 435 dispatcher child callbacks.

After these narrow follow-ups, integrated core tests are **985 passed, 1 skipped,
2 deselected in 26.84s**, with the same two unchanged cloud PID exclusions.

Seventeen new regressions cover complete second-pass sibling checks, renamed or
aliased parents, late descriptor release, no-atime metadata-only coverage, fresh
boot reads/EOF, name replacement, malformed identity and bounded FD cleanup.
An existing executable-read failure injection is now scoped to that executable's
device/inode, so it does not accidentally fail the unrelated boot clock read;
its FD closure assertion is unchanged. The fixture closes its owned clock FDs.

Field source sizes are loader **2160**, bootstrap **49102**, dispatcher **412466**
bytes. Dispatcher SHA-256:
`06f5e5b659967a5a8375d981fe6e58401bba65b29054df50be363501f98ce79f`.
All are within the approved three-file caps. Original runtime candidate, wheel,
projection, budgets, package/session/marker protocol, 82 output members and six
host files remain unchanged. `full_guest_filesystem_peak_proven=false`: application
accounting and boundary observations do not prove continuous filesystem peaks.

## Next task for local Codex

1. Use this exact published source and its successful CI result. Preserve private
   inputs and existing work; do not substitute the frozen candidate or field wheel.
2. Finish C3 with the existing private freeze flow: verify all original source
   relations and all three amendment A/B/C ancestry bindings; independently build
   and parse the exact package twice. Confirm the original size/deadline/output
   constraints and the new v2 object against those actual private inputs.
3. Only after every existing release predicate passes, record the exact reviewed
   dispatcher digest in the existing host allowlist and freeze the corresponding D.
   Source readiness alone is insufficient. If evidence is missing, retain
   NOT_ISSUED and report the specific missing input; do not request approval again
   for the already approved A or start another qualification route.
4. Continue only the original conditional single F1: H01 semantic PASS → Q4
   semantic PASS → H11, using the existing SSH/environment. Retain old evidence;
   no reconnect, automatic retry, cleanup, new marker/request or repeated historical
   installation. Stop on failure and retain the original result.

This cloud turn issued no carrier and performed no real H01/Q4/H11. It cannot
assert the current private marker is absent. Production E3, NAS, E4–E6 and side
features remain outside this work. The remaining goal is the actual returned
business result plus original cancel/recovery acceptance, not another feature branch.

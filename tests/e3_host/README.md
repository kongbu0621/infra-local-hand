# Explicit isolated host entries

Before a complete fixture exists, use the standalone read-only
[existing guest handoff](../../docs/a2-execution/E3_QUOTA_Q2_MACHINE_HANDOFF.md).
The current three-phase route is documented in the
[batch preflight and retained-evidence handoff](../../docs/a2-execution/E3_QUOTA_Q2_HANDOFF.md).
All entries are test-only, require explicit inputs, and retain production/Q3
acceptance as false. Ordinary test discovery never starts them on the host.

| Entry | Role |
| --- | --- |
| `q2_host_export.py` | Explicit existing Q1 guest facts and missing Q2 input groups; no provisioning or fixture required |
| `q2_fixture_check.py` | Read-only aggregate preflight for the full supervisor/three-phase fixture |
| `q2_supervisor.py` | One original target-controller launch, independent stop, capture and seal inside an already supervised root service |
| `q2_launcher.py` | One ordinary resident and permanent journal for the same operation's preflight/business/evidence chain |
| `q2_resident.py` | Original broker/SQLite operation in the fixed ordinary process |
| `q2_evidence_review.py` | Bounded offline review of explicit retained output/declaration directories against an independently pinned seal SHA-256 |

Preflight is a snapshot, not a reusable launch authorization. Offline review
establishes retained-artifact consistency, not current host state or historical
capacity peaks. The supervisor's own original external stop remains required.
The entries above require prepared resources and never provision accounts,
mounts, quota or cgroups. None replays a consumed experiment. Missing inputs
report BLOCKED rather than synthesizing private values from unit-test fixtures.

## Separately authorized fixture preparation

`LH-Q2-FIXTURE-PREP-v1` is closed at the exact baseline and Owner decision in
[the closure record](../../docs/governance/Q2_FIXTURE_PREPARATION_OWNER_DECISION.md).
`q2_prepare_driver.py --plan ABSOLUTE_PRIVATE_PLAN --sha256 PLAN_SHA256 --execute`
is the single explicit resource-preparation and original-handoff entry. It
requires the supplied isolated guest, initial-namespace root, all current host
pins and the complete strict plan. No-argument entry points remain inert.

| Module | Responsibility |
| --- | --- |
| `q2_prepare_contract.py` | Exact private plan fields, isolated scope and finite resource ceilings |
| `q2_prepare.py` | Pre-mutation host/capacity/source checks, create-only reservation, new ordinary account, seven quota roots and five parents |
| `q2_prepare_build.py` | Exact Git and wheel verification, offline installation, native compilation and ordinary installed-identity check |
| `q2_prepare_assembly.py` | Real policy, allocator and three-phase declarations, with no invented running identity or issued deadline |
| `q2_prepare_driver.py` | Observed preparation facts to declarations and empty ordinary ledger, then fresh exec into the original owner |
| `q2_prepare_run.py` | Actual same-process supervisor binding, complete check, one original launch and independently observed exit/EOF |
| `q2_prepare_delivery.py` | Bounded create-only archive delivery and external client capture |

The private delivery fixes guest/account/path/project choices outside public
source. It preserves the original SSH/admin endpoint as the final observer of
client exit and both stream EOFs. All preparation, ordinary, administrative and
outer capture costs are declared before use. A retained reservation or partial
installation blocks replay; failures retain their records. Installation never
formats, mounts, changes packages or resets old allocations.

`RESOURCES_PREPARED`, `PREPARED`, complete transport and modeled test success
are distinct results. Only the running supervisor can complete the full fixture
check, using its actual PID, invocation and cgroup. The batch retains Q2/Q3 and
production acceptance as false; live evidence still requires review.

## Earlier single-phase entries

`q2_batch_check.py` is a read-only, explicitly invoked Q2 assembly preflight.
It is not discovered by the ordinary unit-test runner and does not execute Q3.

Without an exact private fixture it reports `BLOCKED` and exits 3. With a
fixture it verifies the pinned clean source, protected observer configuration,
original identities/capacity and actual controller/host prerequisites. A
`CHECKED` result still sets Q2 acceptance and production support to false.

See [the fixture schema, command and remaining bridge work](../../docs/a2-execution/E3_QUOTA_Q2_PHASE_CLOSURE.md).

`q2_phase_driver.py` drives one **already prepared** original resident phase over
an inherited credentialed bridge. It does not construct a broker, issue a grant,
or provision a fixture. No fixture reports BLOCKED (exit 3). See
[exact v1 prepared-phase input and remaining composition gaps](../../docs/a2-execution/E3_QUOTA_Q2_BRIDGE.md).

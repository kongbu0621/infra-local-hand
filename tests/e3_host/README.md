# Explicit isolated host entries

The current three-phase route is documented in the
[batch preflight and retained-evidence handoff](../../docs/a2-execution/E3_QUOTA_Q2_HANDOFF.md).
All entries are test-only, require explicit inputs, and retain production/Q3
acceptance as false. Ordinary test discovery never starts them on the host.

| Entry | Role |
| --- | --- |
| `q2_fixture_check.py` | Read-only aggregate preflight for the full supervisor/three-phase fixture |
| `q2_supervisor.py` | One original target-controller launch, independent stop, capture and seal inside an already supervised root service |
| `q2_launcher.py` | One ordinary resident and permanent journal for the same operation's preflight/business/evidence chain |
| `q2_resident.py` | Original broker/SQLite operation in the fixed ordinary process |
| `q2_evidence_review.py` | Bounded offline review of explicit retained output/declaration directories against an independently pinned seal SHA-256 |

Preflight is a snapshot, not a reusable launch authorization. Offline review
establishes retained-artifact consistency, not current host state or historical
capacity peaks. The supervisor's own original external stop remains required.
No entry provisions accounts, mounts, quota or cgroups, and none replays a
consumed experiment. Missing inputs report BLOCKED rather than synthesizing
private host values from unit-test fixtures.

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

# Core execution development checkpoint — 2026-10-04

This is implementation work under the existing CLOSED core delivery and binding
scopes. It does not change R, A, the field protocol, resource limits, candidate,
projection, wheel, or the conditional F1 release requirements.

The complete development checkpoint adds current-guest admission/capacity,
existing-account preparation, H01 execution, Q4 running cancellation, H11 recovery,
candidate module loading, original empty-ledger checks, closed-ledger export and
dynamic phase facts. It is **not field-releasable**. No SSH connection, installation,
fixture mutation, original-chain execution, cleanup or automatic retry occurred.

The complete dispatcher is 326139 bytes, SHA-256
`5fa175cfe862bb710c1554597a51fe0255024d624af48b0391ffcf0e01641e8c`.
The approved maximum remains 262144 bytes. The original field-size tests correctly
reject this development checkpoint. The complete core test selection produced
586 passed and 3 failed: two field-size assertions and the unchanged host writer
process-identity test, whose ordinary `/proc`/PID relationship is not provided by
this cloud execution environment. These are not reported as a green full suite.

Admission, quota, account and manager facts in the new isolated tests are synthetic;
SQLite and child-process tests exercise real local objects. No test result replaces
H01/Q4/H11 field evidence. Guest shared installation physical peak accounting is
still unproven. The Q4 requirement for three original stage InvocationIDs remains
strict, including when cancellation may precede result-reader startup.

The following publication commit selects the core execution/evidence dependency
closure within the existing field byte limit. The oversized admission and actual
preparation implementation remains in this development ancestor, together with
its tests, for subsequent integration. Current main must keep explicit admission,
preparation and usage blockers and an empty field allowlist until those remaining
requirements are actually satisfied.

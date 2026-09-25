# Explicit isolated host entries

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

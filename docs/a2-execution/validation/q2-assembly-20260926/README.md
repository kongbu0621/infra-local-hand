# Q2 assembly repair verification

2026-09-26. Scope: isolated existing Q2 code repair, received-report review and
candidate installation identity. New fixture preparation remains **OPEN**.

## Exact candidate

- Local source tested: `e912b3eaa7bce19e27aa167c281ccc8126d6c6f8`.
- Public source and proposed documentation A: `2ea59b8d1b262632bae5636938107ef2f002a59b`.
- Exact common tree: `dcb3b7163afc4187b9eb5b04d8d73d14a2a1f5e5`.
- Local/public commits have distinct identities; tree equality is recorded in
  `publication-map.json`. The wheel was built from the exact **public** commit.
- Source tests ran with a clean checkout before and after, Python 3.12.14,
  kernel 6.18.44, `PYTHONPATH=tools:tests`, `PYTHONDONTWRITEBYTECODE=1`.

## Source and default-entry results

| Command group | Collected | Passed | Skipped | Exit |
| --- | ---: | ---: | ---: | ---: |
| `python -B -m unittest discover -s tests -p 'test_local_hand_jobs*.py' -v` | 565 | 551 | 14 | 0 |
| `python -B -m unittest discover -s tests -p 'test_e3_quota*.py' -v` | 489 | 488 | 1 | 0 |
| Total | 1054 | 1039 | 15 | — |

Thirteen skips concern real AF_UNIX client/transport tests in the jobs suite;
one jobs skip is real delegated cgroup integration. The quota skip is a real
listener IPC test. Executor restrictions are not PASS or live-host evidence.
The eight explicit host entrypoints ran with `python -I -B` and no arguments:
host-export, fixture-check, evidence-review, batch-check, supervisor, launcher,
resident and driver all returned the expected BLOCKED exit 3. Actual commands,
timestamps and log digests are in `metadata.json`.

The repaired regression includes a real immutable Policy, SQLite allocator and
three-phase journal/configuration chain. Kernel quota facts and process-manager
observations remain modeled in these tests. No real Q2 fixture was created.

During development an added test initially overlapped a synthetic ordinary root
with the management evidence directory. Only that test's synthetic ordinary
prefix was corrected; production geometry checks were retained. This initial
failure is separate from the clean candidate results above.

## Exact public build and fresh installation

An independent checkout used the exact public Git commit object, verified by its
object hash, and the exact tree above. The pinned build/test packages from
`requirements-build.txt` were reused in a new isolated Python 3.12 environment;
each copied distribution file was checked against its installed RECORD. No
runtime dependency was added and no network package update was performed.

Build: `python -m build --wheel --no-isolation --outdir <separate-dist>`.
Installation: a fresh venv, `python -m pip install --no-index --no-deps <wheel>`.
An isolated `python -I -B` check outside the source checkout validated build
metadata, implementation identity, all package payload files, and broker/MCP
release identities against their installed code.

- Wheel: `infra_local_hand-0.2.0a1-py3-none-any.whl`, 265849 bytes.
- SHA-256: `e60a7649f0b0883edb0d986c12ae8e5aca5607261043e5fcf6643ab4e2e18e10`.
- All 53 payload files match the exact public commit's Git blobs.
- Installed payload digest: `2953bbb0ef9f5e2133db2ef26e6a2a8a096e8652bb2fdbc389c29d06d153e329`.
- Fresh runtime contains only `pip==25.0.1` and `infra-local-hand==0.2.0a1`.
- Optional MCP dependencies are absent; validating its package identity does not
  claim an active MCP connection or service.
- All 15 recorded build/install/identity commands exited 0. The wheel build's
  disabled-byte-compilation warning is retained in stderr.

`candidate-build-identity.json` and the build/install/identity logs preserve this
scope. The wheel is a build candidate, not an installation in the supplied guest.
Administrative source/native/harness artifacts remain separate from the wheel.

## CI and remaining boundary

The previous public candidate's Ubuntu CI had 1486 passed, 1 failed and 12 skipped;
Linux's subsequent build/install steps did not run. The failure was the test's
root-only O_NOATIME assumption, now covered by separate refusal tests.
The new exact public candidate's
[run 36223849535](https://github.com/kongbu0621/infra-local-hand/actions/runs/36223849535)
is tracked in `ci-status.json`; a pending run is not a successful result.

The received report audit is in `../../E3_QUOTA_Q2_ASSEMBLY_REVIEW.md`. It retains
28 observed selected Q1 checks and nine undelivered Q2 input groups; raw machine
data remains private. The exact new preparation proposal is recorded in
`../../../governance/Q2_FIXTURE_PREPARATION_BASELINE.md`.
Q2/Q3 acceptance and production support remain false. No Q1 replay, fixture
provisioning, quota change, user creation, host deployment or new-scope
implementation occurred in this batch.

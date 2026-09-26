# Q2 preparation account compatibility repair

Date: 2026-09-26. This is a repair within the already CLOSED
`LH-Q2-FIXTURE-PREP-v1` scope, not an authorization to replay its failed delivery.
The original three approved documents remain byte-identical.

## Observed failure

The actual isolated-guest preparation reached the ordinary-account step.
`groupadd` exited 0. `useradd` exited 3 with the configuration error
`unknown item 'CREATE_MAIL_SPOOL'`. Both command streams reached EOF;
the outer batch also retained its real exit 3 and both EOFs. This is a command
compatibility failure, not a transport or capture loss.

The supplied read-only diagnostic binds the original plan and receipt. It found
the planned empty primary group, no account by name or UID, and no subsequent
planned directories apart from the preparation record directory. No Q2 fixture
was generated and no Q2 runtime was issued. Full retained-object preservation
must still be checked before recovery; the failed receipt contains no
`retained_after` inventory.

Private diagnostic SHA-256:
`21ec1472a61c0ca9e0adf863ee8034c05c3e54c2388b5d99b32bfb446b6a3e85`.
Raw machine paths, identifiers and records remain private.

## Repair

The account command no longer sends `CREATE_MAIL_SPOOL` through `useradd -K`.
It uses `--system` with the same explicitly planned non-root UID and primary GID,
locked password, nologin shell, no home creation and no log initialization.
It does not request subordinate IDs. Account identity and supplementary groups
remain verified after successful creation.

The upstream [shadow 4.13 useradd source](https://github.com/shadow-maint/shadow/blob/4.13/src/useradd.c)
distinguishes the useradd-defaults mail setting from `-K` login.defs keys;
system-account mode skips mail creation and, without `-F`, subordinate-ID allocation.
This source check supports the chosen arguments; it is not a claim that the
repaired account command has already run on the real guest.

Failed commands now include argv, real exit/EOF state, a bounded readable
stdout/stderr summary, and the raw result's digest and saved-record status in the
batch receipt. Raw captured bytes and existing failure verdicts are retained.
Each readable stream summary is limited to 4096 bytes before decoding and marks
truncation. This avoids another diagnostic round trip merely to discover stderr.

## Verification and limits

Targeted preparation, contract, driver, assembly, delivery and run tests:
**72 passed, 1 skipped in 3.28 seconds**. The skip requires an ordinary UID that
is not mapped in this executor; its credential/ledger check still requires the guest.
`git diff --check` passed. No host account or group was created by these tests.

Verified source SHA-256:

| File | SHA-256 |
| --- | --- |
| `tests/e3_host/q2_prepare.py` | `eb33238332d582b7cd40c64be4114e6f4254ee689e90ca64f4c87cb82c0215df` |
| `tests/test_e3_quota_q2_prepare.py` | `1c79f12fe10bd3704d5cd766d1617fdfbb1ca69f9fc30bd674d87856b3f64cd9` |

Checks cover explicit non-root account arguments, rejection of wrong identity or
extra groups, stopping after user creation failure, and retaining raw stderr,
real exit and both EOFs while producing a bounded readable summary. Existing
assembly/delivery/run regressions remain covered by the targeted suite.

The original delivered candidate's [CI run](https://github.com/kongbu0621/infra-local-hand/actions/runs/36228040236)
completed successfully. That earlier CI and this local repair suite do not prove
real guest recovery or Q2/Q3 acceptance. The application candidate selected for
installation remains the original pinned candidate; this repair does not replace it.

## Pending recovery decision

The original preparation window has expired. The approved preparation
[architecture](q2-fixture-preparation/ARCHITECTURE.md) requires recovery to preserve
the original intent and budgets; its [implementation plan](q2-fixture-preparation/IMPLEMENTATION_PLAN.md)
prohibits extending the total deadline. A new bounded recovery window therefore
needs a distinct decision under the repository's change rule.

The [recovery requirements](q2-preparation-recovery/REQUIREMENTS.md),
[architecture](q2-preparation-recovery/ARCHITECTURE.md) and
[implementation plan](q2-preparation-recovery/IMPLEMENTATION_PLAN.md) propose
`LH-Q2-PREP-RECOVERY-v1`, still OPEN. They preserve the original failed receipt,
plan, primary group, installed candidate and capacity commitments. No new
executable recovery path is implemented or delivered by this repair.

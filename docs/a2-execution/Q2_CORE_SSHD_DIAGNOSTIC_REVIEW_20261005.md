# Core sshd source rejection diagnostics

2026-10-05 +08:00. This is an offline diagnostic repair, not a fourth acceptance
attempt or a claim that the 05b field failure is fixed. The existing CLOSED core
development authority remains applicable because no accepted grammar, policy,
source, privilege, budget or execution rule changes. The direct pinned R was
read again. The release allowlist stays empty and production E3 stays restricted.

## Confirmed failure and available sources

The [05b result](Q2_CORE_POST_SUDO_ACCEPTANCE_REVIEW_20261005.md) retains the exact
issued D `8704a24b6c3c79ce4a36028ae2182dec2a35843e`, its consumed request and five
capture files. It reached sshd source validation after sudo checks, then returned
only `CORE_ADMIT_SSHD_GRAMMAR`. No failed source line, configuration snapshot,
business output package or case verdict was returned. Business execution and
result collection remain UNKNOWN. The later containment commit
`71d6f43d98a8b71763e7925c43b2becaec184e11` now has
[completed 3/3 CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37281378948).

The bounded local search used only retained material and archive indexes:

- No matching sshd configuration filename was found in the known VM management
  directory, Downloads or the non-test temporary material search. Test fixture
  copies and source checkouts are not machine originals.
- Both retained historical tar archives matched their collection-capture hashes.
  The host archive has 49 members and the guest archive 3102; neither member
  directory contains `sshd_config`. The host manifest, guest manifest and guest
  inventory also contain no such source reference.
- All six fixed guest horizon ZIPs matched their existing size/SHA pins. Their
  member counts are respectively 218, 224, 232, 267, 271 and 115; none contains
  an sshd configuration member.

Archive and index reads used the existing stable O_NOATIME/no-follow reader;
archives were inspected in memory, not extracted. No VM disk payload was read or
mounted. This search does not prove that no copy exists anywhere else, nor does
it recover the missing 05b source from historical defaults.

## Reproduction and unchanged security boundary

An in-memory input with the fixed Include and `AcceptEnv LANG LC_*` reproduces
the original generic grammar rejection. OpenSSH documents `*` and `?` in
[AcceptEnv](https://man.openbsd.org/sshd_config#AcceptEnv). That establishes an
OpenSSH grammar fact, not the actual contents of this guest or this failure.
The approved binding requirements retain STOP_AND_RETAIN for unknown sshd
Include/Match/quote/glob syntax. This repair therefore does not allow `LC_*`,
quotes, other Includes or active Match, and does not substitute helper exit zero
for the five required effective-policy predicates.

The diagnostic now distinguishes quote/expansion, missing arguments, Match,
Include location/target/count, keyword, glob and source encoding failures.
It adds only fixed uppercase codes, one-based file/parser-line indexes, file and
byte/line/Include counts, path digest and source digest. File order is the
existing collector input order. Line numbers use the existing `splitlines()`
parser semantics; L0 denotes a whole-file check, and F0/L0 a whole-closure check.
Whole-closure SHA binds the ordered path-digest/byte-count/file-digest array;
path digests use UTF-8 with surrogatepass. No raw line, private path, credentials
or arbitrary exception text is emitted. The unchanged bootstrap carries these
codes through the existing bounded stderr channel; no new read, helper, output
file or protocol is added.

## Scoped verification

- 29 new cases cover every rejection branch, second-file identity, encoding,
  whole-closure failure, original positive cases, non-LF parser line boundaries,
  and the existing 65-file/262144-byte-per-file limits. Real bootstrap `main()`
  error handling preserves the diagnostic without echoing raw input; tested
  diagnostic lengths remain below 384 bytes.
- Eight relevant test modules: **395 passed / 10 skipped / 8.18s**. The skips
  require root for existing protected-file/installation/helper fixtures and are
  not counted as passes. The earlier 207/2 run is a subset, not extra coverage.
- An additional in-memory comparison with the actual 71d6f43 parser produced
  identical acceptance/rejection for 1284 synthetic inputs: 53 accepted and
  1231 rejected. This is bounded compatibility evidence, not a general proof or
  a field result. `git diff --check` passed.
- Dispatcher: 448810 / 524288 bytes, SHA-256
  `10839026bd841024ab9e3be35793a0d779cba1e1d6794f0dd1c41434e1868078`.
  Bootstrap remains 49031 / 49152 bytes, unchanged SHA-256
  `4a58b342ea4fabb95903e9362cc9b0007c6aafda5a5ece3203692c5033982ce3`.
  No full local source suite, installed-package verification or private delivery
  freeze was rerun for this diagnostic-only change.

## Remaining direct blocker

The exact rejected configuration bytes or a precise field diagnostic are still
missing. Do not name AcceptEnv as the actual cause, change system configuration,
or claim this diagnostic code has repaired the 05b field failure. A targeted
compatibility repair must first be grounded in identifiable input; any material
change to the fixed accepted profile follows R's change rule.

This work made zero new SSH/carrier requests and no marker, batch, installation,
cleanup or retry. All three consumed attempts, original UNKNOWN states and full
commitments remain. Do not use a future diagnostic invocation as an unapproved
fourth acceptance request. H01 → Q4 → H11 remains unaccepted, and side work stays
paused. The immediate handoff is this offline diagnostic and its limits, not a
new field instruction or another full-suite run.

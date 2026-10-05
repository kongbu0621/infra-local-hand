# Core sudo long-listing compatibility repair — 2026-10-05

## Observed failure and scope

Baseline `d846c72afbdc1c46441cac133621b26c87e1730d` records the consumed
`lhqcore-20261005a` request: HELLO, BIND and package transfer completed; admission
returned `CORE_ADMIT_SUDO_OUTPUT` before H01. The original sudo stdout was not
retained. Therefore the exact failed parser assertion remains unproven; the
following are reproduced code defects, not a reconstructed field transcript.

This is a compatibility/diagnostic repair within the existing CLOSED core
development scope. The pinned R was read directly. It creates no new field
authority, batch, request, package issuance or release digest. Both consumed
attempts, their evidence and obligations remain retained. The release allowlist
remains empty; business truth and remote closure remain UNKNOWN. Side work stays
paused and production E3 remains `E3_SUPERVISION_UNVERIFIED`.

## Reproduced defects and bounded repair

The original parser split only on the old bare `Sudoers entry:` header and
accepted commands only with eight leading spaces. Official sudo 1.9.15p5
[display.c](https://github.com/sudo-project/sudo/blob/SUDO_1_9_15p5/plugins/sudoers/display.c)
prints the source file after that header and a literal TAB before commands.
For pipe output, it sets width to zero;
[lbuf.c](https://github.com/sudo-project/sudo/blob/SUDO_1_9_15p5/lib/util/lbuf.c)
then emits those bytes unchanged. The
[official version note](https://www.sudo.ws/posts/2023/11/more-info-with-ll-in-sudo-1.9.15/)
also documents the new source label. Each format change independently reproduces
the original rejection. The parser also incorrectly required a Defaults header
when no matching Defaults exist.

The repaired parser recognizes these formats. A source label must exactly name
a regular sudoers file already read and held by the current policy collector;
`sudo.conf` is excluded. Labels never cause extra filesystem reads. The source
literal, executable identity, helper invocation/budgets, account, RunAsUsers,
RunAsGroups and NOPASSWD grant checks remain required. Unknown fields, options,
restricted commands, duplicate/empty command lists and ambiguous control bytes
fail closed. The collector passes its existing regular-file inventory directly.

Each sudo-output rejection now carries a fixed stage, one-based line/entry
index (zero for whole-output checks), bytes, LF-delimited line count, entry and
source-header counts, TAB/space command counts and uppercase SHA-256. No input
line, path or arbitrary exception text is echoed. The code uses only the
existing `CORE_[A-Z0-9_]+` error channel, so the unchanged bootstrap retains it
in the original bounded stderr file. There is no new writer, file or protocol.

## Verification and local handoff

- Added 45 regression cases. Original-code checks reproduced the TAB, source
  header and absent-Defaults failures; the old space-only fixture still passed.
- Eight related modules: **248 passed** (Python 3.12 environment, umask 022).
  This includes real bootstrap `main()` preservation of the complete diagnostic,
  no raw-content disclosure, and a diagnostic below 384 B at the helper's
  65536 B output limit. These are isolated tests, not field acceptance.
- Dispatcher: **438842 / 524288 B**, SHA-256
  `1d16a65c6e2f61deacf673d454f316b9bec39a9bbe7df97f5016f3998923d612`.
  Bootstrap stays **49031 / 49152 B**, byte-identical to baseline.
- Native CI is to validate the exact resulting commit; no local full-suite or
  installed-package PASS is claimed by these targeted results.

Local Codex should first sync the exact repair, review its diff and reuse
retained private inputs for offline source/package verification. Do not issue
another SSH request, retry the consumed batch, reinstall or clean evidence.
Before any further field execution, the existing repository rule requires a
new exact batch approval chain; this repair and its tests do not supply one.
The next useful field milestone remains H01 → Q4 → H11 with original evidence
returned, rather than further side functionality.

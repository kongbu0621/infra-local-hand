# First-node P0/P1 primitive probe

`first_node_probe.py` is an explicitly invoked Linux fixture, outside ordinary
test discovery and the installed product. It supports the first-node work in
[the implementation plan](../docs/MULTI_NODE_IMPLEMENTATION_PLAN.md#7-按交付物推进).

Read-only configuration inspection:

```sh
sudo /usr/bin/python3 -I -B tests/first_node_probe.py --inspect --manager-config /protected/manager.json
```

Native synthetic isolation check, using the same configuration inspection:

```sh
sudo /usr/bin/python3 -I -B tests/first_node_probe.py --probe --manager-config /protected/manager.json
```

Store output privately: configuration identities, local paths and kernel facts
are deployment evidence. The inspector uses an explicit output allow-list;
credentials, private keys, task content and raw configuration are not exported.

The native mode creates one fresh `/run/lhp1…` fixture and one transient slice.
Five fixed Python workers use distinct unused numeric UIDs/GIDs, without adding
system accounts. A fixed `setpriv` launcher drops to each numeric identity and
clears all capability sets before Python runs; the short launcher alone receives
SETUID, SETGID and SETPCAP. This avoids relying on NSS entries for numeric systemd
`User=` settings. The system service leaves `User=` unset: systemd 255 can
drop SETUID on its explicit-UID/seccomp path before exec, while NoNewPrivileges
prevents restoration for the root launcher. The three-capability bound and
worker privilege checks remain in force. Actual real/effective/saved/filesystem IDs, empty supplementary groups and all five
zero capability sets are checked, including the replacement worker after UID reuse.
Each service has a 64 MiB memory ceiling, four processes, a
10% CPU quota, a 150-second lifetime and no capabilities. The parent is capped
at 512 MiB, 24 processes and 50% of one CPU. Workers write only tiny synthetic
files and use fixture Unix sockets; they do not call Local Hand or access NAS.
The first worker is capped before the aggregate slice properties are applied.

The probe records real kernel identities and limits, own-file/socket positive
controls, foreign-file/socket permission refusals and management-socket refusal.
Every response is bound to the expected PID, UID and command sequence, and must
contain exactly four file and four socket refusals with integer errno values.
An existing response file alone is insufficient: the service must still be
active with that PID when the coordinator observes it. That service observation
is included in the response record; a still-activating service is awaited within
the existing deadline. Before the stop check, the original worker must again
be observed active, so an already exited worker cannot satisfy that check.
It stops one worker and checks that the other four still answer under their
original PIDs. Before reusing the stopped worker's UID, it moves that worker's
files beneath a root-only retained directory; the new worker must be unable to
read either the old file or old socket. A missing file or disconnected socket
does not count as permission isolation.

Launcher stderr is retained in root-private fixture files (at most 64 KiB each)
and copied into a failed report before cleanup. A collected or failed launcher
causes an immediate failure instead of waiting for a missing readiness file;
exit code alone does not establish its cause.
Completed identity observations are retained incrementally if a later worker
fails to start or become ready. Old reports without live service observations
cannot retrospectively establish this additional observation-time check.

Only fixture units are stopped/reverted. Original fixture cgroups and their
parent slice must be empty or absent before generated files are removed or
parent limits reverted. A missing controller file does not prove cgroup absence;
an existing group without readable exit evidence remains uncertain.
Exit checks also require complete manager fields, no pending unit job, and zero
main/control PIDs for services. The returned `ControlGroup` path must be empty
or match the fixed original fixture path; another empty group cannot substitute for it.
The parent slice's manager state and quiescence check are recorded separately
from its current cgroup population. An empty slice with a pending job remains
uncertain, so its limits and fixture files are retained.
Uncertain cleanup is reported and
preserves the remaining fixture. Production service units, accounts, quota
allocations and existing tasks are not modified. Failure can be investigated
and followed by a fresh fixture; it does not lock the production executor.

`PASS` proves these selected OS primitives in this fixture. It does **not** prove
five Local Hand tasks, product manager/runner integration, quota allocation,
project exclusion, persistent queue recovery, OAuth, arbitrary-code sandboxing
or hardware saturation. Those remain separate implementation and acceptance
steps. In particular, copying the current single-task UID/IPC setup and changing
only its concurrency number is not a validated implementation.

The properties follow the host's systemd 255 contracts:
[execution identities and filesystem controls](https://www.freedesktop.org/software/systemd/man/255/systemd.exec.html),
[hierarchical resource controls](https://www.freedesktop.org/software/systemd/man/255/systemd.resource-control.html).
Private namespaces, cgroups and read-only mounts do not independently confer
cross-user data confidentiality; the positive and negative probes are required.

The launcher correction follows the corresponding [systemd 255 execution code](https://github.com/systemd/systemd/blob/v255/src/core/exec-invoke.c#L4431-L4491); local failure and subsequent acceptance remain separate evidence.

# Local usage and verification

## 客户端、Server、MCP 与 Tailscale 是什么关系

完整的术语解释、通信连接图、“查询任务状态”示例及网络与授权边界见
[README 的连接说明](../README.md#客户端servermcp-与-tailscale-是什么关系)。
下面继续介绍具体运行模式、命令参数与部署步骤。

## 控制器已退出、任务尚未下发时的管理员收尾

维护入口 `admin.local_hand_system_manager.unstarted_recovery` 不是 MCP 工具，也不是重新启动任务的入口。
仅在原控制器已经退出、同一启动环境和原始身份仍可证明、账本没有任何阶段下发时使用。
已执行任务、跨重启、缺失原 invocation、控制器或管理进程仍活动等情况不适用。
部署者须从已核验的原安装加载核心，并显式选择维护模块；不能从任意当前目录隐式导入代码。

必填参数为 `--current`（原受保护 current.json）、`--operation-id`、`--request-digest`、
`--serial` 和 `--archive-parent`（受保护的私有归档父目录）。身份参数必须来自原记录，
不能为通过校验而改成其他任务或新尝试。需本机管理员权限，但 SQLite 始终由其普通 owner 打开。
以单线程独立进程运行，保留默认 `SIGCHLD` 处理。忽略该信号或安装自定义回收处理器
会在读取任务前报 `RECOVERY_CHILD_REAP_POLICY`；入口不会自行改写调用方的信号设置。
无 `--apply` 时只核验，不更新应用账本；仍会使用 SQLite 读取锁／共享内存并另建私有诊断归档。

显式 `--apply` 会重新核验，而不是复用前次检查结果。通过后仅将原任务收尾为 UNKNOWN，
追加一条事件并释放已证明安全的执行占用，不删除配额目录、不封装成功证据或启动业务。
若最后回复丢失或写诊断失败，保留原归档，对同一身份再次调用以核对。已完成收尾
须与原不可变收尾事件一致，包括严格布尔退出证明及当前事件序号。存在矛盾则保留原件，
不报告重复调用成功；核对通过才返回 `ALREADY_COMPLETED`。
最终成功输出还要求子进程及本次资源清理完成。若提交后因清理失败而命令报错，
不能据此认定未提交；仍沿同一身份核对，不另行提交任务。
不要改 UUID、重跑原启动命令或重新提交任务来处理未知提交结果。
该结果不是业务成功、MCP 接入或完整部署验收。实现及验证边界见
[开发记录](DEVELOPMENT.md#控制器退出后的未下发任务收尾2026-10-22)。

## 作业入口与运行模式

先确认已部署服务的运行模式，再读取 `lh_capabilities`。Local Hand 的 MCP Server 提供网络入口，
`local-hand-jobs` 是本地 socket 客户端；它们可访问同一个后端，工具能力取决于该后端的模式及调用者权限。
`local-hand-mcp` 的四种启动模式互斥：

| 服务模式 | 任务来源与使用方式 |
| --- | --- |
| `--resident` | 常驻入口，由管理服务按已登记的能力准备资源。按 capabilities 的 `preparation`、profile 和获准引用调用 `lh_job_prepare`；`READY` 后将返回的完整 `request` 原样交给 `lh_job_submit` |
| `--prepared-task` | 预备单任务入口，部署者已准备一个固定任务。获准主体从 capabilities 获取 `prepared_request`，原样提交；保留其中的 UUID，不另行准备新任务 |
| `--session` | 执行会话入口，部署者提供已绑定的任务会话及请求。按该会话的固定请求提交，不提供常驻自动准备能力 |
| `--read-only` | 保留结果入口，沿原 ID 读取已有任务。只支持能力、状态和证据查询，不支持准备、提交、取消或核对执行 |

独立 `local-hand-broker` 提供 `--session` / `--read-only`；`local-hand-mcp` 还提供与其后端模式一致的维护 socket。
本地调用者使用部署者配置的 socket 路径和已映射身份，例如只读查询能力：

```sh
local-hand-jobs --socket /absolute/deployment/maintenance.sock lh_capabilities --json '{}'
```

常驻准备需要新的小写 UUID v4、`kind` 和 `profile_ref`；`workspace.edit`
还需要对应的 `inputs`。`PREPARING` 时使用原 UUID 和参数继续查询，准备本身不执行业务。
`FAILED` 时保留返回，修复原因后可用同一 UUID、原参数加 `retry_failed=true` 重试准备。
提交响应不明时沿原 `operation_id` 查询，不能把准备重试当作业务重放。

保存完整原请求与 `request_digest`。取消使用 `expected_request_digest` 和明确的 `target`；
取消整个原任务时为 `{"kind":"job"}`，随后查询退出证明。
重连后的 `lh_job_status` 查询与 `lh_job_reconcile` 核对执行是不同操作；当前常驻入口不提供后者。
只有已暴露且获准使用该工具的入口才能发起核对，并需保留该轮独立的 `reconcile_id`，使用原任务 ID 和摘要核对原效果。
证据按清单分页、按块取回；`lh_evidence_read_chunk` 的 `expected_sha256` 来自可信清单，
最终核对原任务关联、文件大小及完整摘要。

MCP 客户端应读取已安装服务暴露的工具 schema；源码中的当前参数定义见
[contract.py](../tools/local_hand_jobs/contract.py)，返回结构和工具说明见
[server.py](../tools/local_hand_mcp/server.py)。[作业架构](a2-execution/ARCHITECTURE.md#ax-a07-mcp-工具和二进制证据r03r04r07r08r09)
记录设计约束；其中的工具表不包含后来新增的准备与项目读取入口，不能替代当前工具发现结果。

## Archive and read a completed result locally

`local-hand-archive` is an optional Linux caller-side consumer of Artifact Ledger.
It accepts an already completed `SUCCEEDED / SEALED` task and retains the exact
ZIP, external manifest, seal, original status response and source information.
For `workspace.edit`, the ZIP includes the patch, before/after bytes and fixed
validation output. Nothing in the bundle is executed or applied.

Install a verified `infra-artifact-ledger` wheel alongside this package in an
independent Python 3.12 environment. This integration uses the public
`bounded-local-v0.1` library API, verified with Ledger `0.2.0a1` from commit
`6707a1b521c9c4718674620e6c584656bd434e4c`. The affected consumer suite also passes
with the 17 Ledger product modules in merged `58b08fa9cb188c48feec45592a0f775c7178fd7a`.
Build the selected fixed source using its
declared build dependencies; install the resulting local wheel with
`python -m pip install --no-index --no-deps /path/to/verified-ledger.whl`.
Ledger is not downloaded automatically or required for normal Local Hand use.

Retain the **raw authenticated `lh_job_status` response** (either the result
object or its successful `structuredContent` wrapper), plus the downloaded
`evidence.zip`, `evidence.manifest`, and `evidence.seal`. The caller must obtain
the status SHA-256 from that trusted response; hashing an arbitrary file does
not authenticate it. The archive verifies its identity, seal, manifest, ZIP
members and content digests against this supplied trust anchor.

```sh
local-hand-archive archive --store /absolute/private/archive \
  --producer local-hand:my-instance --status /absolute/retained/status.json \
  --status-sha256 TRUSTED_STATUS_SHA256 --evidence-dir /absolute/retained/evidence

local-hand-archive read --store /absolute/private/archive \
  --artifact-id RETURNED_ARTIFACT_ID --version-id RETURNED_VERSION_ID \
  --output /absolute/private/new-readback

local-hand-archive resume --store /absolute/private/archive \
  --producer local-hand:my-instance --operation-id ORIGINAL_OPERATION_ID
```

The store is a dedicated local directory, separate from execution ledgers and
source evidence. Use a persistent local filesystem supporting SQLite, directory
fsync and Linux create-only rename. All cooperating calls take a bounded,
nonblocking store lock. Do not point another writer directly at `ledger.sqlite`
or place the store on shared network storage. The output parent must exist;
read-back publishes a new directory and refuses to overwrite existing output.

`archive` returns one explicit Artifact ID and Version ID. This first consumer
maps each `(producer, operation_id)` to one immutable completed bundle, with
random owned IDs retained before either Ledger write. A later observation of
the same task/seal reuses the first status snapshot; changed request or evidence
bindings are conflicts. It does not choose a "latest" version, combine different
tasks into a version history or infer identity from filenames/digests.

If a response is lost, `resume` uses the saved original requests and bytes,
queries both original operations and checks their fingerprints before continuing.
It needs no original download directory. Create and append are separate Ledger
transactions: failure can leave the artifact identity committed without a version.
Keep the entire store, including pending directories, after errors. Nonzero exit
does not imply rollback; repeated successful calls return the same IDs and timestamp
without another version. A missing initialized database or corrupt payload is an
error, never an instruction to initialize again, repair history or rerun business.
The store also binds the database file identity and keeps a separate task
reservation before writing. Missing recovery directories and replaced databases
are conflicts; restoring the originals allows the same request to continue.
An existing task reservation is checked before database initialization, even
when the global marker is missing. Each confirmed create/append also gets an
immutable receipt outside SQLite before the caller reports success. If that
operation subsequently disappears or its timestamp changes, recovery rejects
the inconsistency instead of replaying it, including after an in-place database
rollback that preserves the file identity. The Artifact/Version record must also
retain the same timestamp as its own create/append operation; a disagreement is
rejected before continuing with another write. A failed receipt publication can
resume by querying the original operation; it does not require another commit.
New requests use a stable per-task idempotency scope as a second guard against
lost recovery files. Copying/replacing a database alone is not a supported store move; the explicit recovery binding below is required.
Existing v1 requests keep their original bytes and operation identities; their
first archive/resume adds guards without rewriting Ledger records. These guards
cannot establish whether a legacy database was replaced before that first use.
Receipts similarly preserve commits first confirmed by this consumer; losing
both the database history and its external receipts cannot prove an earlier
commit. Keep the whole store and retain failed attempts.

`read` needs only the store and explicit IDs. It verifies the actual bytes and
source bindings, then returns the original evidence files and `source.json`.
JSON responses use UTF-8 on stdout. The read-only commands `read`, `read-snapshot`
and `recovery-checkpoint` use `commit_state=not_applicable` on errors because they
never submit an archive transaction; local output may still have been published.
Other commands retain the relevant Ledger `commit_state` where known.
Archival success concerns preservation and read-back, not new
authentication, task execution, validation execution or knowledge admission.
Output delivery can fail after work has completed. A nonzero exit or missing
response does not prove that nothing was saved: retain the original store or
output directory and inspect its requests and receipts before continuing.
This local consumer does not establish A2 NAS recovery, A3's two consumer classes,
Windows archive support or the full Code Driver loop.

To run the affected checks with the verified optional wheel installed:
`python -B -m pytest -q tests/test_local_hand_artifact_archive.py tests/test_local_hand_jobs_evidence_client.py tests/test_local_hand_archive_recovery.py tests/test_local_hand_archive_snapshot.py`.
Without that wheel, the consumer integration tests are explicitly skipped;
the local bundle validation tests still run on Linux.

### Read an exact evidence version from a NAS snapshot

`read-snapshot` consumes a previously published Ledger snapshot through Ledger's
public recovery adapter. It preserves the original Artifact/Version and source
task identities. The adapter resolves the private storage binding and checks the
mounted target; Local Hand validates the exact evidence version. This path uses
Ledger `0.2.0a1` recovery APIs. The initial read-back used Ledger source
`78d6c5b07d47898083a47ac85d67cc5966b3760b`; the reviewed mount-alias isolation
fix is in `d83b665760dfc683fb60bccfcf99189ee231dba2`, submitted in
[Ledger PR #15](https://github.com/kongbu0621/infra-artifact-ledger/pull/15).
Use the paired fixed Ledger build for that protection. These source identities
are distinct even though the alpha package version is unchanged; see the
[review and installation record](DEVELOPMENT.md#gx10-成果的-nas-备份与准确读回2026-10-23).

```sh
local-hand-archive read-snapshot \
  --snapshot /absolute/approved-mount/archive/SNAPSHOT_ID \
  --storage-config /absolute/private/storage-config.json \
  --expected-manifest-sha256 TRUSTED_SNAPSHOT_MANIFEST_SHA256 \
  --artifact-id ORIGINAL_ARTIFACT_ID --version-id ORIGINAL_VERSION_ID \
  --scratch-parent /absolute/private/local-scratch \
  --output /absolute/private/new-snapshot-readback
```

Use the manifest digest from the independently retained original snapshot
receipt. The storage configuration is Ledger's existing mounted-storage schema;
physical paths and mount identity belong in deployment configuration, not task
inputs. For a supported local snapshot, omit `--storage-config`.

The output parent and scratch directory must already exist on a supported local
filesystem. Output paths containing `..` are rejected before restoration.
These writable directories must be outside the read-only input, including
paths that refer to it through another mount. Ledger owns this storage isolation;
different path strings or mount IDs do not establish different directories.
The command first restores and verifies a fresh local database; it
never opens SQLite on NAS. It retains `ledger.sqlite`, the Ledger restore response
in `snapshot-receipt/restore.json`, the five verified files in `evidence/`, and the
completed read response in `read-receipt/result.json`. Existing output is refused.
Use the complete original archive store for subsequent `archive` or `resume`
calls. A snapshot readback does not contain the consumer's original requests and
commit receipts. A populated database without its archive initialization marker
is rejected before another task is staged or committed; an empty database left
by interrupted initialization can still be resumed.
Keep partial output after errors; a fresh read may use a new local output
directory. Storage errors retain Ledger's `publication_state` and `stage`, which
refer to the local restoration, not a new NAS write.
The command never submits a Ledger transaction, so error responses use
`commit_state=not_applicable`; a failed read does not make the original archive
commit unknown. A receipt may become visible before a later synchronization
error, so its presence alone does not prove that the whole command completed.

This command does not publish another snapshot, resume archive writes, bind a
restored archive or execute the original task. NAS backup and exact read-back are
the snapshot branch of the [storage-node plan](MULTI_NODE_IMPLEMENTATION_PLAN.md#4-nas-成果归档最小新增实现).
An authenticated online receiver, automatic outbox and NAS MCP job entry remain
separate implementation work. Successful read-back does not establish those
capabilities or NAS power-loss durability.

### Filesystem identity after device renumbering

New stores use format v3 and bind the database inode to the filesystem ID returned
by Linux `fstatvfs`, while keeping the original identity in task reservations.
This permits a device number change when the same filesystem ID and inode remain.
The filesystem must provide a nonzero ID that persists across its remounts; this
change does not establish that property for every Linux filesystem. The
[Linux interface documentation](https://www.man7.org/linux/man-pages/man2/statfs.2.html)
explains that filesystem ID semantics vary. Copies/cloned filesystems, inode
reuse after deletion, and concurrent writers that bypass the store lock remain
outside the supported identity model. Older consumers reject new v3 stores.

Legacy stores retain their old device/inode checks. If a device number changes,
do not rewrite the identity files or initialize another database. When you have
a **trusted, previously retained SHA-256 of the complete current database**, close
all writers and run this local maintenance command:

```sh
local-hand-archive bind-filesystem --store /absolute/private/archive \
  --expected-database-sha256 TRUSTED_DATABASE_CHECKPOINT_SHA256
```

The digest is an explicit trust anchor, not a hash freshly taken from an unknown
or possibly rolled-back database. It must describe the intended current history;
the command cannot discover lost history when both records and external receipts
are missing. Without that checkpoint, retain the store and investigate its identity.

The command requires the original inode, rejects database sidecars (including
broken links), verifies the full Ledger and every retained commit receipt, and
checks the checkpoint again before publishing one immutable filesystem binding.
It preserves the original format, reservations, requests, database bytes and
receipts. Every existing reservation must match the original bytes required by
`resume`; changed formatting, extra fields or altered identity types are rejected
before a new binding is published, including when checking an existing binding.
Each confirmed request must match its retained task mapping: request
format, kind, idempotency scope/key, Artifact/Version IDs and source relationship.
Another task's valid request and receipt cannot stand in for the original ones.
An append confirmation also requires the original create operation, even if its
own receipt is missing.
It never initializes a store, executes an archive operation or recreates a missing
receipt. A partial archive remains partial; successful binding only establishes
filesystem continuity. A repeat with the same unchanged checkpoint reuses the
binding. The operation remains
bounded to one trusted local user and cooperating callers holding the store lock.
Afterward, use `read` with the original Artifact/Version IDs and `resume` with the
original producer/operation ID; these do not justify repeating the source task.

### Resume an archive after database restoration

With writers stopped and the original store isolated, capture a trusted checkpoint:

```sh
local-hand-archive recovery-checkpoint --store /absolute/private/original-archive > checkpoint.json
```

Retain the returned `checkpoint_sha256` independently. Preserve the entire archive directory, including original requests, receipts and old bindings. Restore the Ledger through its public snapshot API; retain that restore's `database_sha256`. Select and isolate the intended restored instance before enabling writes. Then bind its new physical file explicitly:

```sh
local-hand-archive bind-restored --store /absolute/private/restored-archive \
  --checkpoint /absolute/private/checkpoint.json \
  --expected-checkpoint-sha256 TRUSTED_CHECKPOINT_SHA256 \
  --expected-database-sha256 VERIFIED_RESTORED_DATABASE_SHA256
```

The binding checks the complete public Ledger export against the checkpoint, verifies the original consumer files and confirmed operations, and appends one immutable physical binding. It does not execute Ledger writes or finish a partial archive. Old `read`, `resume` and `archive` commands then keep their original identity and duplicate-submission rules. A successful old request returns its original IDs and timestamp; an unconfirmed original request can continue after its state is checked.

Both checkpoint and binding verification require every committed operation in this dedicated archive to have its original retained request. Losing both a task directory and its reservation is rejected even when the Ledger itself verifies successfully. Reservation bytes must match the original canonical form used by `resume`; do not reformat them. A staged task whose operations have not committed can still be preserved and continued.

If publication loses its response, repeat the same binding before new writes; an already matching binding returns `reused=true`. Once the archive advances, its old checkpoint is no longer a current binding input. Capture a new checkpoint before a later restoration; prior bindings remain preserved. Wrong content, changed consumer files, missing confirmed history, sidecars and replaced files are rejected. `read` and `recovery-checkpoint` can open an existing lock on a read-only mount; they do not create a missing lock. Read output still goes to a new writable directory outside the store.

For ordinary `read`, the output parent must also be physically outside the complete archive, including its consumer request directories and child mounts. Linux mount observations and held directory identities reject visible bind aliases before output publication. An unavailable observation fails without publishing, and can be retried after the cause is resolved. This check assumes stable mounts during access under the existing trusted-user profile; it does not provide atomic protection against a concurrent privileged mount replacement.

The checkpoint is a trust input, not authorization or automatic writer isolation. It requires a quiescent dedicated local store and the bounded public Ledger export (including its payload capacity limit). Archive commands share an exclusive lock, but external writers that bypass that lock must be stopped and isolated by the caller. File identity, size and timestamp checks detect changes; they do not prove quiescence, and same-size rewrites can share timestamps on some filesystems. Scanning stops at 4096 entries and 1 GiB of consumer files; each opened file's size is checked against the remaining byte budget before its content is read. Larger archives require a separately designed recovery profile. Failed `.pending-` entries count toward the scan budget, while their unpublished contents remain untraversed and outside the fingerprint. They are retained, never automatically deleted. Only the selected new recovery binding is excluded from the original inventory so publication retries work at the limit. These commands do not establish online backup, automatic failover, reboot isolation or an additional A3 consumer.

## Run the installed Ledger A2 local check

此临时阶段测试已退出正式新任务入口；原使用说明迁至[历史留档](history/LEDGER_LOCAL_A2_TEST.md)。
已有任务沿原 ID 查询、取消或取回证据；历史 `READY` 请求不能据此首次启动新执行。

## Land a verified workspace edit locally

After verifying a completed `workspace.edit` evidence bundle, extract its
`workspace-result.json`, `workspace-before.txt` and `workspace-after.txt`.
Use the result member's SHA-256 from the verified manifest. The local entry
point consumes these verified files; it does not authenticate evidence itself.
The local [Node Profile](#explicit-admission) repository name must match
`source_ref`, and its fixed validation with the returned `validation_ref` must
be explicitly replay-safe. This entry reuses the profile format; applying the
verified result does not submit another task through MCP or the Git mailbox.

```sh
python -m local_hand.workspace_apply --profile LOCAL_PROFILE --repository SOURCE_REF \
  --result workspace-result.json --result-sha256 VERIFIED_RESULT_SHA256 \
  --before workspace-before.txt --after workspace-after.txt \
  --expected-head OBSERVED_FULL_HEAD --output NEW_PRIVATE_ATTEMPT_DIRECTORY
```

This single-file local operation checks source ancestry, HEAD, index and file
digests against stored Git objects, ignoring local replace refs and grafts, then
uses the existing CAS writer and fixed validation runner. Unrelated
dirty files are allowed. A matching after-image skips the write and validates
locally after confirming file synchronization. Changed targets and staged reverts
remain conflicts; no merge or rollback overwrites them.
Successful completion also synchronizes the final target after validation and
binds read-back to that same file. Identical bytes from a validator's replacement
file alone do not confirm that the replacement has been synchronized.
On Windows the final synchronization requires a writable handle; failure to open
or flush that handle remains `UNCONFIRMED` without changing file permissions.
Git's working tree must match the registered repository directory throughout
the attempt. Linked worktrees are supported; redirecting `core.worktree` to a
different directory is a conflict, even when HEAD and file contents match.
Targets marked `assume-unchanged` or `skip-worktree` are rejected before writing
because Git can hide their actual changes. The flags are retained; once the
caller resolves them, a fresh attempt can proceed. Flag changes made during
validation are also conflicts.
Each attempt retains before/after content, final diff, validation output and
`report.json` outside the repository. The final Git diff uses no color, standard
`a/` and `b/` prefixes and three context lines so repository display preferences
do not make the patch unusable by ordinary `git apply`; Git configuration is retained.
A retry uses a fresh output directory and
checks current bytes first. No remote task is submitted, and no commit or push
is performed. The output parent must already exist; each attempt directory is new.

The cooperative write lease spans precheck, write, validation and final observation.
Use `--lease-root` when other Local Hand writers use a configured lease directory;
all cooperating writers must use the same root. Final checks cover HEAD, index
entries and their assume-unchanged/skip-worktree flags, target bytes/mode,
other tracked Git differences, and nonignored untracked
entry metadata (up to 1000 files). Git observations retain the existing 2 MiB
output bounds. Validation is trusted local code, not a filesystem sandbox; ignored
outputs and effects outside the checkout are not covered by these comparisons.
Pre-existing hidden flags on unrelated paths are retained; those paths do not
receive independent byte comparisons beyond what Git reports.
The held lease's repository identity is rechecked before writing, before validation
and at final observation. Replacing the checkout cannot yield a successful result
even when its contents match. Attempt directory identity is checked around each
record publication; detected replacement stops publication and leaves the original
records in place. These checks do not sandbox a hostile concurrent filesystem writer.

Interruptions, incomplete synchronization and report-storage failures remain
`UNCONFIRMED`. If publishing a report fails, the CLI return retains the write state
and error; a pending or visible candidate file is not a persistence acknowledgment.
Previously completed remote tasks and failed local attempt records are retained.

## Build and install

Use Python 3.12 and a clean committed checkout. Build and runtime environments
must be newly created directories. Choose a new absolute work directory first;
the following names are examples, not live deployment defaults.

```sh
python3.12 -m venv /absolute/new-work/build-venv
/absolute/new-work/build-venv/bin/python -m pip install -r requirements-build.txt
/absolute/new-work/build-venv/bin/python -m pytest -q
/absolute/new-work/build-venv/bin/python -m compileall -q tools tests
/absolute/new-work/build-venv/bin/python -m build --wheel --no-isolation --outdir /absolute/new-work/dist
python3.12 -m venv /absolute/new-work/runtime-venv
/absolute/new-work/runtime-venv/bin/python -m pip install --no-deps /absolute/new-work/dist/infra_local_hand-0.2.0a1-py3-none-any.whl
cd /absolute/new-work
/absolute/new-work/runtime-venv/bin/python -I /absolute/checkout/tools/verify_installed.py --wheel /absolute/new-work/dist/infra_local_hand-0.2.0a1-py3-none-any.whl --run-root /absolute/new-work/acceptance
```

On Windows, venv Python is `Scripts/python.exe`. The source test suite and
installed direct-action tests are portable; the installed CLI transport fixture
is POSIX-specific and reports SKIP on Windows. Preserve its report and logs.
For a second candidate, retain prior artifacts and use new build/runtime paths.

### MCP runtime dependencies

The commands above install the base wheel with `--no-deps`. The MCP entry also
needs the optional `[mcp]` runtime dependencies; the base install alone cannot
start the MCP service. For the verified CPython 3.12 / Linux x86_64 target, install
the repository's complete hash-locked dependency set into that same new runtime:

```sh
/absolute/new-work/runtime-venv/bin/python -m pip install --require-hashes -r /absolute/checkout/requirements-mcp-linux-x86_64-py312.lock
/absolute/new-work/runtime-venv/bin/python -m pip check
```

The lock includes the versions declared by `[mcp]` in [pyproject.toml](../pyproject.toml).
Other Python/platform targets need their own resolved lock and verification;
the Linux x86_64 lock is not portable to every host. Installing dependencies does
not create a broker policy, execution session, resident manager or external
authentication configuration. Choose the [entry mode](#作业入口与运行模式), then supply
that deployment's existing configuration. `local-hand-mcp --help` lists the
required policy, mode, authentication and port arguments; it does not verify a
working deployment.

### Job service deployment inputs

`local-hand-mcp --config` and `local-hand-broker --policy` load a protected job
policy with schema `lh-policy-v1` or `lh-policy-v2`, including deployment identity,
principals, resource references and budgets; see [policy.py](../tools/local_hand_jobs/policy.py).
MCP's separate `--auth-config` uses `lh-mcp-auth-v1` to bind the external issuer,
resource and authorization settings; see [auth.py](../tools/local_hand_mcp/auth.py).
Local Hand is the resource server: it validates tokens but does not implement
the login page, authorization-code exchange, token issuance or refresh service.
Those belong to a separately deployed OAuth/OIDC identity service; installing
this package or writing `--auth-config` does not provision it. See the
[component ownership and authentication flow](../README.md#认证服务在哪里实现).
For resident mode, `--resident` names a `local-hand-resident-adapter/v1` routing
descriptor that connects to the existing management service. It is separate from
both the broker policy and the manager's own configuration.

The protected `lh-mcp-auth-v1` configuration optionally accepts
`"document_proxy_url": "http://127.0.0.1:3128"` (example port only). This selects
a local HTTP CONNECT proxy for issuer discovery and JWKS reads; allowed proxy
hosts are `localhost`, `127.0.0.1` and `[::1]`, with an explicit port from 1 to
65535 and no credentials, query, fragment or non-root path. Omit the field or
use `null` for the previous direct-connect behavior. Authorization URLs on those
loopback hosts always bypass the proxy. TLS certificate verification remains
enabled, redirects remain disabled, and proxy failure does not fall back to
direct access. Environment proxy variables are still ignored (`trust_env=False`).
This setting neither starts the proxy nor configures the browser, MCP client,
token endpoint requests made by the client, or job subprocesses.

Older releases reject this new configuration field. When rolling back to an
older release, restore its compatible authentication configuration as well;
do not change issuer, audience or subject ownership to work around connectivity.
Check discovery and JWKS under the actual service account before declaring
authentication ready.

MCP startup now validates both discovery and at least one usable signing key
before accepting HTTP requests. Transient discovery/JWKS read failures receive
bounded retries within a shared 60-second startup deadline; invalid metadata,
TLS certificates or key material fail immediately. The first token uses the
same validated key cache, with the existing TTL and rotation cooldown. This
public-document check does not prove login, signing, refresh or external routing;
verify those separately after installation or an authentication configuration
change. The local task manager remains independent of this network startup.

The preparation and execution components under `tools/admin/` are deployed
separately by the operator; they are **not included in the wheel's packages**.
The source entry points are [resident_service.py](../tools/admin/local_hand_system_manager/resident_service.py)
for persistent preparation and [task_service.py](../tools/admin/local_hand_system_manager/task_service.py)
for task execution. They require the deployment's configured accounts, protected
directories, process management and resource setup. Use the existing deployment's
bound configuration when connecting to it; installing the wheel or its MCP
dependencies does not provision these components.

## Explicit admission

The Node Profile format below is shared by the legacy `local-hand-worker` /
`local-hand-connect` entry and the current [local workspace application](#land-a-verified-workspace-edit-locally).
The mailbox/controller steps here and **Installation provenance** below apply
to the legacy Task/Result and Git mailbox entry.
The Node Profile below is not a job broker policy, MCP authentication config or
resident descriptor. For the MCP / `local-hand-jobs` backend, use the
[job service deployment inputs](#job-service-deployment-inputs) above.

Node Profile requires exactly `profile_schema`, `node_id`, `projects_root`,
`repositories`, `transport_policy`. The schema is `local-hand-profile/v2`.
Each repository requires `path`, boolean `single_writer`, and `validations`.
Each validation has fixed `argv`, finite numeric `timeout_seconds` in (0,3600],
and boolean `replay_safe`. Missing and unknown keys are rejected.

Transport policy requires exactly `schema_version`, `remote_url`,
`allowed_remote_urls`, `branch`; schema is `local-hand-git-mailbox/v1`.
Supported remotes are explicit `user@host:owner/repository.git` or
`ssh://user@host[:port]/owner/repository.git`. Every admitted spelling must be
listed and name the same SSH user/host/port/repository. No local/file/HTTP remote
or implicit branch is accepted. Synthetic examples are in the test fixtures.

Use `python -m local_hand.config --profile PROFILE --repository NAME` to check
a profile before installation. Controller `init`, `submit`, `wait`, and `call`
require `--policy FILE`. `build` remains offline. A controller mailbox has a
create-only admission marker; changing policy requires a newly admitted clone.
Worker's optional `--mailbox-branch` is an assertion against the profile.
`wait` and `call` additionally require `--expected-provenance-file`; that file
must contain the exact admitted `implementation_commit`, `package_digest`, and
`profile_digest`. A result is never accepted without this source policy.
`call` rejects invalid wait timing before submitting a task. When the fetched
mailbox contains both a canonical result and a conflict for the exact task
digest, `wait`/`call` validate and return the conflict first. Invalid conflict
identity, provenance, or a conflict claiming success fails closed.

## Installation provenance

An installed worker requires a create-only record from
`python -m local_hand.installation --help`. Supply the retained original wheel,
profile, installation UUID, runtime Git/SSH/key/known_hosts absolute paths,
state and mailbox roots. Match these bindings at startup using
`LOCAL_HAND_INSTALL_RECORD`, `LOCAL_HAND_INSTALL_INSTANCE_ID`, and the runtime
path variables shown in that module. Do not modify an existing installation
record to migrate an environment. Every returned result binds the actual build
commit, core digest and raw profile digest.

The Linux/Windows service bootstrap scripts remain source-staging installers:
they require a clean Git checkout and stamp copied source, not a wheel install.
Their required profile/repository/state/run-user inputs replace deployment
defaults. Their presence inside the wheel does not make them wheel installers.
Do not invoke them for S1 live deployment; service cutover is S2 scope.

Old profiles, controller markers and state directories are not silently
upgraded. Preserve them and use an explicit separately authorized migration.

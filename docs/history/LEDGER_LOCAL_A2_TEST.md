# Ledger 本地 A2 临时测试留档

`ledger.test.local_a2` 是为 Ledger A2 阶段设计的固定合成测试，绑定指定源码、安装环境和
`tests/installed_snapshot_walkthrough.py`。它不接收用户数据，也不是日常备份、恢复或维护接口。
现有需求没有要求把这条阶段验证路径作为长期服务；需要复查安装结果时，按 Ledger 自身的测试说明
使用本地测试脚本，并复用仍适用的既有证据。因此本仓将其归入临时测试历史，不新增“验收模式”开关。

## 当前处理

- 正常能力发现、准备及提交的公开输入声明不再列出这个 kind。旧运行环境登记不能重新开放它。
- 新任务准备、旧准备的重试/刷新、新任务接收及尚未启动控制器的首次启动均拒绝；不删除旧任务或改写未知结果。
- 保留原 UUID、kind、请求摘要、测试实现和证据。原身份仍可查询状态、取消在途任务、读取封存证据。
- 历史准备调用只返回原准备状态/请求；`READY` 不表示现在可以首次提交。历史提交的同 ID 核对
  只返回原已接收任务，不能重放业务。历史配置仍可读取，以便恢复这些记录。
- 旧控制器仍在运行时，停用类型的提交转为原任务状态查询，并核对任务 ID 和请求摘要；
  不向旧版本转发提交。查不到原任务就如实返回，不能据此新建或换 ID 重试。
  已接收的在途任务不会因升级被自动取消；需要停止时仍沿原任务申请取消并确认退出。

这些是源码边界；已有部署只有升级到包含此修改的版本后才生效。此文不证明运行服务已更新。
跨版本部署仍需按原维护流程登记与实际读取版本匹配的只读策略，保持原任务身份和存储目标，
保留旧配置。历史 kind 兼容不豁免源码与安装载荷校验，也不证明旧配置能直接套用新读取器。
未来是否需要正式的维护验收接口，应先确认具体维护场景、输入、输出和重复使用需求，再单独设计。

## 原使用说明（历史快照）

下面原文来自本次修改前的 [USAGE](https://github.com/kongbu0621/infra-local-hand/blob/a532ed14becb9de5b1f9910dcf21fd5ad9f21e1c/docs/USAGE.md#run-the-installed-ledger-a2-local-check)，
用于解释旧配置、旧任务和证据。**其中的新建、登记启用及提交步骤已不适用于当前版本，不应照此启用作业。**

## Run the installed Ledger A2 local check

`ledger.test.local_a2` is an optional fixed job for continuing Ledger's installed
snapshot/recovery acceptance with an existing runtime. It executes the pinned
`tests/installed_snapshot_walkthrough.py` once, using that venv's Python with
`-I -B`, a new task-owned `local-parent`, and the registered source commit. It
passes no storage configuration and does not enable NAS jobs. The eight required
calls are API and CLI `create`, `verify`, `restore`, and `check_restore`.

Before preparing a new task, reuse any retained result that already covers the
same installation and execution environment. Keep an uncertain attempt on its
original operation ID and query it; do not prepare a replacement just because a
response was lost. A failed run retains its synthetic directories and logs.

The operator registers the existing runtime in the protected resident manager
configuration under `local_a2.runtimes[REF]`. Each descriptor has these fields:

| Fields | Binding |
| --- | --- |
| `source_root`, `source_commit`, `source_blobs` | Retained Ledger source and actual build-source SHA; all 17 runtime modules plus the fixed smoke script, using `local_a2_jobs.SOURCE_BLOBS` |
| `runtime_root`, `runtime_python`, `runtime_python_realpath`, `runtime_python_sha256` | Existing isolated venv, its original Python invocation path, and the explicitly resolved interpreter bytes |
| `venv_config_sha256`, `console_script_sha256` | Existing `pyvenv.cfg` and `bin/artifact-ledger` entry point |
| `package_root` | Installed `infra_artifact_ledger` package directory inside that venv |
| `wheel`, `wheel_sha256` | Retained wheel file and SHA-256, compared with source and installed payload |

The descriptor is a trusted operator registration, not a caller claim that an
arbitrary venv was produced by `ledger.prepare`. The source commit must come from
the retained build record; the smoke script itself does not attest a Git commit.
Preflight verifies fixed source bytes, wheel and installed module contents,
interpreter and entry point. A bounded probe uses the same interpreter with
`-I -S -B` to verify that the interpreter's actual import search selects the
registered package before enabling site processing or importing Ledger. It
compares the 17 modules' current-interpreter, unoptimized bytecode candidates
with compilation of the verified source, including nested code fields such as
stack size and qualified names that normal Python code-object equality omits.
Other interpreter and optimization caches are left unread and unchanged; neither
fixed business command enables optimization. The runtime must exclude system site packages
and unregistered startup hooks. The sole permitted `.pth` file is the exact
standard `distutils-precedence.pth`; the fixed environment sets
`SETUPTOOLS_USE_DISTUTILS=stdlib` for both the walkthrough and its CLI children,
so that file does not load `_distutils_hack`. On Debian/Ubuntu Python 3.11/3.12,
the probe restores the verified venv prefixes before asking the interpreter for
site directories, without running site initialization. A standard-library
`sitecustomize.py` is admitted only when it is exactly empty, or contains the
exact Apport hook with `apport_python_hook` absent from the actual import search.
In either case its selected bytecode must match that inert source; an empty
source cannot hide executable cached code. Other startup modules remain rejected.
A shadow `bin/pyvenv.cfg` or an `._pth` search-path override beside the invoked or resolved interpreter is
rejected before starting that interpreter. The base interpreter and its standard
library remain trusted deployment inputs. Original files remain read-only; the
venv is not rebuilt, copied, or cleaned. Private paths and build receipts stay in
the deployment.

The same manager `local_a2` object supplies explicit `budgets`, `limits`, and
per-role `quotas` in the existing resident preparation format. `budgets.nas_bytes`
must be zero; the existing three-phase resource checks remain in force. The ordinary MCP
adapter descriptor has only `local_a2: {"runtime_refs": [REF], "budgets": BUDGET}`;
it never receives the private runtime descriptor. Preparation creates a task
policy with only the selected runtime and grants `runtime_refs` for that task.
Old deployment descriptors need no new field. Omitting this registration leaves
the capability unavailable for new attempts. The resident registration is shared
by principals admitted by the manager and authorized for submit by the entry
policy; historical task-specific kind/runtime grants do not define this dynamic
registry. Each generated task policy grants only its selected runtime to its
owner. Entry scope checks and durable revocations remain effective.

Removing a runtime registration prevents new attempts. Polling an existing
preparation with its original owner, UUID and inputs still returns the original
READY request or retained preparation state, including after an interrupted
response or restart. This does not refresh an expired request or rerun a failed
attempt; a new attempt requires the current registration again.

Use the existing private maintenance procedure to install the reviewed Hand
revision and update these two configurations, preserving historical installs,
task catalogs, ledgers and evidence. Refresh the connected tool schema after the
service update. Do not use `workspace.edit` to change the running service or to
execute a shell command. No new maintenance endpoint is required.

Then use the direct MCP tools:

1. Read `lh_capabilities`; require `ledger.test.local_a2` and the intended
   `runtime_ref` in the returned profile.
2. Call `lh_job_prepare` with a new UUID, that `profile_ref`,
   `kind="ledger.test.local_a2"`, and `inputs={"runtime_ref": REF}`. Poll
   `PREPARING` with the same inputs and UUID. Preparation does not run Ledger.
3. Submit the exact `READY.request` once, and query that operation until exit and
   durable sealing. Cancellation and interrupted-response recovery use the
   existing task tools and original request digest.
4. Fetch and verify the complete evidence bundle. Require the fixed script's
   strict PASS report, all eight calls, matching installed identity, and the
   actual execution filesystem. Record `nas_publish_flow=NOT_RUN` and
   `nas_loss_exercise=NOT_RUN` separately from the local result.

The scratch parent **inside the execution namespace** must be actual ext4, XFS,
or Btrfs supported by Ledger. Its production filesystem check rejects overlay
and tmpfs before creating synthetic data. The registered outer task deadline and
resource limits remain authoritative; the script's per-operation timeout is not
a promise about whole-task elapsed time. Source tests and modeled quota/service
tests do not establish this installed or field result. This job does not replace
the separate Ledger resource-boundary or NAS acceptance work.

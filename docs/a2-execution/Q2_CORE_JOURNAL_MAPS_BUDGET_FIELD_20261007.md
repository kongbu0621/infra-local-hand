# Journal MB2：累计 FD 条目上限拒绝

2026-10-07（Asia/Shanghai）。**唯一 MB2 替代预检窗口 CONSUMED / FAILED；journal 维护未开始。**
本记录依据 Owner 在当前对话返回的终端截图，以及准确冻结 D 的静态源码解释。
没有重跑预检、sudo/writer、SSH、proc 扫描或补采，没有修改现场、阈值、覆盖或预算。

## 准确链与证据来源

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，沿用本会话已直接读取并验证的固定规则。
- A：`d18b490a7cdb63ee43044a29a89746ef78fccff3`，
  `LH-Q2-CORE-JOURNAL-MAPS-BUDGET-v1` / MB1–MB2。
- [准确 Owner B](../governance/Q2_CORE_JOURNAL_MAPS_BUDGET_OWNER_DECISION.md)：
  `LH-Q2-CORE-JOURNAL-MAPS-BUDGET-CLOSURE-20261007-01`。
- 独立 C：`3d928a323d1aad12c20a66594bb295d4df14fab0`。
- 截图执行候选 D：`68b63da88d70cfb8151f66a75c7f523baaf012d2`，tree
  `6b5a5b993aac33132e3a2e64f6ac318add0bd6d3`。
- [MB1 验证与冻结记录](Q2_CORE_JOURNAL_MAPS_BUDGET_REVIEW_20261007.md)及准确 D 的
  [CI 37500889014](https://github.com/kongbu0621/infra-local-hand/actions/runs/37500889014)
  保留原有证据范围，不替代现场准入。

来源事件：`LH-Q2-CORE-JOURNAL-MB2-RETURN-20261007-01`。截图桌面时钟显示 10 月 7 日 08:37，
不是程序的精确起止时间。上方还含旧 v1/v2 返回；以下仅登记底部新的 `LH_Q2_MB2_SUMMARY`。
截图、完整原文与实际 PID/TID 保留于私有对话/终端，不进入公共仓库。

## 选择性转录

以下不是完整 JSON 重建，也不是对原始流或宿主状态的独立认证：

| 字段 | 新返回 |
| --- | --- |
| `D` | `68b63da88d70cfb8151f66a75c7f523baaf012d2` |
| `phase` / `state` | `preflight` / `BLOCKED` |
| `exit_code` / `child_exit` | `3` / `3` |
| `child_checkpoint` | `1` |
| `error_type` | `ObservationError` |
| `reason` 与 `child_failure.reason` 的固定阶段 | `GROWTH_PROC_LIMIT_FD_TOTAL` |
| reason 中的首次拒绝值 `N` | `262145` |
| reason 中的原上限 `MAX` | `262144` |
| 父层/child failure 的 `errno` | 均为 `null` |
| `marker_created` / `ssh_requests` | `false` / `0` |
| `writer_report_count` | `0` |
| `last_step` / `started` | 均为 `null` |
| shell 保留的 CLI JSON 长度 | `671` B |
| writer stdout / stderr 长度 | `685` B / `0` B |

完整 reason 还带有 PID/TID；这里明确省略这些私有值，不冒充完整 reason。
没有取得完整 JSON/child stdout，也没有独立验证截图中的摘要。零成功报告不表示没有失败报告。
`LH_Q2_MB2_PREFLIGHT` / `LH_Q2_MB2_RESULT` 及旧变量应继续保留在原终端。
command substitution 去除了末尾换行，因此 671 B 不能标为原始 CLI stdout 长度。
本执行者未从其它进程读取这些变量或重建输出。

## 准确源码解释

`collect_image_writers()` 对每个 task 获取初始 FD snapshot，再逐条累加 `totals[1]`，调用：

```python
_proc_limit("FD_TOTAL", totals[1], 262144, pid, tid)
```

等于上限仍允许，大于上限立即拒绝，所以本次首次拒绝值比原上限多 **1**。
这是逐 task 的初始 FD snapshot 条目累计量；同一进程的多个 task 仍各自计数。
它不是宿主唯一打开文件数、某一进程实际 FD 上限，也不是 observer 的 `RLIMIT_NOFILE=128`。
初始 snapshot 在此累计循环前已对条目执行 stat；该累计数也不含后续 snapshot 复核及匹配项
的额外 fdinfo/stat 读取。因此不能将 262144 描述为全部内核读取或 stat 调用的硬上限。

准确 D 的既有 `test_fd_total_counts_repeated_per_task_snapshots` 已覆盖四份 65536 条目
snapshot 恰好通过、第五份首条在 262145 拒绝，源函数和生成 payload 共用此测试。
MB1 没有修改该上限或计数算法；本次文档登记无需重复既有隔离测试，也未运行现场探针。

FD 检查先于当前 task 的 maps 读取；首次 FD 拒绝不能证明全量 maps 扫描已通过，也不能
证明固定 512 MiB 已足够。首次超限值不是完整扫描需求，不能据此认定只增加 1 就能完成。
PID/TID 只是拒绝时的扫描上下文，没有各 task 明细，不能归因于某个应用或认定唯一原因。
尚无完整扫描、writer 排他性或后续维护准入证明；旧窗口的 UNKNOWN 不由本次返回追补。

## 消耗与边界

截图字段与准确源码顺序表明，本交接路径在 checkpoint 1 停止，没有进入 execute。
该路径未创建 marker、发送 SSH 或开始正常关机、备份、镜像增长、VM 启动、ext4 增长及
H01/Q4/H11；没有维护 receipt 或 journal 扩容成功证据。这不是宿主其它活动的完整盘点。

窗口一旦开始即消耗，无 marker 不返还授权。MB2 与全部旧窗口继续保持已消耗；准确候选、
交接和输出只作保留证据，不得重跑、清除 STARTED、换 shell/session/候选或删除对象重开。
没有额外预检、sudo/writer 探测、补采、重试、重连、清理、恢复或预算自动调整授权。

任何后续方案应先整体审阅逐 task 扫描覆盖、FD/maps 计数、资源上限与原期限的关系。
提高 FD 上限、去重、跳过 task 或再开窗口都不是本次批准内的静默修复；实质变更及新窗口
须有准确 A、Owner B 和独立 C。本记录仅解释和登记失败，不提出未经核验的新阈值。
原认证、全部检查、15s/900s/780s、除已批准 maps cap 外的预算和累计维护次数保持，
H01/Q4/H11 及扩展支线继续不执行。

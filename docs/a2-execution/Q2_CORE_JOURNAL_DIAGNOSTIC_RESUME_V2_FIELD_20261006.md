# Journal v2 DR2：累计 maps 文本上限拒绝

2026-10-06（Asia/Shanghai）。**唯一 v2 替代预检窗口 CONSUMED / FAILED；journal 维护未开始。**
本记录依据当前对话 Owner 返回的真实终端截图，以及准确 D 的静态源码解释。
没有重跑预检、sudo/writer、SSH、proc 扫描或补采，没有修改阈值、覆盖、预算或现场对象。

## 准确链与证据来源

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，沿用已读取并验证的直接固定规则。
- A：`4341487c9be9ef64cf6fccbd973ed438a66e7483`，
  `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v2` / DR1–DR2。
- [Owner B](../governance/Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_V2_OWNER_DECISION.md)：
  `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-V2-CLOSURE-20261006-01`。
- 独立 C：`807d61b75841a416064f4c1ec1d7c2e0187e0d49`。
- 截图中的执行候选 D：`4236ac62e61c0cdf62b49f3620c325454e8fba99`，tree
  `7e26a8a4267fa2379eff9dea92ecfb853633f6ef`。
- [DR1 验证与冻结记录](Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_V2_REVIEW_20261006.md)及准确 D 的
  [成功 CI 37482894717](https://github.com/kongbu0621/infra-local-hand/actions/runs/37482894717)
  保持原含义；成功 CI 没有替代现场准入。

来源事件：`LH-Q2-CORE-JOURNAL-DRV2-RETURN-20261006-01`，当前对话 Owner 在交接后返回的截图。
截图桌面时钟为 23:11，不作为精确开始/结束时间。截图也显示早先 v1 的输出，以下只登记底部
`LH_Q2_DRV2_SUMMARY` 的新返回。截图、完整原文及实际 PID/TID 保留在私有对话/终端，不进入公共仓库。

## 选择性转录

以下不是重新构造的完整 JSON，也不是对原始流或宿主状态的独立认证：

| 字段 | 新返回 |
| --- | --- |
| `D` | `4236ac62e61c0cdf62b49f3620c325454e8fba99` |
| `phase` / `state` | `preflight` / `BLOCKED` |
| `exit_code` / `child_exit` | `3` / `3` |
| `error_type` | `ObservationError` |
| `child_checkpoint` | `1` |
| `reason` 与 `child_failure.reason` 的固定阶段 | `GROWTH_PROC_LIMIT_MAPS_TOTAL_BYTES` |
| reason 中的首次拒绝值 `N` | `67115642` B |
| reason 中的原上限 `MAX` | `67108864` B，即 64 MiB |
| 父层/child failure 的 `errno` | 均为 `null` |
| `marker_created` / `ssh_requests` | `false` / `0` |
| `writer_report_count` | `0` |
| `last_step` / `started` | 均为 `null` |
| shell 保留的 CLI JSON 长度 | `700` B |
| writer stdout / stderr 长度 | `700` B / `0` B |

完整 reason 还含有有界 PID/TID；本表是明确省略这些私有值的选择性转录，不冒充完整 reason。
未取得完整 JSON/child stdout，未独立校验截图中的摘要。零成功报告与保留了失败报告并不矛盾。
`LH_Q2_DRV2_PREFLIGHT` / `LH_Q2_DRV2_RESULT` 应继续留在原终端，旧 `LH_Q2_DR2_*` 变量也保留。
command substitution 已去除末尾换行；700 B 的 shell 文本不能标为原始 CLI stdout 长度。
本执行者没有从其它进程读取这些变量或重建输出。

## 源码解释及限度

准确 D 的 `collect_image_writers()` 对每个 task 读取一次受原单文件 1 MiB 上限约束的
`maps`，将 `len(maps)` 加入 `totals[2]`，随后在同一位置调用：

```python
_proc_limit("MAPS_TOTAL_BYTES", totals[2], 64 * MIB, pid, tid)
```

`_proc_limit` 只在 observed 大于 cap 时拒绝，并使用该判定已有的数据生成 reason。
因此截图报告的本次首次拒绝差额为 **6778 B**。它是逐 task 累计读取的文本字节，不是进程 RSS、
唯一映射量、journal 可用容量或宿主完整 maps 总量。扫描在首次超限处停止，没有继续枚举/读取
来计算总需求；不能据此宣称把预算增加 6778 B 就足够。

同一进程的多个 task 按原实现分别读取、分别计入累计量。源码及既有隔离测试明确保留此语义；
截图没有各 task 明细，不能归因于某个应用、线程数量、单个 maps 文件过大或确定的重复量。
PID/TID 只是首次拒绝时的扫描上下文，不足以认定该进程是唯一原因。

父层源码按现有五字段 schema、允许的 request 规则、reason/errno 约束接受失败报告，随后传播
具体原因。此处只是对截图返回与准确源序的解释，没有把缺失的原始报告视为已独立验证。
已明确的是**本次返回的拒绝阶段与首次计数**，不是完整扫描通过或 writer 排他性证明。
旧 v1/T3 的具体触发分支、计数和其它历史 UNKNOWN 均不由本次结果追补。

## 消耗和后续边界

依据截图阶段/计数及准确源码顺序，本次在 checkpoint 1 停止，没有进入 execute。
本交接路径的 marker、SSH、正常关机、备份、镜像增长、VM 启动、ext4 增长及 H01/Q4/H11
均未发生；没有维护 receipt 或 journal 扩容成功证据。这不是对宿主其它活动的完整盘点。

新窗口已经开始即消耗；无 marker 不返还窗口。v2 与全部旧窗口保持失败/已消耗。
准确 D、交接文本和已有输出只能保留为证据，不得再次执行、清除 STARTED 变量、换 shell、
换 session/候选或删除对象来重开。没有额外预检、权限探测、补采、重试、重连、清理或恢复授权。

本次诊断已定位实际拒绝类别；后续若要解决准入问题，应先审阅扫描覆盖与资源预算设计。
提高 maps 上限、按进程去重、跳过 task 或改变观察量都不能作为 v2 内的静默修复。
任何这类实质变化或另一次现场窗口均须自己的准确 A、Owner B 和独立 C；本记录不批准它们。
当前只完成源码解释和结果登记，没有实现变更或新现场方案。原 15s/900s/780s、全部检查、预算
和累计维护次数保持，H01/Q4/H11 及扩展支线继续不执行。

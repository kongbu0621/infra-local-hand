# Journal W2：PID 复核阶段一致性拒绝

2026-10-07（Asia/Shanghai）。**唯一 W2 替代预检窗口 CONSUMED / FAILED；journal 维护未开始。**
依据 Owner 返回的终端截图，以及准确 D 的静态源码解释。没有重跑、补采、现场 proc 读取、
sudo/writer 探测或 SSH，没有修改阈值、覆盖、协议、期限或现场对象。

## 准确链与来源

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，沿用本会话已读取并核验的直接固定规则。
- A：`42a66be98c45e817e866d3fb86a1c184c2ce55f9`，
  `LH-Q2-CORE-JOURNAL-SCAN-WORK-v1` / W1–W2。
- [Owner B](../governance/Q2_CORE_JOURNAL_SCAN_WORK_OWNER_DECISION.md)：事件
  `LH-Q2-CORE-JOURNAL-SCAN-WORK-CLOSURE-20261007-01`。
- 独立 C：`1f656f7dab12ddb02c6927d3fc08c2fbe81ffebc`。
- 截图执行候选 D：`57c7f8e19e047d8caeea401593d8e4bbd4dc373d`，tree
  `3d77eee6ad4b41de2c7a4aad29bbd17335d65e11`。
- [W1 验证与冻结](Q2_CORE_JOURNAL_SCAN_WORK_REVIEW_20261007.md)及
  [准确 D CI 37555791202](https://github.com/kongbu0621/infra-local-hand/actions/runs/37555791202)
  保留源码/隔离验证的含义，不替代现场准入。

来源事件：`LH-Q2-CORE-JOURNAL-W2-RETURN-20261007-01`。Owner 在当前对话提交的截图桌面时钟
显示 10 月 7 日 09:54，不是程序精确起止时间。上方包含旧 v1/v2/MB2 输出；以下只登记底部
新的 `LH_Q2_W2_SUMMARY`。原截图和完整终端输出保持私有，不复制进公共仓库。

## 选择性转录

以下是截图中可见字段，不是重建的完整 JSON 或对原始流/宿主状态的独立认证：

| 字段 | 新返回 |
| --- | --- |
| `D` | `57c7f8e19e047d8caeea401593d8e4bbd4dc373d` |
| `phase` / `state` | `preflight` / `BLOCKED` |
| `exit_code` / `child_exit` | `3` / `3` |
| `child_checkpoint` | `1` |
| 父层及 child failure 的 `reason` | `GROWTH_PROC_DRIFT` |
| `error_type` | `ObservationError` |
| 父层及 child failure 的 `errno` | 均为 `null` |
| `marker_created` / `ssh_requests` | `false` / `0` |
| `writer_report_count` | `0` |
| `last_successful_writer_progress` | `null` |
| `last_step` / `started` | 均为 `null` |
| shell 保留的 CLI JSON 长度 | `950` B |
| writer stdout / stderr 长度 | `1005` B / `0` B |

`child_failure.progress` 与摘要 `failure_progress` 显示相同的已取得前缀：

| progress 字段 | 值 |
| --- | ---: |
| `phase` | `PID_RECHECK` |
| `scan_complete` | `false` |
| `pids_listed` | `594` |
| `pids_completed` | `419` |
| `tasks_started` / `tasks_completed` | `1549` / `1549` |
| `fd_initial_stat_attempts` | `57255` |
| `fd_recheck_stat_attempts` | `57255` |
| `fd_match_stat_attempts` | `35` |
| `maps_files_read` | `1549` |
| `maps_bytes_read` | `137564054` B |
| `maps_max_file_bytes` | `494727` B |
| `last_valid_elapsed_ns` | `[7925994212, 7925993991]` |

三类 FD stat 尝试之和为 **114545**。这不是全部系统调用数或唯一打开文件数。
maps 是逐 task 完整读回的文本字节，不是 RSS 或唯一映射量。上述 FD/maps 前缀未触及
2097152 次/512 MiB 的接受上限，但完整需求与全量可行性仍未知。既有失败不能相减来
推算工作量变化或说明某个应用已退出；各次现场时刻和已取得前缀不同。

两个时钟值是相对该 writer request.started 的最后成功检查样本，约 7.926 秒；不是精确
失败时刻、整体维护窗口耗时或全量扫描耗时，不能据此推算剩余任务都能在原期限内完成。
PID 完成数是已通过本 PID 所有复核的数量；当前失败 PID 尚未计入。task 完成不替代
该 PID 的末尾复核或最终全局 PID 集合复核；不能把 419/594 当作等成本的工作完成比例。

没有取得完整 JSON/child stdout，未独立验证截图摘要。本执行者没有从其它进程读取终端变量
或重建输出。950 B 是 command substitution 去除末尾换行后的 shell 文本，不是原始 CLI stdout。
`LH_Q2_W2_PREFLIGHT` / `LH_Q2_W2_RESULT`、全部旧变量及原终端应继续保留。

## 源码定位与未决事实

准确 D 在设置 `phase="PID_RECHECK"` 后，先重新枚举当前 PID 的 task，再联合要求 task 列表
相同及 PID stat 的 starttime 与初读相同。此阶段有三处可以产生同一个 `GROWTH_PROC_DRIFT`：

1. `_bounded_names()` 复查 task 枚举时发现重复名称；
2. 复查 task 列表与初始列表不同；
3. 列表一致后，PID stat 的 starttime 与初读不同。

联合条件短路：前一检查失败时不会继续后一个。截图没有分支编号、前后列表、具体 PID 或
前后 starttime，不能区分上述三项，不能归因于某个进程、线程创建/退出、PID 重用或重复枚举。
这不是已经定位到最终全局 PID 列表变化；那个阶段名应是 `FINAL_PID_RECHECK`，本次尚未到达。

已有 v2 进度确实保留了拒绝阶段和统计前缀，但没有完整扫描、父层 writer 集合准入或排他性
证明。W1 的隔离测试/CI 继续有效，不能将这次现场失败记成 W2 完成。所有历史 UNKNOWN 保留。

## 消耗与停止边界

按截图与准确源码顺序，本交接在 checkpoint 1 失败，没有进入 execute。
该路径没有 marker、SSH、正常关机、备份、镜像增长、VM 启动、ext4 增长或 H01/Q4/H11；
没有合格维护 receipt 或 journal 扩容成功证据。这不是对宿主其它活动的完整盘点。

W2 窗口已经开始即消耗，无 marker 不退款；全部旧窗口仍保持已消耗。准确候选及交接只作
历史证据，不得重新执行、清除 STARTED、换 shell/session/候选或删除对象绕过消费。
本次只做源码解释和文档登记，不修改实现、不补充测试或调用现场，既有验证无需重跑。

W1–W2 原批准不允许用重试、重复扫描、跳过 task/PID、去重、放宽身份/集合一致性或停止
宿主应用来让结果通过，也不允许据此前缀自动提额或延长时限。任何改变扫描覆盖/一致性合同
或再开现场窗口的后续方案，都须先完成具体设计审阅与准确 A、Owner B、独立 C。
原认证、全部检查、15s/900s/780s、已批准预算和累计维护次数保持；新 boot 核心采用、
H01/Q4/H11、补采、清理、恢复及扩展支线继续不执行。

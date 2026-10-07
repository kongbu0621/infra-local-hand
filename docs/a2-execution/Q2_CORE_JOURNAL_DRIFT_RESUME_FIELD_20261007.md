# Journal 漂移接续 DR2：task 成员列表复核拒绝

2026-10-07（Asia/Shanghai）。**本次唯一 DR2 替代窗口 CONSUMED / FAILED；journal 维护未开始。**
依据 Owner 返回的终端截图和准确候选源码做选择性登记。没有重跑、补采、现场扫描、
sudo/writer 探测、SSH、修改源码或调整一致性/预算/期限。

## 准确链与证据范围

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，沿用本会话已完整读取并核验的固定规则。
- A：`4f2a6a37ad5afd027dbde0f1656a3552750cb3b2`，
  `LH-Q2-CORE-JOURNAL-DRIFT-RESUME-v1` / DR1–DR2。
- [Owner B](../governance/Q2_CORE_JOURNAL_DRIFT_RESUME_OWNER_DECISION.md)：
  `LH-Q2-CORE-JOURNAL-DRIFT-RESUME-CLOSURE-20261007-01`。
- 独立 C：`e13f8efcb8dee4e4280dd722f7836ea94a27b83b`。
- 截图执行 D：`309c6e1cacfdf05cabeeac9d27f487acad524b61`，tree
  `f5d8d720eb34f1165cfe026db1a13e1c1e78a223`。
- [DR1 验证与冻结](Q2_CORE_JOURNAL_DRIFT_RESUME_REVIEW_20261007.md)以及
  [准确 CI 37575372661](https://github.com/kongbu0621/infra-local-hand/actions/runs/37575372661)
  保留离线/源码验证含义，不替代本次失败的现场准入。

来源事件：`LH-Q2-CORE-JOURNAL-DRIFT-RESUME-RETURN-20261007-01`。当前对话截图桌面时钟
显示 10 月 7 日 13:34，底部终端状态栏为 13:33；两者均不作为程序精确起止时间。
上方有 v1/v2/MB2/W2 旧输出；本记录只转录底部新的 `LH_Q2_DRIFT_SUMMARY`。
原截图、终端变量及完整输出保留私有；未独立取得或认证完整 JSON/child stdout。

## 可见返回

| 字段 | 本次值 |
| --- | --- |
| `phase` / `state` | `preflight` / `BLOCKED` |
| `child_checkpoint` | `1` |
| `exit_code` / `child_exit` | `3` / `3` |
| 父层及 child failure 的 `reason` | `GROWTH_PROC_DRIFT_PID_TASK_SET` |
| `error_type` | `ObservationError` |
| 父层及 child failure 的 `errno` | 均为 `null` |
| `marker_created` / `ssh_requests` | `false` / `0` |
| `writer_report_count` | `0` |
| `last_successful_writer_progress` | `null` |
| `last_step` / `started` | 均为 `null` |
| shell 保留 JSON 长度 | `978` B |
| writer stdout / stderr 长度 | `1020` B / `0` B |

`child_failure.progress` 与摘要 `failure_progress` 显示相同前缀：

| progress 字段 | 值 |
| --- | ---: |
| `phase` | `PID_RECHECK` |
| `scan_complete` | `false` |
| `pids_listed` / `pids_completed` | `618` / `338` |
| `tasks_started` / `tasks_completed` | `1322` / `1322` |
| `fd_initial_stat_attempts` | `51986` |
| `fd_recheck_stat_attempts` | `51986` |
| `fd_match_stat_attempts` | `35` |
| `maps_files_read` | `1322` |
| `maps_bytes_read` | `132547020` B |
| `maps_max_file_bytes` | `493715` B |
| `last_valid_elapsed_ns` | `[12174740347, 12174740157]` |

三类 FD stat 尝试合计 **104007**；maps 是逐 task 完整读取的文本字节。它们是失败前缀，
不是全量需求、唯一 FD/映射量或全部内核操作数。该前缀在现行 2097152 次/512 MiB 界内，
本轮首因是一致性拒绝；不能因此宣称完整扫描能在预算及原期限内完成。
最后成功双钟样本约 12.175 秒，相对该 writer 的 request.started；不是精确失败时刻、
整个维护窗口耗时或全扫描时间。338 个完成 PID 不包含当前复核失败的 PID，
task 完成计数也不替代 PID 末尾复核和最终全局 PID 集合复核。

978 B 对应 command substitution 去除末尾换行后的 shell JSON，不冒充原始 CLI stdout。
没有抄录难以独立校验的截图哈希、重建完整输出或读取其它进程中的终端变量。

## 已定位的判据与仍未知的原因

准确 D 的 `collect_image_writers` 在 `PID_RECHECK` 顺序执行：

1. 重新枚举当前数字 PID 路径的 task 名称，要求其排序后列表与初读列表相同；
2. 只有列表一致，才读取该 PID 的 stat 并复核 starttime；
3. 两项通过才增加 `pids_completed`；所有 PID 完成后再复核最终全局 PID 集合。

本次明确失败在第 1 项。初始和复查枚举都完成且通过重复名称检查；否则会返回独立的
`DUPLICATE_TASK_ENTRIES` 或 `DUPLICATE_TASK_ENTRIES_RECHECK` 后缀。
两个列表已经排序，差异涉及成员，不能仅解释为枚举顺序不同。该 PID 的末尾 starttime
读取和最终全局 PID 集合复核尚未执行，无法证明两个观察时点仍是同一个进程实例。

截图不含具体 PID、前后 TID 列表及差集；不能判定新增/退出了哪些线程、数量是否变化、
哪个应用引起变化，或是否涉及 PID 重用。不能把未知活动认定为安全、认定恶意，或据此
停止宿主应用、忽略新增 task、去重、复用旧扫描或放宽接受条件。
本次诊断已区分拒绝项，未解决一致性问题。不能倒推此前 W2 的通用错误也是同一分支；
所有历史 UNKNOWN 保留。

## 消耗与后续边界

按截图和准确交接顺序，本次在预检 checkpoint 1 失败，未进入 execute/checkpoint 2。
此路径 marker false、SSH0，没有正常关机、备份、镜像增长、VM 启动、ext4 增长或核心业务。
没有合格维护 receipt，不能记 journal 扩容、新 boot 核心采用或 H01/Q4/H11 成功。
这些是本调用的返回和路径结论，不是对宿主其它活动的完整盘点。

窗口开始即消耗；无 marker 不返还次数。本次最终交接与待决草稿、全部旧交接均只保留为
证据，禁止重跑、清除 STARTED、换 shell/session/候选或删除对象绕过消耗。
保留 `LH_Q2_DRIFT_PREFLIGHT` / `LH_Q2_DRIFT_RESULT`、全部旧变量及原终端。

本次仅登记现场返回并静态核对源码，未改变实现、批准文档或冻结候选；不重复已完成测试。
原检查、预算、15s/900s/780s、累计维护次数及停止规则保持。后续若需要改变扫描覆盖/
一致性合同或再开现场窗口，须先审阅具体方案并取得准确 A、Owner B 和独立 C；
不能用调高预算、延长期限或又一次无差异重跑代替解决本次拒绝条件。
不重试、补采、探测、清理、恢复或扩展支线；不执行新 boot 核心采用或 H01/Q4/H11。

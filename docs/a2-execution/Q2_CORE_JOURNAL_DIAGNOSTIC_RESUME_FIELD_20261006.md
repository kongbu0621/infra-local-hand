# Journal DR2：proc 扫描边界拒绝，窗口已消耗

2026-10-06（Asia/Shanghai）。**DR2 唯一替代预检窗口已失败并关闭；journal 维护未开始。**
本记录依据 Owner 在当前对话返回的终端截图及准确候选源码，登记已发生结果和证据限度。
没有重新调用预检、sudo、writer、SSH、现场 proc 扫描或补采，也没有修改任何阈值或现场对象。

## 准确批准与已执行候选

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。本执行者重新读取直接固定规则并核对
  SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- A：`ef46ac169fd9084875cb5c5148a9c4985ace680c`，
  `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v1` / DR1–DR2。
- [Owner B](../governance/Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_OWNER_DECISION.md)：
  `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-CLOSURE-20261006-01`。
- 独立 C：`65026c8c7722bc487c317d392b50b017a7350dee`。
- 实际交接候选 D：`deab8acdabf0d35294f55fa87f2bc86d542fdf2e`，tree
  `ee9d848085ad89ec953b9f102da8217bf193c147`。
- [DR1 验证与冻结记录](Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_REVIEW_20261006.md)及准确 D 的
  [成功 CI 37458930058](https://github.com/kongbu0621/infra-local-hand/actions/runs/37458930058)
  保持原证据含义；后续文档提交没有替换本次执行候选。

来源事件为当前对话 Owner 返回的 DR2 结果截图，登记 ID
`LH-Q2-CORE-JOURNAL-DR2-RETURN-20261006-01`。截图桌面时钟显示 21:47；不将它当作
程序精确开始/结束时间、完整原始输出或独立 host attestation。截图与完整机器原文不进入公共仓库。

## 可读返回

以下是截图中可读字段的选择性转录，不是重新生成或独立校验的完整 JSON：

| 字段 | 截图返回 |
| --- | --- |
| `D` | `deab8acdabf0d35294f55fa87f2bc86d542fdf2e` |
| `phase` | `preflight` |
| `state` | `BLOCKED` |
| `exit_code` / `child_exit` | `3` / `3` |
| `error_type` | `ObservationError` |
| `reason` | `GROWTH_PROC_LIMIT` |
| `child_checkpoint` | `1` |
| `child_failure` | `{"errno":null,"reason":"GROWTH_PROC_LIMIT"}` |
| `errno` | `null` |
| `marker_created` | `false` |
| `ssh_requests` | `0` |
| `writer_report_count` | `0` |
| shell 保留的 CLI JSON 文本长度 | `588` B |
| writer stdout / stderr 长度 | `643` B / `0` B |

没有从截图中的 digest 文本反推 stdout 内容，也未声称校验了完整原始 JSON 的摘要。
`writer_report_count=0` 表示没有成功报告；与已保留的 `child_failure` 不矛盾。
CLI JSON 文本仍应保留在原终端的 `LH_Q2_DR2_PREFLIGHT` / `LH_Q2_DR2_RESULT` 中；
command substitution 已去除末尾换行，因此 588 B 不应标为原始 CLI stdout 字节数。
此处没有从其它进程读取这些变量，也没有重新执行命令来重建它们。

## 准确源码解释与未知项

准确 D 的 `WriterProtocol.observe()` 在非零退出时验证固定失败 schema、request 绑定、
`complete=false`、reason 与 errno，才生成 `child_failure` 并传播具体 reason。
依据该源码解释本次返回：父层报告接受了匹配本次请求的失败报告，保留了 proc 扫描拒绝类别。
这仍是返回报告及源序的推论，不是对未收到的 stdout 原文的独立验证。
原 T3 的具体失败原因和 root payload 执行 UNKNOWN 不由本次结果补写。

`GROWTH_PROC_LIMIT` 在 D 中用于下列不同检查，错误码本身不唯一定位触发分支：

| 检查点 | 原有条件或上限 |
| --- | --- |
| proc PID 枚举 | 最多 32768 个数字名称 |
| 单 PID 的 task 枚举 | 最多 32768 个数字名称 |
| 单 task 的 FD 快照 | 名称必须为数字，最多 65536 个条目 |
| 累计 task 访问 | 最多 65536 |
| 累计 FD 访问 | 最多 262144 |
| 单次 stat / 匹配镜像 fdinfo / maps 读取 | 分别最多 16384 B / 4096 B / 1 MiB |
| 累计 maps 文本读取 | 最多 64 MiB |

表中的累计数按实际遍历的每个 task 计数；不是唯一宿主 FD 数、唯一映射量或 RSS。
`_bounded_names`、`_proc_read`、`_fd_snapshot` 和 `collect_image_writers` 共用这一 reason。
固定 writer payload 注入了专用 mount reader；源码的无注入 mountinfo fallback 不是本次调用路线。
截图没有报告触发分支、当时计数或单项读取长度；**准确触发项保持 UNKNOWN**。
不得据此断言 PID 太多、浏览器线程过多、某个进程 maps 过大或累计 maps 一定超限。
也不能仅凭该错误认定原检查有 bug，或通过增大阈值、略过 task/不可读进程来制造 PASS。

本次只完成上述静态定位；没有修改源码或新增测试，没有重复现场读取。
未来不改变读取/拒绝语义的离线诊断保留修复可在其已关闭开发边界内评估；它不会恢复本窗口，
也无法追回本次未记录的分支或计数。新的现场调用、阈值/覆盖变更仍须准确审阅和授权。

## 消耗、维护计数与停止

这一次替代预检已经开始，在 checkpoint 1 失败并返回。没有 marker 不返还窗口。
依截图的阶段/计数及准确源码顺序，本次 marker、SSH、正常关机、备份、journal 镜像增长、
VM 启动、ext4 增长及 H01/Q4/H11 均为 0；没有维护 receipt 或扩容成功证据。
这些是本次交接路径的结论，不是对宿主其它活动的完整盘点或独立远端退出证明。

原批准要求“任何失败、未知、超时或绑定漂移立即停止后续动作；没有 marker 也不返还该窗口”。
因此旧窗口和本次 DR2 均保留为已消耗/失败，固定交接文件与准确 D 只能作为历史证据保留，
不能再次执行。不要清除 `LH_Q2_DR2_STARTED`、换 shell/候选/session 或删除对象来重跑。
没有新的窗口、sudo/writer 探测、补采、重连、清理或恢复授权。

原 15s/900s/780s、全部检查、资源预算和累计维护次数不变。任何下一次受影响现场窗口需
另有准确 A、Owner B 和独立 C；已有 DR1、CI 或本记录不构成该决定。
不执行 H01/Q4/H11，不扩展 namespace/watchdog 等支线，生产 `E3_SUPERVISION_UNVERIFIED` 保持。

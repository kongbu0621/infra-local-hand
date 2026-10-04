# Local Hand 核心最小修订：Owner 决定

- Decision Authority / Owner：当前项目 Owner（本工作会话用户）。
- 决定记录日期：2026-10-04 +08:00；采用下列本地 event ID，不虚构平台消息 ID 或精确发送时刻。
- 本地事件：`LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-CLOSURE-20261004-01`。
- 稳定来源：本文件保留本工作会话的准确 Owner 回复，以及随附截图的请求上下文，供 Owner 核验。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。executor 本轮直接读取 pinned upstream rule；
  SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 匹配原采用记录。
- Documentation A：`0bdb49cae5586be60a7ba31d4a8e8367854d1e8c`；tree
  `ee15aa4fa26fd2e87b40f6fad72828265e5cf9bc`；parent `c83dad17040e9f8cec148303083c47311f8b7fb9`。
- Scope：`LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-v1`；D1–D4 与条件单次 F1。
- 准确三文档及摘要：[baseline registration](Q2_CORE_BINDING_FINALIZATION_AMENDMENT_BASELINE.md)。
  本轮复算三项摘要均匹配；A 原文、历史 OPEN 标签和 baseline 登记不改动。

## Owner 准确回复 B

> 按原 R，批准 A `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c`，接受其中三项前提及上述资源保证变化，关闭该范围 Gate，执行 D1–D4 和条件单次 F1；只推进核心，暂停支线。

## 随附请求上下文

Owner 随本回复提供的截图明确显示请求所指的资源变化：

> 结果保存采用应用限额和实际文件占用检查，不再承诺共享文件系统全过程的物理硬上限。

截图中的确认请求与上面 Owner 回复同文；仓库在收到 B 前已经以
`f841bc5` 登记准确 A，完整请求及三个治理前提保留在上述 baseline registration。
本记录不把截图中的助手请求本身当作 Owner B，也不补造旧 proposal 的批准。

## 准确范围与保留限制

Owner 接受 A 的三项治理前提：唯一 carrier 内 post-entry JIT 自观察及其非 pre-entry 证明的限制；
固定 source-horizon 完整性及本批次终结前不另签发 Q2 batch；准确 management anchor/六文件的可信
单写者窗口及不能技术排除 change-and-revert 的剩余信任。

Owner 同时接受 host capture 改为应用写入限额与 scope-owned 六文件实际分配量的采样验收。
两流合计最多 52 MiB、六角色逻辑量合计最多 55132160 B、固定最多六文件；64 MiB/16-inode 数值
保留为 A 定义的应用/观测边界，不再保证共享宿主文件系统含 metadata、journal 或未观测瞬时分配的
全过程物理峰值。必须真实报告 `full_filesystem_peak_proven=false`；超限或 UNKNOWN 仍停止并保留。

本独立 C 后按 A 实施 D1–D4，验证并冻结准确 D/tree/package/release。全部门通过才条件执行单次 F1：
最多一次 O_EXCL marker、最多一次 carrier request，同一 carrier 内 H01 semantic PASS → Q4 semantic
PASS → H11。H01 保留空 ledger gate；H11 恢复自己的 origin 原 ledger/request/execution/unit/grant/
deadline，不复用 Q4 ledger、不重启业务、不重新读取或封装业务 result、不新建 grant/unit、不延长时限。

保留固定 candidate/wheel/harness/对象、guest physical/admission/CPU/peak、32 MiB input、60 MiB
outer-output refusal、900/800/750 秒外层时限与原 reserves。六文件保留 receipt/capture v1 与原 live
caller 验收；没有 attestation、第七文件、local restart COMPLETE、内核证明或专用存储建设。
复用既有 SSH/准备环境，只允许原 A 的本批 create-only candidate placement，不覆盖旧安装或现场。

marker 创建即消费，任何失败不退款、不产生第二 request/marker、重连、重试、换名绕过或旧批次重放。
禁止 host sudo/系统配置变更、清理、公开私有 raw、把 UNKNOWN 提升为成功；namespace/watchdog 和
其它支线暂停，production `E3_SUPERVISION_UNVERIFIED` 保持，生产/E4–E6/NAS 不在范围内。

本文件和根 AGENTS.md 的 CLOSED 登记共同组成 bookkeeping-only C；不含 source/test/prototype、
dependency、runtime configuration、package 或现场动作。首个 D 必须以 C 为直接父提交，不 squash。
此时仍为 package=null / NOT_ISSUED，核心批次 marker/request/H01/Q4/H11/任务/退出/结果回收均为 0。
原 A `74366b3`、B、C `a8dd077` 及其不可 release 的部分 D 保持历史准确。material changes 仍按 R reopen。
